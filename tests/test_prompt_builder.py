"""
Unit tests for llm.prompt_builder.PromptBuilder.
These tests are fully isolated — no LLM, no DB, no Redis.
"""

import pytest

from llm.prompt_builder import PromptBuilder


class TestRagPrompt:
    def test_includes_question(self, sample_chunks, sample_sources):
        prompt = PromptBuilder.build_rag_prompt(
            question="What is the leave policy?",
            context_chunks=sample_chunks,
            sources=sample_sources,
        )
        assert "What is the leave policy?" in prompt
        assert "ANSWER:" in prompt

    def test_embeds_every_chunk(self, sample_chunks, sample_sources):
        prompt = PromptBuilder.build_rag_prompt(
            question="q",
            context_chunks=sample_chunks,
            sources=sample_sources,
        )
        for chunk in sample_chunks:
            assert chunk in prompt

    def test_labels_sources_with_index(self, sample_chunks, sample_sources):
        prompt = PromptBuilder.build_rag_prompt(
            question="q",
            context_chunks=sample_chunks,
            sources=sample_sources,
        )
        assert "[Source 1: hr_policy.pdf]" in prompt
        assert "[Source 2: finance_handbook.pdf]" in prompt
        assert "[Source 3: security_policy.pdf]" in prompt

    def test_optional_user_name(self, sample_chunks, sample_sources):
        with_name = PromptBuilder.build_rag_prompt(
            question="q",
            context_chunks=sample_chunks,
            sources=sample_sources,
            user_name="Asha",
        )
        without_name = PromptBuilder.build_rag_prompt(
            question="q",
            context_chunks=sample_chunks,
            sources=sample_sources,
        )
        assert "Employee: Asha" in with_name
        assert "Employee:" not in without_name

    def test_conversation_history_included(self, sample_chunks, sample_sources):
        prompt = PromptBuilder.build_rag_prompt(
            question="And the second?",
            context_chunks=sample_chunks,
            sources=sample_sources,
            conversation_history=[
                {"role": "user", "content": "What is the first rule?"},
                {"role": "assistant", "content": "The first rule is X."},
            ],
        )
        assert "PREVIOUS CONVERSATION:" in prompt
        assert "User: What is the first rule?" in prompt
        assert "Assistant: The first rule is X." in prompt

    def test_history_truncated_when_long(self, sample_chunks, sample_sources):
        long_content = "x" * 600
        prompt = PromptBuilder.build_rag_prompt(
            question="q",
            context_chunks=sample_chunks,
            sources=sample_sources,
            conversation_history=[{"role": "user", "content": long_content}],
        )
        # Truncated at 300 chars + "..."
        assert "..." in prompt
        assert long_content not in prompt

    def test_empty_history_omitted(self, sample_chunks, sample_sources):
        prompt = PromptBuilder.build_rag_prompt(
            question="q",
            context_chunks=sample_chunks,
            sources=sample_sources,
            conversation_history=[],
        )
        assert "PREVIOUS CONVERSATION:" not in prompt


class TestOtherPrompts:
    def test_no_results_response_is_consistent(self):
        a = PromptBuilder.build_no_results_response("q1")
        b = PromptBuilder.build_no_results_response("totally different question")
        assert a == b
        assert "don't have" in a.lower() or "do not have" in a.lower()

    def test_disambiguation_lists_sources(self):
        msg = PromptBuilder.build_disambiguation_response(
            "john",
            ["resume_john_a.pdf", "resume_john_b.pdf"],
        )
        assert "john" in msg.lower()
        assert "resume_john_a.pdf" in msg
        assert "resume_john_b.pdf" in msg

    def test_disambiguation_caps_at_five(self):
        sources = [f"file_{i}.pdf" for i in range(10)]
        msg = PromptBuilder.build_disambiguation_response("x", sources)
        # Only first 5 should appear
        assert "file_4.pdf" in msg
        assert "file_5.pdf" not in msg

    def test_summary_prompt_uses_bullet_format(self):
        prompt = PromptBuilder.build_summary_prompt(
            "Some long content",
            summary_type="bullet",
            max_points=3,
        )
        assert "3 bullet" in prompt
        assert "Some long content" in prompt

    def test_query_focus_prompt_contains_question(self):
        prompt = PromptBuilder.build_query_focus_prompt("Where is the office?")
        assert "Where is the office?" in prompt
        assert "FOCUSED QUERY:" in prompt
