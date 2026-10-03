"""Unit tests for SectionOrchestrator."""

import logging
from dataclasses import replace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import anthropic
import pytest
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda

from docgen.cache.content_cache import SectionContentCache
from docgen.config import DEFAULT_CONFIG
from docgen.core.section_orchestrator import SectionOrchestrator
from docgen.models.file_analysis import FileAnalysis
from docgen.utils.cost_tracker import CostTracker

# The Anthropic and OpenAI SDKs build their errors from httpx2 objects; the
# releases at the dependency floors still use httpx. Type-check against httpx2,
# the version in uv.lock.
if TYPE_CHECKING:
    import httpx2 as httpx
else:
    try:
        import httpx2 as httpx
    except ImportError:
        import httpx

ANALYSES = [
    FileAnalysis(
        file_path="app.py",
        entities=[],
        imports=[],
        content="x = 1\n",
        _skip_validation=True,
    )
]


def counting_chain(calls: list[str]) -> RunnableLambda:
    """A chain that records each prompt and returns numbered content."""

    def generate(prompt: str) -> str:
        calls.append(prompt)
        return f"content {len(calls)}"

    return RunnableLambda(generate)


def cached_orchestrator(cache, model_name, **kwargs) -> SectionOrchestrator:
    """An orchestrator that uses the given section cache."""
    return SectionOrchestrator(
        DEFAULT_CONFIG,
        model_name=model_name,
        section_cache=cache,
        current_analyses=ANALYSES,
        **kwargs,
    )


def test_cache_hit_is_recorded_under_the_selected_model():
    """Cached sections are recorded under the model that generates sections."""
    section_cache = MagicMock()
    section_cache.get_cached_section.return_value = "cached content"
    cost_tracker = CostTracker()
    orchestrator = SectionOrchestrator(
        DEFAULT_CONFIG,
        model_name="claude-opus-5",
        cost_tracker=cost_tracker,
        section_cache=section_cache,
        current_analyses=[MagicMock()],
    )

    content = orchestrator._generate_section_with_cache(MagicMock(), "Overview")

    assert content == "cached content"
    assert list(cost_tracker.usage_by_model) == ["claude-opus-5"]


def test_generated_sections_record_reported_token_usage(fake_chat_model_with_usage):
    """Each generated section records the tokens the model reported."""
    cost_tracker = CostTracker()
    orchestrator = SectionOrchestrator(
        DEFAULT_CONFIG,
        model_name="claude-sonnet-5",
        parallel=True,
        cost_tracker=cost_tracker,
        selected_sections=["overview", "dependencies"],
    )
    chain = fake_chat_model_with_usage | StrOutputParser()

    _, errors = orchestrator.generate_documentation_sections(chain)

    assert errors == []
    stats = cost_tracker.usage_by_model["claude-sonnet-5"]
    assert (stats.input_tokens, stats.output_tokens, stats.requests) == (240, 60, 2)
    assert not stats.estimated


def test_changing_model_regenerates_cached_section(tmp_path):
    """A cached section is reused for the same model and regenerated for another."""
    cache = SectionContentCache(tmp_path)
    calls: list[str] = []
    chain = counting_chain(calls)

    first = cached_orchestrator(cache, "claude-sonnet-5")._generate_section_with_cache(
        chain, "Overview"
    )
    again = cached_orchestrator(cache, "claude-sonnet-5")._generate_section_with_cache(
        chain, "Overview"
    )
    other = cached_orchestrator(cache, "claude-haiku-4-5")._generate_section_with_cache(
        chain, "Overview"
    )

    assert (first, again, other) == ("content 1", "content 1", "content 2")


def test_changing_prompt_regenerates_cached_section(tmp_path):
    """The cache key covers the exact prompt, including preprocessing."""
    cache = SectionContentCache(tmp_path)
    calls: list[str] = []
    chain = counting_chain(calls)

    cached_orchestrator(cache, "claude-sonnet-5")._generate_section_with_cache(
        chain, "Overview"
    )
    changed = cached_orchestrator(
        cache,
        "claude-sonnet-5",
        section_preprocessors={"overview": lambda prompt, _: prompt + " Be brief."},
    )._generate_section_with_cache(chain, "Overview")

    assert changed == "content 2"
    assert calls[1].endswith(" Be brief.")


@pytest.mark.parametrize(
    "change",
    [
        {"RETRIEVER_K": 5},
        {"RETRIEVER_SEARCH_TYPE": "mmr"},
        {"RETRIEVER_SCORE_THRESHOLD": 0.5},
        {"RETRIEVER_FETCH_K": 40},
        {"RETRIEVER_LAMBDA_MULT": 0.9},
        {"DEFAULT_MAX_OUTPUT_TOKENS": 4096},
    ],
)
def test_changing_retrieval_or_output_settings_regenerates_cached_section(
    tmp_path, change
):
    """Settings that shape a section's text are part of its cache key."""
    cache = SectionContentCache(tmp_path)
    calls: list[str] = []
    chain = counting_chain(calls)
    # Similarity search, so that both MMR and a score threshold are changes
    base = replace(DEFAULT_CONFIG, RETRIEVER_SEARCH_TYPE="similarity")

    SectionOrchestrator(
        base,
        model_name="claude-sonnet-5",
        section_cache=cache,
        current_analyses=ANALYSES,
    )._generate_section_with_cache(chain, "Overview")
    changed = SectionOrchestrator(
        replace(base, **change),
        model_name="claude-sonnet-5",
        section_cache=cache,
        current_analyses=ANALYSES,
    )._generate_section_with_cache(chain, "Overview")

    assert changed == "content 2"


def test_changing_the_rag_template_regenerates_cached_section(tmp_path, monkeypatch):
    """The template that wraps every section prompt is part of the cache key."""
    cache = SectionContentCache(tmp_path)
    calls: list[str] = []
    chain = counting_chain(calls)
    cached_orchestrator(cache, "claude-sonnet-5")._generate_section_with_cache(
        chain, "Overview"
    )

    monkeypatch.setattr(
        "docgen.core.section_orchestrator.RAG_PROMPT_TEMPLATE", "{context}\n{question}"
    )
    changed = cached_orchestrator(
        cache, "claude-sonnet-5"
    )._generate_section_with_cache(chain, "Overview")

    assert changed == "content 2"


def test_force_refresh_regenerates_and_still_caches(tmp_path):
    """force_refresh ignores cached content but caches the fresh result."""
    cache = SectionContentCache(tmp_path)
    calls: list[str] = []
    chain = counting_chain(calls)

    cached_orchestrator(cache, "claude-sonnet-5")._generate_section_with_cache(
        chain, "Overview"
    )
    refreshed = cached_orchestrator(
        cache, "claude-sonnet-5", force_refresh=True
    )._generate_section_with_cache(chain, "Overview")
    after = cached_orchestrator(cache, "claude-sonnet-5")._generate_section_with_cache(
        chain, "Overview"
    )

    assert (refreshed, after) == ("content 2", "content 2")
    assert len(calls) == 2


def test_truncated_section_is_flagged_and_not_cached(
    tmp_path, caplog, fake_chat_model_with_usage
):
    """A section cut off at the output limit is marked, warned about, and regenerated."""
    cache = SectionContentCache(tmp_path)
    cost_tracker = CostTracker()
    model = fake_chat_model_with_usage.model_copy(update={"stop_reason": "max_tokens"})
    chain = model | StrOutputParser()

    with caplog.at_level("WARNING", logger="docgen"):
        for _ in range(2):
            content = cached_orchestrator(
                cache, "claude-sonnet-5", cost_tracker=cost_tracker
            )._generate_section_with_cache(chain, "Overview")

    assert content.startswith("generated text")
    assert "cut off at the model's output limit" in content
    assert any("Overview" in r.getMessage() for r in caplog.records)
    # Not served from the cache: both calls reached the model
    assert cost_tracker.usage_by_model["claude-sonnet-5"].cached_requests == 0
    assert cost_tracker.usage_by_model["claude-sonnet-5"].requests == 2


def failing_chain(message: str) -> RunnableLambda:
    """A chain that raises the same error for every section."""

    def generate(prompt: str) -> str:
        raise RuntimeError(message)

    return RunnableLambda(generate)


@pytest.mark.parametrize("parallel", [False, True])
def test_failed_section_is_reported_once(parallel):
    """A failed section records its error without a repeated prefix."""
    orchestrator = SectionOrchestrator(
        DEFAULT_CONFIG,
        model_name="claude-sonnet-5",
        parallel=parallel,
        selected_sections=["overview", "dependencies"],
    )

    sections, errors = orchestrator.generate_documentation_sections(
        failing_chain("boom")
    )

    names = [section["title"] for section in sections]
    assert sorted(errors) == sorted((name, "RuntimeError: boom") for name in names)
    assert [section["content"] for section in sections] == [
        "*Error generating this section: RuntimeError: boom*"
    ] * len(names)


def test_rejected_api_key_is_reported_with_what_to_do():
    """A provider error on a section names the provider and the fix."""
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    body = {"type": "error", "error": {"type": "authentication_error"}}
    rejected = anthropic.AuthenticationError(
        f"Error code: 401 - {body}",
        response=httpx.Response(401, request=request),
        body=body,
    )

    def generate(prompt: str) -> str:
        raise rejected

    orchestrator = SectionOrchestrator(
        DEFAULT_CONFIG, model_name="claude-sonnet-5", selected_sections=["overview"]
    )
    _, errors = orchestrator.generate_documentation_sections(RunnableLambda(generate))

    assert errors == [
        (
            "Overview",
            f"Anthropic rejected the API key; check ANTHROPIC_API_KEY ({rejected})",
        )
    ]


def test_failed_section_is_left_to_the_caller_to_report(caplog):
    """The orchestrator logs a failure only at debug level, with its traceback."""
    orchestrator = SectionOrchestrator(
        DEFAULT_CONFIG, model_name="claude-sonnet-5", selected_sections=["overview"]
    )

    with caplog.at_level(logging.DEBUG, logger="docgen"):
        orchestrator.generate_documentation_sections(failing_chain("boom"))

    problems = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert [r for r in problems if r.name.startswith("docgen")] == []
    failures = [r for r in caplog.records if r.exc_info]
    assert [r.getMessage() for r in failures] == ["Section 'Overview' failed"]
