"""
All database models for Nexus.
Four tables: User, Document, AuditLog, RefreshToken.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, Column, DateTime, Float,
    ForeignKey, Integer, String,
    Text, JSON, Index
)
from sqlalchemy.orm import relationship
from db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def generate_uuid() -> str:
    return str(uuid.uuid4())


# ── Department ────────────────────────────────────────────────

class Department(Base):
    """
    Organization departments.
    """
    __tablename__ = "departments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), unique=True, nullable=False, index=True)
    
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<Department id={self.id} name={self.name}>"


# ── User ─────────────────────────────────────────────────────

class User(Base):
    """
    Organization employees who access Nexus.
    Roles stored as JSON list — flexible, no separate roles table needed for v1.
    """
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    department = Column(String(100), nullable=True)
    hierarchy = Column(Integer, default=1, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Roles e.g. ["employee", "hr"]
    roles = Column(JSON, nullable=False, default=list)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    audit_logs = relationship("AuditLog", back_populates="user", lazy="dynamic")
    refresh_tokens = relationship("RefreshToken", back_populates="user", lazy="dynamic", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_users_email_active", "email", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} roles={self.roles}>"


# ── Document ──────────────────────────────────────────────────

class Document(Base):
    """
    Metadata for every document ingested into the knowledge base.
    Actual content lives in Qdrant — this tracks who uploaded what and permissions.
    """
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    departments = Column(JSON, default=list, nullable=False)
    hierarchy = Column(Integer, default=1, nullable=False)

    # Which roles can access this document
    allowed_roles = Column(JSON, nullable=False, default=list)

    # Ingestion status
    status = Column(
        String(50),
        nullable=False,
        default="pending"
        # values: pending, processing, completed, failed
    )
    error_message = Column(Text, nullable=True)

    # Ingestion stats
    total_chunks = Column(Integer, nullable=True)
    ingestion_time_seconds = Column(Float, nullable=True)

    # Who uploaded it
    uploaded_by = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    uploader = relationship("User", foreign_keys=[uploaded_by])

    __table_args__ = (
        Index("idx_documents_status", "status"),
        Index("idx_documents_uploaded_by", "uploaded_by"),
    )

    def __repr__(self) -> str:
        return f"<Document id={self.id} filename={self.filename} status={self.status}>"


# ── Topic Tree ───────────────────────────────────────────────

class TopicNode(Base):
    """
    Hierarchical topic nodes for semantic grouping.
    Tree structure: root -> topic -> document
    """
    __tablename__ = "topics"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    parent_id = Column(String(36), ForeignKey("topics.id", ondelete="CASCADE"), nullable=True)
    level = Column(Integer, nullable=False, default=0)
    path = Column(String(1000), nullable=False)

    # For document-level nodes only
    doc_id = Column(String(36), nullable=True, index=True)

    # Embedding for topic-level nodes
    embedding = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    parent = relationship("TopicNode", remote_side=[id], backref="children")

    __table_args__ = (
        Index("idx_topics_parent", "parent_id"),
        Index("idx_topics_name", "name"),
        Index("idx_topics_level", "level"),
    )

    def __repr__(self) -> str:
        return f"<TopicNode id={self.id} name={self.name} level={self.level}>"


# ── AuditLog ──────────────────────────────────────────────────

class AuditLog(Base):
    """
    Every query made by every user is logged here.
    Non-negotiable for an org tool — when employees claim wrong answers,
    this is your evidence trail.
    """
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)

    # Who asked
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    user_email = Column(String(255), nullable=False)
    user_roles = Column(JSON, nullable=False)

    # What they asked
    question = Column(Text, nullable=False)
    question_hash = Column(String(64), nullable=False)  # for dedup analysis

    # What we returned
    answer = Column(Text, nullable=True)
    sources = Column(JSON, nullable=True, default=list)
    chunks_retrieved = Column(Integer, nullable=True)
    cache_hit = Column(Boolean, default=False, nullable=False)

    # Performance
    response_time_ms = Column(Float, nullable=True)
    embedding_time_ms = Column(Float, nullable=True)
    retrieval_time_ms = Column(Float, nullable=True)
    llm_time_ms = Column(Float, nullable=True)

    # Request metadata
    request_id = Column(String(36), nullable=True)
    ip_address = Column(String(45), nullable=True)

    # Status
    status = Column(String(50), nullable=False, default="success")
    error_code = Column(String(100), nullable=True)

    # Timestamp
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="audit_logs")

    __table_args__ = (
        Index("idx_audit_user_created", "user_id", "created_at"),
        Index("idx_audit_question_hash", "question_hash"),
        Index("idx_audit_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} user={self.user_email} status={self.status}>"


# ── RefreshToken ──────────────────────────────────────────────

class RefreshToken(Base):
    """
    Tracks issued refresh tokens.
    Allows admin to revoke specific sessions and
    prevents refresh token reuse attacks.
    """
    __tablename__ = "refresh_tokens"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    jti = Column(String(36), unique=True, nullable=False, index=True)

    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    is_revoked = Column(Boolean, default=False, nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_reason = Column(String(255), nullable=True)

    # Device/session info
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Relationships
    user = relationship("User", back_populates="refresh_tokens")

    __table_args__ = (
        Index("idx_refresh_tokens_user_revoked", "user_id", "is_revoked"),
    )

    def __repr__(self) -> str:
        return f"<RefreshToken jti={self.jti} user_id={self.user_id} revoked={self.is_revoked}>"


class CustomQA(Base):
    """
    Admin-defined question-answer pairs.
    Matched questions bypass the RAG pipeline for instant, curated responses.
    Uses embedding similarity for fuzzy matching.
    """
    __tablename__ = "custom_qa"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Question patterns — JSON list of strings that should match
    # e.g. ["What is the company holiday list?", "holidays", "company holidays"]
    question_patterns = Column(JSON, nullable=False)

    # The curated answer to return
    answer = Column(Text, nullable=False)

    # Category for organization (e.g. "HR", "IT", "General")
    category = Column(String(100), nullable=True)

    # Higher priority answers are checked first
    priority = Column(Integer, default=0, nullable=False)

    # Toggle without deleting
    is_active = Column(Boolean, default=True, nullable=False)

    # Audit
    created_by = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=True)

    __table_args__ = (
        Index("idx_custom_qa_active_priority", "is_active", "priority"),
    )

    def __repr__(self) -> str:
        preview = str(self.question_patterns)[:60]
        return f"<CustomQA id={self.id} patterns={preview} active={self.is_active}>"