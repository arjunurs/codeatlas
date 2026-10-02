"""Unit tests for SectionOrchestrator."""

from unittest.mock import MagicMock

from langchain_core.output_parsers import StrOutputParser

from docgen.config import DEFAULT_CONFIG
from docgen.core.section_orchestrator import SectionOrchestrator
from docgen.utils.cost_tracker import CostTracker


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
