# CLAUDE.md

Guidance for AI coding agents working in this repository. Human contributors can start with
[CONTRIBUTING.md](CONTRIBUTING.md); the two agree.

## Project

codeatlas generates an HTML documentation site for a Python codebase: Mermaid diagrams built
from the AST, and narrative sections written by Claude over code retrieved from a Chroma
vector store (RAG). The package is `docgen` (`src/docgen`); the command is `codeatlas`, with
`docgen` kept as an alias.

## Commands

```bash
uv sync                                  # install, including dev tools
uv run pre-commit install                # file checks, ruff, and ty on commit

# The checks CI runs (.github/workflows/test.yml): lint once, tests on 3.10 to 3.13
uv sync --locked
uv run ruff check src tests
uv run ruff format --check src tests
uv run ty check                              # type check of src and tests
uv run pytest tests --cov-fail-under=87      # CI's coverage minimum, counting branches
# CI's lowest-deps job also runs the tests with the oldest allowed dependencies;
# see CONTRIBUTING.md before running it, since it rewrites uv.lock

uv run pytest tests/unit/core/test_generator.py::test_initialization   # one test
uv run pytest -k analyzer                                              # by name

# Free runs: no API keys, no network
uv run codeatlas --source . --diagrams-only -o <dir>
uv run codeatlas --source . --dry-run -o <dir>         # placeholder sections

# Paid run: needs ANTHROPIC_API_KEY and OPENAI_API_KEY
uv run codeatlas --source <path> --api-key-env .env -o <dir>
```

## Architecture

`cli.py` calls `CodeDocumentationGenerator.generate_documentation()`, which runs five stages:

| Stage | Module | What it does |
|---|---|---|
| Analyze | `core/analyzer.py` | Parses each file's AST into classes, functions, imports, and calls |
| Diagram | `core/diagrams.py`, `utils/diagram_*.py` | Builds five Mermaid diagram types, then validates them |
| Index | `core/rag_pipeline.py`, `cache/vector_cache.py` | Chunks and embeds the code (OpenAI), stores it in Chroma |
| Write | `core/section_orchestrator.py`, `prompts/` | One Claude call per section, in parallel threads |
| Render | `core/renderer.py`, `templates/` | Markdown to HTML, sanitized with nh3, rendered with Jinja2 |

Other places to know:

- `core/generator.py`: `CodeDocumentationGenerator` runs the pipeline. It takes an LLM and an
  embedding provider (optional in diagrams-only and dry-run modes) plus `GenerationOptions`,
  `CacheConfig`, and `GeneratorConfig`.
- `config.py`: defaults, and `QUALITY_MODE_MODELS` (`fast`, `balanced`, `best` to Claude
  model IDs). `create_default_providers()` in `providers/registry.py` picks the model:
  `--anthropic-model`, then the quality mode, then the default.
- `providers/`: `LLMProvider` and `EmbeddingProvider` protocols in `base.py`, the Anthropic and
  OpenAI implementations, and `registry.py`.
- `prompts/sections.py`: five core sections, plus Migration Guidance, Code Quality Insights,
  and Cross-Reference Documentation, which run only when named in `--sections`.
- `cache/`: level 1 caches embeddings per file; level 2 (`content_cache.py`) caches sections,
  keyed on their code dependencies, the model, and the exact prompt.
- `utils/`: diagram validation (`diagram_validator.py`, `diagram_validators.py`,
  `diagram_rules.py`), cost (`cost_tracker.py` holds the prices), token usage
  (`usage_tracking.py`), API keys, logging.
- `exceptions/errors.py`: every custom exception inherits from `DocumentationError`.

`--diagrams-only` stops after the diagram stage. `--dry-run` skips the index and write stages.
Design decisions, caching, measured cost, and failure behavior are in
[docs/architecture.md](docs/architecture.md).

## Gotchas

- `.env` in the repo root may hold real API keys. Never read or print it; pass it with
  `--api-key-env .env`.
- `pytest` addopts already include `-q` and a coverage report. Adding another `-q` hides the
  "N passed" summary.
- The section cache key does not include the output token limit, the RAG wrapper template, or
  the `--retriever-*` settings. After changing those, run once with `--force-refresh`.
- In a git repository, change detection only sees committed changes.
- `langchain-anthropic` retries twice on its own; the stop reason is in
  `message.response_metadata`.

## Rules

These are shared with Cursor: one copy in `.cursor/rules/`, imported here.

@.cursor/rules/python.mdc
@.cursor/rules/tests.mdc
@.cursor/rules/verify.mdc
