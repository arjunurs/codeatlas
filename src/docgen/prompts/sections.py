"""Section prompt definitions for documentation generation.

This module defines all the section prompts used in documentation generation,
providing a single source of truth for prompt content.
"""

from .templates import PromptTemplate

# Order in which sections appear in the documentation
SECTION_ORDER: list[str] = [
    "Overview",
    "Dependencies",
    "Key Classes and Functions",
    "Data Flow",
    "Integration Points",
]


# Section prompt configurations
SECTION_PROMPTS: dict[str, PromptTemplate] = {
    "Overview": PromptTemplate(
        title="Overview",
        task="Analyze the codebase and provide a comprehensive overview.",
        sections=[
            "Main Purpose and Functionality",
            "Key Components and Responsibilities",
            "How Different Parts Work Together",
            "Overall Architecture and Design Patterns",
        ],
        additional_context="Identify design patterns (Factory, Strategy, Observer, etc.), architectural style (library/CLI/service/framework), and key abstractions. Focus on the big picture and how components collaborate.",
        few_shot_examples=[
            """## Main Purpose and Functionality
`ledgerline` is a command-line tool that imports bank statements and reconciles them against a ledger. `cli.main()` parses the arguments and hands a `ReconcileJob` to the `Reconciler`, which matches each statement line to a ledger entry and writes a report.

## Key Components and Responsibilities
- `StatementParser` - Reads CSV and OFX statements into `Transaction` records
- `Reconciler` - Matches transactions to ledger entries by amount and date, within a tolerance
- `LedgerStore` - Loads and saves the ledger as a SQLite database
- `ReportWriter` - Renders matched, missing, and unexpected entries as Markdown

## How Different Parts Work Together
The run is a pipeline: parse, then match, then report. `Reconciler.run()` takes the parsed transactions and the open `LedgerStore`, and returns a `ReconcileResult` that `ReportWriter` renders; nothing is written to the ledger unless `--apply` is set.

## Overall Architecture and Design Patterns
A small layered CLI: parsing and storage sit behind the `Reconciler`. Parsers are chosen by file extension from a registry (`PARSERS`), so a new statement format is one new class."""
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
        additional_context="Group dependencies by purpose (web framework, testing, CLI, data processing, ML/AI). Explain WHY each dependency is needed with specific use cases. Note any version constraints, security considerations, or alternatives that were considered.",
        few_shot_examples=[
            """## Core Dependencies
- `tabular-io>=2.1` - Reads CSV statements in `StatementParser` (`tabular_io.read_rows()`)
- `ofxkit>=0.9` - Parses OFX statements; `OfxParser` wraps its `load()`

## Optional Dependencies
- `rich` (extra `pretty`) - Colored terminal reports; `ReportWriter` imports it only when `--color` is set, and falls back to plain text when it is missing

## Version Requirements
- Python >= 3.10 (`requires-python` in `pyproject.toml`)
- `tabular-io>=2.1`: earlier versions lack the `dialect=` argument that `StatementParser` passes

## Integration Points
`StatementParser` hides both parsing libraries behind one `parse(path)` method, so the rest of the code never imports them."""
        ],
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
        additional_context="Focus on public APIs and main entry points. Show usage patterns with concrete examples from the codebase. Identify protocols, abstract base classes, inheritance hierarchies, and composition relationships. Explain the responsibility of each component.",
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
        additional_context="Trace complete data transformations from input to output. Show error propagation paths and recovery mechanisms. Identify state management patterns (mutable vs immutable data, caching strategies). Explain validation and normalization steps.",
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
        additional_context="Document authentication methods (API keys, OAuth, tokens), API contracts and endpoints, rate limits and quotas, retry strategies, and error handling for external services. Explain configuration sources (env vars, files, CLI args) and validation.",
    ),
}


# Optional sections (not generated by default - require explicit --sections flag)
OPTIONAL_SECTION_PROMPTS: dict[str, PromptTemplate] = {
    "Migration Guidance": PromptTemplate(
        title="Migration Guidance",
        task="Identify deprecated patterns and suggest modern alternatives.",
        sections=[
            "Deprecated Python Patterns",
            "Library Deprecations",
            "Missing Modern Features",
            "Security Concerns",
            "Recommended Migrations",
        ],
        additional_context="""Focus on actionable improvements:
- Python 2 style code (print statements, old string formatting, dict.iteritems())
- Deprecated stdlib modules (imp, optparse, asyncore)
- Missing type hints where they would improve clarity and safety
- Old-style classes (not inheriting from object in Python 2 codebases)
- Sync code that could benefit from async/await
- Security issues (eval, exec, unsafe deserialization, shell=True in subprocess, SQL concatenation)
- Missing dataclasses where they would simplify code

For each issue: Show the current pattern, explain the risk/limitation, and provide the modern alternative with a concrete example.""",
    ),
    "Code Quality Insights": PromptTemplate(
        title="Code Quality Insights",
        task="Analyze code quality, patterns, and architectural decisions.",
        sections=[
            "Architectural Patterns Identified",
            "Design Decisions and Trade-offs",
            "Code Smells and Concerns",
            "Best Practices Observed",
            "Suggestions for Improvement",
        ],
        additional_context="""Provide balanced, constructive analysis:
- What's done WELL (preserve and extend these patterns in future development)
- What could be IMPROVED (actionable, specific suggestions with examples)
- Acknowledge TRADE-OFFS (explain intentional decisions vs accidental technical debt)

Use concrete examples from the actual code. Focus on maintainability, testability, extensibility, and performance. Be specific about the impact of each observation.""",
    ),
    "Cross-Reference Documentation": PromptTemplate(
        title="Cross-Reference Documentation",
        task=(
            "Document where key components are defined and used throughout the codebase. "
            "You will receive pre-analyzed cross-reference data showing exact import relationships."
        ),
        sections=[
            "Core Classes - Usage Map",
            "Key Functions - Call Sites",
            "Important Modules - Import Graph",
            "Public APIs - Consumer Analysis",
        ],
        additional_context="""The pre-analyzed data provides:
- Exact file paths where components are defined (with line numbers)
- Complete list of files that import each component
- Import counts for quantifying usage

Your task:
1. Use the pre-analyzed data as the factual foundation
2. Add PURPOSE explanations: Why is each component important? What role does it play?
3. Add CONTEXT from the codebase: How do consumers typically use this component?
4. Identify PATTERNS: Are there common usage patterns? Architectural insights?
5. Highlight KEY INTEGRATIONS: Which components work together frequently?

Format with clear structure:
- Use tables for components with many importers
- Use code snippets to show typical usage patterns
- Group related components together
- Prioritize high-impact, frequently-used components""",
    ),
}


def get_section_prompt(section_name: str) -> str:
    """Get the rendered prompt for a documentation section.

    Args:
        section_name: Name of the section (must be in SECTION_PROMPTS or OPTIONAL_SECTION_PROMPTS)

    Returns:
        The rendered prompt string

    Raises:
        KeyError: If section_name is not found in either prompt dictionary
    """
    # Check both required and optional sections
    all_prompts = {**SECTION_PROMPTS, **OPTIONAL_SECTION_PROMPTS}

    if section_name not in all_prompts:
        available = ", ".join(all_prompts.keys())
        raise KeyError(
            f"Unknown section: {section_name}. Available sections: {available}"
        )

    return all_prompts[section_name].render()


def get_all_section_prompts() -> dict[str, str]:
    """Get all section prompts as rendered strings.

    Returns:
        Dictionary mapping section names to rendered prompts
    """
    return {name: template.render() for name, template in SECTION_PROMPTS.items()}


def get_all_available_sections() -> list[str]:
    """Get names of all available sections (required + optional).

    Returns:
        List of all section names that can be generated
    """
    return SECTION_ORDER + list(OPTIONAL_SECTION_PROMPTS.keys())


def _matches_selection(section: str, selection: str) -> bool:
    """Check whether a user-supplied section name refers to a section.

    Matching is loose: case-insensitive and by substring, and also with spaces,
    "_", "-", and a joining "and" removed, so "dataflow", "code_quality", and
    "classes" all match.

    Args:
        section: Section name, e.g. "Key Classes and Functions"
        selection: Name as the user typed it, e.g. "classes"

    Returns:
        True if the selection refers to the section
    """
    section_lower = section.lower()
    selection_lower = selection.lower()
    section_squashed = (
        section_lower.replace(" ", "_")
        .replace("_and_", "_")
        .replace("_", "")
        .replace("-", "")
    )
    selection_squashed = selection_lower.replace("_", "").replace("-", "")
    return selection_lower in section_lower or selection_squashed in section_squashed


def select_sections(selected: list[str] | None) -> list[str]:
    """Resolve a section selection to section names in documentation order.

    Blank names, such as the empty entry from a trailing comma, are ignored.

    Args:
        selected: Section names as the user gave them, or None for the default

    Returns:
        The core sections when nothing is selected; otherwise every core or
        optional section that matches any selected name

    Raises:
        ValueError: If a selected name matches no section
    """
    names = [name.strip() for name in selected or [] if name.strip()]
    if not names:
        return list(SECTION_ORDER)

    available = get_all_available_sections()
    unknown = [
        name
        for name in names
        if not any(_matches_selection(section, name) for section in available)
    ]
    if unknown:
        raise ValueError(
            f"Unknown section(s): {', '.join(unknown)}. "
            f"Available sections: {', '.join(available)}"
        )

    return [
        section
        for section in available
        if any(_matches_selection(section, name) for name in names)
    ]
