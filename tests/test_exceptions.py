"""
Unit tests for core.exceptions — verifies error codes, HTTP statuses,
and details propagate correctly through the hierarchy.
"""

import pytest

from core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ErrorCode,
    ExtractionFailedError,
    FileTooLargeError,
    GenerationTimeoutError,
    GreenBaseException,
    QueryFailedError,
    RateLimitExceededError,
    RecordNotFoundError,
    TokenExpiredError,
)


class TestBaseBehavior:
    def test_default_status_is_500(self):
        e = GreenBaseException("boom")
        assert e.http_status == 500
        assert e.error_code == ErrorCode.INTERNAL_ERROR

    def test_to_dict_shape(self):
        e = GreenBaseException("boom", details={"x": 1})
        d = e.to_dict()
        assert d["message"] == "boom"
        assert d["details"] == {"x": 1}
        assert d["error_code"] == "INTERNAL_ERROR"


class TestAuthErrors:
    def test_authentication_is_401(self):
        e = AuthenticationError()
        assert e.http_status == 401

    def test_token_expired_carries_code(self):
        e = TokenExpiredError()
        assert e.error_code == ErrorCode.TOKEN_EXPIRED
        assert e.http_status == 401

    def test_authorization_is_403(self):
        e = AuthorizationError(required_roles=["admin"])
        assert e.http_status == 403
        assert e.details["required_roles"] == ["admin"]


class TestIngestionErrors:
    def test_file_too_large_records_sizes(self):
        e = FileTooLargeError("big.pdf", size_mb=120.5, max_mb=50)
        assert e.http_status == 422
        assert e.details["size_mb"] == 120.5
        assert e.details["max_mb"] == 50
        assert "big.pdf" in e.message

    def test_extraction_failed_records_reason(self):
        e = ExtractionFailedError("doc.pdf", "OCR returned empty text")
        assert e.details["filename"] == "doc.pdf"
        assert e.details["reason"] == "OCR returned empty text"


class TestRetrievalAndLlm:
    def test_query_failed_is_500(self):
        e = QueryFailedError("connection refused")
        assert e.http_status == 500
        assert e.error_code == ErrorCode.QUERY_FAILED

    def test_generation_timeout_records_seconds(self):
        e = GenerationTimeoutError(timeout_seconds=60)
        assert e.details["timeout_seconds"] == 60


class TestMisc:
    def test_record_not_found_is_404(self):
        e = RecordNotFoundError("Document", "doc-123")
        assert e.http_status == 404
        assert e.details["resource"] == "Document"
        assert e.details["identifier"] == "doc-123"

    def test_rate_limit_is_429(self):
        e = RateLimitExceededError(retry_after_seconds=42)
        assert e.http_status == 429
        assert e.details["retry_after_seconds"] == 42
