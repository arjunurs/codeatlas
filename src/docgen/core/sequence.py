"""Planning the sequence diagram: where it starts and which calls it draws.

The diagram starts at the function, outside test code, that reaches the most
of the project's code, and follows the calls it makes between the project's
classes. A call to a plain function, or to a method of the same class or one
it inherits from, is not drawn: the walk goes into it, so the calls it makes
are drawn from the caller.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum

from ..models.call_graph import CallGraph
from .modules import longest_prefix

# Levels of calls drawn below the entry point: its own, and the ones they make
DEPTH = 2

_TEST_MODULES = frozenset({"conftest", "test", "tests"})


class Participants(Enum):
    """What the diagram's participants are.

    Classes, unless the entry point reaches no class; then modules, unless
    all it reaches is in one module; then functions.
    """

    CLASSES = "classes"
    MODULES = "modules"
    FUNCTIONS = "functions"


@dataclass(frozen=True)
class Message:
    """One call drawn in the sequence diagram.

    Attributes:
        sender: The participant making the call
        receiver: The participant called
        label: What is called, as in load() or, for a constructor, Store()
        nested: The calls the receiver makes while handling this one
    """

    sender: str
    receiver: str
    label: str
    nested: tuple[Message, ...] = ()


@dataclass(frozen=True)
class SequencePlan:
    """What a sequence diagram draws.

    Attributes:
        entry: The function the diagram starts at
        start: The participant that runs it
        participants: What the participants are
        messages: The calls drawn, in the order they are made
        truncated: Whether calls were left out to keep within the limit
    """

    entry: str
    start: str
    participants: Participants
    messages: tuple[Message, ...]
    truncated: bool


def plan_sequence(graph: CallGraph, max_messages: int) -> SequencePlan | None:
    """Plan the sequence diagram for a call graph.

    Args:
        graph: The call graph
        max_messages: The most calls to draw

    Returns:
        The plan, or None when no function calls another in the project
    """
    entry = choose_entry(graph)
    if entry is None:
        return None
    for participants in (Participants.CLASSES, Participants.MODULES):
        plan = _Planner(graph, participants, max_messages).plan(entry)
        if plan.messages:
            return plan
    # Every function is its own participant, so the entry's calls are drawn
    return _Planner(graph, Participants.FUNCTIONS, max_messages).plan(entry)


def choose_entry(graph: CallGraph) -> str | None:
    """The function, outside test code, that reaches the most of the project.

    Only a function that nothing outside test code calls is considered. A
    call to a class reaches its __init__. Ties go to the first name in
    sorted order.

    Args:
        graph: The call graph

    Returns:
        The entry point, or None when no function reaches another
    """
    callees = {function: list(_reached(graph, function)) for function in graph.calls}
    called = {
        callee
        for caller, reached in callees.items()
        if not _is_test(caller)
        for callee in reached
    }
    entry, most = None, 0
    for function in sorted(graph.calls):
        if function in called or _is_test(function):
            continue
        reach = _reach(function, callees)
        if reach > most:
            entry, most = function, reach
    return entry


def _reached(graph: CallGraph, function: str) -> Iterator[str]:
    """The analyzed functions a function's traced calls run."""
    for callee in graph.calls[function]:
        if callee in graph.classes:
            init = _method(graph, callee, "__init__")
            if init:
                yield init
        elif callee in graph.calls:
            yield callee


def _reach(function: str, callees: dict[str, list[str]]) -> int:
    """How many other functions a function reaches, directly or not."""
    seen = {function}
    pending = [function]
    while pending:
        for callee in callees[pending.pop()]:
            if callee not in seen:
                seen.add(callee)
                pending.append(callee)
    return len(seen) - 1


def _method(graph: CallGraph, class_name: str, name: str) -> str | None:
    """The method a class runs for a name, its own or one it inherits."""
    for current in [class_name, *graph.classes[class_name]]:
        method = f"{current}.{name}"
        if method in graph.calls:
            return method
    return None


def _is_test(function: str) -> bool:
    """Whether a function is test code: in a test module, or a test itself."""
    return any(
        part in _TEST_MODULES or part.startswith("test_")
        for part in function.split(".")
    )


class _Planner:
    """Walks the calls from the entry point, deciding which to draw."""

    def __init__(
        self, graph: CallGraph, participants: Participants, max_messages: int
    ) -> None:
        self._graph = graph
        self._participants = participants
        self._max_messages = max_messages
        self._drawn: set[tuple[str, str, str]] = set()
        self._walked: set[tuple[str, str, int]] = set()
        self._truncated = False

    def plan(self, entry: str) -> SequencePlan:
        """Plan the diagram that starts at an entry point."""
        start = self._participant(entry) or self._module(entry) or entry
        messages = self._walk(entry, start, 1, frozenset({entry}))
        return SequencePlan(
            entry, start, self._participants, tuple(messages), self._truncated
        )

    def _walk(
        self, function: str, participant: str, level: int, stack: frozenset[str]
    ) -> list[Message]:
        """The calls a participant makes while running a function.

        Args:
            function: The function being run
            participant: The participant running it
            level: How many drawn calls led here, the entry point's being 1
            stack: The functions being run, so recursion ends

        Returns:
            The calls to draw, in order
        """
        if (function, participant, level) in self._walked:
            return []
        self._walked.add((function, participant, level))
        messages: list[Message] = []
        for callee in self._graph.calls[function]:
            if self._truncated:
                break
            if callee in self._graph.classes:
                message = self._construct(callee, participant)
                if message:
                    messages.append(message)
                continue
            if callee not in self._graph.calls:
                continue
            receiver = self._participant(callee)
            if receiver is None or self._is_self(receiver, participant):
                if callee not in stack:
                    messages.extend(
                        self._walk(callee, participant, level, stack | {callee})
                    )
                continue
            label = f"{callee.rpartition('.')[2]}()"
            if not self._draw(participant, receiver, label):
                continue
            nested: list[Message] = []
            if level < DEPTH and callee not in stack:
                nested = self._walk(callee, receiver, level + 1, stack | {callee})
            messages.append(Message(participant, receiver, label, tuple(nested)))
        return messages

    def _construct(self, class_name: str, participant: str) -> Message | None:
        """The message for creating an instance, which is drawn but not followed.

        A class with no __init__ of its own or inherited in the analyzed code,
        such as a dataclass or an exception, holds data rather than taking
        part, so creating one is not drawn; nor is creating one's own kind.
        """
        if _method(self._graph, class_name, "__init__") is None:
            return None
        receiver = (
            self._module(class_name)
            if self._participants is Participants.MODULES
            else class_name
        )
        if receiver is None or self._is_self(receiver, participant):
            return None
        label = f"{class_name.rpartition('.')[2]}()"
        if not self._draw(participant, receiver, label):
            return None
        return Message(participant, receiver, label)

    def _draw(self, sender: str, receiver: str, label: str) -> bool:
        """Whether to draw a call: each is drawn once, up to the limit."""
        if (sender, receiver, label) in self._drawn:
            return False
        if len(self._drawn) >= self._max_messages:
            self._truncated = True
            return False
        self._drawn.add((sender, receiver, label))
        return True

    def _participant(self, function: str) -> str | None:
        """The participant that runs a function, or None if its caller does."""
        if self._participants is Participants.FUNCTIONS:
            return function
        if self._participants is Participants.MODULES:
            return self._module(function)
        owner = function.rpartition(".")[0]
        return owner if owner in self._graph.classes else None

    def _is_self(self, receiver: str, participant: str) -> bool:
        """Whether a call to a participant stays with the caller.

        That is the same participant, or, between classes, one the caller
        inherits from: its methods run on the caller's own instance.
        """
        return receiver == participant or receiver in self._graph.classes.get(
            participant, ()
        )

    def _module(self, name: str) -> str | None:
        """The analyzed module a function or class is in."""
        return longest_prefix(name, self._graph.modules.__contains__)
