"""
Redis connection management for Nexus.
Singleton pattern — one connection pool shared across entire app.
Never create raw Redis connections anywhere else.
"""

import redis
from redis import ConnectionPool
from redis.exceptions import (
    ConnectionError as RedisConnectionError,
    TimeoutError as RedisTimeoutError,
    RedisError
)
from typing import Optional
from core.config import get_settings
from core.exceptions import CacheUnavailableError, ServiceUnavailableError
from core.logger import get_logger, TimedOperation

logger = get_logger(__name__)
settings = get_settings()


class RedisClient:
    """
    Manages Redis connection pool.
    Single instance shared across the application.
    Handles connection failures gracefully — cache failure
    must NEVER crash the main application.
    """

    _instance: Optional["RedisClient"] = None
    _pool: Optional[ConnectionPool] = None
    _client: Optional[redis.Redis] = None

    def __new__(cls) -> "RedisClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def initialize(self) -> None:
        """
        Initialize connection pool.
        Call once at application startup.
        """
        try:
            self._pool = ConnectionPool(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD or None,
                max_connections=settings.REDIS_MAX_CONNECTIONS,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )

            self._client = redis.Redis(connection_pool=self._pool)

            # Verify connection immediately
            self._client.ping()

            logger.info(
                "redis_connected",
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                max_connections=settings.REDIS_MAX_CONNECTIONS
            )

        except RedisConnectionError as e:
            logger.error(
                "redis_connection_failed",
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                error=str(e)
            )
            raise ServiceUnavailableError("Redis") from e

        except Exception as e:
            logger.error("redis_initialization_failed", error=str(e))
            raise ServiceUnavailableError("Redis") from e

    @property
    def client(self) -> redis.Redis:
        """
        Get Redis client.
        Raises if not initialized.
        """
        if self._client is None:
            raise CacheUnavailableError(
                "Redis client not initialized. Call initialize() first."
            )
        return self._client

    def is_healthy(self) -> bool:
        """
        Check if Redis is reachable.
        Use this for health checks — never raises.
        """
        try:
            self._client.ping()
            return True
        except Exception:
            return False

    def close(self) -> None:
        """Clean up connections on shutdown."""
        if self._pool:
            self._pool.disconnect()
            logger.info("redis_disconnected")


# Module-level singleton
redis_client = RedisClient()


def get_redis() -> redis.Redis:
    """
    Dependency injection helper.
    Use in FastAPI routes and services.

    Usage:
        from cache.redis_client import get_redis
        client = get_redis()
    """
    return redis_client.client