"""Unit tests for configuration helpers."""

import pytest

from docgen.config import (
    DEFAULT_CONFIG,
    GeneratorConfig,
    QualityMode,
    get_model_for_quality_mode,
)


@pytest.mark.parametrize(
    ("mode", "model"),
    [
        (QualityMode.FAST, "claude-haiku-4-5"),
        (QualityMode.BALANCED, "claude-sonnet-5"),
        (QualityMode.BEST, "claude-opus-5"),
    ],
)
def test_quality_mode_selects_model(mode, model):
    """Each quality mode maps to its own model tier."""
    assert get_model_for_quality_mode(mode) == model


def test_default_model_is_the_balanced_model():
    """A run with no model or mode flags uses the balanced model."""
    assert (
        get_model_for_quality_mode(QualityMode.BALANCED)
        == DEFAULT_CONFIG.DEFAULT_ANTHROPIC_MODEL
    )


def test_retrieval_uses_mmr_by_default():
    """MMR skips near-duplicate chunks, which repetitive code is full of."""
    assert DEFAULT_CONFIG.RETRIEVER_SEARCH_TYPE == "mmr"


def test_score_threshold_with_mmr_rejected():
    """A score threshold applies only to similarity search, so it is not ignored."""
    with pytest.raises(ValueError, match="similarity search"):
        GeneratorConfig(RETRIEVER_SEARCH_TYPE="mmr", RETRIEVER_SCORE_THRESHOLD=0.5)


def test_score_threshold_with_similarity_search_accepted():
    config = GeneratorConfig(
        RETRIEVER_SEARCH_TYPE="similarity", RETRIEVER_SCORE_THRESHOLD=0.5
    )

    assert config.RETRIEVER_SCORE_THRESHOLD == 0.5
