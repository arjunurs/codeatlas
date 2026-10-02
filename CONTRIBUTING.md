# Contributing to codeatlas

Thank you for your interest in contributing! This guide will help you get started.

## Quick Start

### Prerequisites

- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) package manager
- Git

### Setup Development Environment

1. **Clone the repository**
   ```bash
   git clone https://github.com/arjunurs/codeatlas.git
   cd codeatlas
   ```

2. **Install dependencies**
   ```bash
   uv sync
   ```

3. **Install pre-commit hooks**
   ```bash
   uv run pre-commit install
   ```

4. **Verify setup**
   ```bash
   # Run tests
   uv run pytest tests/ -v

   # Run pre-commit checks
   uv run pre-commit run --all-files
   ```

## Development Workflow

### Making Changes

Follow this workflow for every contribution:

#### 1. Run Code Simplifier
Use the code-simplifier plugin to review and clean up your changes before committing.

#### 2. Commit Changes
```bash
git add .
git commit -m "descriptive message"
```

**Pre-commit hooks run automatically** and check:
- ✅ **ruff check --fix** - Lint and auto-fix issues
- ✅ **ruff format** - Format code consistently
- ⚠️ **ty check** - Type check (non-blocking, shows warnings)

If hooks fail, fix the issues and commit again.

#### 3. Run Tests Before Pushing

**REQUIRED:** Always run tests before pushing.

```bash
# Run all tests with coverage
uv run pytest tests/ -v

# Or run separately:
uv run pytest tests/unit/ -v        # Unit tests (fast, ~0.8s)
uv run pytest tests/integration/ -v # Integration tests (slower)
```

**Requirements:**
- ✅ All 196 unit tests must pass
- ✅ All 11 integration tests must pass
- ✅ Code coverage must remain at 75%+

#### 4. Push When Tests Pass
```bash
git push
```

### Why Tests Aren't in Pre-Commit

Tests run **manually** before push (not on every commit) to keep commits fast (0.25s) while maintaining quality. Pre-commit hooks focus on quick checks that complete instantly.

## Code Style

### Standards

- **Type hints** required for all function signatures
- **Google-style docstrings** for all public functions and classes
- **PEP 8** compliance with Ruff formatting (88 char line length)
- **Dataclasses** for data models with `__post_init__` validation

### Enforced by Pre-Commit Hooks

- **Ruff** (lint) - Checks code quality, imports, naming conventions
- **Ruff Format** - Formats code consistently
- **Ty** (type check) - Validates type annotations (non-blocking)

### Manual Commands

```bash
# Lint and auto-fix
uv run ruff check src/ tests/ --fix

# Format code
uv run ruff format src/ tests/

# Type check
uv run ty check

# Run all pre-commit hooks manually
uv run pre-commit run --all-files
```

## Testing

### Test Structure

```
tests/
├── unit/              # Unit tests (fast, isolated)
│   ├── core/          # Core functionality tests
│   ├── models/        # Data model tests
│   ├── providers/     # Provider tests
│   └── utils/         # Utility tests
└── integration/       # Integration tests (slower, end-to-end)
```

### Running Tests

```bash
# All tests with coverage
uv run pytest tests/ -v

# Specific test file
uv run pytest tests/unit/core/test_generator.py -v

# Specific test
uv run pytest tests/unit/core/test_generator.py::test_generate_documentation_success -v

# Tests matching pattern
uv run pytest -k "test_analyzer" -v

# With coverage report
uv run pytest tests/ -v --cov=docgen --cov-report=term-missing
```

### Writing Tests

- **Unit tests**: Mock external dependencies, test individual functions/classes
- **Integration tests**: Test complete workflows end-to-end
- **Fixtures**: Use shared fixtures from `tests/conftest.py`
- **Naming**: Use descriptive names (`test_<function>_<scenario>`)
- **Coverage**: Aim to maintain or improve the 75% coverage threshold

## Pull Request Process

### Before Creating a PR

1. ✅ Run code simplifier
2. ✅ All pre-commit hooks pass
3. ✅ All tests pass (196 unit + 11 integration)
4. ✅ Code coverage at 75%+
5. ✅ Documentation updated if needed

### PR Guidelines

- **Title**: Clear, descriptive summary (e.g., "Add caching support for vector store")
- **Description**: Explain what, why, and how
  - What problem does this solve?
  - What approach did you take?
  - Any breaking changes?
- **Small PRs**: Keep changes focused and reviewable
- **Documentation**: Update README.md or docs/ if adding features
- **Tests**: Include tests for new functionality

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] All tests pass locally

## Checklist
- [ ] Code follows style guidelines
- [ ] Pre-commit hooks pass
- [ ] Documentation updated
- [ ] Tests provide adequate coverage
```

## Project Structure

```
codeatlas/
├── src/docgen/              # Main package
│   ├── core/                # Core functionality
│   │   ├── analyzer.py      # Code analysis
│   │   ├── diagrams.py      # Diagram generation
│   │   └── generator.py     # Main orchestrator
│   ├── models/              # Data models
│   ├── providers/           # LLM provider abstractions
│   ├── prompts/             # Prompt management
│   ├── templates/           # HTML templates
│   ├── utils/               # Utilities
│   └── cache/               # Caching system
├── tests/                   # Test suite
├── docs/                    # Documentation
│   ├── features/            # Feature docs
│   ├── design/              # Design decisions
│   └── development/         # Developer guides
└── pyproject.toml           # Project configuration
```

## Documentation

### When to Update Documentation

| File | Update When |
|------|-------------|
| `README.md` | Changing installation, CLI usage, or features |
| `docs/features/` | Adding or modifying features |
| `docs/design/` | Making architectural decisions |
| `docs/development/` | Changing development processes |

### Documentation Style

- Use **clear, concise language**
- Include **code examples** for features
- Add **usage examples** for new CLI options
- Use **tables** for structured information
- Include **diagrams** for complex concepts

## Common Development Tasks

### Adding a New CLI Option

1. Add argument to `src/docgen/cli.py` in `parse_args()`
2. Pass parameter to `CodeDocumentationGenerator`
3. Implement functionality in generator
4. Add tests in `tests/unit/test_cli.py`
5. Update `README.md` with new option

### Adding a New LLM Provider

1. Create provider class in `src/docgen/providers/`
2. Implement `LLMProvider` or `EmbeddingProvider` protocol
3. Register in `src/docgen/providers/registry.py`
4. Add tests in `tests/unit/providers/`
5. Update documentation

### Adding a New Diagram Type

1. Add method to `DiagramGenerator` in `src/docgen/core/diagrams.py`
2. Add tests in `tests/unit/core/test_diagrams.py`
3. Update CLI to support new diagram type
4. Document in `README.md`

## Getting Help

- **Issues**: Check [GitHub Issues](https://github.com/arjunurs/codeatlas/issues)
- **Discussions**: Start a discussion for questions
- **Documentation**: See [docs/](docs/) for detailed guides

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on the code, not the person
- Help create a welcoming environment

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

## Additional Resources

- [Pre-Commit Hooks Setup Guide](docs/development/pre-commit.md)
- [Cost Optimization Design](docs/design/cost-optimization.md)
- [Diagrams-Only Feature](docs/features/diagrams-only.md)
- [Implementation Notes](docs/development/implementation.md)
