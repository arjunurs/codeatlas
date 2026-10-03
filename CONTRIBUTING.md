# Contributing to codeatlas

## Setup

You need Python 3.10 or newer, [uv](https://docs.astral.sh/uv/), and Git.

```bash
git clone https://github.com/arjunurs/codeatlas.git
cd codeatlas
uv sync
uv run pre-commit install
```

No API keys are needed for development: the tests replace the APIs with fakes and mocks, and
`uv run codeatlas --source . --diagrams-only` exercises the analysis and diagram pipeline
without network calls.

## Checks

CI runs these four commands on Python 3.10 to 3.13. Run them before pushing:

```bash
uv sync --locked
uv run ruff check src tests
uv run ruff format --check src tests
uv run pytest tests
```

`pytest` prints a coverage report on every run. There is no enforced threshold yet; do not lower
coverage with a change.

### Pre-commit hooks

`.pre-commit-config.yaml` runs these on staged files:

- **ruff-check** (with `--fix`): lint rules `E`, `F`, `I`, `N`, `W`, `UP` from `pyproject.toml`
- **ruff-format**: formatting
- **ty**: type check of `src/`; non-blocking, it reports but never fails a commit

The hook's ruff `rev` must match the ruff version in `uv.lock`, which CI uses through
`uv run`. A mismatch lets a commit fail locally on code that CI accepts, or the reverse. After
upgrading ruff, update the `rev` and run `uv run pre-commit run --all-files`.

Tests are not a hook, to keep commits fast. Run them yourself before pushing.

## Code style

- Type hints on all function signatures
- Google-style docstrings for public functions and classes
- Ruff formatting, 88-character lines
- Dataclasses for data models, with validation in `__post_init__`

## Tests

```
tests/
├── conftest.py        # shared fixtures, including fake LangChain chat and embedding models
├── unit/              # fast and isolated: cache, core, models, prompts, providers,
│                      # templates, utils, plus test_cli.py and test_config.py
└── integration/       # full generator runs with a real Chroma store and fake models
```

```bash
uv run pytest tests/unit/core/test_generator.py          # one file
uv run pytest tests/unit/core/test_generator.py::test_initialization  # one test
uv run pytest -k analyzer                                # by name
```

Guidelines:

- Write a failing test first for a bug, then fix it.
- For behavior that passes through a LangChain chain (callbacks, usage, stop reasons), use the
  `fake_chat_model_with_usage` and `fake_embeddings` fixtures: they are real LangChain models
  that need no network. Use `MagicMock` only where the chain itself is not under test.
- Tests that generate diagrams from synthetic data can use
  `DiagramGenerator(validate_diagrams=False)`; validation has its own tests.
- Name tests after the behavior they check, for example
  `test_unknown_section_rejected_at_construction`.

## Pull requests

- Keep each change focused, with a plain description of what changed and why.
- Include tests for new behavior and for fixed bugs.
- Update the docs in the same change when behavior or flags change:

| File | Update when |
|---|---|
| `README.md` | Installation, CLI usage, or user-visible features change |
| `docs/architecture.md` | The pipeline, caching, providers, or failure behavior change |
| `docs/design/` | Proposing a significant design change |
| `CONTRIBUTING.md` | The development workflow or tooling changes |

## Common changes

### A new CLI option

1. Add the argument in `parse_args()` in `src/docgen/cli.py` and pass it to
   `CodeDocumentationGenerator`.
2. Implement it in the generator or the component it affects.
3. Add tests in `tests/unit/test_cli.py` and for the behavior itself.
4. If users will reach for it, add it to the options table in `README.md`.

### A new LLM or embedding provider

1. Subclass `BaseLLMProvider` or `BaseEmbeddingProvider` in `src/docgen/providers/base.py`
   and implement `_create_llm()` or `_create_embeddings()`.
2. Register it in `src/docgen/providers/registry.py`.
3. Add tests in `tests/unit/providers/`.

The CLI always uses Anthropic and OpenAI. Another provider is used through the Python API, by
passing provider instances to `CodeDocumentationGenerator.create(llm_provider=...,
embedding_provider=...)`.

### A new diagram type

1. Add a value to `DiagramType` in `src/docgen/models/diagram_validation.py`. This also makes
   it a valid `--diagrams` name.
2. Add a `generate_*` method to `DiagramGenerator` in `src/docgen/core/diagrams.py` that
   validates its output, and register a validator for the type in `DiagramValidator`
   (`src/docgen/utils/diagram_validator.py`).
3. Call it from `_generate_all_diagrams()` in `src/docgen/core/generator.py`.
4. Add the page to `diagram_files` in `src/docgen/core/renderer.py` and a link in
   `src/docgen/templates/files/navigation.html`.
5. Add tests in `tests/unit/core/test_diagrams.py`, and check that the diagram renders in a
   browser.

## Project layout

```
src/docgen/
├── cli.py            # argument parsing and the codeatlas command
├── config.py         # GeneratorConfig defaults, quality modes
├── core/             # analyzer, diagrams, generator, RAG pipeline, sections, renderer
├── cache/            # vector store and section caches
├── providers/        # Anthropic and OpenAI providers, registry
├── prompts/          # section prompts and selection
├── templates/        # Jinja2 HTML templates
└── utils/            # logging, API keys, cost tracking, diagram validation
```

See [docs/architecture.md](docs/architecture.md) for how the pieces fit together.

## Questions and license

Open a [GitHub issue](https://github.com/arjunurs/codeatlas/issues) for bugs and questions.
By contributing, you agree that your contributions are licensed under the MIT License.
