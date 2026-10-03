"""Unit tests for the DiagramGenerator class.

This module contains comprehensive tests for diagram generation functionality,
including architecture, class, sequence, dependency, and function call diagrams.
"""

from unittest.mock import MagicMock

import pytest

from docgen.core.diagrams import DiagramGenerator, select_diagrams
from docgen.exceptions.errors import DiagramGenerationError, DiagramValidationError
from docgen.models.call_graph import CallGraph
from docgen.models.code_entity import CodeEntity, EntityType
from docgen.models.diagram_validation import DiagramType
from docgen.models.file_analysis import FileAnalysis
from docgen.utils.diagram_validator import DiagramValidator


@pytest.fixture
def diagram_generator():
    """Create a DiagramGenerator instance for testing."""
    # Disable validation for tests to avoid issues with synthetic test data
    return DiagramGenerator(validate_diagrams=False)


@pytest.fixture
def sample_analyses():
    """Create sample FileAnalysis objects for testing."""
    return [
        FileAnalysis(
            file_path="/path/to/module1.py",
            entities=[
                CodeEntity(
                    name="Class1",
                    docstring="First test class",
                    type=EntityType.CLASS,
                    methods=["method1", "method2"],
                    start_line=1,
                    end_line=5,
                    source="class Class1:\n    def method1(self):\n        pass\n    def method2(self):\n        pass",
                    parent_class="BaseClass",
                ),
                CodeEntity(
                    name="function1",
                    docstring="First test function",
                    type=EntityType.FUNCTION,
                    start_line=10,
                    end_line=12,
                    source="def function1():\n    pass",
                ),
            ],
            imports=["os", "module2.Class2"],
            content="",
            _skip_validation=True,
        ),
        FileAnalysis(
            file_path="/path/to/module2.py",
            entities=[
                CodeEntity(
                    name="Class2",
                    docstring="Second test class",
                    type=EntityType.CLASS,
                    methods=["method3"],
                    start_line=1,
                    end_line=3,
                    source="class Class2:\n    def method3(self):\n        pass",
                )
            ],
            imports=["module1.Class1"],
            content="",
            _skip_validation=True,
        ),
    ]


def test_architecture_diagram_groups_modules_by_package(diagram_generator):
    """Modules sit in their package, named within it; a package's own module is __init__."""
    module_imports = {
        "shop.payments.gateway": {"shop"},
        "shop.orders": {"shop.payments.gateway"},
        "shop.cli": {"shop.orders", "shop"},
        "shop": set(),
        "shop.payments": set(),
        "main": {"shop.cli"},
    }

    diagram = diagram_generator.generate_architecture_diagram(module_imports)

    assert diagram == "\n".join(
        [
            "graph TD",
            '    main["main"]',
            '    subgraph shop__group["shop"]',
            '        shop["__init__"]',
            '        shop_cli["cli"]',
            '        shop_orders["orders"]',
            "    end",
            '    subgraph shop_payments__group["shop.payments"]',
            '        shop_payments["__init__"]',
            '        shop_payments_gateway["gateway"]',
            "    end",
            "    main --> shop_cli",
            "    shop_cli --> shop",
            "    shop_cli --> shop_orders",
            "    shop_orders --> shop_payments_gateway",
            "    shop_payments_gateway --> shop",
        ]
    )


def test_architecture_diagram_keeps_the_most_connected_modules():
    """When there are too many modules, the most linked ones are kept."""
    generator = DiagramGenerator(max_nodes=2, validate_diagrams=False)
    module_imports = {"app.a": {"app.core"}, "app.b": {"app.core"}, "app.core": set()}

    diagram = generator.generate_architecture_diagram(module_imports)

    assert 'app_core["core"]' in diagram and 'app_a["a"]' in diagram
    assert 'app_b["b"]' not in diagram
    assert "Diagram truncated: showing top 2 nodes" in diagram


def test_architecture_diagram_without_modules_says_so(diagram_generator):
    """No analyzed modules gives a one-note diagram."""
    assert diagram_generator.generate_architecture_diagram({}) == (
        'graph TD\n    note["No files to analyze"]'
    )


def test_generate_class_diagram(diagram_generator, sample_analyses):
    """Test class diagram generation."""
    diagram = diagram_generator.generate_class_diagram(sample_analyses)

    # Verify diagram structure
    assert diagram.startswith("classDiagram")
    assert "class Class1" in diagram
    assert "class Class2" in diagram
    assert "Class1 --|> BaseClass" in diagram
    assert "+method1()" in diagram
    assert "+method2()" in diagram
    assert "+method3()" in diagram


SHOP_CALLS = CallGraph(
    calls={
        "shop.cli.main": [
            "shop.cli.parse",
            "shop.store.Store",
            "shop.store.Store.load",
            "print",
        ],
        "shop.cli.parse": ["shop.store.Store.check"],
        "shop.store.Store.__init__": [],
        "shop.store.Store.load": ["shop.store.Store.read", "shop.db.Db.query"],
        "shop.store.Store.read": [],
        "shop.store.Store.check": [],
        "shop.db.Db.query": [],
    },
    classes={"shop.store.Store": [], "shop.db.Db": []},
    modules=frozenset({"shop", "shop.cli", "shop.store", "shop.db"}),
)


def test_sequence_diagram_draws_calls_between_classes_from_the_entry():
    """Participants are declared by short name; nested calls are activations."""
    diagram = diagram_generator_with_validation().generate_sequence_diagram(SHOP_CALLS)

    assert diagram == "\n".join(
        [
            "sequenceDiagram",
            "    participant shop_cli as cli",
            "    participant shop_store_Store as Store",
            "    participant shop_db_Db as Db",
            "    shop_cli->>shop_store_Store: check()",
            "    shop_cli->>shop_store_Store: Store()",
            "    shop_cli->>+shop_store_Store: load()",
            "    shop_store_Store->>shop_db_Db: query()",
            "    deactivate shop_store_Store",
        ]
    )
    result = DiagramValidator().validate(diagram, DiagramType.SEQUENCE)
    assert result.is_valid
    assert result.warnings == []


def diagram_generator_with_validation(max_nodes: int = 50) -> DiagramGenerator:
    """A diagram generator that validates what it generates."""
    return DiagramGenerator(max_nodes=max_nodes, validate_diagrams=True)


def test_sequence_diagram_notes_when_calls_are_left_out():
    """Past max_nodes calls, a note on the entry's participant says so."""
    diagram = diagram_generator_with_validation(2).generate_sequence_diagram(SHOP_CALLS)

    assert diagram.splitlines()[-3:] == [
        "    shop_cli->>shop_store_Store: check()",
        "    shop_cli->>shop_store_Store: Store()",
        "    Note over shop_cli: Diagram truncated: showing the first 2 calls",
    ]


def test_sequence_diagram_names_clashing_participants_in_full(diagram_generator):
    """Two classes with the same name are told apart by their full names."""
    call_graph = CallGraph(
        calls={
            "app.main": ["a.Store.save", "b.Store.save"],
            "a.Store.save": [],
            "b.Store.save": [],
        },
        classes={"a.Store": [], "b.Store": []},
        modules=frozenset({"app", "a", "b"}),
    )

    diagram = diagram_generator.generate_sequence_diagram(call_graph)

    assert diagram.splitlines()[1:4] == [
        "    participant app as app",
        "    participant a_Store as a.Store",
        "    participant b_Store as b.Store",
    ]


def test_sequence_diagram_names_functions_within_their_module(diagram_generator):
    """When functions take part, each is named within its module."""
    call_graph = CallGraph(
        calls={"app.cli.main": ["app.cli.load"], "app.cli.load": []},
        modules=frozenset({"app", "app.cli"}),
    )

    diagram = diagram_generator.generate_sequence_diagram(call_graph)

    assert diagram.splitlines() == [
        "sequenceDiagram",
        "    participant app_cli_main as main",
        "    participant app_cli_load as load",
        "    app_cli_main->>app_cli_load: load()",
    ]


def test_generate_dependency_diagram(diagram_generator):
    """Test dependency diagram generation."""
    dependencies = {"package1": {"dep1", "dep2"}, "package2": {"dep3"}}

    diagram = diagram_generator.generate_dependency_diagram(dependencies)

    # Verify diagram structure
    assert diagram.startswith("graph LR")
    assert 'package1["package1"]' in diagram
    assert 'dep1["dep1"]' in diagram
    assert "package1 --> dep1" in diagram


def test_call_graph_shows_calls_between_project_functions(diagram_generator):
    """Calls the analyzer traced are drawn, grouped by module; the rest are left out."""
    call_graph = CallGraph(
        calls={
            "app.cli.main": ["app.core.run", "print", "app.core.Config"],
            "app.core.run": ["app.core.Config.load", "len"],
            "app.core.Config.load": [],
            "app.core.unused": ["print"],
        },
        modules=frozenset({"app", "app.cli", "app.core"}),
    )

    diagram = diagram_generator.generate_call_graph_diagram(call_graph)

    assert diagram == "\n".join(
        [
            "graph TD",
            '    subgraph app_cli__group["app.cli"]',
            '        app_cli_main["main"]',
            "    end",
            '    subgraph app_core__group["app.core"]',
            '        app_core_Config["Config"]',
            '        app_core_Config_load["Config.load"]',
            '        app_core_run["run"]',
            "    end",
            "    app_cli_main --> app_core_Config",
            "    app_cli_main --> app_core_run",
            "    app_core_run --> app_core_Config_load",
        ]
    )


def test_call_graph_without_modules_uses_full_names(diagram_generator):
    """Without module names to group by, each function keeps its full name."""
    diagram = diagram_generator.generate_call_graph_diagram(
        CallGraph(calls={"a.f": ["a.g"]})
    )

    assert diagram == 'graph TD\n    a_f["a.f"]\n    a_g["a.g"]\n    a_f --> a_g'


def test_call_graph_without_project_calls_says_so(diagram_generator):
    """Only calls to built-ins and libraries gives a one-note diagram."""
    diagram = diagram_generator.generate_call_graph_diagram(
        CallGraph(calls={"app.main": ["print"]})
    )

    assert diagram == 'graph TD\n    note["No calls found between project functions"]'


def test_generate_call_graph_diagram_with_limit(diagram_generator):
    """Test function call graph diagram with node limit."""
    # Create more than MAX_NODES functions
    call_graph = CallGraph(calls={f"m.func{i}": [f"m.func{i + 1}"] for i in range(100)})

    diagram = diagram_generator.generate_call_graph_diagram(call_graph)

    # Verify diagram respects node limit
    assert "Diagram truncated: showing top" in diagram
    # Each function appears once in node definition and once in edge
    node_count = sum(
        1 for line in diagram.split("\n") if line.strip().startswith("m_func")
    )
    assert node_count <= diagram_generator.max_nodes * 2


def test_dependency_diagram_groups_third_party_packages(diagram_generator):
    """Project packages come first; packages they use from elsewhere are grouped."""
    dependencies = {
        "shop.payments": {"stripe", "shop"},
        "shop": {"shop.payments", "requests"},
    }

    diagram = diagram_generator.generate_dependency_diagram(dependencies)

    assert diagram == "\n".join(
        [
            "graph LR",
            '    shop["shop"]',
            '    shop_payments["shop.payments"]',
            '    subgraph third_party__group["Third-party packages"]',
            '        requests["requests"]',
            '        stripe["stripe"]',
            "    end",
            "    shop --> requests",
            "    shop --> shop_payments",
            "    shop_payments --> shop",
            "    shop_payments --> stripe",
        ]
    )


def test_dependency_diagram_keeps_the_most_connected_packages():
    """When there are too many, the packages most linked to the rest are kept."""
    generator = DiagramGenerator(max_nodes=3, validate_diagrams=False)
    dependencies = {"a": {"hub"}, "b": {"hub"}, "c": {"hub"}, "hub": set(), "d": set()}

    diagram = generator.generate_dependency_diagram(dependencies)

    assert 'hub["hub"]' in diagram
    assert 'a["a"]' in diagram and 'b["b"]' in diagram
    assert 'c["c"]' not in diagram and 'd["d"]' not in diagram
    assert "c --> hub" not in diagram
    assert "Diagram truncated: showing top 3 nodes" in diagram


def test_clean_names_in_diagrams(diagram_generator):
    """Test name cleaning in diagrams."""
    dependencies = {"package-name": {"dep.name", "@scope/name"}}

    diagram = diagram_generator.generate_dependency_diagram(dependencies)

    # Verify special characters are handled - node IDs are cleaned, labels are quoted
    assert 'package_name["package-name"]' in diagram
    assert 'dep_name["dep.name"]' in diagram
    assert 'scope_name["@scope/name"]' in diagram


def test_empty_inputs(diagram_generator):
    """Test diagram generation with empty inputs."""
    # Empty analyses
    with pytest.raises(DiagramGenerationError, match="No files to analyze"):
        diagram_generator.generate_class_diagram([])

    # Empty dependencies
    with pytest.raises(DiagramGenerationError, match="No dependencies to analyze"):
        diagram_generator.generate_dependency_diagram({})

    # Empty call graph
    with pytest.raises(
        DiagramGenerationError, match="No calls found between project functions"
    ):
        diagram_generator.generate_sequence_diagram(CallGraph(calls={}))


def test_diagram_generation_error_handling(diagram_generator):
    """Test error handling in diagram generation."""
    # Test with invalid dependencies
    with pytest.raises(DiagramGenerationError):
        diagram_generator.generate_dependency_diagram(None)

    # Test with a call graph whose calls reach no project function
    with pytest.raises(DiagramGenerationError):
        diagram_generator.generate_sequence_diagram(
            CallGraph(calls={"app.main": ["app.missing"]})
        )


@pytest.mark.parametrize(
    ("builder", "diagram_type", "make_input"),
    [
        ("generate_class_diagram", "class", lambda analyses: analyses),
        (
            "generate_architecture_diagram",
            "architecture",
            lambda _: {"app": {"util"}, "util": set()},
        ),
        (
            "generate_call_graph_diagram",
            "callgraph",
            lambda _: CallGraph(calls={"app.main": ["app.helper"]}),
        ),
        ("generate_sequence_diagram", "sequence", lambda _: SHOP_CALLS),
    ],
)
def test_validation_failure_is_reported_once(
    sample_analyses, builder, diagram_type, make_input
):
    """A diagram that fails validation says so once, without a second prefix."""
    generator = DiagramGenerator(validate_diagrams=True)
    generator.validator = MagicMock()
    generator.validator.validate.side_effect = DiagramValidationError("bad syntax")

    with pytest.raises(
        DiagramGenerationError,
        match=f"^Generated {diagram_type} diagram failed validation: bad syntax$",
    ):
        getattr(generator, builder)(make_input(sample_analyses))


def test_sequence_diagram_no_interactions(diagram_generator):
    """Calls only to built-ins and libraries leave no sequence to draw."""
    call_graph = CallGraph(calls={"app.main": ["print"], "app.run": []})

    with pytest.raises(
        DiagramGenerationError, match="No calls found between project functions"
    ):
        diagram_generator.generate_sequence_diagram(call_graph)


ALL_DIAGRAMS = ["architecture", "class", "sequence", "callgraph", "dependency"]


@pytest.mark.parametrize("selection", [None, [], [""], ["", " "]])
def test_no_diagram_selection_returns_all(selection):
    """Without a selection, every diagram type is generated."""
    assert select_diagrams(selection) == ALL_DIAGRAMS


@pytest.mark.parametrize(
    ("selection", "expected"),
    [
        (["class"], ["class"]),
        (["Class"], ["class"]),
        ([" CLASS "], ["class"]),
        (["class", ""], ["class"]),
        (["call_graph"], ["callgraph"]),
        (["call-graph"], ["callgraph"]),
        (["dependency", "architecture"], ["architecture", "dependency"]),
    ],
)
def test_diagram_selection_normalizes_names(selection, expected):
    """Names match case-insensitively, ignoring "_", "-", and blanks."""
    assert select_diagrams(selection) == expected


def test_unknown_diagram_raises_with_available_names():
    """A name that is not a diagram type is rejected, listing the valid names."""
    with pytest.raises(ValueError, match="Unknown diagram") as excinfo:
        select_diagrams(["class", "clas"])

    message = str(excinfo.value)
    assert "Unknown diagram(s): clas." in message
    assert "callgraph" in message


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("AbstractAsyncContextManager[_T]", "AbstractAsyncContextManager"),
        ("Getter[Headers]", "Getter"),
        ("Sequence[Tuple[bytes, bytes]]", "Sequence"),
        ("typing.NamedTuple('Url', [('scheme', str)])", "typing_NamedTuple"),
        ("my pkg:mod", "my_pkg_mod"),
    ],
)
def test_clean_name_produces_identifier(name, expected):
    """Generic arguments and call arguments are dropped from node IDs."""
    assert DiagramGenerator._clean_name(name) == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        # Flowchart keywords
        ("linkStyle", "linkStyle_node"),
        ("classDef", "classDef_node"),
        ("flowchart", "flowchart_node"),
        ("href", "href_node"),
        # Class diagram keywords
        ("namespace", "namespace_node"),
        ("cssClass", "cssClass_node"),
        ("link", "link_node"),
        # Sequence keywords, which Mermaid matches in any case
        ("create", "create_node"),
        ("Note", "Note_node"),
        ("box", "box_node"),
        ("title", "title_node"),
        ("deactivate", "deactivate_node"),
        # Not keywords
        ("created", "created"),
        ("as", "as"),
    ],
)
def test_mermaid_keywords_are_not_used_as_ids(name, expected):
    """An ID Mermaid would read as a keyword gets a suffix, so the diagram parses."""
    assert DiagramGenerator._clean_name(name) == expected


def test_sequence_participant_named_like_a_keyword(diagram_generator):
    """A module named box takes part as box_node, still labeled box."""
    call_graph = CallGraph(
        calls={"app.main": ["box.pack"], "box.pack": []},
        modules=frozenset({"app", "box"}),
    )

    diagram = diagram_generator.generate_sequence_diagram(call_graph)

    assert diagram.splitlines() == [
        "sequenceDiagram",
        "    participant app as app",
        "    participant box_node as box",
        "    app->>box_node: pack()",
    ]


def test_class_diagram_handles_generic_base_classes(diagram_generator):
    """Generic base classes do not leak brackets into the class diagram."""
    analyses = [
        FileAnalysis(
            file_path="/path/to/context.py",
            entities=[
                CodeEntity(
                    name="AsyncLiftContextManager",
                    docstring="",
                    type=EntityType.CLASS,
                    parent_class="AbstractAsyncContextManager[_T]",
                ),
                CodeEntity(
                    name="HeadersGetter",
                    docstring="",
                    type=EntityType.CLASS,
                    parent_class="Getter[Headers]",
                ),
            ],
            imports=[],
            content="",
            _skip_validation=True,
        )
    ]

    diagram = diagram_generator.generate_class_diagram(analyses)

    assert "AsyncLiftContextManager --|> AbstractAsyncContextManager" in diagram
    assert "HeadersGetter --|> Getter" in diagram
    assert "[" not in diagram
