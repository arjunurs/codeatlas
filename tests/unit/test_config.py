"""Unit tests for configuration helpers."""

import pytest

from docgen.config import (
    DEFAULT_CONFIG,
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
    assert DEFAULT_CONFIG.DEFAULT_ANTHROPIC_MODEL == get_model_for_quality_mode(
        QualityMode.BALANCED
    )
