"""
Pydantic response schemas for Project Nexus API.
Every response follows the same envelope structure.
Never return raw data — always wrap in these models.
"""

from typing import Any, Dict, Generic, List, Optional, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """
    Standard API response envelope.
    Every endpoint returns this shape — success or failure.
    """
    success: bool
    data: Optional[T] = None
    error: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None

    @classmethod
    def ok(cls, data: Any, request_id: Optional[str] = None) -> "APIResponse":
        return cls(success=True, data=data, request_id=request_id)

    @classmethod
    def fail(
        cls,
        error_code: str,
        message: str,
        request_id: Optional[str] = None,
        details: Optional[Dict] = None
    ) -> "APIResponse":
        return cls(
            success=False,
            error={
                "code": error_code,
                "message": message,
                "details": details or {}
            },
            request_id=request_id
        )


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    roles: List[str]
    department: Optional[str]
    hierarchy: int = 1
    is_active: bool


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    user: UserResponse


class Citation(BaseModel):
    """A single citation: a source filename plus the pages it covers."""
    file: str
    pages: List[int] = []


class QueryResponse(BaseModel):
    answer: str
    sources: List[str]
    citations: List[Citation] = []
    chunks_retrieved: int
    cache_hit: bool
    performance: Dict[str, float]
    rate_limit: Dict[str, Any]


class DocumentResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    file_size_bytes: int
    departments: List[str] = []
    hierarchy: int = 1
    allowed_roles: List[str]
    status: str
    total_chunks: Optional[int]
    uploaded_at: str
    ingestion_time_seconds: Optional[float]


class IngestionResponse(BaseModel):
    doc_id: str
    filename: str
    status: str
    total_chunks: int
    total_words: int
    ingestion_time_seconds: float
    warnings: List[str]


class HealthResponse(BaseModel):
    status: str
    services: Dict[str, Any]
    version: str