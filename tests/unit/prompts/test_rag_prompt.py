"""Tests for the prompt template every section is written with."""

from docgen.prompts.rag_prompt import RAG_PROMPT_TEMPLATE


def test_prompt_does_not_ask_for_what_is_missing():
    """Asked to admit gaps, the model filled sections with notes on the context."""
    prompt = RAG_PROMPT_TEMPLATE.lower()

    assert "admit gaps" not in prompt
    assert "information is missing" not in prompt


def test_prompt_keeps_sections_to_what_the_excerpts_show():
    """What the excerpts do not show is left out, not guessed or reported."""
    assert "Describe only behavior the excerpts show" in RAG_PROMPT_TEMPLATE
    assert "Leave out what the excerpts do not show" in RAG_PROMPT_TEMPLATE


def test_prompt_says_readers_never_see_the_excerpts():
    """Told only not to write about the context, sections on Flask still said
    "the code shown" and "not shown"; the reason and the phrases are spelled out."""
    assert (
        "Readers see only your documentation, never the excerpts" in RAG_PROMPT_TEMPLATE
    )
    for phrase in ("the code shows", "the code shown", "not shown"):
        assert f'"{phrase}"' in RAG_PROMPT_TEMPLATE
