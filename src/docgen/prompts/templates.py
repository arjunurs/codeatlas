"""Prompt template system for documentation generation.

This module defines the PromptTemplate dataclass and rendering utilities
for consistent prompt formatting across all documentation sections.
"""

from dataclasses import dataclass

# Standard formatting instructions shared across all prompts
STANDARD_FORMAT_INSTRUCTIONS = """Format your response using proper Markdown with these specific requirements:
1. Use ## for main sections and ### for subsections
2. All code elements (class names, method names, properties) must be wrapped in `backticks`
3. Use proper list indentation with - or * for bullets
4. Add blank lines between sections and list items for clarity
5. Use ```python for code blocks"""

# Standard code reference instructions
CODE_REFERENCE_INSTRUCTIONS = """Be specific and use examples from the actual code.
Every class name, method name, function name, and property must be in `backticks`."""


@dataclass
class PromptTemplate:
    """Template for generating documentation section prompts.

    Attributes:
        title: The section title (e.g., "Overview")
        task: The main task description for the LLM
        sections: List of markdown sections to include
        format_instructions: Custom formatting instructions (uses standard if None)
        reference_instructions: Code reference instructions (uses standard if None)
        additional_context: Any additional context to append
        few_shot_examples: Optional list of example outputs to guide the LLM
    """

    title: str
    task: str
    sections: list[str]
    format_instructions: str | None = None
    reference_instructions: str | None = None
    additional_context: str | None = None
    few_shot_examples: list[str] | None = None

    def render(self) -> str:
        """Render the complete prompt string.

        Returns:
            The formatted prompt string ready for LLM consumption
        """
        parts = [self.task]

        # Add few-shot examples FIRST (before instructions)
        if self.few_shot_examples:
            parts.append("\n## Examples of Good Output\n")
            parts.append(
                "These examples describe a different, made-up project. They show "
                "the format and depth wanted; describe the code in the excerpts, "
                "not the examples.\n"
            )
            for i, example in enumerate(self.few_shot_examples, 1):
                parts.append(f"### Example {i}:")
                parts.append(example)
                parts.append("")  # Empty line after each example

        # Add formatting instructions
        format_inst = self.format_instructions or STANDARD_FORMAT_INSTRUCTIONS
        parts.append(format_inst)

        # Add sections
        if self.sections:
            parts.append("\nInclude these sections:")
            for section in self.sections:
                parts.append(f"## {section}")
            parts.append("")  # Empty line after sections

        # Add reference instructions
        ref_inst = self.reference_instructions or CODE_REFERENCE_INSTRUCTIONS
        parts.append(ref_inst)

        # Add any additional context
        if self.additional_context:
            parts.append(self.additional_context)

        return "\n".join(parts)


def render_prompt(template: PromptTemplate) -> str:
    """Render a prompt template to a string.

    This is a convenience function that simply calls template.render().

    Args:
        template: The PromptTemplate to render

    Returns:
        The rendered prompt string
    """
    return template.render()
