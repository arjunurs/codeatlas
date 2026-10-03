# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

codeatlas is a Python tool that automatically generates comprehensive documentation for Python codebases using LLMs (Anthropic Claude and OpenAI). It analyzes code structure, generates architectural diagrams (Mermaid), and creates interactive HTML documentation.

The Python package is `docgen` (`src/docgen`). The CLI is installed as `codeatlas`, with `docgen` kept as an alias.

## Common Commands

```bash
# Install dependencies (using uv)
uv sync

# Run all tests with coverage
uv run pytest tests/ -v

# Run a specific test file
uv run pytest tests/unit/core/test_generator.py -v

# Run a specific test
uv run pytest tests/unit/core/test_generator.py::test_generate_documentation_success -v

# Run tests matching a pattern
uv run pytest -k "test_analyzer" -v

# Lint and auto-fix
uv run ruff check src/ tests/ --fix

# Format code
uv run ruff format src/ tests/

# Type checking
uv run ty check

# Run pre-commit hooks manually (lint, format, type check)
pre-commit run --all-files

# Run the CLI
uv run codeatlas --source ./my_project --output ./docs

# Generate only diagrams (no API costs, no API keys needed)
uv run codeatlas --source ./my_project --diagrams-only

# Dry-run mode (analyze without LLM calls)
uv run codeatlas --source ./my_project --dry-run

# Generate with optional sections
uv run codeatlas --source ./my_project --sections "overview,migration_guidance,code_quality"

# Tune RAG retrieval for diversity
uv run codeatlas --source ./my_project --retriever-search-type mmr --retriever-k 15
```

## Architecture

### Core Data Flow

```
Source Directory → CodeAnalyzer → FileAnalysis[] → CodeDocumentationGenerator
                                                            ↓
                                        ┌───────────────────┼───────────────────┐
                                        ↓                   ↓                   ↓
                                DiagramGenerator    RAG Chain (LCEL)     TemplateManager
                                        ↓                   ↓                   ↓
                                Mermaid Diagrams    Section Content      HTML Output

Special Modes:
- --diagrams-only: Skips RAG Chain entirely (no API calls, no costs)
- --dry-run: Creates RAG Chain but generates placeholder section content
```

### Key Components

**`src/docgen/core/generator.py`** - `CodeDocumentationGenerator`
- Main orchestrator class that coordinates the entire documentation pipeline
- Creates vector store from code analysis using ChromaDB
- Uses LCEL (LangChain Expression Language) RAG chain for content generation
- Supports both legacy API keys and provider instances for flexibility

**`src/docgen/core/analyzer.py`** - `CodeAnalyzer`
- Parses Python AST to extract classes, functions, imports
- Produces `FileAnalysis` and `CodeEntity` models

**`src/docgen/core/cross_reference.py`** - `CrossReferenceAnalyzer`
- Tracks component definitions and usage across the codebase
- Builds import/usage graphs for "where used" analysis
- Provides pre-analyzed data for Cross-Reference Documentation section

**`src/docgen/core/diagrams.py`** - `DiagramGenerator`
- Generates Mermaid diagrams: architecture, class, sequence, dependency, call graph
- Validates diagrams before output (configurable via `validate_diagrams` parameter)
- Supports custom validation configuration via `ValidationConfig`

**`src/docgen/providers/`** - Provider Abstraction Layer
- `base.py`: `LLMProvider` and `EmbeddingProvider` protocols
- `anthropic.py`: Claude implementation
- `openai.py`: GPT and embeddings implementations
- `registry.py`: Provider factory and registration

**`src/docgen/prompts/`** - Prompt Management
- `sections.py`: Defines documentation sections:
  - **5 core sections** (always generated): Overview, Dependencies, Key Classes, Data Flow, Integration Points
  - **3 optional sections** (require --sections flag): Migration Guidance, Code Quality Insights, Cross-Reference Documentation
- `templates.py`: `PromptTemplate` dataclass with few-shot examples for structured prompts

**`src/docgen/templates/`** - HTML Generation
- `html.py`: `TemplateManager` with Jinja2, supports file-based and embedded templates
- `files/`: HTML template files (base, index, section, diagrams, search, navigation)

### Models

- `CodeEntity`: Represents a class or function with metadata (name, type, docstring, line numbers)
- `FileAnalysis`: Contains all entities, imports, and content for a single file
- `ComponentReference`: Tracks where components are defined and used (for cross-reference analysis)
- `DiagramType`, `ValidationError`, `ValidationResult`, `ValidationConfig`: Diagram validation models

### Diagram Validation System

**`src/docgen/utils/diagram_validator.py`** - Core Validator
- `DiagramValidator`: Main validation orchestrator with auto-detection
- `BaseValidator`: Base class for type-specific validators
- Supports configurable validation modes: strict (default) or permissive

**`src/docgen/utils/diagram_validators.py`** - Type-Specific Validators
- 5 validators: Architecture, Class, Sequence, CallGraph, Dependency
- Each with specialized validation rules for their diagram type

**`src/docgen/utils/diagram_rules.py`** - Validation Rules (15+ rules)
- **Common rules** (all diagrams): syntax_header, quote_escaping, special_characters, node_id_format, empty_diagram
- **Graph rules** (architecture, call graph, dependency): graph_direction, node_definition, edge_syntax
- **Class rules**: class_declaration
- **Sequence rules**: participant_references

**Validation Configuration:**
```python
from docgen.models.diagram_validation import ValidationConfig
from docgen.core.diagrams import DiagramGenerator

# Strict mode (default): Errors fail validation
config = ValidationConfig(mode="strict")
generator = DiagramGenerator(validate_diagrams=True, validation_config=config)

# Permissive mode: Only critical errors fail
config = ValidationConfig(mode="permissive")

# Disable specific rules
config = ValidationConfig(disabled_rules={"empty_diagram"})

# Fail on warnings
config = ValidationConfig(fail_on_warnings=True)

# Disable validation entirely
generator = DiagramGenerator(validate_diagrams=False)
```

### Exception Hierarchy

All custom exceptions inherit from `DocumentationError`:
- `CodeParseError`, `DiagramGenerationError`, `ApiKeyError`, `VectorStoreError`, `FileEncodingError`, `TemplateError`, `LLMError`, `EmbeddingError`, `PathValidationError`
  - `DiagramValidationError` (inherits from `DiagramGenerationError`): Raised when diagram validation fails

## Testing Patterns

Tests are organized under `tests/unit/` and `tests/integration/`. Key patterns:

- Mock the RAG chain directly (returns strings after `StrOutputParser`), not individual LLM components
- `FileAnalysis` no longer validates file existence - it's a pure data model
- Use `_skip_validation=True` in tests when creating FileAnalysis instances
- Shared fixtures in `tests/conftest.py`: `sample_code_entity`, `mock_llm`, `mock_embeddings`, `temp_source_dir`
- Cross-reference tests use string list format for imports: `["helper.HelperClass"]`
- **Diagram validation**: Tests that generate diagrams use `DiagramGenerator(validate_diagrams=False)` to avoid validation issues with synthetic test data. For validation-specific tests, see `tests/unit/utils/test_diagram_validator.py` and `tests/integration/test_diagram_validation.py`

## API Keys

The generator requires both Anthropic and OpenAI API keys (except in `--dry-run` or `--diagrams-only` modes):
- Set via environment variables: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`
- Or via `--api-key-env .env` flag to load from a .env file

**Note:** Direct CLI arguments for API keys are not supported for security reasons.

**Note:** In `--diagrams-only` mode, no API keys are required and no LLM API calls are made.

## RAG Retrieval Configuration

The RAG retrieval process can be tuned via config parameters:

**Retrieval Strategies:**
- **Similarity Search** (default): Direct cosine similarity ranking
- **MMR (Maximal Marginal Relevance)**: Balances relevance with diversity to avoid redundant context

**Configuration Parameters:**
- `RETRIEVER_K`: Number of documents to retrieve (default: 10)
- `RETRIEVER_SEARCH_TYPE`: "similarity" or "mmr" (default: "similarity")
- `RETRIEVER_SCORE_THRESHOLD`: Minimum similarity score filter (optional)
- `RETRIEVER_FETCH_K`: Documents to fetch before MMR reranking (default: 20)
- `RETRIEVER_LAMBDA_MULT`: MMR diversity parameter, 0=max diversity, 1=max relevance (default: 0.5)

**When to Use MMR:**
- Large codebases with repetitive patterns
- When you want diverse examples rather than similar code
- To avoid context dominated by a single module

## Optional Documentation Sections

**Core Sections** (always generated):
1. Overview - System purpose, components, architecture
2. Dependencies - Core/optional deps, versions, integrations
3. Key Classes and Functions - Public APIs, usage examples
4. Data Flow - Processing pipeline, data structures
5. Integration Points - External systems, authentication

**Optional Sections** (require `--sections` flag):
1. **Migration Guidance** - Deprecated patterns, security issues, modern alternatives
2. **Code Quality Insights** - Architectural patterns, trade-offs, improvement suggestions
3. **Cross-Reference Documentation** - Where components are defined and used

**Usage:**
```bash
# Generate only specific sections
docgen --source ./src --sections "overview,dependencies,migration_guidance"

# Generate all sections
docgen --source ./src --sections "overview,dependencies,classes,dataflow,integration,migration_guidance,code_quality,cross_reference"
```

**Special Handling:**
- Cross-reference section receives pre-analyzed import/usage data from `CrossReferenceAnalyzer`
- Optional sections use different cache dependencies (see `cache/content_cache.py`)
- Migration and quality sections require full code context ("all" dependency)

## Using Context7 for Library Documentation

**IMPORTANT:** Always use Context7 MCP tools automatically when:
- Generating code using libraries or frameworks
- Providing setup or configuration steps
- Looking up library/API documentation

**Workflow:**
1. Use `resolve-library-id` to find the correct library
2. Use `query-docs` to get up-to-date documentation
3. Provide answers based on official docs, not training data

**Do NOT guess or rely on training data** for library-specific implementation details. Always query Context7 first.

## Code Style

- Type hints required for all function signatures
- Google-style docstrings
- PEP 8 with Ruff formatting (88 char line length)
- Dataclasses for models with `__post_init__` validation
- Enforced by pre-commit hooks: ruff (lint), ruff-format, ty (type check)

## Pre-Commit Workflow

**IMPORTANT:** Always follow this workflow for every change:

### Step 1: Run Code Simplifier

```bash
# Use the code-simplifier plugin to review and simplify changes
# This ensures code remains clean and maintainable
```

The code simplifier will:
- Reduce complexity in methods
- Simplify conditional logic
- Remove redundant code
- Improve naming and readability
- Consolidate duplicate patterns

### Step 2: Commit Changes (Hooks Run Automatically)

```bash
git add .
git commit -m "descriptive message"
```

**Pre-commit hooks run automatically** and check:
- ✅ **ruff check --fix**: Lint and auto-fix issues
- ✅ **ruff format**: Format code consistently
- ⚠️ **ty check**: Type check (non-blocking, shows warnings)

If hooks fail, fix the issues and commit again.

### Step 3: Run Tests Before Pushing

**DO NOT SKIP THIS STEP!** Tests are not in pre-commit hooks for performance, but are **required** before pushing.

```bash
# Run all tests with coverage
uv run pytest tests/ -v

# Or run separately:
uv run pytest tests/unit/ -v        # Unit tests (fast, ~0.8s)
uv run pytest tests/integration/ -v # Integration tests (slower)
```

**Verify:**
- ✅ All 394 unit tests pass
- ✅ All 35 integration tests pass
- ✅ Code coverage remains at 75%+

### Step 4: Push When Tests Pass

```bash
git push
```

### Why Tests Are Not in Pre-Commit Hooks

**Decision:** Tests run **manually** before push, not automatically on commit.

**Rationale:**
- Pre-commit hooks are for **fast checks** (lint, format, type) - complete in 0.25s
- Tests take longer (~1-2s for unit, more for integration)
- Allows rapid iteration during development
- You still run tests, just before push instead of commit
- CI/CD provides additional verification

**Rule of thumb:** Pre-commit = fast quality checks, Manual = comprehensive tests

### Pre-Commit Hooks Setup

First-time setup:
```bash
# Install pre-commit hook manager
uv sync  # Installs pre-commit from dev dependencies

# Install git hooks
pre-commit install

# (Optional) Run on all files to verify setup
pre-commit run --all-files
```

**Note:** Pre-commit hooks will run automatically on `git commit`. If hooks fail, the commit is aborted and you can fix the issues and try again.

This practice ensures:
- Code quality is maintained automatically
- No regressions are introduced
- The codebase stays clean and consistent
- Linting, formatting, and type checking happen before commits

## Documentation Maintenance

When making changes to the codebase, keep these files in sync:

| File | Update When |
|------|-------------|
| `docs/` | Changing architecture, adding modules/exceptions, or changing feature behavior |
| `README.md` | Changing installation, CLI usage, or requirements |
| `CLAUDE.md` | Changing commands, architecture patterns, or testing approaches |

## Claude Code Workflow Optimizations

Guidance for using Claude Code sub-agents and library documentation lookup in this project.

### Sub-agent Usage Guidelines

**IMPORTANT:** Claude should proactively use sub-agents for this project. Do NOT manually search with Grep/Glob for open-ended questions.

#### Explore Agent (ALWAYS use for understanding code)
**Trigger automatically when user asks:**
- "How does X work?"
- "Where is Y used?"
- "What calls Z?"
- "Explain the flow of..."
- Any architecture or design question

```python
# Use Task tool with subagent_type="Explore"
# Example: "How does the RAG chain work?"
# → Launch Explore agent, NOT manual Grep/Glob
```

#### Plan Agent (ALWAYS use for complex changes)
**Trigger automatically when task involves:**
- Adding new diagram types
- Adding new documentation sections
- Modifying the generator pipeline
- Changes touching 3+ files
- Any architectural decision

```python
# Use EnterPlanMode tool
# Example: "Add support for flowchart diagrams"
# → Enter plan mode to design approach first
```

#### Code Review Agent (ALWAYS use before commits)
**Trigger automatically:**
- After completing any feature implementation
- Before creating commits with significant changes
- When user says "review", "check", or "ready to commit"

```python
# Use Task tool with subagent_type="pr-review-toolkit:code-reviewer"
# Focus on: type hints, docstrings, exception handling, test coverage
```

#### Direct Search (only for specific lookups)
**Use Grep/Glob directly ONLY when:**
- Looking for exact class/function name: `class DiagramGenerator`
- Finding specific file: `**/diagrams.py`
- Searching known string: `"MERMAID_RESERVED_WORDS"`

**Do NOT use Grep/Glob for:**
- Understanding how something works
- Finding where something is used broadly
- Architectural questions

### Context7 Integration

Always use Context7 MCP tools when working with external libraries:

1. **LangChain/LCEL**: Query for chain composition patterns
2. **Mermaid**: Query for diagram syntax and features
3. **Jinja2**: Query for template syntax and filters
4. **ChromaDB**: Query for vector store operations

```
# Example: Before modifying RAG chain
1. resolve-library-id for "langchain"
2. query-docs for "LCEL chain composition"
3. Implement based on official docs
```

### Recommended Workflow

1. **Start feature**: Use the Explore sub-agent to understand relevant code
2. **Plan changes**: Use Plan agent for complex features
3. **Implement**: Run ruff and the relevant tests as you go
4. **Review**: Run a code review sub-agent before committing
5. **Test**: Run full test suite before pushing
6. **Document**: Update CLAUDE.md if architecture changes
