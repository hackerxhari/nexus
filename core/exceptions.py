"""
Custom exception hierarchy for Nexus.
Every error in the system maps to one of these.
Never raise generic Python exceptions in business logic.
"""

from typing import Optional, Dict, Any
from enum import Enum


class ErrorCode(str, Enum):
    """Machine-readable error codes for API responses."""

    # Auth errors
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_INVALID = "TOKEN_INVALID"
    TOKEN_REVOKED = "TOKEN_REVOKED"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"
    ACCOUNT_DISABLED = "ACCOUNT_DISABLED"

    # Ingestion errors
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    EMBEDDING_FAILED = "EMBEDDING_FAILED"
    INGESTION_FAILED = "INGESTION_FAILED"
    EMPTY_DOCUMENT = "EMPTY_DOCUMENT"

    # Retrieval errors
    COLLECTION_NOT_FOUND = "COLLECTION_NOT_FOUND"
    QUERY_FAILED = "QUERY_FAILED"
    NO_RESULTS_FOUND = "NO_RESULTS_FOUND"

    # LLM errors
    MODEL_NOT_AVAILABLE = "MODEL_NOT_AVAILABLE"
    GENERATION_FAILED = "GENERATION_FAILED"
    GENERATION_TIMEOUT = "GENERATION_TIMEOUT"

    # Cache errors
    CACHE_UNAVAILABLE = "CACHE_UNAVAILABLE"

    # Database errors
    DATABASE_ERROR = "DATABASE_ERROR"
    RECORD_NOT_FOUND = "RECORD_NOT_FOUND"
    DUPLICATE_RECORD = "DUPLICATE_RECORD"

    # Validation errors
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_INPUT = "INVALID_INPUT"

    # Rate limit
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

    # Generic
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


class GreenBaseException(Exception):
    """
    Base exception for all Nexus errors.
    All custom exceptions must inherit from this.
    """

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        http_status: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.http_status = http_status
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_code": self.error_code.value,
            "message": self.message,
            "details": self.details
        }

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"code={self.error_code.value}, "
            f"message={self.message!r})"
        )


# ── Authentication & Authorization ──────────────────────────

class AuthenticationError(GreenBaseException):
    """Raised when authentication fails."""
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(
            message=message,
            error_code=kwargs.get("error_code", ErrorCode.INVALID_CREDENTIALS),
            http_status=401,
            details=kwargs.get("details", {})
        )


class TokenExpiredError(AuthenticationError):
    def __init__(self, message: str = "Token has expired"):
        super().__init__(
            message=message,
            error_code=ErrorCode.TOKEN_EXPIRED
        )


class TokenInvalidError(AuthenticationError):
    def __init__(self, message: str = "Token is invalid"):
        super().__init__(
            message=message,
            error_code=ErrorCode.TOKEN_INVALID
        )


class TokenRevokedError(AuthenticationError):
    def __init__(self, message: str = "Token has been revoked"):
        super().__init__(
            message=message,
            error_code=ErrorCode.TOKEN_REVOKED
        )


class AuthorizationError(GreenBaseException):
    """Raised when user lacks required permissions."""
    def __init__(
        self,
        message: str = "You don't have permission to access this resource",
        required_roles: Optional[list] = None
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.INSUFFICIENT_PERMISSIONS,
            http_status=403,
            details={"required_roles": required_roles or []}
        )


class AccountDisabledError(AuthenticationError):
    def __init__(self, message: str = "Account has been disabled"):
        super().__init__(
            message=message,
            error_code=ErrorCode.ACCOUNT_DISABLED
        )


# ── Ingestion Errors ─────────────────────────────────────────

class IngestionError(GreenBaseException):
    """Base class for all ingestion errors."""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code=kwargs.get("error_code", ErrorCode.INGESTION_FAILED),
            http_status=422,
            details=kwargs.get("details", {})
        )


class FileTooLargeError(IngestionError):
    def __init__(self, filename: str, size_mb: float, max_mb: int):
        super().__init__(
            message=f"File '{filename}' is {size_mb:.1f}MB. Maximum allowed is {max_mb}MB.",
            error_code=ErrorCode.FILE_TOO_LARGE,
            details={
                "filename": filename,
                "size_mb": size_mb,
                "max_mb": max_mb
            }
        )


class UnsupportedFileTypeError(IngestionError):
    def __init__(self, filename: str, file_type: str, allowed: list):
        super().__init__(
            message=f"File type '{file_type}' is not supported.",
            error_code=ErrorCode.UNSUPPORTED_FILE_TYPE,
            details={
                "filename": filename,
                "file_type": file_type,
                "allowed_types": allowed
            }
        )


class ExtractionFailedError(IngestionError):
    def __init__(self, filename: str, reason: str):
        super().__init__(
            message=f"Failed to extract text from '{filename}': {reason}",
            error_code=ErrorCode.EXTRACTION_FAILED,
            details={"filename": filename, "reason": reason}
        )


class EmptyDocumentError(IngestionError):
    def __init__(self, filename: str):
        super().__init__(
            message=f"No extractable text found in '{filename}'.",
            error_code=ErrorCode.EMPTY_DOCUMENT,
            details={"filename": filename}
        )


class EmbeddingFailedError(IngestionError):
    def __init__(self, reason: str):
        super().__init__(
            message="Failed to generate embeddings.",
            error_code=ErrorCode.EMBEDDING_FAILED,
            details={"reason": reason}
        )


# ── Retrieval Errors ─────────────────────────────────────────

class RetrievalError(GreenBaseException):
    """Base class for retrieval errors."""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code=kwargs.get("error_code", ErrorCode.QUERY_FAILED),
            http_status=500,
            details=kwargs.get("details", {})
        )


class CollectionNotFoundError(RetrievalError):
    def __init__(self, collection_name: str):
        super().__init__(
            message=f"Vector collection '{collection_name}' not found.",
            error_code=ErrorCode.COLLECTION_NOT_FOUND,
            details={"collection": collection_name}
        )


class QueryFailedError(RetrievalError):
    def __init__(self, reason: str):
        super().__init__(
            message="Vector search query failed.",
            error_code=ErrorCode.QUERY_FAILED,
            details={"reason": reason}
        )


# ── LLM Errors ───────────────────────────────────────────────

class LLMError(GreenBaseException):
    """Base class for LLM errors."""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code=kwargs.get("error_code", ErrorCode.GENERATION_FAILED),
            http_status=503,
            details=kwargs.get("details", {})
        )


class ModelNotAvailableError(LLMError):
    def __init__(self, model_name: str):
        super().__init__(
            message=f"LLM model '{model_name}' is not available.",
            error_code=ErrorCode.MODEL_NOT_AVAILABLE,
            details={"model": model_name}
        )


class GenerationTimeoutError(LLMError):
    def __init__(self, timeout_seconds: int):
        super().__init__(
            message=f"LLM generation timed out after {timeout_seconds} seconds.",
            error_code=ErrorCode.GENERATION_TIMEOUT,
            details={"timeout_seconds": timeout_seconds}
        )


class GenerationFailedError(LLMError):
    def __init__(self, reason: str):
        super().__init__(
            message="LLM failed to generate a response.",
            error_code=ErrorCode.GENERATION_FAILED,
            details={"reason": reason}
        )


# ── Cache Errors ─────────────────────────────────────────────

class CacheUnavailableError(GreenBaseException):
    """Raised when Redis is unreachable."""
    def __init__(self, reason: str = "Cache service unavailable"):
        super().__init__(
            message=reason,
            error_code=ErrorCode.CACHE_UNAVAILABLE,
            http_status=503,
            details={"reason": reason}
        )


# ── Database Errors ───────────────────────────────────────────

class DatabaseError(GreenBaseException):
    """Base class for database errors."""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code=kwargs.get("error_code", ErrorCode.DATABASE_ERROR),
            http_status=500,
            details=kwargs.get("details", {})
        )


class RecordNotFoundError(DatabaseError):
    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            message=f"{resource} not found.",
            error_code=ErrorCode.RECORD_NOT_FOUND,
            http_status=404,
            details={"resource": resource, "identifier": str(identifier)}
        )


class DuplicateRecordError(DatabaseError):
    def __init__(self, resource: str, field: str, value: Any):
        super().__init__(
            message=f"{resource} with {field} '{value}' already exists.",
            error_code=ErrorCode.DUPLICATE_RECORD,
            http_status=409,
            details={"resource": resource, "field": field, "value": str(value)}
        )


# ── Validation Errors ─────────────────────────────────────────

class ValidationError(GreenBaseException):
    """Raised when input validation fails."""
    def __init__(self, message: str, fields: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code=ErrorCode.VALIDATION_ERROR,
            http_status=422,
            details={"fields": fields or {}}
        )


# ── Rate Limit ────────────────────────────────────────────────

class RateLimitExceededError(GreenBaseException):
    """Raised when user exceeds request rate limit."""
    def __init__(self, retry_after_seconds: int = 60):
        super().__init__(
            message="Too many requests. Please slow down.",
            error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
            http_status=429,
            details={"retry_after_seconds": retry_after_seconds}
        )


# ── Service Errors ────────────────────────────────────────────

class ServiceUnavailableError(GreenBaseException):
    """Raised when a dependent service is down."""
    def __init__(self, service_name: str):
        super().__init__(
            message=f"{service_name} is currently unavailable.",
            error_code=ErrorCode.SERVICE_UNAVAILABLE,
            http_status=503,
            details={"service": service_name}
        )