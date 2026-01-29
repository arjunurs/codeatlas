# Cost Optimization Features

This document provides a quick guide to the cost optimization features in the Code Documentation Generator.

## Quick Start

**No configuration needed!** All cost optimization features are enabled by default.

```bash
# First run - generates documentation and creates cache
docgen --source ./my_project -o ./docs

# Second run - uses cache (much faster and cheaper)
docgen --source ./my_project -o ./docs
```

## Cost Savings

| Scenario | Before | After | Savings |
|----------|--------|-------|---------|
| First run | $5.00 | $5.00 | 0% |
| No changes | $5.00 | $0.00 | 100% |
| 5% changed | $5.00 | $0.20 | 96% |
| 50% changed | $5.00 | $2.60 | 48% |

## Features

### 1. Vector Store Caching (85-95% savings on embeddings)
Automatically caches embeddings and only regenerates them when files change.

### 2. Section Content Caching (60-80% savings on LLM calls)
Caches generated documentation sections and only regenerates when dependencies change.

### 3. Quality Modes (50-90% additional savings)
Choose between speed/cost and quality:

```bash
# Fast mode - cheapest (~$0.10 per run)
docgen --source ./src --quality-mode fast

# Balanced mode - good tradeoff (~$0.50 per run) [default]
docgen --source ./src --quality-mode balanced

# Best mode - highest quality (~$2.00 per run)
docgen --source ./src --quality-mode best
```

### 4. Parallel Generation (60% faster)
Generates multiple sections in parallel for faster completion.

```bash
# Disable if needed
docgen --source ./src --no-parallel
```

### 5. Cost Tracking
Automatically shows API usage and estimated costs at the end:

```
============================================================
  API Usage & Cost Summary
============================================================
Duration: 12.3s
Total Requests: 15
Cache Hit Rate: 66.7%
Estimated Cost: $0.0234
============================================================
```

## Cache Management

```bash
# Show cache statistics
docgen --source ./src --cache-stats

# Clear cache
docgen --source ./src --clear-cache

# Force refresh (ignore cache)
docgen --source ./src --force-refresh

# Disable caching
docgen --source ./src --no-cache

# Custom cache location
docgen --source ./src --cache-dir /tmp/my-cache
```

## CI/CD Usage

For CI/CD pipelines where you want fresh builds:

```bash
# Option 1: Disable caching
docgen --source ./src -o ./docs --no-cache

# Option 2: Force refresh
docgen --source ./src -o ./docs --force-refresh
```

## Development Workflow

For active development where code changes frequently:

```bash
# Default behavior - uses cache when possible
docgen --source ./src -o ./docs

# If something seems wrong, force refresh
docgen --source ./src -o ./docs --force-refresh
```

## Cost Optimization Tips

1. **Use cache by default** - Let the system automatically optimize costs
2. **Choose quality mode wisely** - Use "fast" for draft docs, "best" for releases
3. **Monitor costs** - Check the summary after each run
4. **Clean old caches** - Run `--clear-cache` periodically if disk space is limited

## Cache Location

Default: `.docgen_cache/<project_hash>/`

The cache includes:
- `chromadb/` - Vector store with embeddings
- `file_metadata.json` - File change tracking
- `section_cache.json` - Generated section content

Typical size: 1-5 MB per project

## Troubleshooting

**Problem**: Cache seems stale or incorrect
```bash
docgen --source ./src -o ./docs --force-refresh
```

**Problem**: Out of disk space
```bash
docgen --source ./src --clear-cache
```

**Problem**: Want to see what's cached
```bash
docgen --source ./src --cache-stats
```

**Problem**: Parallel generation causing issues
```bash
docgen --source ./src --no-parallel
```

## API Usage

You can also use these features programmatically:

```python
from docgen.core.generator import CodeDocumentationGenerator
from docgen.config import QualityMode

generator = CodeDocumentationGenerator(
    anthropic_api_key="your-key",
    openai_api_key="your-key",
    # Enable caching (default: True)
    cache_enabled=True,
    cache_dir="/path/to/cache",
    force_refresh=False,
    # Quality mode
    quality_mode=QualityMode.BALANCED,
    # Parallel generation (default: True)
    parallel_sections=True,
    # Cost tracking (default: True)
    enable_cost_tracking=True,
)

generator.generate_documentation("./src", "./docs")
```

## See Also

- [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - Full technical details
- [README.md](README.md) - General usage documentation
- [spec.md](spec.md) - Architecture specification
