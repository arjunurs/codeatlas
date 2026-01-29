"""Prompt templates for documentation generation.

This module provides a centralized system for managing prompts used
in documentation generation, reducing duplication and improving maintainability.
"""

from .sections import SECTION_ORDER, SECTION_PROMPTS, get_section_prompt
from .templates import PromptTemplate, render_prompt

__all__ = [
    "PromptTemplate",
    "render_prompt",
    "SECTION_PROMPTS",
    "SECTION_ORDER",
    "get_section_prompt",
]
