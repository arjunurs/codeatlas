"""Setup configuration for the Code Documentation Generator package."""

from setuptools import setup, find_packages

# Read version from package __init__.py
with open('src/docgen/__init__.py', 'r') as f:
    for line in f:
        if line.startswith('__version__'):
            version = line.split('=')[1].strip().strip('"').strip("'")
            break

# Read long description from README
with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='code-documentation-generator',
    version=version,
    description='Generate comprehensive documentation for Python codebases using LLMs',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Your Name',
    author_email='your.email@example.com',
    url='https://github.com/yourusername/CodeDocumentationGenerator',
    package_dir={'': 'src'},
    packages=find_packages(where='src'),
    install_requires=[
        'langchain-anthropic>=0.1.0',
        'langchain-openai>=0.0.5',
        'langchain>=0.1.0',
        'anthropic>=0.18.1',
        'networkx>=3.0',
        'jinja2>=3.0.0',
        'python-dotenv>=1.0.0',
        'requirements-parser>=0.5.0'
    ],
    entry_points={
        'console_scripts': [
            'docgen=docgen.cli:main',
        ],
    },
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Topic :: Documentation',
        'Topic :: Software Development :: Documentation',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    python_requires='>=3.8',
    keywords='documentation, code analysis, llm, ai, documentation generator',
) 