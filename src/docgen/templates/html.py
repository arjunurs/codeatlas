"""HTML templates for documentation generation.

This module provides the HTML templates used to generate the final documentation,
including styling and interactive features.
"""

from typing import Dict, Any, Optional
from pathlib import Path
import os
from jinja2 import Environment, Template, BaseLoader, TemplateNotFound

class StringTemplateLoader(BaseLoader):
    """Custom template loader that loads templates from strings."""
    
    def __init__(self, templates):
        self.templates = templates
        
    def get_source(self, environment, template):
        if template in self.templates:
            source = self.templates[template]
            return source, None, lambda: True
        raise TemplateNotFound(template)

class TemplateManager:
    """Manages HTML templates for documentation generation.
    
    This class handles loading and rendering of various documentation templates
    including the main index, section pages, and diagram views.
    """
    
    def __init__(self):
        """Initialize the template manager."""
        # Define template mapping
        template_map = {
            'base': _BASE_TEMPLATE,
            'index': _INDEX_TEMPLATE,
            'section': _SECTION_TEMPLATE,
            'diagrams': _DIAGRAMS_TEMPLATE,
            'search': _SEARCH_TEMPLATE,
            'navigation': _NAVIGATION_TEMPLATE
        }
        
        # Create environment with string loader
        self.env = Environment(
            loader=StringTemplateLoader(template_map),
            autoescape=True
        )
        
        # Load all templates
        self.templates = {
            name: self.env.get_template(name)
            for name in template_map
        }
    
    def render_template(
        self,
        template_name: str,
        context: Dict[str, Any],
        output_dir: str,
        filename: Optional[str] = None
    ) -> None:
        """Render a template and save it to a file.
        
        Args:
            template_name: Name of the template to render
            context: Template context data
            output_dir: Output directory path
            filename: Optional custom filename
        """
        if template_name not in self.templates:
            raise ValueError(f"Unknown template: {template_name}")
            
        template = self.templates[template_name]
        output = template.render(**context)
        
        if filename:
            output_path = os.path.join(output_dir, filename)
        else:
            output_path = os.path.join(output_dir, f"{template_name}.html")
            
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(output)

def get_template_manager() -> TemplateManager:
    """Get a template manager instance.
    
    Returns:
        TemplateManager instance
    """
    return TemplateManager()

# Base template with common structure and styling
_BASE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>{{ title }}</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .mermaid {
            min-height: 400px;
            overflow: auto;
        }
        .diagram-container {
            width: 100%;
            overflow: auto;
            resize: both;
            min-height: 400px;
            border: 1px solid #e5e7eb;
            padding: 1rem;
        }
        .zoom-buttons {
            position: absolute;
            top: 10px;
            right: 10px;
            z-index: 100;
        }
        .zoom-button {
            background: white;
            border: 1px solid #e5e7eb;
            padding: 5px 10px;
            margin: 0 2px;
            cursor: pointer;
            border-radius: 4px;
        }
        .zoom-button:hover {
            background: #f3f4f6;
        }
        .sidebar {
            width: 300px;
            height: 100vh;
            position: fixed;
            top: 0;
            left: 0;
            overflow-y: auto;
            background: white;
            border-right: 1px solid #e5e7eb;
            padding: 1rem;
        }
        .main-content {
            margin-left: 300px;
            padding: 2rem;
        }
        .search-box {
            width: 100%;
            padding: 0.5rem;
            border: 1px solid #e5e7eb;
            border-radius: 4px;
            margin-bottom: 1rem;
        }
        .nav-item {
            padding: 0.5rem;
            cursor: pointer;
            border-radius: 4px;
            display: block;
            width: 100%;
            margin-bottom: 0.25rem;
            white-space: normal;
            word-wrap: break-word;
        }
        .nav-item:hover {
            background: #f3f4f6;
        }
        .nav-item.active {
            background: #e5e7eb;
        }
        .nav-section {
            margin-bottom: 1rem;
        }
        .nav-section h3 {
            margin-bottom: 0.5rem;
            padding: 0.5rem 0;
            border-bottom: 1px solid #e5e7eb;
        }
    </style>
    <script>
        mermaid.initialize({
            startOnLoad: true,
            theme: 'default',
            securityLevel: 'loose',
            maxTextSize: 100000,
            fontSize: 14,
            fontFamily: 'monospace'
        });

        function zoomDiagram(diagramId, factor) {
            const container = document.getElementById(diagramId);
            const svg = container.querySelector('svg');
            if (!svg) return;
            
            const currentScale = svg.style.transform ? 
                parseFloat(svg.style.transform.replace('scale(', '').replace(')', '')) : 1;
            const newScale = currentScale * factor;
            
            svg.style.transform = `scale(${newScale})`;
            svg.style.transformOrigin = 'top left';
        }

        function search() {
            const query = document.getElementById('search').value.toLowerCase();
            const results = [];
            
            // Search in content
            document.querySelectorAll('.searchable').forEach(element => {
                if (element.textContent.toLowerCase().includes(query)) {
                    results.push({
                        title: element.getAttribute('data-title'),
                        url: element.getAttribute('data-url'),
                        excerpt: element.textContent.substring(0, 200) + '...'
                    });
                }
            });
            
            // Update results
            const resultsContainer = document.getElementById('search-results');
            resultsContainer.innerHTML = results.map(result => `
                <div class="p-4 border-b">
                    <a href="${result.url}" class="text-blue-600 hover:text-blue-800 font-medium">
                        ${result.title}
                    </a>
                    <p class="text-gray-600 text-sm mt-1">${result.excerpt}</p>
                </div>
            `).join('');
        }
    </script>
</head>
<body class="bg-gray-100">
    <div class="sidebar">
        <input type="text" id="search" placeholder="Search documentation..." 
               class="search-box" onkeyup="search()">
        <div id="navigation">
            {{ navigation | safe }}
        </div>
    </div>
    <div class="main-content">
        {% block content %}{% endblock %}
    </div>
</body>
</html>
"""

# Index page template
_INDEX_TEMPLATE = """
{% extends "base" %}
{% block content %}
<h1 class="text-4xl font-bold mb-8">{{ documentation.title }}</h1>

<div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-12">
    <div class="bg-white p-6 rounded-lg shadow-lg">
        <h2 class="text-2xl font-semibold mb-4">Quick Links</h2>
        <ul class="space-y-2">
            {% for section in documentation.sections %}
            <li>
                <a href="{{ base_url }}/sections/{{ section.title | lower | replace(' ', '_') }}.html" 
                   class="text-blue-600 hover:text-blue-800">
                    {{ section.title }}
                </a>
            </li>
            {% endfor %}
        </ul>
    </div>
    
    <div class="bg-white p-6 rounded-lg shadow-lg">
        <h2 class="text-2xl font-semibold mb-4">Diagrams</h2>
        <ul class="space-y-2">
            <li><a href="{{ base_url }}/diagrams/architecture.html" class="text-blue-600 hover:text-blue-800">System Architecture</a></li>
            <li><a href="{{ base_url }}/diagrams/dependencies.html" class="text-blue-600 hover:text-blue-800">Package Dependencies</a></li>
            <li><a href="{{ base_url }}/diagrams/classes.html" class="text-blue-600 hover:text-blue-800">Class Diagram</a></li>
            <li><a href="{{ base_url }}/diagrams/sequence.html" class="text-blue-600 hover:text-blue-800">Sequence Diagram</a></li>
            <li><a href="{{ base_url }}/diagrams/call_graph.html" class="text-blue-600 hover:text-blue-800">Call Graph</a></li>
        </ul>
    </div>
</div>

<div class="bg-white p-6 rounded-lg shadow-lg mb-8">
    <h2 class="text-2xl font-semibold mb-4">Overview</h2>
    <div class="prose max-w-none">
        {{ documentation.sections[0].content | safe }}
    </div>
</div>

<footer class="text-center text-gray-500 mt-12">
    Generated on {{ documentation.generated_date }}
</footer>
{% endblock %}
"""

# Section page template
_SECTION_TEMPLATE = """
{% extends "base" %}
{% block content %}
<div class="bg-white p-6 rounded-lg shadow-lg">
    <h1 class="text-4xl font-bold mb-8">{{ section.title }}</h1>
    <div class="prose max-w-none searchable" data-title="{{ section.title }}" data-url="{{ url }}">
        {{ section.content | safe }}
    </div>
</div>
{% endblock %}
"""

# Diagrams page template
_DIAGRAMS_TEMPLATE = """
{% extends "base" %}
{% block content %}
<div class="bg-white p-6 rounded-lg shadow-lg">
    <h1 class="text-4xl font-bold mb-8">{{ title }}</h1>
    <div class="relative">
        <div class="zoom-buttons">
            <button class="zoom-button" onclick="zoomDiagram('diagram', 1.2)">+</button>
            <button class="zoom-button" onclick="zoomDiagram('diagram', 0.8)">-</button>
        </div>
        <div id="diagram" class="diagram-container">
            <div class="mermaid">
                {{ diagram }}
            </div>
        </div>
    </div>
    {% if description %}
    <div class="mt-8 prose max-w-none">
        {{ description | safe }}
    </div>
    {% endif %}
</div>
{% endblock %}
"""

# Search results template
_SEARCH_TEMPLATE = """
{% extends "base" %}
{% block content %}
<div class="bg-white p-6 rounded-lg shadow-lg">
    <h1 class="text-4xl font-bold mb-8">Search Results</h1>
    <div id="search-results"></div>
</div>
{% endblock %}
"""

# Navigation partial template
_NAVIGATION_TEMPLATE = """
<nav>
    <div class="nav-section">
        <a href="{{ base_url }}index.html" class="nav-item {% if active == 'index' %}active{% endif %}">
            <i class="fas fa-home mr-2"></i> Home
        </a>
    </div>
    
    <div class="nav-section">
        <h3 class="font-semibold">Documentation</h3>
        {% for section in sections %}
        <a href="{{ base_url }}sections/{{ section | lower | replace(' ', '_') }}.html" 
           class="nav-item {% if active == section %}active{% endif %}">
            {{ section }}
        </a>
        {% endfor %}
    </div>
    
    <div class="nav-section">
        <h3 class="font-semibold">Diagrams</h3>
        <a href="{{ base_url }}diagrams/architecture.html" class="nav-item {% if active == 'architecture' %}active{% endif %}">
            <i class="fas fa-project-diagram mr-2"></i> System Architecture
        </a>
        <a href="{{ base_url }}diagrams/dependencies.html" class="nav-item {% if active == 'dependencies' %}active{% endif %}">
            <i class="fas fa-cubes mr-2"></i> Package Dependencies
        </a>
        <a href="{{ base_url }}diagrams/classes.html" class="nav-item {% if active == 'classes' %}active{% endif %}">
            <i class="fas fa-sitemap mr-2"></i> Class Diagram
        </a>
        <a href="{{ base_url }}diagrams/sequence.html" class="nav-item {% if active == 'sequence' %}active{% endif %}">
            <i class="fas fa-exchange-alt mr-2"></i> Sequence Diagram
        </a>
        <a href="{{ base_url }}diagrams/call_graph.html" class="nav-item {% if active == 'call_graph' %}active{% endif %}">
            <i class="fas fa-code-branch mr-2"></i> Call Graph
        </a>
    </div>
</nav>
""" 