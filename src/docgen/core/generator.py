"""Documentation generator core functionality.

This module provides the main CodeDocumentationGenerator class that orchestrates
the entire documentation generation process.
"""

import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Sequence
import logging
import shutil

from langchain_anthropic import ChatAnthropic
from langchain_openai import OpenAIEmbeddings
from langchain.prompts import ChatPromptTemplate
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain.chains import RetrievalQA

from .analyzer import CodeAnalyzer
from .diagrams import DiagramGenerator
from ..models.file_analysis import FileAnalysis
from ..templates.html import get_template_manager
from ..exceptions.errors import DocumentationError, ApiKeyError

logger = logging.getLogger(__name__)

class CodeDocumentationGenerator:
    """Generates comprehensive documentation for Python codebases using LLMs.
    
    This class orchestrates the documentation generation process by:
    1. Analyzing Python source code structure and relationships
    2. Generating various architectural diagrams
    3. Using LLMs to explain code patterns and architecture
    4. Creating an interactive HTML documentation
    
    The generated documentation includes:
    - System architecture overview
    - Package dependencies
    - Class diagrams
    - Sequence diagrams
    - Function call graphs
    - Detailed explanations of key components
    
    Attributes:
        llm: LangChain chat model for text generation
        embeddings: Vector embeddings for semantic search
        text_splitter: Text splitter for chunking documents
        temperature: Temperature for LLM generation
        analyzer: Code analyzer for parsing source files
        diagram_generator: Generator for Mermaid diagrams
    """
    
    def __init__(
        self,
        anthropic_api_key: str,
        openai_api_key: str,
        temperature: float = 0.2,
        model: str = "claude-3-sonnet-20240229"
    ) -> None:
        """Initialize the documentation generator.
        
        Args:
            anthropic_api_key: API key for Anthropic's Claude
            openai_api_key: API key for OpenAI embeddings
            temperature: Temperature for LLM generation (0.0 to 1.0)
            model: Anthropic model to use
            
        Raises:
            ValueError: If temperature is not between 0 and 1
            ApiKeyError: If API keys are invalid
        """
        if not 0 <= temperature <= 1:
            raise ValueError("Temperature must be between 0 and 1")
            
        if not anthropic_api_key or not openai_api_key:
            raise ApiKeyError("Both Anthropic and OpenAI API keys are required")
        
        # Initialize LLM components
        try:
            self.llm = ChatAnthropic(
                anthropic_api_key=anthropic_api_key,
                model_name=model,
                temperature=temperature
            )
            self.embeddings = OpenAIEmbeddings(
                api_key=openai_api_key,
                model="text-embedding-3-small"
            )
        except Exception as e:
            raise ApiKeyError(f"Failed to initialize LLM components: {str(e)}")
            
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000,
            chunk_overlap=200
        )
        self.temperature = temperature
        
        # Initialize analysis components
        self.analyzer = CodeAnalyzer()
        self.diagram_generator = DiagramGenerator()
        self.template_manager = get_template_manager()
    
    def generate_documentation(self, directory_path: str, output_dir: str) -> None:
        """Generate comprehensive documentation for a Python codebase.
        
        Args:
            directory_path: Path to the directory containing Python source files
            output_dir: Directory where documentation will be generated
            
        Raises:
            DocumentationError: If documentation generation fails
            ValueError: If directory paths are invalid
        """
        # Validate and convert paths
        abs_directory_path = os.path.abspath(directory_path)
        abs_output_dir = os.path.abspath(output_dir)
        
        if not os.path.isdir(abs_directory_path):
            raise ValueError(f"Invalid source directory: {directory_path}")
            
        # Create output directory structure
        os.makedirs(abs_output_dir, exist_ok=True)
        os.makedirs(os.path.join(abs_output_dir, 'sections'), exist_ok=True)
        os.makedirs(os.path.join(abs_output_dir, 'diagrams'), exist_ok=True)
        os.makedirs(os.path.join(abs_output_dir, 'assets'), exist_ok=True)
        
        try:
            # Analyze codebase
            logger.info("Analyzing Python files...")
            analyses = self.analyzer.analyze_directory(abs_directory_path)
            
            if not analyses:
                logger.error("No Python files found in directory")
                raise DocumentationError("No Python files found in directory")
            
            # Create documents for vector store
            logger.info("Creating vector store...")
            documents = self._create_documents(analyses)
            
            if not documents:
                logger.error("No documentation content could be generated")
                raise DocumentationError("No documentation content could be generated")
            
            # Create vector store and QA chain
            logger.info("Creating vector store and QA chain...")
            texts = self.text_splitter.split_documents(documents)
            vector_store = Chroma.from_documents(texts, self.embeddings)
            qa_chain = RetrievalQA.from_chain_type(
                llm=self.llm,
                chain_type="stuff",
                retriever=vector_store.as_retriever()
            )
            
            # Generate diagrams
            logger.info("Generating diagrams...")
            try:
                diagrams = {
                    'architecture': self.diagram_generator.generate_architecture_diagram(analyses),
                    'class_diagram': self.diagram_generator.generate_class_diagram(analyses),
                    'sequence': self.diagram_generator.generate_sequence_diagram(
                        self.analyzer.analyze_function_calls(analyses)
                    ),
                    'package_dependencies': self.diagram_generator.generate_dependency_diagram(
                        self.analyzer.analyze_package_dependencies()
                    ),
                    'function_calls': self.diagram_generator.generate_call_graph_diagram(
                        self.analyzer.analyze_function_calls(analyses)
                    )
                }
            except Exception as e:
                logger.warning(f"Error generating diagrams: {str(e)}")
                diagrams = {}
            
            # Generate documentation sections
            logger.info("Generating documentation content...")
            documentation = {
                'title': 'Code Documentation',
                'generated_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'sections': [
                    {
                        'title': 'Overview',
                        'content': qa_chain.run(
                            "Analyze the codebase and provide a comprehensive overview including:\n"
                            "1. The main purpose and functionality\n"
                            "2. Key components and their responsibilities\n"
                            "3. How different parts work together\n"
                            "4. The overall architecture and design patterns used\n"
                            "Be specific and use examples from the actual code."
                        )
                    },
                    {
                        'title': 'Dependencies',
                        'content': qa_chain.run(
                            "Analyze the project dependencies and explain:\n"
                            "1. Core external packages used\n"
                            "2. Purpose of each major dependency\n"
                            "3. Version requirements and compatibility\n"
                            "4. How dependencies are managed\n"
                            "Include specific examples from requirements.txt."
                        )
                    },
                    {
                        'title': 'Key Classes and Functions',
                        'content': qa_chain.run(
                            "Describe the key classes and functions including:\n"
                            "1. Main classes, their purposes and relationships\n"
                            "2. Important methods and their functionality\n"
                            "3. Design patterns and principles used\n"
                            "4. Code organization and structure\n"
                            "Use specific examples from the codebase."
                        )
                    },
                    {
                        'title': 'Data Flow',
                        'content': qa_chain.run(
                            "Explain the data flow through the system including:\n"
                            "1. How data is processed and transformed\n"
                            "2. Key data structures and their usage\n"
                            "3. Input/output handling\n"
                            "4. Error handling and validation\n"
                            "Provide concrete examples from the code."
                        )
                    },
                    {
                        'title': 'Integration Points',
                        'content': qa_chain.run(
                            "Describe how the code integrates with other systems:\n"
                            "1. External APIs and services used\n"
                            "2. Integration patterns and protocols\n"
                            "3. Authentication and security\n"
                            "4. Error handling and fallbacks\n"
                            "Include specific integration examples."
                        )
                    }
                ]
            }
            
            # Generate HTML documentation
            logger.info("Generating HTML documentation...")
            self._generate_html_documentation(documentation, diagrams, abs_output_dir)
            logger.info(f"Documentation generated successfully in {abs_output_dir}")
            
        except Exception as e:
            logger.error(f"Error generating documentation: {str(e)}")
            raise DocumentationError(f"Failed to generate documentation: {str(e)}")
    
    def _create_documents(self, analyses: Sequence[FileAnalysis]) -> List[Document]:
        """Create LangChain documents from file analyses.
        
        Args:
            analyses: List of file analysis results
            
        Returns:
            List of LangChain documents for vector store
        """
        documents: List[Document] = []
        
        for analysis in analyses:
            # Add file content
            documents.append(Document(
                page_content=analysis.content,
                metadata={"source": analysis.file_path}
            ))
            
            # Add entity information
            for entity in analysis.entities:
                doc = f"Type: {entity.type}\nName: {entity.name}\n"
                if entity.docstring:
                    doc += f"Description: {entity.docstring}\n"
                if entity.type == 'class':
                    doc += f"Methods: {', '.join(entity.methods)}\n"
                    if entity.parent_class:
                        doc += f"Inherits from: {entity.parent_class}\n"
                documents.append(Document(
                    page_content=doc,
                    metadata={"source": analysis.file_path}
                ))
                
        return documents
    
    def _generate_html_documentation(
        self,
        documentation: Dict[str, Any],
        diagrams: Dict[str, str],
        output_dir: str
    ) -> None:
        """Generate HTML documentation with embedded diagrams.
        
        Args:
            documentation: Dictionary containing documentation content
            diagrams: Dictionary containing Mermaid diagram codes
            output_dir: Directory where HTML files will be generated
            
        Raises:
            DocumentationError: If HTML generation fails
        """
        try:
            # Generate index page
            self.template_manager.render_template(
                'index',
                {
                    'title': documentation['title'],
                    'documentation': documentation,
                    'navigation': self._generate_navigation('index', documentation['sections'])
                },
                output_dir,
                'index.html'
            )
            
            # Generate section pages
            for section in documentation['sections']:
                section_file = f"sections/{section['title'].lower().replace(' ', '_')}.html"
                self.template_manager.render_template(
                    'section',
                    {
                        'title': section['title'],
                        'section': section,
                        'url': section_file,
                        'navigation': self._generate_navigation(section['title'], documentation['sections'])
                    },
                    output_dir,
                    section_file
                )
            
            # Generate diagram pages
            diagram_descriptions = {
                'architecture': 'System architecture showing component relationships',
                'dependencies': 'Package dependency graph showing external and internal dependencies',
                'classes': 'Class diagram showing inheritance and composition relationships',
                'sequence': 'Sequence diagram showing main workflow interactions',
                'call_graph': 'Function call graph showing code execution flow'
            }
            
            diagram_files = {
                'architecture': diagrams.get('architecture', ''),
                'dependencies': diagrams.get('package_dependencies', ''),
                'classes': diagrams.get('class_diagram', ''),
                'sequence': diagrams.get('sequence', ''),
                'call_graph': diagrams.get('function_calls', '')
            }
            
            for name, diagram in diagram_files.items():
                if diagram:
                    self.template_manager.render_template(
                        'diagrams',
                        {
                            'title': name.replace('_', ' ').title(),
                            'diagram': diagram,
                            'description': diagram_descriptions.get(name, ''),
                            'navigation': self._generate_navigation(name, documentation['sections'])
                        },
                        output_dir,
                        f"diagrams/{name}.html"
                    )
            
            # Generate search page
            self.template_manager.render_template(
                'search',
                {
                    'title': 'Search Documentation',
                    'navigation': self._generate_navigation('search', documentation['sections'])
                },
                output_dir,
                'search.html'
            )
                
        except Exception as e:
            logger.error(f"Error generating HTML documentation: {str(e)}")
            raise DocumentationError(f"Failed to generate HTML documentation: {str(e)}")
    
    def _generate_navigation(self, active_page: str, sections: List[Dict[str, str]]) -> str:
        """Generate navigation HTML for the current page.
        
        Args:
            active_page: Currently active page
            sections: List of documentation sections
            
        Returns:
            Navigation HTML content
        """
        return self.template_manager.templates['navigation'].render(
            active=active_page,
            sections=[s['title'] for s in sections]
        ) 