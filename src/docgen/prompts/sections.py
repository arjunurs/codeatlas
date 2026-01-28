"""Section prompt definitions for documentation generation.

This module defines all the section prompts used in documentation generation,
providing a single source of truth for prompt content.
"""

from typing import Dict, List

from .templates import PromptTemplate


# Order in which sections appear in the documentation
SECTION_ORDER: List[str] = [
    "Overview",
    "Dependencies",
    "Key Classes and Functions",
    "Data Flow",
    "Integration Points",
]


# Section prompt configurations
SECTION_PROMPTS: Dict[str, PromptTemplate] = {
    "Overview": PromptTemplate(
        title="Overview",
        task="Analyze the codebase and provide a comprehensive overview.",
        sections=[
            "Main Purpose and Functionality",
            "Key Components and Responsibilities",
            "How Different Parts Work Together",
            "Overall Architecture and Design Patterns",
        ],
    ),
    "Dependencies": PromptTemplate(
        title="Dependencies",
        task="Analyze the project dependencies and explain:",
        sections=[
            "Core Dependencies",
            "Optional Dependencies",
            "Version Requirements",
            "Integration Points",
        ],
        reference_instructions=(
            "Be specific and reference actual dependencies from the project."
        ),
    ),
    "Key Classes and Functions": PromptTemplate(
        title="Key Classes and Functions",
        task="Describe the key classes and functions.",
        sections=[
            "Core Classes",
            "Helper Functions",
            "Class Relationships",
            "Usage Examples",
        ],
    ),
    "Data Flow": PromptTemplate(
        title="Data Flow",
        task="Explain the data flow through the system.",
        sections=[
            "Data Processing Flow",
            "Key Data Structures",
            "Input/Output Handling",
            "Error Handling",
        ],
    ),
    "Integration Points": PromptTemplate(
        title="Integration Points",
        task="Describe how the code integrates with other systems.",
        sections=[
            "External Integrations",
            "Authentication",
            "Error Handling",
            "Configuration",
        ],
    ),
}


def get_section_prompt(section_name: str) -> str:
    """Get the rendered prompt for a documentation section.

    Args:
        section_name: Name of the section (must be in SECTION_PROMPTS)

    Returns:
        The rendered prompt string

    Raises:
        KeyError: If section_name is not found in SECTION_PROMPTS
    """
    if section_name not in SECTION_PROMPTS:
        available = ", ".join(SECTION_PROMPTS.keys())
        raise KeyError(
            f"Unknown section: {section_name}. Available sections: {available}"
        )

    return SECTION_PROMPTS[section_name].render()


def get_all_section_prompts() -> Dict[str, str]:
    """Get all section prompts as rendered strings.

    Returns:
        Dictionary mapping section names to rendered prompts
    """
    return {name: template.render() for name, template in SECTION_PROMPTS.items()}
