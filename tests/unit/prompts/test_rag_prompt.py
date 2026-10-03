"""Tests for the prompt template every section is written with."""

from docgen.prompts.rag_prompt import RAG_PROMPT_TEMPLATE


def test_prompt_does_not_ask_for_what_is_missing():
    """Asked to admit gaps, the model filled sections with notes on the context."""
    prompt = RAG_PROMPT_TEMPLATE.lower()

    assert "admit gaps" not in prompt
    assert "information is missing" not in prompt


def test_prompt_keeps_sections_to_what_the_context_shows():
    """What the context does not show is left out, not guessed or reported."""
    assert "Describe only behavior the context shows" in RAG_PROMPT_TEMPLATE
    assert "do not write about the context itself" in RAG_PROMPT_TEMPLATE
