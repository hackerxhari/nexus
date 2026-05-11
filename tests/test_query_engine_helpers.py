"""
Unit tests for pure helper functions in retrieval.query_engine.

These cover the non-IO parts of the RAG pipeline:
- source-name cleaning
- name-query extraction
- score filtering
- cross-document identifier extraction
- RBAC enforcement
- cache role-match check
- history-aware re-ranking
"""

import pytest

from retrieval.query_engine import (
    _clean_source_name,
    _extract_name_query,
    _filter_results_by_score,
    _extract_cross_doc_identifiers,
    _enforce_role_access,
    _cache_roles_ok,
    _rerank_results_by_name_query,
    _history_rerank,
    _build_citations,
)


class FakeResult:
    """Minimal duck-typed stand-in for retrieval.vector_store.SearchResult."""

    def __init__(
        self,
        id,
        text,
        score,
        source_file="doc.pdf",
        allowed_roles=None,
        departments=None,
        hierarchy=1,
        pages=None,
    ):
        self.id = id
        self.text = text
        self.score = score
        self.source_file = source_file
        self.allowed_roles = allowed_roles or []
        self.departments = departments or []
        self.hierarchy = hierarchy
        self.pages = pages or []


class TestCleanSourceName:
    def test_strips_uuid_prefix(self):
        name = "550e8400-e29b-41d4-a716-446655440000_report.pdf"
        assert _clean_source_name(name) == "report.pdf"

    def test_leaves_normal_name_alone(self):
        assert _clean_source_name("plain.pdf") == "plain.pdf"

    def test_case_insensitive_uuid(self):
        name = "550E8400-E29B-41D4-A716-446655440000_R.pdf"
        assert _clean_source_name(name) == "R.pdf"


class TestExtractNameQuery:
    @pytest.mark.parametrize(
        "question, expected",
        [
            ("Who is John Doe", "john doe"),
            ("who's John Doe", "john doe"),
            ("Tell me about Alice", "alice"),
            ("describe the project", "the project"),
            ("about marketing", "marketing"),
            ("What is the budget?", "what is the budget?"),
        ],
    )
    def test_extracts_after_prefix(self, question, expected):
        assert _extract_name_query(question) == expected


class TestFilterResultsByScore:
    def test_empty_returns_empty(self):
        assert _filter_results_by_score([]) == []

    def test_keeps_top_scored(self):
        results = [
            FakeResult("a", "x", 0.9),
            FakeResult("b", "y", 0.8),
            FakeResult("c", "z", 0.1),
        ]
        kept = _filter_results_by_score(results)
        # The 0.9 result must always survive
        assert any(r.score == 0.9 for r in kept)


class TestCrossDocIdentifierExtraction:
    def test_extracts_roll_no(self):
        results = [
            FakeResult("1", "Roll No: 101 | Name: John", 0.9, "students.pdf")
        ]
        ids = _extract_cross_doc_identifiers(results, "find John's marks")
        assert "101" in ids

    def test_extracts_emp_id(self):
        results = [
            FakeResult(
                "1",
                "Employee ID: EMP-42 | Name: Asha",
                0.9,
                "staff.pdf",
            )
        ]
        ids = _extract_cross_doc_identifiers(results, "find marks")
        assert "EMP-42" in ids

    def test_extracts_reg_no(self):
        results = [
            FakeResult("1", "Reg No: 2024CS01 | Name: Sam", 0.9, "reg.pdf")
        ]
        ids = _extract_cross_doc_identifiers(results, "x")
        assert "2024CS01" in ids

    def test_no_identifiers_returns_empty(self):
        # Text avoids the substring "id"/"roll"/"reg" so no pattern fires
        results = [FakeResult("1", "Plain narrative text only.", 0.5)]
        assert _extract_cross_doc_identifiers(results, "x") == []


class TestEnforceRoleAccess:
    def test_admin_bypasses_department(self):
        results = [
            FakeResult(
                "1",
                "secret",
                0.9,
                allowed_roles=["employee"],
                departments=["engineering"],
                hierarchy=3,
            )
        ]
        filtered = _enforce_role_access(
            results,
            user_roles=["admin", "employee"],
            user_department="hr",
            user_hierarchy=1,
        )
        assert len(filtered) == 1

    def test_unauthorized_role_blocked(self):
        results = [
            FakeResult(
                "1",
                "secret",
                0.9,
                allowed_roles=["admin"],
                departments=[],
                hierarchy=1,
            )
        ]
        filtered = _enforce_role_access(
            results,
            user_roles=["employee"],
            user_department="hr",
            user_hierarchy=1,
        )
        assert filtered == []

    def test_dept_match_required_for_non_global(self):
        results = [
            FakeResult(
                "1",
                "x",
                0.9,
                allowed_roles=["employee"],
                departments=["finance"],
                hierarchy=1,
            )
        ]
        filtered = _enforce_role_access(
            results,
            user_roles=["employee"],
            user_department="engineering",
            user_hierarchy=1,
        )
        assert filtered == []

    def test_hierarchy_blocks_below_doc_level(self):
        results = [
            FakeResult(
                "1",
                "x",
                0.9,
                allowed_roles=["manager"],
                departments=["engineering"],
                hierarchy=5,
            )
        ]
        filtered = _enforce_role_access(
            results,
            user_roles=["manager"],
            user_department="engineering",
            user_hierarchy=2,
        )
        assert filtered == []

    def test_no_dept_restriction_open_to_all(self):
        results = [
            FakeResult(
                "1",
                "x",
                0.9,
                allowed_roles=["employee"],
                departments=[],
                hierarchy=1,
            )
        ]
        filtered = _enforce_role_access(
            results,
            user_roles=["employee"],
            user_department="any",
            user_hierarchy=1,
        )
        assert len(filtered) == 1


class TestCacheRolesOk:
    def test_no_union_means_unrestricted(self):
        assert _cache_roles_ok({"answer": "x"}, ["employee"]) is True

    def test_any_role_match_passes(self):
        cached = {"allowed_roles_union": ["admin", "manager"]}
        assert _cache_roles_ok(cached, ["employee", "manager"]) is True

    def test_no_match_blocks(self):
        cached = {"allowed_roles_union": ["admin"]}
        assert _cache_roles_ok(cached, ["employee"]) is False


class TestNameRerank:
    def test_boosts_chunks_with_all_name_parts(self):
        results = [
            FakeResult("1", "Alice Smith works in HR", 0.5),
            FakeResult("2", "Bob mentions nothing here", 0.5),
        ]
        reranked = _rerank_results_by_name_query("Who is Alice Smith", results)
        assert reranked[0].id == "1"

    def test_short_name_query_unchanged(self):
        results = [
            FakeResult("1", "first chunk", 0.5),
            FakeResult("2", "second chunk", 0.6),
        ]
        reranked = _rerank_results_by_name_query("Hi", results)
        # No reranking happens because query is too short
        assert [r.id for r in reranked] == ["1", "2"]


class TestHistoryRerank:
    def test_empty_history_unchanged(self):
        results = [
            FakeResult("1", "x", 0.5),
            FakeResult("2", "y", 0.6),
        ]
        out = _history_rerank(results, None)
        assert [r.id for r in out] == ["1", "2"]
        out = _history_rerank(results, [])
        assert [r.id for r in out] == ["1", "2"]

    def test_boosts_chunks_overlapping_with_history(self):
        results = [
            FakeResult("1", "totally unrelated content here", 0.5),
            FakeResult("2", "vacation policy details inside", 0.5),
        ]
        history = [
            {"role": "user", "content": "Tell me about the vacation policy"},
            {"role": "assistant", "content": "Vacation is covered in section 4"},
        ]
        out = _history_rerank(results, history)
        # The vacation-mentioning chunk should now lead
        assert out[0].id == "2"


class TestBuildCitations:
    def test_aggregates_pages_per_source(self):
        results = [
            FakeResult("1", "x", 0.9, source_file="a.pdf", pages=[1, 2]),
            FakeResult("2", "y", 0.8, source_file="a.pdf", pages=[2, 3]),
            FakeResult("3", "z", 0.7, source_file="b.pdf", pages=[7]),
        ]
        used = ["a.pdf", "b.pdf"]
        citations = _build_citations(results, used)
        by_file = {c["file"]: c["pages"] for c in citations}
        assert by_file["a.pdf"] == [1, 2, 3]
        assert by_file["b.pdf"] == [7]

    def test_strips_uuid_prefix_in_citations(self):
        uuid_file = "550e8400-e29b-41d4-a716-446655440000_report.pdf"
        results = [
            FakeResult("1", "x", 0.9, source_file=uuid_file, pages=[5])
        ]
        citations = _build_citations(results, ["report.pdf"])
        assert citations[0]["file"] == "report.pdf"
        assert citations[0]["pages"] == [5]

    def test_skips_sources_not_in_used_list(self):
        results = [
            FakeResult("1", "x", 0.9, source_file="a.pdf", pages=[1]),
            FakeResult("2", "y", 0.8, source_file="b.pdf", pages=[2]),
        ]
        citations = _build_citations(results, ["a.pdf"])
        assert len(citations) == 1
        assert citations[0]["file"] == "a.pdf"
