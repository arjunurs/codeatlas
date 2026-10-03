"""Unit tests for planning the sequence diagram."""

from docgen.core.sequence import (
    Message,
    Participants,
    choose_entry,
    plan_sequence,
)
from docgen.models.call_graph import CallGraph


def graph(
    calls: dict[str, list[str]],
    classes: dict[str, list[str]] | None = None,
    modules: tuple[str, ...] = (),
) -> CallGraph:
    """A call graph; modules default to each function's first part."""
    names = modules or tuple({name.split(".")[0] for name in calls})
    return CallGraph(calls=calls, classes=classes or {}, modules=frozenset(names))


def messages(call_graph: CallGraph, max_messages: int = 50) -> tuple[Message, ...]:
    """The planned messages, which must exist."""
    plan = plan_sequence(call_graph, max_messages)
    assert plan is not None
    return plan.messages


def test_entry_is_the_function_that_reaches_the_most():
    """Of the functions nothing calls, the one reaching most others wins."""
    call_graph = graph(
        {
            "a.main": ["a.run"],
            "a.run": ["a.step"],
            "a.step": [],
            "a.other": ["a.step"],
        }
    )

    assert choose_entry(call_graph) == "a.main"


def test_test_code_is_never_the_entry():
    """Tests reach the most code, but are not where the program starts."""
    call_graph = graph(
        {
            "tests.test_app.test_main": ["app.main", "app.run"],
            "conftest.fixture": ["app.main"],
            "app.check.test_main": ["app.main"],
            "app.main": ["app.run"],
            "app.run": [],
        }
    )

    assert choose_entry(call_graph) == "app.main"


def test_ties_go_to_the_first_name():
    """Two entry points that reach as much are decided by name."""
    call_graph = graph(
        {"b.main": ["b.run"], "b.run": [], "a.main": ["a.run"], "a.run": []}
    )

    assert choose_entry(call_graph) == "a.main"


def test_calling_a_class_reaches_its_init():
    """A constructor call counts what __init__ calls, and __init__ is not a root."""
    call_graph = graph(
        {
            "app.main": ["app.Store"],
            "app.Store.__init__": ["app.Db.connect", "app.Db.check"],
            "app.Db.connect": [],
            "app.Db.check": [],
            "app.other": ["app.Db.connect", "app.Db.check"],
        },
        classes={"app.Store": [], "app.Db": []},
    )

    assert choose_entry(call_graph) == "app.main"


def test_no_entry_without_calls_between_functions():
    """Only calls to built-ins and libraries leave nothing to draw."""
    call_graph = graph({"app.main": ["print"], "app.run": []})

    assert choose_entry(call_graph) is None
    assert plan_sequence(call_graph, 50) is None


def test_methods_of_other_classes_are_drawn_from_the_caller():
    """Plain functions are folded in: what they call is drawn from the caller."""
    call_graph = graph(
        {
            "app.cli.main": ["app.cli.parse", "print", "app.store.Store.load"],
            "app.cli.parse": ["app.store.Store.check"],
            "app.store.Store.load": [],
            "app.store.Store.check": [],
        },
        classes={"app.store.Store": []},
        modules=("app", "app.cli", "app.store"),
    )

    plan = plan_sequence(call_graph, 50)

    assert plan is not None
    assert (plan.entry, plan.start) == ("app.cli.main", "app.cli")
    assert plan.participants is Participants.CLASSES
    assert plan.messages == (
        Message("app.cli", "app.store.Store", "check()"),
        Message("app.cli", "app.store.Store", "load()"),
    )


def test_own_and_inherited_methods_are_folded():
    """A method called on the same instance is not drawn; what it calls is."""
    call_graph = graph(
        {
            "app.main": ["app.Child.run"],
            "app.Child.run": ["app.Child.helper", "app.Base.ping"],
            "app.Child.helper": ["app.Db.read"],
            "app.Base.ping": ["app.Db.query"],
            "app.Db.read": [],
            "app.Db.query": [],
        },
        classes={"app.Base": [], "app.Child": ["app.Base"], "app.Db": []},
    )

    assert messages(call_graph) == (
        Message(
            "app",
            "app.Child",
            "run()",
            (
                Message("app.Child", "app.Db", "read()"),
                Message("app.Child", "app.Db", "query()"),
            ),
        ),
    )


def test_constructors_are_drawn_but_not_followed():
    """Creating an instance is one message; what __init__ does is wiring."""
    call_graph = graph(
        {
            "app.main": [
                "app.Store",
                "app.Item",
                "app.Child",
                "app.Store.load",
                "app.helper",
            ],
            "app.helper": ["app.Store"],
            "app.Store.__init__": ["app.Db.connect"],
            "app.Store.load": ["app.Store"],
            "app.Base.__init__": [],
            "app.Db.connect": [],
        },
        classes={
            "app.Store": [],
            "app.Item": [],
            "app.Base": [],
            "app.Child": ["app.Base"],
            "app.Db": [],
        },
    )

    # Item has no __init__ (a dataclass, say); Child inherits Base's; Store
    # creating another Store is not drawn, nor is creating a Store again
    assert messages(call_graph) == (
        Message("app", "app.Store", "Store()"),
        Message("app", "app.Child", "Child()"),
        Message("app", "app.Store", "load()"),
    )


def test_calls_two_levels_below_the_entry_are_drawn_but_not_followed():
    """The entry's calls and the ones they make are drawn; deeper ones are not."""
    call_graph = graph(
        {
            "app.main": ["app.A.run"],
            "app.A.run": ["app.B.go"],
            "app.B.go": ["app.C.deep"],
            "app.C.deep": [],
        },
        classes={"app.A": [], "app.B": [], "app.C": []},
    )

    assert messages(call_graph) == (
        Message("app", "app.A", "run()", (Message("app.A", "app.B", "go()"),)),
    )


def test_each_call_is_drawn_once_and_recursion_ends():
    """A call reached again, or through recursion, is not drawn again."""
    call_graph = graph(
        {
            "app.main": ["app.A.run", "app.helper", "app.one", "app.two"],
            "app.helper": ["app.helper", "app.A.run", "app.missing.function"],
            "app.A.run": ["app.A.run"],
            "app.one": ["app.shared"],
            "app.two": ["app.shared"],
            "app.shared": ["app.A.stop"],
            "app.A.stop": [],
        },
        classes={"app.A": []},
    )

    assert messages(call_graph) == (
        Message("app", "app.A", "run()"),
        Message("app", "app.A", "stop()"),
    )


def test_the_limit_truncates_the_plan():
    """Past max_messages calls, the rest are left out and the plan says so."""
    call_graph = graph(
        {"app.main": ["app.A.one", "app.A.two"], "app.A.one": [], "app.A.two": []},
        classes={"app.A": []},
    )

    plan = plan_sequence(call_graph, 1)

    assert plan is not None
    assert plan.messages == (Message("app", "app.A", "one()"),)
    assert plan.truncated


def test_modules_take_part_when_no_class_is_reached():
    """A codebase of plain functions is drawn between its modules."""
    call_graph = graph(
        {
            "pkg.cli.main": ["pkg.util.tool", "pkg.cli.helper"],
            "pkg.cli.helper": [],
            "pkg.util.tool": ["pkg.db.run"],
            "pkg.db.run": [],
        },
        modules=("pkg", "pkg.cli", "pkg.util", "pkg.db"),
    )

    plan = plan_sequence(call_graph, 50)

    assert plan is not None
    assert plan.participants is Participants.MODULES
    assert plan.messages == (
        Message(
            "pkg.cli", "pkg.util", "tool()", (Message("pkg.util", "pkg.db", "run()"),)
        ),
    )


def test_modules_create_instances_of_their_classes():
    """With modules taking part, creating an instance is a call to its module."""
    # Child creating a Base is creating its own kind, so classes draw nothing
    call_graph = graph(
        {"pkg.child.Child.run": ["pkg.base.Base"], "pkg.base.Base.__init__": []},
        classes={"pkg.base.Base": [], "pkg.child.Child": ["pkg.base.Base"]},
        modules=("pkg", "pkg.base", "pkg.child"),
    )

    plan = plan_sequence(call_graph, 50)

    assert plan is not None
    assert plan.participants is Participants.MODULES
    assert plan.messages == (Message("pkg.child", "pkg.base", "Base()"),)


def test_functions_take_part_when_everything_is_in_one_module():
    """A one-module script is drawn between its functions."""
    call_graph = graph(
        {"app.main": ["app.load"], "app.load": ["app.parse"], "app.parse": []}
    )

    plan = plan_sequence(call_graph, 50)

    assert plan is not None
    assert plan.participants is Participants.FUNCTIONS
    assert plan.start == "app.main"
    assert plan.messages == (
        Message(
            "app.main",
            "app.load",
            "load()",
            (Message("app.load", "app.parse", "parse()"),),
        ),
    )
