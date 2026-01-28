"""Prompt templates for documentation generation.

This module provides a centralized system for managing prompts used
in documentation generation, reducing duplication and improving maintainability.
"""

from .templates import PromptTemplate, render_prompt
from .sections import SECTION_PROMPTS, SECTION_ORDER, get_section_prompt

__all__ = [
    "PromptTemplate",
    "render_prompt",
    "SECTION_PROMPTS",
    "SECTION_ORDER",
    "get_section_prompt",
]
