"""Diagram generation module.

This module provides functionality for generating various types of diagrams
for code documentation.
"""

import logging
import re
from collections import Counter, defaultdict
from collections.abc import Sequence

from ..exceptions.errors import DiagramGenerationError, DiagramValidationError
from ..models.call_graph import CallGraph
from ..models.code_entity import EntityType
from ..models.diagram_validation import DiagramType, ValidationConfig
from ..models.file_analysis import FileAnalysis
from .modules import longest_prefix
from .sequence import Message, plan_sequence

logger = logging.getLogger(__name__)


def select_diagrams(selected: list[str] | None) -> list[str]:
    """Resolve a diagram selection to diagram type names.

    Names match case-insensitively and ignore "_" and "-", so "Class" and
    "call_graph" both work. Blank names, such as the empty entry from a
    trailing comma, are ignored.

    Args:
        selected: Diagram names as the user gave them, or None for all

    Returns:
        The selected diagram type names in generation order, or all of them
        when nothing is selected

    Raises:
        ValueError: If a selected name is not a diagram type
    """
    available = [diagram_type.value for diagram_type in DiagramType]
    names = [name.strip() for name in selected or [] if name.strip()]
    if not names:
        return available

    keys = {name: name.lower().replace("_", "").replace("-", "") for name in names}
    unknown = [name for name, key in keys.items() if key not in available]
    if unknown:
        raise ValueError(
            f"Unknown diagram(s): {', '.join(unknown)}. "
            f"Available diagrams: {', '.join(available)}"
        )

    return [name for name in available if name in keys.values()]


class DiagramGenerator:
    """Generates various types of diagrams for code documentation.

    This class provides methods for generating:
    - Class diagrams
    - Sequence diagrams
    - Dependency diagrams
    - Call graph diagrams
    """

    def __init__(
        self,
        max_nodes: int = 50,
        *,
        validate_diagrams: bool = True,
        validation_config: ValidationConfig | None = None,
    ):
        """Initialize the diagram generator.

        Args:
            max_nodes: Maximum number of nodes to show in diagrams
            validate_diagrams: Whether to validate generated diagrams
            validation_config: Optional validation configuration
        """
        self.max_nodes = max_nodes
        self.validate_diagrams = validate_diagrams
        self.validation_config = validation_config or ValidationConfig()
        self.validator = None

        if self.validate_diagrams:
            # Import here to avoid circular dependency
            from ..utils.diagram_validator import DiagramValidator

            self.validator = DiagramValidator(self.validation_config)

    def _validate_diagram(
        self,
        diagram_content: str,
        diagram_type: DiagramType,
    ) -> None:
        """Validate a generated diagram.

        Args:
            diagram_content: The diagram content to validate
            diagram_type: The type of diagram

        Raises:
            DiagramGenerationError: If validation fails in strict mode
        """
        if not self.validate_diagrams or not self.validator:
            return

        try:
            result = self.validator.validate(
                diagram_content,
                diagram_type,
                raise_on_error=True,  # Fail fast on errors
            )

            if result.has_warnings:
                logger.warning(
                    f"{diagram_type.value} diagram has "
                    f"{len(result.warnings)} warning(s)"
                )
                for warning in result.warnings:
                    logger.warning(f"  {warning}")

        except DiagramValidationError as e:
            raise DiagramGenerationError(
                f"Generated {diagram_type.value} diagram failed validation: {e}"
            ) from e

    # Mermaid reserved keywords that cannot be used as node IDs
    MERMAID_RESERVED_WORDS = frozenset(
        {
            "click",
            "call",
            "graph",
            "subgraph",
            "end",
            "style",
            "linkStyle",
            "classDef",
            "class",
            "direction",
            "participant",
            "actor",
            "note",
            "loop",
            "alt",
            "else",
            "opt",
            "par",
            "critical",
            "break",
        }
    )

    @staticmethod
    def _clean_name(name: str) -> str:
        """Clean a name for use in Mermaid diagram node IDs.

        Args:
            name: Name to clean

        Returns:
            Cleaned name safe for use as a Mermaid node ID
        """
        # Drop generic or call arguments, as in base classes like
        # "Getter[Headers]" or "NamedTuple('Url', [...])"
        clean = re.split(r"[\[(]", name, maxsplit=1)[0]
        # Replace any other character that is not valid in an identifier
        clean = re.sub(r"\W", "_", clean)
        # Collapse multiple consecutive underscores into single underscore
        # (e.g., "version___version" -> "version_version")
        clean = re.sub(r"_+", "_", clean)
        # Strip leading/trailing underscores (Mermaid can misinterpret these)
        clean = clean.strip("_")
        # Ensure ID doesn't start with a digit
        if clean and clean[0].isdigit():
            clean = "n" + clean
        # Handle Mermaid reserved keywords by adding suffix
        if clean.lower() in DiagramGenerator.MERMAID_RESERVED_WORDS:
            clean = clean + "_node"
        # Handle empty result
        if not clean:
            clean = "node"
        return clean

    def _append_truncation_note(
        self,
        diagram: list[str],
        nodes_added: int,
        entity_type: str = "nodes",
        diagram_type: str = "flowchart",
    ) -> None:
        """Append a truncation note if node limit was reached.

        Args:
            diagram: List of diagram lines
            nodes_added: Number of nodes added
            entity_type: Type of entities (nodes, classes, etc.)
            diagram_type: Type of diagram (flowchart or class)
        """
        if nodes_added >= self.max_nodes:
            diagram.append("")
            note_text = f"Diagram truncated: showing top {self.max_nodes} {entity_type}"
            if diagram_type == "class":
                # Class diagrams have no free-standing nodes, but do support
                # a diagram-level note
                diagram.append(f'    note "{note_text}"')
            else:
                # Flowchart/graph diagrams support node definitions
                diagram.append(f'    truncation_notice["{note_text}"]')

    def generate_class_diagram(self, analyses: Sequence[FileAnalysis]) -> str:
        """Generate a class diagram from file analyses.

        Args:
            analyses: List of file analyses

        Returns:
            Mermaid class diagram source

        Raises:
            DiagramGenerationError: If no classes are found or the diagram fails
                validation
        """
        if not analyses:
            raise DiagramGenerationError("No files to analyze")

        # Collect unique classes
        classes = {}  # Use dict to ensure uniqueness by name
        for analysis in analyses:
            for entity in analysis.entities:
                if entity.type == EntityType.CLASS:
                    clean_name = self._clean_name(entity.name)
                    if clean_name not in classes:
                        classes[clean_name] = entity

        if not classes:
            raise DiagramGenerationError("No classes found in analyzed files")

        # Start with class diagram declaration
        diagram_lines = ["classDiagram"]

        # First declare all classes and their members
        nodes_added = 0
        for clean_name, cls in classes.items():
            if nodes_added >= self.max_nodes:
                break

            # Add class declaration
            if cls.methods:
                # Class with methods
                diagram_lines.append(f"    class {clean_name} {{")
                # Method names are identifiers, so they need no escaping
                for method in cls.methods:
                    diagram_lines.append(f"        +{method}()")
                diagram_lines.append("    }")
            else:
                # Empty class
                diagram_lines.append(f"    class {clean_name}")

            nodes_added += 1

        # Add blank line before relationships
        if nodes_added > 0:
            diagram_lines.append("")

        # Add inheritance relationships
        # Include all parent classes even if not in diagram
        for clean_name, cls in classes.items():
            if cls.parent_class:
                clean_parent = self._clean_name(cls.parent_class)
                # Add relationship regardless of whether parent is in diagram
                diagram_lines.append(f"    {clean_name} --|> {clean_parent}")

        # Add truncation note if needed
        self._append_truncation_note(
            diagram_lines, nodes_added, "classes", diagram_type="class"
        )

        diagram = "\n".join(diagram_lines)

        # Validate before returning
        self._validate_diagram(diagram, DiagramType.CLASS)

        return diagram

    def generate_sequence_diagram(self, call_graph: CallGraph) -> str:
        """Generate a sequence diagram of the calls from the project's entry point.

        It starts at the function, outside test code, that reaches the most
        of the project, and draws the calls between classes, two levels deep,
        in the order they are made, each once, up to max_nodes calls. Calls to
        plain functions, and to the caller's own or inherited methods, are
        followed but not drawn; creating an instance is drawn but not
        followed. See sequence.py for the rules.

        Args:
            call_graph: The traced calls

        Returns:
            Mermaid sequence diagram source

        Raises:
            DiagramGenerationError: If no function calls another in the
                project, or the diagram fails validation
        """
        plan = plan_sequence(call_graph, self.max_nodes)
        if plan is None:
            raise DiagramGenerationError("No calls found between project functions")

        participants = [plan.start]
        lines: list[str] = []

        def add(messages: tuple[Message, ...]) -> None:
            for message in messages:
                if message.receiver not in participants:
                    participants.append(message.receiver)
                sender = self._clean_name(message.sender)
                receiver = self._clean_name(message.receiver)
                if not message.nested:
                    lines.append(f"    {sender}->>{receiver}: {message.label}")
                    continue
                lines.append(f"    {sender}->>+{receiver}: {message.label}")
                add(message.nested)
                lines.append(f"    deactivate {receiver}")

        add(plan.messages)
        labels = self._participant_labels(participants, call_graph)
        diagram = ["sequenceDiagram"]
        diagram.extend(
            f"    participant {self._clean_name(name)} as {labels[name]}"
            for name in participants
        )
        diagram.extend(lines)
        if plan.truncated:
            diagram.append(
                f"    Note over {self._clean_name(plan.start)}: Diagram truncated: "
                f"showing the first {self.max_nodes} calls"
            )

        diagram_content = "\n".join(diagram)

        # Validate before returning
        self._validate_diagram(diagram_content, DiagramType.SEQUENCE)

        return diagram_content

    @staticmethod
    def _participant_labels(
        participants: list[str], call_graph: CallGraph
    ) -> dict[str, str]:
        """Short names for participants, full ones where short ones clash.

        A class or module is named by its last part, and a function by its
        name within its module.
        """

        def short(name: str) -> str:
            if name in call_graph.classes or name in call_graph.modules:
                return name.rpartition(".")[2]
            module = longest_prefix(name, call_graph.modules.__contains__)
            return name[len(module) + 1 :] if module else name

        labels = {name: short(name) for name in participants}
        counts = Counter(labels.values())
        return {
            name: label if counts[label] == 1 else name
            for name, label in labels.items()
        }

    def generate_dependency_diagram(self, dependencies: dict[str, set[str]]) -> str:
        """Generate a dependency diagram between packages.

        The project's packages come first, then the third-party packages they
        use, in a group of their own. When there are more than max_nodes, the
        packages with the most links are kept.

        Args:
            dependencies: Each project package, mapped to the packages it
                imports; a name that is not a key is a third-party package

        Returns:
            Mermaid graph diagram source

        Raises:
            DiagramGenerationError: If there are no packages, or the diagram
                fails validation
        """
        if not dependencies:
            raise DiagramGenerationError("No dependencies to analyze")

        internal = set(dependencies)
        external = {dep for deps in dependencies.values() for dep in deps} - internal
        edges = {
            (package, dep) for package, deps in dependencies.items() for dep in deps
        }
        shown = self._most_connected(internal | external, edges)

        diagram = ["graph LR"]
        diagram.extend(self._node_line(name) for name in sorted(internal & shown))
        third_party = sorted(external & shown)
        if third_party:
            diagram.append(
                f'    subgraph {self._group_id("third_party")}["Third-party packages"]'
            )
            diagram.extend(f"    {self._node_line(name)}" for name in third_party)
            diagram.append("    end")
        diagram.extend(
            f"    {self._clean_name(source)} --> {self._clean_name(target)}"
            for source, target in sorted(edges)
            if source in shown and target in shown
        )
        if len(shown) < len(internal | external):
            self._append_truncation_note(diagram, len(shown))

        diagram_content = "\n".join(diagram)

        # Validate before returning
        self._validate_diagram(diagram_content, DiagramType.DEPENDENCY)

        return diagram_content

    def _most_connected(self, nodes: set[str], edges: set[tuple[str, str]]) -> set[str]:
        """The max_nodes nodes with the most edges, ties broken by name."""
        links = dict.fromkeys(nodes, 0)
        for source, target in edges:
            links[source] += 1
            links[target] += 1
        ranked = sorted(nodes, key=lambda node: (-links[node], node))
        return set(ranked[: self.max_nodes])

    def _group_id(self, name: str) -> str:
        """A subgraph ID for a group. Node IDs never contain "__", so it is unique."""
        return f"{self._clean_name(name)}__group"

    def _node_line(self, name: str, label: str | None = None) -> str:
        """A node definition, labeled with the name unless a label is given."""
        text = (name if label is None else label).replace('"', "'")
        return f'    {self._clean_name(name)}["{text}"]'

    def generate_call_graph_diagram(self, call_graph: CallGraph) -> str:
        """Generate a call graph of the calls between the project's functions.

        Only calls the analyzer traced to the analyzed code are drawn. Those
        callees have qualified names; a call to a built-in or a library keeps
        its bare name and is left out, as is a function with no drawn calls.
        Functions are grouped by module and named within it. When there are
        more than max_nodes, the most connected are kept.

        Args:
            call_graph: The traced calls, and the modules to group them by

        Returns:
            Mermaid graph diagram markup

        Raises:
            DiagramGenerationError: If the diagram fails validation
        """
        edges = {
            (caller, callee)
            for caller, callees in call_graph.calls.items()
            for callee in callees
            if "." in callee
        }
        if not edges:
            return 'graph TD\n    note["No calls found between project functions"]'

        functions = {name for edge in edges for name in edge}
        shown = self._most_connected(functions, edges)

        groups: dict[str, list[str]] = defaultdict(list)
        for function in sorted(shown):
            module = longest_prefix(function, call_graph.modules.__contains__)
            groups[module or ""].append(function)

        diagram = ["graph TD"]
        for module in sorted(groups):
            members = groups[module]
            if not module:
                diagram.extend(self._node_line(function) for function in members)
                continue
            diagram.append(f'    subgraph {self._group_id(module)}["{module}"]')
            for function in members:
                label = function[len(module) + 1 :]
                diagram.append(f"    {self._node_line(function, label)}")
            diagram.append("    end")
        diagram.extend(
            f"    {self._clean_name(caller)} --> {self._clean_name(callee)}"
            for caller, callee in sorted(edges)
            if caller in shown and callee in shown
        )
        if len(shown) < len(functions):
            self._append_truncation_note(diagram, len(shown))

        diagram_content = "\n".join(diagram)

        # Validate before returning
        self._validate_diagram(diagram_content, DiagramType.CALL_GRAPH)

        return diagram_content

    def generate_architecture_diagram(self, module_imports: dict[str, set[str]]) -> str:
        """Generate an architecture diagram of the project's modules.

        Each module sits in a group for its package and is named within it; a
        package's own __init__ module is named __init__. Edges are imports
        between the modules. When there are more than max_nodes modules, the
        most connected are kept.

        Args:
            module_imports: Each project module, mapped to the project modules
                it imports

        Returns:
            Mermaid graph diagram markup

        Raises:
            DiagramGenerationError: If the diagram fails validation
        """
        if not module_imports:
            return 'graph TD\n    note["No files to analyze"]'

        modules = set(module_imports)
        edges = {
            (module, imported)
            for module, imports in module_imports.items()
            for imported in imports
            if imported in modules
        }
        shown = self._most_connected(modules, edges)

        # A module that other modules sit inside is a package's __init__
        packages = {
            module
            for module in modules
            if any(m.startswith(f"{module}.") for m in modules)
        }
        groups: dict[str, list[str]] = defaultdict(list)
        for module in sorted(shown):
            package = module if module in packages else module.rpartition(".")[0]
            groups[package].append(module)

        diagram = ["graph TD"]
        for package in sorted(groups):
            members = groups[package]
            if not package:
                diagram.extend(self._node_line(module) for module in members)
                continue
            diagram.append(f'    subgraph {self._group_id(package)}["{package}"]')
            for module in members:
                label = module[len(package) + 1 :] if module != package else "__init__"
                diagram.append(f"    {self._node_line(module, label)}")
            diagram.append("    end")
        diagram.extend(
            f"    {self._clean_name(source)} --> {self._clean_name(target)}"
            for source, target in sorted(edges)
            if source in shown and target in shown
        )
        if len(shown) < len(modules):
            self._append_truncation_note(diagram, len(shown))

        diagram_content = "\n".join(diagram)

        # Validate before returning
        self._validate_diagram(diagram_content, DiagramType.ARCHITECTURE)

        return diagram_content
