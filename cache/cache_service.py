"""
All cache operations for Nexus.
Three responsibilities: query cache, token blacklist, rate limiting.
Every method is safe — Redis failures are logged but never crash the app.
"""

import hashlib
import json
import time
from typing import Any, Dict, List, Optional

from redis.exceptions import RedisError

from cache.redis_client import get_redis
from core.config import get_settings
from core.exceptions import RateLimitExceededError
from core.logger import get_logger, TimedOperation

logger = get_logger(__name__)
settings = get_settings()


class CacheKeys:
    """
    Centralized cache key definitions.
    Never build cache keys inline anywhere else — always use this class.
    Changing a key pattern? Change it here once, affects entire codebase.
    """

    @staticmethod
    def query_result(
        question: str,
        topic_id: Optional[str] = None,
        department: Optional[str] = None
    ) -> str:
        """
        Cache key for RAG query results.
        """
        normalized_question = question.strip().lower()
        topic_part = topic_id or "_"
        department_part = department or "_"
        content = f"{normalized_question}|{topic_part}|{department_part}"
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        return f"nexus:query:{content_hash}"

    @staticmethod
    def token_blacklist(jti: str) -> str:
        return f"nexus:blacklist:{jti}"

    @staticmethod
    def rate_limit(user_id: str, window_minute: int) -> str:
        return f"nexus:ratelimit:{user_id}:{window_minute}"

    @staticmethod
    def user_session(user_id: str) -> str:
        return f"nexus:session:{user_id}"


class QueryCacheService:
    """
    Caches full RAG query results.
    Cache miss → full RAG pipeline → store result.
    Cache hit → return instantly, skip embedding + Qdrant + Ollama.
    """

    def get(
        self,
        question: str,
        topic_id: Optional[str] = None,
        department: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached query result.
        Returns None on miss or any Redis error.
        Never raises — cache failure is not a fatal error.
        """
        key = CacheKeys.query_result(question, topic_id, department)

        try:
            with TimedOperation(logger, "cache_get", key=key):
                cached = get_redis().get(key)

            if cached:
                result = json.loads(cached)
                logger.info(
                    "query_cache_hit",
                    key=key,
                    question_preview=question[:50]
                )
                return result

            logger.debug("query_cache_miss", key=key)
            return None

        except RedisError as e:
            # Cache failure must never block the main query
            logger.warning(
                "query_cache_get_failed",
                key=key,
                error=str(e)
            )
            return None

        except json.JSONDecodeError as e:
            # Corrupted cache entry — delete it and return miss
            logger.warning(
                "query_cache_corrupted",
                key=key,
                error=str(e)
            )
            self._safe_delete(key)
            return None

    def set(
        self,
        question: str,
        topic_id: Optional[str],
        department: Optional[str],
        result: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """
        Store query result in cache.
        Returns True on success, False on failure.
        Never raises.
        """
        key = CacheKeys.query_result(question, topic_id, department)
        ttl = ttl or settings.REDIS_QUERY_CACHE_TTL

        try:
            serialized = json.dumps(result, ensure_ascii=False)

            # Sanity check — don't cache massive responses
            if len(serialized) > 1_000_000:  # 1MB limit
                logger.warning(
                    "query_cache_skip_too_large",
                    key=key,
                    size_bytes=len(serialized)
                )
                return False

            get_redis().setex(key, ttl, serialized)

            logger.info(
                "query_cache_set",
                key=key,
                ttl_seconds=ttl,
                size_bytes=len(serialized)
            )
            return True

        except RedisError as e:
            logger.warning(
                "query_cache_set_failed",
                key=key,
                error=str(e)
            )
            return False

    def invalidate_by_source(self, source_file: str) -> int:
        """
        Invalidate all cached queries that used a specific source.
        Call this when a document is re-ingested or deleted.
        Returns number of keys deleted.
        """
        # Scan pattern — only invalidates query keys
        pattern = "nexus:query:*"
        deleted = 0

        try:
            cursor = 0
            while True:
                cursor, keys = get_redis().scan(
                    cursor=cursor,
                    match=pattern,
                    count=100
                )

                for key in keys:
                    try:
                        value = get_redis().get(key)
                        if value:
                            data = json.loads(value)
                            sources = data.get("sources", [])
                            if source_file in sources:
                                get_redis().delete(key)
                                deleted += 1
                    except Exception:
                        continue

                if cursor == 0:
                    break

            logger.info(
                "cache_invalidated_by_source",
                source_file=source_file,
                deleted_count=deleted
            )
            return deleted

        except RedisError as e:
            logger.warning(
                "cache_invalidation_failed",
                source_file=source_file,
                error=str(e)
            )
            return 0

    def clear_all(self) -> int:
        """
        Delete all cached query results.
        Returns number of keys deleted.
        """
        pattern = "nexus:query:*"
        deleted = 0

        try:
            cursor = 0
            while True:
                cursor, keys = get_redis().scan(
                    cursor=cursor,
                    match=pattern,
                    count=200
                )

                if keys:
                    deleted += get_redis().delete(*keys)

                if cursor == 0:
                    break

            logger.info("query_cache_cleared", deleted_count=deleted)
            return deleted

        except RedisError as e:
            logger.warning("query_cache_clear_failed", error=str(e))
            return 0

    def _safe_delete(self, key: str) -> None:
        """Delete a key without raising."""
        try:
            get_redis().delete(key)
        except Exception:
            pass


class TokenBlacklistService:
    """
    Manages JWT token revocation via Redis.
    When a user logs out or is disabled, their token JTI is blacklisted.
    Every authenticated request checks this before proceeding.
    """

    def blacklist(
        self,
        jti: str,
        expires_in_seconds: int
    ) -> bool:
        """
        Add a token JTI to the blacklist.
        TTL matches token expiry so Redis auto-cleans expired entries.
        """
        if not jti:
            logger.warning("blacklist_empty_jti")
            return False

        key = CacheKeys.token_blacklist(jti)

        try:
            get_redis().setex(key, expires_in_seconds, "revoked")
            logger.info(
                "token_blacklisted",
                jti=jti,
                expires_in_seconds=expires_in_seconds
            )
            return True

        except RedisError as e:
            # This IS a critical failure — log as error not warning
            logger.error(
                "token_blacklist_failed",
                jti=jti,
                error=str(e)
            )
            return False

    def is_blacklisted(self, jti: str) -> bool:
        """
        Check if a token has been revoked.
        Returns True (treat as blacklisted) on Redis failure — fail secure.
        """
        if not jti:
            return True  # No JTI = treat as invalid

        key = CacheKeys.token_blacklist(jti)

        try:
            result = get_redis().exists(key)
            if result:
                logger.warning("blacklisted_token_used", jti=jti)
            return bool(result)

        except RedisError as e:
            # Fail secure — if we can't check, deny access
            logger.error(
                "blacklist_check_failed",
                jti=jti,
                error=str(e)
            )
            return True

    def revoke_all_user_tokens(self, user_id: str) -> None:
        """
        Mark that all tokens for a user should be rejected.
        Used when disabling an account or forcing re-login.
        Stored separately from individual JTI blacklists.
        """
        key = CacheKeys.user_session(user_id)
        try:
            # Store timestamp — any token issued before this is invalid
            get_redis().setex(
                key,
                settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
                str(time.time())
            )
            logger.info("all_user_tokens_revoked", user_id=user_id)
        except RedisError as e:
            logger.error(
                "revoke_all_tokens_failed",
                user_id=user_id,
                error=str(e)
            )


class RateLimitService:
    """
    Sliding window rate limiter using Redis.
    Counts requests per user per minute window.
    """

    def check_and_increment(
        self,
        user_id: str,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Check rate limit and increment counter.
        Returns status dict with remaining requests info.
        Raises RateLimitExceededError if limit exceeded.
        """
        limit = limit or settings.RATE_LIMIT_PER_MINUTE
        current_minute = int(time.time() // 60)
        key = CacheKeys.rate_limit(user_id, current_minute)

        try:
            pipeline = get_redis().pipeline()
            pipeline.incr(key)
            pipeline.expire(key, 60)
            results = pipeline.execute()

            current_count = results[0]
            remaining = max(0, limit - current_count)

            if current_count > limit:
                logger.warning(
                    "rate_limit_exceeded",
                    user_id=user_id,
                    count=current_count,
                    limit=limit
                )
                raise RateLimitExceededError(retry_after_seconds=60)

            logger.debug(
                "rate_limit_check",
                user_id=user_id,
                count=current_count,
                limit=limit,
                remaining=remaining
            )

            return {
                "allowed": True,
                "current_count": current_count,
                "limit": limit,
                "remaining": remaining,
                "reset_in_seconds": 60 - (int(time.time()) % 60)
            }

        except RateLimitExceededError:
            raise

        except RedisError as e:
            # If Redis is down, allow the request — don't block users
            # because of infrastructure failure
            logger.error(
                "rate_limit_check_failed",
                user_id=user_id,
                error=str(e)
            )
            return {
                "allowed": True,
                "current_count": 0,
                "limit": limit,
                "remaining": limit,
                "reset_in_seconds": 60
            }

    def get_current_usage(self, user_id: str) -> int:
        """Get current request count for a user. Returns 0 on error."""
        current_minute = int(time.time() // 60)
        key = CacheKeys.rate_limit(user_id, current_minute)
        try:
            count = get_redis().get(key)
            return int(count) if count else 0
        except Exception:
            return 0


class CacheService:
    """
    Unified cache service.
    Single entry point — inject this wherever cache is needed.

    Usage:
        from cache.cache_service import CacheService
        cache = CacheService()
        cached = cache.queries.get(question, topic_id, department)
    """

    def __init__(self):
        self.queries = QueryCacheService()
        self.blacklist = TokenBlacklistService()
        self.rate_limit = RateLimitService()

    def health_check(self) -> Dict[str, Any]:
        """Check Redis connectivity for health endpoint."""
        try:
            get_redis().ping()
            info = get_redis().info("server")
            return {
                "status": "healthy",
                "redis_version": info.get("redis_version", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "unknown")
            }
        except RedisError as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }