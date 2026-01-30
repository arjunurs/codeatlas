# Code Documentation Generator

A powerful tool for automatically generating comprehensive documentation for Python codebases using Large Language Models (LLMs). It analyzes code structure, relationships, and patterns to create rich, interactive documentation with architectural diagrams.

## Features

- **Automatic code analysis** with AST parsing and entity extraction
- **Enhanced documentation** with LLM-powered insights and explanations
- **5 core documentation sections** (Overview, Dependencies, Key Classes, Data Flow, Integration Points)
- **3 optional sections** for deeper analysis:
  - Migration Guidance (deprecated patterns, security issues, modern alternatives)
  - Code Quality Insights (architectural patterns, trade-offs, improvement suggestions)
  - Cross-Reference Documentation (where components are defined and used)
- **Interactive system diagrams**: architecture, class, sequence, call graph, dependencies
- **Diagram validation** with 15+ rules to catch syntax errors before HTML generation
- **Advanced caching** for incremental updates and cost savings
- **Configurable RAG retrieval** (similarity search, MMR diversity, score thresholds)
- **Rich HTML output** with search and navigation
- **Integration** with Anthropic Claude and OpenAI

## Installation

Using [uv](https://docs.astral.sh/uv/) (recommended):

```bash
git clone https://github.com/arjunurs/CodeDocumentationGenerator.git
cd CodeDocumentationGenerator
uv sync
```

Or install with pip:

```bash
pip install git+https://github.com/arjunurs/CodeDocumentationGenerator.git
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
docgen --source ./my_project

# Specify output directory
docgen --source ./my_project -o ./my-docs

# With .env file for API keys
docgen --source ./my_project --api-key-env ./.env

# With verbose logging
docgen --source ./my_project -v
```

### 3. View the generated documentation

Open `output/index.html` in your browser (or your specified output directory).

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
  -o, --output OUTPUT   Output directory (default: output)

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
  --sections LIST       Sections to generate (comma-separated):
                        Core: overview,dependencies,classes,dataflow,integration
                        Optional: migration_guidance,code_quality,cross_reference
  --diagrams LIST       Generate only: architecture,class,sequence,callgraph,dependency
  --dry-run             Analyze without LLM calls
  --max-files N         Limit files to analyze

RAG Retrieval Options:
  --retriever-k N       Number of documents to retrieve (default: 10)
  --retriever-search-type {similarity,mmr}
                        Retrieval method: similarity (default) or mmr (diversity)
  --retriever-score-threshold FLOAT
                        Minimum similarity score (0.0-1.0, optional)
  --retriever-fetch-k N Documents to fetch before MMR reranking (default: 20)
  --retriever-lambda-mult FLOAT
                        MMR diversity: 0=max diversity, 1=max relevance (default: 0.5)
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

# Generate with optional sections
docgen --source ./src --sections "overview,dependencies,migration_guidance"

# Generate code quality analysis
docgen --source ./src --sections "overview,code_quality,cross_reference"

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

### Configure RAG retrieval

```bash
# Use MMR (Maximal Marginal Relevance) for diverse context
docgen --source ./src --retriever-search-type mmr --retriever-k 15

# Fine-tune MMR diversity (0=max diversity, 1=max relevance)
docgen --source ./src --retriever-search-type mmr --retriever-lambda-mult 0.7

# Set minimum similarity threshold
docgen --source ./src --retriever-score-threshold 0.75
```

## Documentation Features

The generated documentation includes:

### Diagrams
- **System Architecture**: High-level view of system components and their relationships
- **Package Dependencies**: Visualization of package dependencies and their versions
- **Function Call Graph**: Interactive graph showing function calls and relationships
- **Class Diagram**: UML-style class diagram showing inheritance and composition
- **Sequence Diagrams**: Illustrating key system workflows

### Core Sections (always generated)
- **Overview**: System purpose, components, and architecture
- **Dependencies**: Core/optional dependencies, versions, and integrations
- **Key Classes and Functions**: Public APIs with usage examples
- **Data Flow**: Processing pipeline and data structures
- **Integration Points**: External systems and authentication

### Optional Sections (via `--sections` flag)
- **Migration Guidance**: Deprecated patterns, security issues, modern alternatives
- **Code Quality Insights**: Architectural patterns, trade-offs, improvement suggestions
- **Cross-Reference Documentation**: Where components are defined and used throughout the codebase

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
git clone https://github.com/arjunurs/CodeDocumentationGenerator.git
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
