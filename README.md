# Code Documentation Generator

A powerful tool for automatically generating comprehensive documentation for Python codebases using Large Language Models (LLMs). It analyzes code structure, relationships, and patterns to create rich, interactive documentation with architectural diagrams.

## Features

- Automatic code analysis and documentation generation
- Interactive system architecture diagrams
- Package dependency visualization
- Function call graphs
- Class diagrams with inheritance relationships
- Sequence diagrams showing component interactions
- Rich HTML output with interactive features
- Comprehensive API documentation
- Integration with both Anthropic and OpenAI LLMs

## Installation

Using [uv](https://docs.astral.sh/uv/) (recommended):

```bash
git clone https://github.com/yourusername/CodeDocumentationGenerator.git
cd CodeDocumentationGenerator
uv sync
```

Or install with pip:

```bash
pip install git+https://github.com/yourusername/CodeDocumentationGenerator.git
```

## Requirements

- Python 3.10 or higher
- Anthropic API key (for Claude Sonnet 4)
- OpenAI API key (for embeddings)

## Usage

### 1. Set up your API keys

```bash
# Using environment variables (recommended)
export ANTHROPIC_API_KEY=your-key-here
export OPENAI_API_KEY=your-key-here

# Or create a .env file
echo "ANTHROPIC_API_KEY=your-key-here" > .env
echo "OPENAI_API_KEY=your-key-here" >> .env
```

### 2. Generate documentation

```bash
# Basic usage (API keys from environment)
docgen --source ./my_project -o ./docs

# With .env file for API keys
docgen --source ./my_project --api-key-env ./.env

# With verbose logging
docgen --source ./my_project -o ./docs -v
```

### 3. View the generated documentation

Open `docs/index.html` in your browser.

## CLI Options

```
usage: docgen [-h] [--version] --source SOURCE [-o OUTPUT]
              [--api-key-env PATH] [--temperature TEMP]
              [--anthropic-model MODEL] [--openai-embedding-model MODEL]
              [-v] [-q] [--exclude PATTERN] [--no-diagrams]
              [--sections LIST] [--diagrams LIST] [--template-dir PATH]
              [--dry-run] [--max-files N]

Generate comprehensive documentation for Python codebases

options:
  -h, --help            show this help message and exit
  --version, -V         show program's version number and exit
  --source SOURCE       Source directory containing Python files
  -o, --output OUTPUT   Output directory (default: docs)

API Keys:
  --api-key-env PATH    Path to .env file containing API keys
                        (Or set ANTHROPIC_API_KEY and OPENAI_API_KEY env vars)

Model Options:
  --temperature TEMP    LLM temperature 0.0-1.0 (default: 0.2)
  --anthropic-model     Anthropic model (default: claude-sonnet-4-20250514)
  --openai-embedding-model  Embedding model (default: text-embedding-3-small)

Output Options:
  -v, --verbose         Enable verbose logging
  -q, --quiet           Minimal output (errors only)
  --template-dir PATH   Custom HTML template directory

Generation Options:
  --exclude PATTERN     Exclude files matching glob (repeatable)
  --no-diagrams         Skip diagram generation
  --diagrams-only       Generate ONLY diagrams (no LLM calls, no API costs)
  --sections LIST       Generate only: overview,dependencies,classes,dataflow,integration
  --diagrams LIST       Generate only: architecture,class,sequence,callgraph,dependency
  --dry-run             Analyze without LLM calls
  --max-files N         Limit files to analyze
```

## Advanced Usage

### Exclude files and directories

```bash
# Exclude test files
docgen --source ./src --exclude "*_test.py" --exclude "test_*.py"

# Exclude multiple patterns
docgen --source ./src --exclude "__pycache__" --exclude "*.pyc" --exclude "migrations/*"
```

### Generate specific sections or diagrams

```bash
# Only generate overview and dependencies sections
docgen --source ./src --sections overview,dependencies

# Only generate architecture and class diagrams
docgen --source ./src --diagrams architecture,class

# Skip diagram generation entirely (faster)
docgen --source ./src --no-diagrams
```

### Preview mode (no API costs)

```bash
# Dry-run mode: analyze code without making LLM calls
docgen --source ./src --dry-run

# Diagrams-only mode: generate only diagrams (no API costs, no LLM calls)
# Perfect for visualizing code structure without text documentation
docgen --source ./src --diagrams-only

# Combine with --diagrams to select specific diagram types
docgen --source ./src --diagrams-only --diagrams architecture,class
```

### Limit analysis scope

```bash
# Analyze only the first 50 files (useful for large codebases)
docgen --source ./src --max-files 50
```

## Documentation Features

The generated documentation includes:

- **System Architecture**: High-level view of system components and their relationships
- **Package Dependencies**: Visualization of package dependencies and their versions
- **Function Call Graph**: Interactive graph showing function calls and relationships
- **Class Diagram**: UML-style class diagram showing inheritance and composition
- **Main Workflows**: Sequence diagrams illustrating key system workflows
- **Comprehensive Sections**:
  - Overview
  - Dependencies
  - Key Classes and Functions
  - Data Flow
  - Integration Points

## Documentation

### For Users

- **[README](README.md)** - You're reading it! Installation and usage guide

### For Contributors

- **[Contributing Guide](CONTRIBUTING.md)** - How to contribute to the project
- **[Pre-Commit Hooks Setup](docs/development/pre-commit.md)** - Detailed pre-commit configuration
- **[Implementation Notes](docs/development/implementation.md)** - Implementation details and decisions

### Features & Design

- **[Diagrams-Only Mode](docs/features/diagrams-only.md)** - Generate diagrams without API costs
- **[Cost Optimization](docs/design/cost-optimization.md)** - Caching and cost reduction strategies

## Development

### Quick Start

```bash
# Clone and setup
git clone https://github.com/yourusername/CodeDocumentationGenerator.git
cd CodeDocumentationGenerator
uv sync

# Install pre-commit hooks
uv run pre-commit install

# Run tests
uv run pytest tests/ -v
```

### Development Workflow

1. **Make changes** and run code simplifier
2. **Commit** - Pre-commit hooks run automatically (0.25s)
3. **Test** - Run `uv run pytest tests/ -v` before pushing
4. **Push** - When all tests pass

**See [CONTRIBUTING.md](CONTRIBUTING.md) for complete developer guide**, including:
- Detailed setup instructions
- Code style requirements
- Testing guidelines
- Pull request process

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
