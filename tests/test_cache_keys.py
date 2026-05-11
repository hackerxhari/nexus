"""
Unit tests for cache.cache_service.CacheKeys.
Pure-function tests — no Redis connection needed.
"""

import pytest

from cache.cache_service import CacheKeys


class TestQueryKey:
    def test_same_question_same_key(self):
        a = CacheKeys.query_result("What is the leave policy?")
        b = CacheKeys.query_result("What is the leave policy?")
        assert a == b

    def test_case_insensitive(self):
        a = CacheKeys.query_result("Hello World")
        b = CacheKeys.query_result("hello world")
        c = CacheKeys.query_result("HELLO WORLD")
        assert a == b == c

    def test_whitespace_trim(self):
        a = CacheKeys.query_result("  hello  ")
        b = CacheKeys.query_result("hello")
        assert a == b

    def test_different_question_different_key(self):
        a = CacheKeys.query_result("question one")
        b = CacheKeys.query_result("question two")
        assert a != b

    def test_topic_affects_key(self):
        base = CacheKeys.query_result("q")
        topic_a = CacheKeys.query_result("q", topic_id="topic-a")
        topic_b = CacheKeys.query_result("q", topic_id="topic-b")
        assert base != topic_a
        assert topic_a != topic_b

    def test_department_affects_key(self):
        base = CacheKeys.query_result("q")
        eng = CacheKeys.query_result("q", department="engineering")
        hr = CacheKeys.query_result("q", department="hr")
        assert base != eng
        assert eng != hr

    def test_namespaced_under_nexus(self):
        key = CacheKeys.query_result("hello")
        assert key.startswith("nexus:query:")


class TestOtherKeys:
    def test_blacklist_key_namespaced(self):
        key = CacheKeys.token_blacklist("jti-123")
        assert key == "nexus:blacklist:jti-123"

    def test_rate_limit_key_namespaced(self):
        key = CacheKeys.rate_limit("user-7", 12345)
        assert key == "nexus:ratelimit:user-7:12345"

    def test_session_key_namespaced(self):
        key = CacheKeys.user_session("user-7")
        assert key == "nexus:session:user-7"
