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
            min-height: 80vh;
            height: 100%;
            width: 100%;
            overflow: auto;
        }
        .diagram-container {
            width: 100%;
            height: 80vh;
            overflow: auto;
            resize: both;
            border: 1px solid #e5e7eb;
            padding: 0.5rem;
            margin: 0;
            position: relative;
            background: white;
        }
        .zoom-buttons {
            position: absolute;
            top: 10px;
            right: 10px;
            z-index: 100;
            background: rgba(255, 255, 255, 0.9);
            padding: 5px;
            border-radius: 4px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }
        .zoom-button {
            background: white;
            border: 1px solid #e5e7eb;
            padding: 5px 10px;
            margin: 0 2px;
            cursor: pointer;
            border-radius: 4px;
            transition: all 0.2s;
        }
        .zoom-button:hover {
            background: #f3f4f6;
            transform: scale(1.05);
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
            z-index: 10;
        }
        .main-content {
            margin-left: 300px;
            padding: 1rem;
            min-height: 100vh;
            width: calc(100% - 300px);
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
        @media (min-width: 1024px) {
            .diagram-container {
                height: 85vh;
            }
            .mermaid {
                min-height: 85vh;
            }
        }
        @media (min-width: 1536px) {
            .diagram-container {
                height: 90vh;
            }
            .mermaid {
                min-height: 90vh;
            }
        }
    </style>
    <script>
        mermaid.initialize({
            startOnLoad: true,
            logLevel: 'debug',
            theme: 'default',
            securityLevel: 'loose',
            maxTextSize: 100000,
            fontSize: 14,
            fontFamily: 'monospace',
            flowchart: {
                useMaxWidth: false,
                htmlLabels: true,
                curve: 'basis'
            },
            sequence: {
                useMaxWidth: false,
                showSequenceNumbers: true,
                actorMargin: 50,
                messageMargin: 40
            },
            er: {
                useMaxWidth: false
            }
        });

        // Add enhanced error handling for Mermaid initialization
        window.addEventListener('load', function() {
            try {
                mermaid.contentLoaded();
                console.debug('Mermaid initialization completed');
            } catch (e) {
                console.error('Mermaid initialization error:', e);
                console.debug('Mermaid configuration:', mermaid.mermaidAPI.getConfig());
                
                // Add detailed error message to diagram containers
                document.querySelectorAll('.mermaid').forEach(function(el) {
                    if (!el.querySelector('svg')) {
                        console.debug('Diagram content:', el.textContent);
                        el.innerHTML = `
                            <div class="text-red-500 p-4">
                                <p class="font-bold mb-2">Error rendering diagram:</p>
                                <p class="mb-2">${e.message}</p>
                                <div class="bg-gray-100 p-4 rounded overflow-auto">
                                    <p class="font-mono text-sm mb-2">Diagram source:</p>
                                    <pre class="text-xs">${el.textContent}</pre>
                                </div>
                                <p class="mt-4 text-sm">Check browser console for detailed debug information.</p>
                            </div>
                        `;
                    }
                });
            }
        });

        // Add debug logging for zoom operations
        function zoomDiagram(diagramId, factor) {
            const container = document.getElementById(diagramId);
            const svg = container.querySelector('svg');
            if (!svg) {
                console.debug('No SVG found in diagram container:', diagramId);
                return;
            }
            
            try {
                const currentScale = svg.style.transform ? 
                    parseFloat(svg.style.transform.replace('scale(', '').replace(')', '')) : 1;
                const newScale = currentScale * factor;
                
                console.debug('Zooming diagram:', {
                    diagramId,
                    currentScale,
                    newScale,
                    factor
                });
                
                svg.style.transform = `scale(${newScale})`;
                svg.style.transformOrigin = 'top left';
            } catch (e) {
                console.error('Error during zoom operation:', e);
            }
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
    <div class="prose max-w-none searchable space-y-6" data-title="{{ section.title }}" data-url="{{ url }}">
        {% set paragraphs = section.content.split('\n\n') %}
        {% set in_code_block = false %}
        {% set in_list = false %}
        {% set list_level = 0 %}
        {% set current_list = [] %}
        
        {% for paragraph in paragraphs %}
            {% set lines = paragraph.split('\n') %}
            {% set processed_lines = [] %}
            
            {% for line in lines %}
                {% set line = line.strip() %}
                {% if line %}
                    {# Handle headers #}
                    {% if line.startswith('##') %}
                        {% if in_list %}
                            </ul>
                            {% set in_list = false %}
                            {% set list_level = 0 %}
                        {% endif %}
                        {% if in_code_block %}
                            </code></pre>
                            {% set in_code_block = false %}
                        {% endif %}
                        {% set header_level = line.count('#') %}
                        {% set header_text = line.lstrip('#').strip() %}
                        <h{{ header_level }} class="text-{{ 4 - header_level }}xl font-bold mt-8 mb-4">{{ header_text }}</h{{ header_level }}>
                    
                    {# Handle code blocks #}
                    {% elif line.startswith('```') %}
                        {% if not in_code_block %}
                            {% if line.startswith('```python') %}
                                <pre class="bg-gray-50 rounded-lg p-4 overflow-x-auto my-4"><code class="language-python">
                            {% else %}
                                <pre class="bg-gray-50 rounded-lg p-4 overflow-x-auto my-4"><code>
                            {% endif %}
                            {% set in_code_block = true %}
                        {% else %}
                            </code></pre>
                            {% set in_code_block = false %}
                        {% endif %}
                    
                    {# Handle bullet points #}
                    {% elif line.startswith(('- ', '* ')) %}
                        {% if not in_list %}
                            <ul class="list-disc pl-6 space-y-2 my-4">
                            {% set in_list = true %}
                        {% endif %}
                        {% set indent_level = (line.index('-') if '-' in line else line.index('*')) // 2 %}
                        {% if indent_level > list_level %}
                            <ul class="list-disc pl-6 space-y-2">
                            {% set list_level = indent_level %}
                        {% elif indent_level < list_level %}
                            {% for _ in range(list_level - indent_level) %}
                                </ul>
                            {% endfor %}
                            {% set list_level = indent_level %}
                        {% endif %}
                        {% set content = line.lstrip('- *').strip() %}
                        {# Process inline code in list items #}
                        {% set processed_content = [] %}
                        {% set parts = content.split('`') %}
                        {% for i in range(parts|length) %}
                            {% if i % 2 == 0 %}
                                {% set _ = processed_content.append(parts[i]) %}
                            {% else %}
                                {% set _ = processed_content.append('<code class="bg-gray-100 rounded px-1 font-mono text-sm">' ~ parts[i] ~ '</code>') %}
                            {% endif %}
                        {% endfor %}
                        <li class="text-gray-800">{{ processed_content|join('')|safe }}</li>
                    
                    {# Handle regular paragraphs #}
                    {% else %}
                        {% if in_list %}
                            {% for _ in range(list_level + 1) %}
                                </ul>
                            {% endfor %}
                            {% set in_list = false %}
                            {% set list_level = 0 %}
                        {% endif %}
                        {% if in_code_block %}
                            {{ line }}
                        {% else %}
                            {# Process inline code in paragraphs #}
                            {% set processed_text = [] %}
                            {% set parts = line.split('`') %}
                            {% for i in range(parts|length) %}
                                {% if i % 2 == 0 %}
                                    {% set _ = processed_text.append(parts[i]) %}
                                {% else %}
                                    {% set _ = processed_text.append('<code class="bg-gray-100 rounded px-1 font-mono text-sm">' ~ parts[i] ~ '</code>') %}
                                {% endif %}
                            {% endfor %}
                            <p class="text-gray-800 leading-relaxed mb-4">{{ processed_text|join('')|safe }}</p>
                        {% endif %}
                    {% endif %}
                {% endif %}
            {% endfor %}
        {% endfor %}
        
        {# Close any open tags #}
        {% if in_list %}
            {% for _ in range(list_level + 1) %}
                </ul>
            {% endfor %}
        {% endif %}
        {% if in_code_block %}
            </code></pre>
        {% endif %}
    </div>
</div>

<style>
.prose {
    font-size: 1.1rem;
    line-height: 1.75;
    color: #1a202c;
}
.prose p {
    margin-bottom: 1.5rem;
}
.prose h2 {
    font-size: 1.875rem;
    line-height: 2.25rem;
    font-weight: 700;
    color: #1a202c;
    border-bottom: 1px solid #e2e8f0;
    padding-bottom: 0.5rem;
    margin-top: 2rem;
    margin-bottom: 1rem;
}
.prose h3 {
    font-size: 1.5rem;
    line-height: 2rem;
    font-weight: 600;
    color: #1a202c;
    margin-top: 1.5rem;
    margin-bottom: 0.75rem;
}
.prose ul {
    list-style-type: disc;
    padding-left: 1.5rem;
    margin: 1.5rem 0;
}
.prose ul ul {
    margin: 0.5rem 0;
}
.prose li {
    margin: 0.5rem 0;
    padding-left: 0.5rem;
}
.prose code {
    color: #1a202c;
    background-color: #f3f4f6;
    padding: 0.2rem 0.4rem;
    border-radius: 0.25rem;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 0.875em;
    white-space: pre-wrap;
    word-wrap: break-word;
}
.prose pre {
    margin: 1.5rem 0;
    background-color: #f3f4f6;
    padding: 1rem;
    border-radius: 0.5rem;
    overflow-x: auto;
}
.prose pre code {
    background-color: transparent;
    padding: 0;
    color: inherit;
    font-size: 0.875em;
    line-height: 1.7142857;
    white-space: pre;
}
</style>
{% endblock %}
"""

# Diagrams page template
_DIAGRAMS_TEMPLATE = """
{% extends "base" %}
{% block content %}
<div class="bg-white rounded-lg shadow-lg h-full">
    <div class="p-4 border-b">
        <h1 class="text-2xl font-bold">{{ title }}</h1>
    </div>
    <div class="relative">
        <div class="zoom-buttons">
            <button class="zoom-button" onclick="zoomDiagram('diagram', 1.2)" title="Zoom In">
                <i class="fas fa-search-plus"></i>
            </button>
            <button class="zoom-button" onclick="zoomDiagram('diagram', 0.8)" title="Zoom Out">
                <i class="fas fa-search-minus"></i>
            </button>
            <button class="zoom-button" onclick="zoomDiagram('diagram', 1/currentScale)" title="Reset Zoom">
                <i class="fas fa-undo"></i>
            </button>
        </div>
        <div id="diagram" class="diagram-container">
            <pre class="mermaid">
{{- diagram_code | trim | indent(width=12) -}}
            </pre>
        </div>
    </div>
    {% if description %}
    <div class="p-4 border-t">
        <div class="prose max-w-none">
            {{ description | safe }}
        </div>
    </div>
    {% endif %}
</div>

<script>
let currentScale = 1;

function zoomDiagram(diagramId, factor) {
    const container = document.getElementById(diagramId);
    const svg = container.querySelector('svg');
    if (!svg) return;
    
    if (factor === 1/currentScale) {
        // Reset zoom
        currentScale = 1;
    } else {
        currentScale = currentScale * factor;
    }
    
    svg.style.transform = `scale(${currentScale})`;
    svg.style.transformOrigin = 'top left';
}
</script>
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