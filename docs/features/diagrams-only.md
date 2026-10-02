# Diagrams-Only Feature Implementation

## Overview

Added a `--diagrams-only` flag to the codeatlas CLI that allows users to generate **only architectural diagrams** without any LLM API calls, resulting in **zero API costs**.

## Implementation Summary

### Changes Made

#### 1. Core Generator (`src/docgen/core/generator.py`)
- Added `diagrams_only` parameter to `__init__` method
- Modified initialization to make API keys optional when `diagrams_only=True`
- Added logic to skip section generation in `generate_documentation()` when in diagrams-only mode
- Disabled caching and cost tracking in diagrams-only mode

**Key Changes:**
```python
# API keys not required in diagrams-only mode
if diagrams_only:
    logger.info("Diagrams-only mode: API keys not required")
    self.llm = None
    self.embeddings = None

# Skip section generation in diagrams-only mode
if self.diagrams_only:
    logger.info("Diagrams-only mode: skipping LLM calls and section generation")
    documentation = {
        'title': 'Code Documentation (Diagrams Only)',
        'generated_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'sections': []  # No sections in diagrams-only mode
    }
```

#### 2. CLI (`src/docgen/cli.py`)
- Added `--diagrams-only` flag to argument parser
- Added validation to prevent using `--no-diagrams` and `--diagrams-only` together
- Modified API key handling to treat diagrams-only mode like dry-run (placeholder keys)
- Passed `diagrams_only` parameter to generator initialization

**CLI Additions:**
```bash
--diagrams-only       Generate only diagrams without LLM section generation (no API costs)
```

**Validation:**
```python
# Handle mutually exclusive no-diagrams/diagrams-only
if args.no_diagrams and args.diagrams_only:
    print("Error: --no-diagrams and --diagrams-only are mutually exclusive", file=sys.stderr)
    sys.exit(1)
```

#### 3. Tests (`tests/unit/test_cli.py`)
- Added `diagrams_only = False` to all existing test mocks (3 locations)
- Created new test: `test_diagrams_only_skips_api_keys()`
- Created new test: `test_no_diagrams_and_diagrams_only_are_mutually_exclusive()`

**Test Results:**
- All 196 unit tests passing (added 2 new tests)
- Code coverage: 75%

#### 4. Documentation (`README.md`)
- Added `--diagrams-only` to CLI options section
- Added usage examples in "Preview mode (no API costs)" section

## Usage Examples

### Basic Usage
```bash
# Generate only diagrams (no API costs, no LLM calls)
docgen --source ./my_project --diagrams-only
```

### With Specific Diagrams
```bash
# Generate only architecture and class diagrams
docgen --source ./my_project --diagrams-only --diagrams architecture,class
```

### Perfect for CI/CD
```bash
# Quick diagram generation in CI/CD pipelines (no API keys needed)
docgen --source ./src --diagrams-only -o ./docs/diagrams
```

## Benefits

1. **Zero API Costs**: No LLM API calls means no usage charges
2. **No API Keys Required**: Can be used in environments without API credentials
3. **Fast Execution**: Skips all LLM processing, only analyzes code and generates diagrams
4. **Ideal for Visualization**: Perfect for users who only need code structure visualizations
5. **CI/CD Friendly**: Can be integrated into build pipelines without API key management

## What Gets Generated

In diagrams-only mode, the tool generates:
- ✅ All architectural diagrams (architecture, class, sequence, callgraph, dependency)
- ✅ HTML page with interactive diagram viewer
- ✅ Code analysis (file structure, classes, functions, imports)
- ❌ No LLM-generated text sections (overview, dependencies, classes, dataflow, integration)
- ❌ No API costs

## Technical Details

### Mode Comparison

| Feature | Normal Mode | Dry-Run Mode | Diagrams-Only Mode |
|---------|-------------|--------------|-------------------|
| **API Keys** | Required | Not required | Not required |
| **Diagrams** | ✅ Generated | ✅ Generated | ✅ Generated |
| **Sections** | ✅ Generated | ⚠️ Placeholders | ❌ Skipped |
| **Vector Store** | ✅ Created | ❌ Skipped | ❌ Skipped |
| **Caching** | ✅ Enabled | ❌ Disabled | ❌ Disabled |
| **Cost Tracking** | ✅ Enabled | ❌ Disabled | ❌ Disabled |
| **API Costs** | $0.05 - $5.00 | $0.00 | $0.00 |

### Flag Compatibility

| Flag Combination | Result |
|------------------|--------|
| `--diagrams-only` | ✅ Valid - generates only diagrams |
| `--diagrams-only --diagrams architecture,class` | ✅ Valid - generates specific diagrams |
| `--diagrams-only --no-diagrams` | ❌ Error - mutually exclusive |
| `--dry-run --diagrams-only` | ⚠️ Both set - diagrams-only takes precedence |

## Files Modified

1. `src/docgen/core/generator.py` - Added diagrams_only support
2. `src/docgen/cli.py` - Added CLI flag and validation
3. `tests/unit/test_cli.py` - Added test coverage
4. `README.md` - Updated documentation

## Files Created

1. `DIAGRAMS_ONLY_FEATURE.md` - This implementation summary

## Testing

All tests passing:
```bash
# Run CLI tests
uv run pytest tests/unit/test_cli.py -v
# Result: 26 passed

# Run all unit tests
uv run pytest tests/unit/ -v
# Result: 196 passed, 75% coverage
```

## Future Enhancements

Potential improvements:
1. **Diagram Export**: Export diagrams as standalone SVG/PNG files
2. **Minimal Template**: Create a lighter HTML template for diagrams-only mode
3. **Batch Processing**: Generate diagrams for multiple projects in one run
4. **Diagram Comparison**: Compare diagrams across versions to visualize architectural changes
5. **Interactive Filters**: Add filtering options for large diagrams

## Backward Compatibility

✅ **Fully backward compatible**:
- Existing CLI usage works unchanged
- New flag is optional (defaults to `False`)
- No breaking changes to API
- All existing tests continue to pass
