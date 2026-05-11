"""
Pydantic request schemas for Project Nexus API.
Every incoming request is validated against these models.
Bad data never reaches the service layer.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ConversationTurn(BaseModel):
    """A single turn in the conversation history."""
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=2000)


class QueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    department_filter: Optional[str] = None
    bypass_cache: bool = False
    conversation_history: Optional[List[ConversationTurn]] = None

    @field_validator("question")
    @classmethod
    def clean_question(cls, v: str) -> str:
        return v.strip()

    @field_validator("conversation_history")
    @classmethod
    def limit_history(cls, v: Optional[List[ConversationTurn]]) -> Optional[List[ConversationTurn]]:
        """Limit conversation history to last 6 entries (3 turns)."""
        if v and len(v) > 6:
            return v[-6:]
        return v


class CreateUserRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=100)
    roles: List[str] = Field(min_length=1)
    department: Optional[str] = None

    @field_validator("roles")
    @classmethod
    def validate_roles(cls, v: List[str]) -> List[str]:
        from core.security import RoleChecker
        valid = list(RoleChecker.ROLE_HIERARCHY.keys())
        invalid = [r for r in v if r not in valid]
        if invalid:
            raise ValueError(f"Invalid roles: {invalid}. Must be one of {valid}")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number")
        return v


class UpdateUserRolesRequest(BaseModel):
    roles: List[str] = Field(min_length=1)

    @field_validator("roles")
    @classmethod
    def validate_roles(cls, v: List[str]) -> List[str]:
        from core.security import RoleChecker
        valid = list(RoleChecker.ROLE_HIERARCHY.keys())
        invalid = [r for r in v if r not in valid]
        if invalid:
            raise ValueError(f"Invalid roles: {invalid}")
        return v


class IngestDocumentRequest(BaseModel):
    allowed_roles: List[str] = Field(min_length=1)
    department: Optional[str] = None

    @field_validator("allowed_roles")
    @classmethod
    def validate_roles(cls, v: List[str]) -> List[str]:
        from core.security import RoleChecker
        valid = list(RoleChecker.ROLE_HIERARCHY.keys())
        invalid = [r for r in v if r not in valid]
        if invalid:
            raise ValueError(f"Invalid roles: {invalid}")
        return v

class CreateDepartmentRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)