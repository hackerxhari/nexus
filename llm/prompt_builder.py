"""
All prompts for Nexus managed in one place.
Never build prompt strings inline in other files.
Changing prompt behavior = change it here only.
"""

from typing import Dict, List, Optional


class PromptBuilder:
    """
    Builds structured prompts for different query types.
    All prompts follow the same pattern:
      - Clear role definition
      - Strict grounding instruction (answer only from context)
      - Explicit fallback instruction
      - Clean output format
    """

    # System prompt used for all queries
    BASE_SYSTEM_PROMPT = """You are Nexus, an internal AI assistant.
Answer ONLY from the provided context. Never use outside knowledge.
If the answer is not in the context, say: "I don't have that information in the available documents."
Do NOT mention source document names.
Do NOT infer relationships between people unless explicitly stated in the context.
Only mention people and roles directly asked about.
When context chunks from different sources share a common key (Roll No, ID, Employee ID, etc.), connect them to provide a complete answer.
Be concise and professional."""

    @staticmethod
    def build_rag_prompt(
        question: str,
        context_chunks: List[str],
        sources: List[str],
        user_name: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Build a RAG query prompt with retrieved context.
        This is the main prompt used for all employee queries.
        Includes conversation history for multi-turn context.
        """
        # Format context with source labels
        formatted_context = ""
        for i, (chunk, source) in enumerate(
            zip(context_chunks, sources), start=1
        ):
            formatted_context += f"\n[Source {i}: {source}]\n{chunk}\n"

        greeting = f"Employee: {user_name}\n" if user_name else ""

        # Format conversation history if provided
        history_section = ""
        if conversation_history:
            history_lines = []
            for turn in conversation_history:
                role = turn.get("role", "user")
                content = turn.get("content", "").strip()
                if content:
                    label = "User" if role == "user" else "Assistant"
                    # Truncate long history entries to save context window
                    if len(content) > 300:
                        content = content[:300] + "..."
                    history_lines.append(f"{label}: {content}")
            if history_lines:
                history_section = (
                    "\nPREVIOUS CONVERSATION:\n"
                    + "\n".join(history_lines)
                    + "\n"
                )

        return f"""{greeting}
CONTEXT:
{formatted_context}
{history_section}
QUESTION: {question}

Answer concisely from the context above. If the context contains related data across different sources (e.g., same Roll No, ID, or key in multiple sources), combine them to give a complete answer. If the question refers to the previous conversation, use that context too. Do not mention document names.

ANSWER:"""

    @staticmethod
    def build_summary_prompt(
        content: str,
        summary_type: str = "general",
        max_points: int = 5
    ) -> str:
        """
        Build a summarization prompt.
        Used when employees request document summaries.
        """
        type_instructions = {
            "general": "Provide a clear, concise summary of the main points.",
            "bullet": f"Summarize in {max_points} bullet points.",
            "executive": "Provide an executive summary in 2-3 sentences.",
            "action_items": "Extract all action items and deadlines mentioned."
        }

        instruction = type_instructions.get(
            summary_type,
            type_instructions["general"]
        )

        return f"""DOCUMENT CONTENT:
{content}

TASK: {instruction}

Focus only on factual information present in the document.
Do not add opinions or outside information.

SUMMARY:"""

    @staticmethod
    def build_no_results_response(question: str) -> str:
        """
        Standard response when no relevant chunks are found.
        Consistent message regardless of whether it's an RBAC
        block or genuine no results — never reveal which it is.
        """
        return (
            "I don't have information about that in the documents "
            "available to you. If you believe this information should "
            "be accessible, please contact your administrator."
        )

    @staticmethod
    def build_query_focus_prompt(question: str) -> str:
        """
        Build a prompt to extract the core intent and topic.
        Returns a single-line focused query.
        """
        return f"""USER QUESTION:
{question}

TASK: Rewrite the question into a short, focused search query.
Rules:
- Return only one line.
- Do not add extra words or commentary.
- Keep proper nouns and names.

FOCUSED QUERY:"""

    @staticmethod
    def build_disambiguation_response(name_query: str, sources: List[str]) -> str:
        """
        Standard response when multiple exact matches exist.
        """
        items = "\n".join(f"- {s}" for s in sources[:5])
        return (
            f"I found multiple results for \"{name_query}\". "
            "Please provide a more specific query (last name, email, role, or department).\n\n"
            f"Possible matches:\n{items}"
        )