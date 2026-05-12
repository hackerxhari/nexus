"""
Central configuration management for Nexus.
All settings loaded from environment variables with validation.
Never hardcode values anywhere else in the codebase.
"""

from functools import lru_cache
from typing import List, Optional
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import os


class AppSettings(BaseSettings):
    """Core application settings."""
    name: str = Field(default="Nexus", alias="APP_NAME")
    version: str = Field(default="1.0.0", alias="APP_VERSION")
    env: str = Field(default="development", alias="APP_ENV")
    host: str = Field(default="0.0.0.0", alias="APP_HOST")
    port: int = Field(default=8000, alias="APP_PORT")
    debug: bool = Field(default=False, alias="DEBUG")

    @field_validator("env")
    @classmethod
    def validate_env(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"APP_ENV must be one of {allowed}")
        return v


class SecuritySettings(BaseSettings):
    """JWT and authentication settings."""
    secret_key: str = Field(alias="SECRET_KEY")
    access_token_expire_minutes: int = Field(
        default=15,
        alias="ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    refresh_token_expire_days: int = Field(
        default=7,
        alias="REFRESH_TOKEN_EXPIRE_DAYS"
    )
    algorithm: str = Field(default="HS256", alias="ALGORITHM")
    bcrypt_rounds: int = Field(default=12, alias="BCRYPT_ROUNDS")

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return v

    @field_validator("bcrypt_rounds")
    @classmethod
    def validate_bcrypt_rounds(cls, v: int) -> int:
        if not 10 <= v <= 16:
            raise ValueError("BCRYPT_ROUNDS must be between 10 and 16")
        return v


class QdrantSettings(BaseSettings):
    """Qdrant vector database settings."""
    host: str = Field(default="localhost", alias="QDRANT_HOST")
    port: int = Field(default=6333, alias="QDRANT_PORT")
    collection_name: str = Field(
        default="nexus_kb",
        alias="QDRANT_COLLECTION_NAME"
    )
    vector_size: int = Field(default=384, alias="QDRANT_VECTOR_SIZE")

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"


class RedisSettings(BaseSettings):
    """Redis cache settings."""
    host: str = Field(default="localhost", alias="REDIS_HOST")
    port: int = Field(default=6379, alias="REDIS_PORT")
    db: int = Field(default=0, alias="REDIS_DB")
    password: Optional[str] = Field(default=None, alias="REDIS_PASSWORD")
    query_cache_ttl: int = Field(
        default=3600,
        alias="REDIS_QUERY_CACHE_TTL"
    )
    embedding_cache_ttl: int = Field(
        default=86400,
        alias="REDIS_EMBEDDING_CACHE_TTL"
    )
    max_connections: int = Field(
        default=10,
        alias="REDIS_MAX_CONNECTIONS"
    )

    @property
    def url(self) -> str:
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class OllamaSettings(BaseSettings):
    """Ollama LLM settings."""
    host: str = Field(
        default="http://localhost:11434",
        alias="OLLAMA_HOST"
    )
    model: str = Field(default="phi3:mini", alias="OLLAMA_MODEL")
    timeout: int = Field(default=120, alias="OLLAMA_TIMEOUT")
    max_retries: int = Field(default=3, alias="OLLAMA_MAX_RETRIES")
    prewarm: bool = Field(default=True, alias="OLLAMA_PREWARM")
    prewarm_prompt: str = Field(default="hi", alias="OLLAMA_PREWARM_PROMPT")
    num_predict: int = Field(default=128, alias="OLLAMA_NUM_PREDICT")
    temperature: float = Field(default=0.1, alias="OLLAMA_TEMPERATURE")
    num_ctx: int = Field(default=2048, alias="OLLAMA_NUM_CTX")
    top_p: float = Field(default=0.9, alias="OLLAMA_TOP_P")
    top_k: int = Field(default=40, alias="OLLAMA_TOP_K")
    repeat_penalty: float = Field(default=1.1, alias="OLLAMA_REPEAT_PENALTY")


class EmbeddingSettings(BaseSettings):
    """Embedding model settings."""
    model: str = Field(
        default="all-MiniLM-L6-v2",
        alias="EMBEDDING_MODEL"
    )
    batch_size: int = Field(default=32, alias="EMBEDDING_BATCH_SIZE")


class IngestionSettings(BaseSettings):
    """Document ingestion settings."""
    max_file_size_mb: int = Field(default=50, alias="MAX_FILE_SIZE_MB")
    allowed_file_types: str = Field(
        default="pdf,docx,txt,png,jpg,jpeg,tiff",
        alias="ALLOWED_FILE_TYPES"
    )
    chunk_size: int = Field(default=400, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=50, alias="CHUNK_OVERLAP")
    upload_dir: str = Field(default="uploads", alias="UPLOAD_DIR")

    @property
    def allowed_extensions(self) -> List[str]:
        return [ext.strip().lower() for ext in self.allowed_file_types.split(",")]

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @field_validator("chunk_overlap")
    @classmethod
    def validate_overlap(cls, v: int, info) -> int:
        # overlap must be less than chunk_size
        return v


class RateLimitSettings(BaseSettings):
    """Rate limiting settings."""
    per_minute: int = Field(default=10, alias="RATE_LIMIT_PER_MINUTE")
    burst: int = Field(default=5, alias="RATE_LIMIT_BURST")


class LoggingSettings(BaseSettings):
    """Logging configuration."""
    level: str = Field(default="INFO", alias="LOG_LEVEL")
    file: str = Field(default="logs/nexus.log", alias="LOG_FILE")

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {allowed}")
        return v.upper()


class DatabaseSettings(BaseSettings):
    """Relational database settings."""
    url: str = Field(
        default="sqlite:///./nexus.db",
        alias="DATABASE_URL"
    )


class Settings(BaseSettings):
    """
    Master settings class.
    Composes all sub-settings into a single object.
    Use get_settings() to access — never instantiate directly.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # App
    APP_NAME: str = "Nexus"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = False

    # Security
    SECRET_KEY: str = "change-this-in-production-minimum-32-characters-long"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"
    BCRYPT_ROUNDS: int = 12

    # Qdrant
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION_NAME: str = "nexus_kb"
    QDRANT_VECTOR_SIZE: int = 384

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_QUERY_CACHE_TTL: int = 3600
    REDIS_EMBEDDING_CACHE_TTL: int = 86400
    REDIS_MAX_CONNECTIONS: int = 10

    # Ollama
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "phi3:mini"
    OLLAMA_TIMEOUT: int = 120
    OLLAMA_MAX_RETRIES: int = 3
    OLLAMA_PREWARM: bool = True
    OLLAMA_PREWARM_PROMPT: str = "hi"
    OLLAMA_NUM_PREDICT: int = 256
    OLLAMA_TEMPERATURE: float = 0.1
    OLLAMA_NUM_CTX: int = 2048
    OLLAMA_TOP_P: float = 0.9
    OLLAMA_TOP_K: int = 40
    OLLAMA_REPEAT_PENALTY: float = 1.1

    # Embeddings
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_BATCH_SIZE: int = 32

    # Ingestion
    MAX_FILE_SIZE_MB: int = 50
    ALLOWED_FILE_TYPES: str = "pdf,docx,txt,png,jpg,jpeg,tiff,pptx,ppt,xlsx,xls"
    CHUNK_SIZE: int = 400
    CHUNK_OVERLAP: int = 50
    CHUNK_STRATEGY: str = "semantic"
    SEMANTIC_SIM_THRESHOLD: float = 0.55
    UPLOAD_DIR: str = "uploads"

    # Topic Tree
    TOPIC_SIM_THRESHOLD: float = 0.6
    QUERY_TOPIC_THRESHOLD: float = 0.55
    TOPIC_FILTER_ENABLED: bool = False  # Disable hard topic filtering, use as reranking signal

    # Query Understanding
    QUERY_REWRITE_ENABLED: bool = False  # Disabled — saves 2-3s per query
    # Retrieval
    RETRIEVAL_TOP_K: int = 8
    RETRIEVAL_SCORE_THRESHOLD: float = 0.25
    SCORE_RELATIVE_THRESHOLD: float = 0.65
    MIN_SCORE_THRESHOLD: float = 0.30
    MULTI_HOP_ENABLED: bool = False

    # Conversation Context
    CONVERSATION_HISTORY_TURNS: int = 1  # Number of past Q&A turns to include

    # Prompt size control
    CONTEXT_CHAR_BUDGET: int = 9000

    # Custom Q&A
    CUSTOM_QA_ENABLED: bool = True
    CUSTOM_QA_SIMILARITY_THRESHOLD: float = 0.60

    # Network Security
    NAME_RERANK_ENABLED: bool = True
    IP_WHITELIST_ENABLED: bool = False  # Enable IP whitelist middleware when needed
    ALLOWED_IP_RANGES: str = "127.0.0.1/32,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # Vosk STT
    VOSK_ENABLED: bool = True
    VOSK_LANGUAGE: str = "en"
    VOSK_MODEL_PATH: str = "models/vosk-model-en-in-0.5"

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 10
    RATE_LIMIT_BURST: int = 5

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/nexus.log"

    # Database
    DATABASE_URL: str = "sqlite:///./nexus.db"

    # ── Derived properties ──────────────────────────────────

    @property
    def qdrant_url(self) -> str:
        return f"http://{self.QDRANT_HOST}:{self.QDRANT_PORT}"

    @property
    def redis_url(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def allowed_extensions(self) -> List[str]:
        return [e.strip().lower() for e in self.ALLOWED_FILE_TYPES.split(",")]

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.APP_ENV == "production":
            if "change-this" in self.SECRET_KEY:
                raise ValueError(
                    "SECRET_KEY must be changed in production"
                )
            if self.DEBUG:
                raise ValueError(
                    "DEBUG must be False in production"
                )
        if self.CHUNK_OVERLAP >= self.CHUNK_SIZE:
            raise ValueError(
                "CHUNK_OVERLAP must be less than CHUNK_SIZE"
            )
        return self

    def ensure_dirs(self) -> None:
        """Create required directories if they don't exist."""
        dirs = [
            self.UPLOAD_DIR,
            os.path.dirname(self.LOG_FILE)
        ]
        for d in dirs:
            if d:
                os.makedirs(d, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Returns cached Settings instance.
    Use this everywhere — never instantiate Settings directly.
    
    Usage:
        from core.config import get_settings
        settings = get_settings()
    """
    settings = Settings()
    settings.ensure_dirs()
    return settings