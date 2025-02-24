"""HTML templates for documentation generation.

This module provides the HTML templates used to generate the final documentation,
including styling and interactive features.
"""

from typing import Dict, Any
from jinja2 import Environment, Template

def get_documentation_template() -> Template:
    """Return the HTML template for documentation.

    Returns:
        Jinja2 Template object for rendering documentation

    Example:
        >>> template = get_documentation_template()
        >>> html = template.render(documentation=doc_data, diagrams=diagrams)
    """
    env = Environment()
    return env.from_string(_BASE_TEMPLATE)

_BASE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>{{ documentation.title }}</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
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
    </script>
</head>
<body class="bg-gray-100">
    <div class="container mx-auto px-4 py-8">
        <h1 class="text-4xl font-bold mb-8">{{ documentation.title }}</h1>

        <!-- Architecture Diagrams -->
        <div class="mb-12">
            <h2 class="text-2xl font-semibold mb-4">System Architecture</h2>
            <div class="bg-white rounded-lg shadow-lg relative">
                <div class="zoom-buttons">
                    <button class="zoom-button" onclick="zoomDiagram('arch-diagram', 1.2)">+</button>
                    <button class="zoom-button" onclick="zoomDiagram('arch-diagram', 0.8)">-</button>
                </div>
                <div id="arch-diagram" class="diagram-container">
                    <div class="mermaid">
                        {{ diagrams.architecture }}
                    </div>
                </div>
            </div>
        </div>

        <div class="mb-12">
            <h2 class="text-2xl font-semibold mb-4">Package Dependencies</h2>
            <div class="bg-white rounded-lg shadow-lg relative">
                <div class="zoom-buttons">
                    <button class="zoom-button" onclick="zoomDiagram('deps-diagram', 1.2)">+</button>
                    <button class="zoom-button" onclick="zoomDiagram('deps-diagram', 0.8)">-</button>
                </div>
                <div id="deps-diagram" class="diagram-container">
                    <div class="mermaid">
                        {{ diagrams.package_dependencies }}
                    </div>
                </div>
            </div>
        </div>

        <div class="mb-12">
            <h2 class="text-2xl font-semibold mb-4">Function Call Graph</h2>
            <div class="bg-white rounded-lg shadow-lg relative">
                <div class="zoom-buttons">
                    <button class="zoom-button" onclick="zoomDiagram('calls-diagram', 1.2)">+</button>
                    <button class="zoom-button" onclick="zoomDiagram('calls-diagram', 0.8)">-</button>
                </div>
                <div id="calls-diagram" class="diagram-container">
                    <div class="mermaid">
                        {{ diagrams.function_calls }}
                    </div>
                </div>
            </div>
        </div>

        <div class="mb-12">
            <h2 class="text-2xl font-semibold mb-4">Class Diagram</h2>
            <div class="bg-white rounded-lg shadow-lg relative">
                <div class="zoom-buttons">
                    <button class="zoom-button" onclick="zoomDiagram('class-diagram', 1.2)">+</button>
                    <button class="zoom-button" onclick="zoomDiagram('class-diagram', 0.8)">-</button>
                </div>
                <div id="class-diagram" class="diagram-container">
                    <div class="mermaid">
                        {{ diagrams.class_diagram }}
                    </div>
                </div>
            </div>
        </div>

        <div class="mb-12">
            <h2 class="text-2xl font-semibold mb-4">Main Workflows</h2>
            <div class="bg-white rounded-lg shadow-lg relative">
                <div class="zoom-buttons">
                    <button class="zoom-button" onclick="zoomDiagram('seq-diagram', 1.2)">+</button>
                    <button class="zoom-button" onclick="zoomDiagram('seq-diagram', 0.8)">-</button>
                </div>
                <div id="seq-diagram" class="diagram-container">
                    <div class="mermaid">
                        {{ diagrams.sequence }}
                    </div>
                </div>
            </div>
        </div>

        <!-- Documentation Sections -->
        {% for section in documentation.sections %}
        <div class="mb-8">
            <h2 class="text-2xl font-semibold mb-4">{{ section.title }}</h2>
            <div class="bg-white p-6 rounded-lg shadow-lg prose max-w-none">
                {{ section.content | replace('\n', '<br>') | safe }}
            </div>
        </div>
        {% endfor %}

        <footer class="text-center text-gray-500 mt-12">
            Generated on {{ documentation.generated_date }}
        </footer>
    </div>
</body>
</html>
""" 