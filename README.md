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

You can install the package directly from GitHub:

```bash
pip install git+https://github.com/yourusername/CodeDocumentationGenerator.git
```

Or install in development mode:

```bash
git clone https://github.com/yourusername/CodeDocumentationGenerator.git
cd CodeDocumentationGenerator
pip install -e .
```

## Requirements

- Python 3.8 or higher
- Anthropic API key (for Claude 3 Sonnet)
- OpenAI API key (for embeddings)

## Usage

1. Set up your API keys:

```bash
# Using environment variables
export ANTHROPIC_API_KEY=your-key-here
export OPENAI_API_KEY=your-key-here

# Or create a .env file
echo "ANTHROPIC_API_KEY=your-key-here" > .env
echo "OPENAI_API_KEY=your-key-here" >> .env
```

2. Generate documentation:

```bash
# Basic usage
docgen --source ./my_project --output ./docs

# With verbose logging
docgen --source ./my_project --output ./docs --verbose

# Using custom API keys
docgen --source ./my_project --output ./docs \
    --anthropic-api-key sk-ant-... \
    --openai-api-key sk-...
```

3. View the generated documentation by opening `docs/documentation.html` in your browser.

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

## Development

To set up the development environment:

1. Clone the repository
2. Create a virtual environment
3. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```
4. Run tests:
   ```bash
   pytest
   ```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
