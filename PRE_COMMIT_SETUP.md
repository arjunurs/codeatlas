# Pre-Commit Hooks Setup Guide

## Overview

This project uses **pre-commit hooks** to automatically enforce code quality standards before each commit. The hooks run:

1. **ruff check --fix** - Lint Python code and auto-fix issues
2. **ruff format** - Format Python code consistently
3. **ty check** - Type check Python code

## Why Pre-Commit Hooks?

- **Automatic Quality**: Quality checks run before every commit
- **Fast Feedback**: Catch issues immediately, not in CI/CD
- **Consistent Style**: Everyone uses the same formatting and linting
- **Zero Configuration**: Once installed, runs automatically

## Tool Selection

### Ruff (Linting + Formatting)

- **Replaces**: black, flake8, isort, pylint
- **Speed**: 10-100x faster than traditional tools (written in Rust)
- **Official Hook**: Full pre-commit support
- **Auto-fix**: Fixes most issues automatically

### Ty (Type Checking)

- **Replaces**: mypy
- **Speed**: 100x faster than mypy (written in Rust, from Astral)
- **Pre-commit Status**: No official hook yet (issue #269)
- **Workaround**: Using manual local hook via `uv run ty check`
- **Configuration**: Non-blocking (warning-only) - shows issues but doesn't fail commits
  - Ty is in early development (v0.0.14) with some false positives
  - Still provides valuable type checking feedback
  - Can be made blocking later when it matures

## Installation

### First-Time Setup

```bash
# 1. Install dependencies (includes pre-commit)
uv sync

# 2. Install git hooks
pre-commit install

# 3. (Optional) Test on all files
pre-commit run --all-files
```

### What Gets Installed

The `pre-commit install` command creates a git hook at `.git/hooks/pre-commit` that:
- Runs automatically on `git commit`
- Checks only staged files
- Blocks commit if checks fail
- Shows clear error messages

## Usage

### Automatic (Recommended)

```bash
# Pre-commit hooks run automatically when you commit
git add .
git commit -m "your message"

# If hooks fail:
# 1. Fix reported issues
# 2. Stage fixes: git add .
# 3. Try commit again
```

### Manual

```bash
# Run on all files (useful for testing)
pre-commit run --all-files

# Run on specific files
pre-commit run --files src/docgen/cli.py

# Run specific hook only
pre-commit run ruff --all-files
pre-commit run ty-check --all-files

# Skip hooks (not recommended)
git commit --no-verify -m "message"
```

## Configuration

### `.pre-commit-config.yaml`

```yaml
repos:
  # Ruff linting and formatting (official hooks)
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.4
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  # Ty type checking (manual local hook, non-blocking)
  - repo: local
    hooks:
      - id: ty-check
        name: ty type check (non-blocking)
        entry: bash -c 'uv run ty check || true'
        language: system
        types: [python]
        pass_filenames: false
        verbose: true
        files: ^src/
```

### `pyproject.toml` (Ruff Configuration)

```toml
[tool.ruff]
line-length = 88
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]
ignore = []
```

## Updating Hooks

```bash
# Update to latest versions
pre-commit autoupdate

# This updates rev: v0.8.4 to latest ruff version
```

## Troubleshooting

### Hook Fails on Commit

**Problem**: Pre-commit hook fails and blocks commit

**Solution**:
1. Read the error message (shows which file and line)
2. Fix the issue manually
3. Stage fixes: `git add .`
4. Commit again

### Ruff Auto-Fix Changes Files

**Problem**: Ruff modifies files during pre-commit

**Solution**: This is normal! Ruff auto-fixes issues.
1. Review the changes: `git diff`
2. If changes look good: `git add .`
3. Commit again

### Ty Hook Fails

**Problem**: Type errors found by ty

**Solution**:
1. Review error message for specific type issues
2. Fix type annotations or logic
3. Run `uv run ty check` to verify fix
4. Stage and commit again

### Skip Hooks (Emergency Only)

```bash
# Skip all hooks (NOT recommended)
git commit --no-verify -m "emergency fix"

# Better: Fix issues properly or ask for help
```

### Uninstall Hooks

```bash
# Remove git hooks (but keep config)
pre-commit uninstall

# Re-enable later
pre-commit install
```

## Comparison: Old vs New Workflow

### Old Workflow (Manual)

```bash
# Developer had to remember to run:
uv run black src/ tests/     # Format
uv run ruff src/             # Lint
uv run mypy src/             # Type check
uv run pytest tests/ -v      # Test

# Then commit
git commit -m "message"

# Problems:
# - Easy to forget
# - Inconsistent (not everyone runs all checks)
# - Slow (black + mypy are slow)
# - Found issues late (after commit)
```

### New Workflow (Automated)

```bash
# Just commit - hooks run automatically
git commit -m "message"

# Pre-commit automatically runs:
# 1. ruff check --fix (lint + auto-fix)
# 2. ruff format (format)
# 3. ty check (type check)

# Benefits:
# - Automatic (never forget)
# - Consistent (everyone gets same checks)
# - Fast (ruff + ty are 10-100x faster)
# - Early feedback (before commit finishes)

# Still need to run tests manually:
uv run pytest tests/ -v
```

## Performance Comparison

| Tool | Old | New | Speedup |
|------|-----|-----|---------|
| **Format** | black (~2s) | ruff-format (~0.1s) | 20x faster |
| **Lint** | flake8 (~1s) | ruff (~0.05s) | 20x faster |
| **Type Check** | mypy (~10s) | ty (~0.1s) | 100x faster |
| **Total** | ~13s | ~0.25s | **52x faster** |

## Integration with Development Workflow

### Complete Pre-Commit Workflow

1. **Write Code** - Make your changes
2. **Run Code Simplifier** - Use code-simplifier plugin to clean up
3. **Stage Changes** - `git add .`
4. **Commit** - `git commit -m "message"`
   - Pre-commit hooks run automatically
   - If hooks fail, fix issues and try again
5. **Run Tests** - `uv run pytest tests/ -v`
6. **Verify** - All 196 unit tests pass, 75%+ coverage
7. **Push** - `git push`

### CI/CD Integration

Pre-commit hooks run locally, but CI/CD should verify:

```yaml
# .github/workflows/test.yml example
- name: Run pre-commit hooks
  run: pre-commit run --all-files

- name: Run tests
  run: uv run pytest tests/ -v
```

## Migration Notes

### Removed Tools

- ❌ **black** - Replaced by `ruff format`
- ❌ **mypy** - Replaced by `ty`
- ✅ **ruff** - Enhanced with `ruff format`

### Updated Commands

| Old Command | New Command |
|-------------|-------------|
| `uv run black src/` | `uv run ruff format src/` |
| `uv run mypy src/` | `uv run ty check` |
| `uv run ruff src/` | `uv run ruff check src/ --fix` |

### Dependencies

**Removed from `pyproject.toml`**:
```toml
# [dependency-groups] dev
"black>=23.0.0"  # Removed
"mypy>=1.0.0"    # Removed
```

**Added to `pyproject.toml`**:
```toml
# [dependency-groups] dev
"ty>=0.1.0"          # New: Fast type checker
"pre-commit>=3.0.0"  # New: Hook manager
```

## Future Enhancements

### When Ty Gets Official Pre-Commit Hook

Once [astral-sh/ruff-pre-commit#269](https://github.com/astral-sh/ruff-pre-commit/issues/269) is resolved:

```yaml
# Future: Replace manual hook with official hook
- repo: https://github.com/astral-sh/ty-pre-commit
  rev: v0.x.x  # Future version
  hooks:
    - id: ty
```

### Additional Hooks to Consider

```yaml
# Optional: Additional quality hooks
- repo: https://github.com/pre-commit/pre-commit-hooks
  rev: v4.5.0
  hooks:
    - id: check-yaml
    - id: check-toml
    - id: check-merge-conflict
    - id: trailing-whitespace
    - id: end-of-file-fixer
```

## Resources

- **Pre-commit Framework**: https://pre-commit.com/
- **Ruff Documentation**: https://docs.astral.sh/ruff/
- **Ty Documentation**: https://docs.astral.sh/ty/
- **Ruff Pre-commit**: https://github.com/astral-sh/ruff-pre-commit
- **Ty Pre-commit Issue**: https://github.com/astral-sh/ruff-pre-commit/issues/269

## Why Tests Are Not in Pre-Commit Hooks

**Decision:** Tests run **manually** before push, not automatically on commit.

**Rationale:**

1. **Performance:** Pre-commit hooks should be fast (< 10 seconds rule)
   - Current hooks: 0.25s ✅
   - With tests: 1-2s (unit) + more (integration)

2. **Workflow:** Allows rapid iteration during development
   - Commit frequently without waiting for tests
   - Run tests when ready to push

3. **Flexibility:** Tests can be slow or require setup
   - Integration tests may need external resources
   - Not every commit needs to pass tests (work-in-progress)

4. **Best Practice:** Industry standard approach
   - Pre-commit = fast quality checks (lint, format, type)
   - Manual/CI = comprehensive testing

**Recommended Workflow:**
```bash
# 1. Commit (hooks run automatically - 0.25s)
git commit -m "message"

# 2. Test before pushing
uv run pytest tests/ -v

# 3. Push when tests pass
git push
```

**Alternative:** You can add tests to pre-push hooks instead:
```bash
# Tests run on push, not commit (slower, but thorough)
uv run pre-commit install --hook-type pre-push
```

## Questions?

- **"Why not use mypy?"** - Ty is 100x faster and from the same team that made ruff/uv
- **"Why not use black?"** - Ruff format is 20x faster and compatible with black
- **"Why no tests in pre-commit?"** - Keep commits fast (0.25s), run tests before push manually
- **"Can I skip hooks?"** - Yes with `--no-verify`, but strongly discouraged
- **"Do hooks run on CI?"** - Optional, but recommended for consistent enforcement
- **"Are hooks required?"** - Highly recommended. They catch issues immediately.

## Summary

✅ **Benefits of Pre-Commit Hooks:**
- Automatic code quality enforcement
- 52x faster than old tooling
- Consistent across team
- Early feedback (before commit)
- Zero ongoing mental overhead

✅ **Setup is Easy:**
1. `uv sync` - Install dependencies
2. `pre-commit install` - Enable hooks
3. `git commit` - Hooks run automatically

✅ **Minimal Disruption:**
- Hooks fix most issues automatically
- Only blocks commit on real problems
- Clear error messages guide fixes
