"""Call graph model for the documentation generator.

This module defines the CallGraph class: the calls between a codebase's
functions, as the call analysis traced them.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CallGraph:
    """The calls each function in the analyzed code makes.

    Functions are named by module path from the source root, as in
    pkg.module.func and pkg.module.Class.method. A call traced to the analyzed
    code is named the same way; any other call keeps its bare name.

    Attributes:
        calls: Each function and method, mapped to the calls it makes, in the
            order it makes them
        classes: Each analyzed class, mapped to its analyzed base classes in
            the order methods are looked up in them
        modules: The analyzed modules' names
    """

    calls: dict[str, list[str]]
    classes: dict[str, list[str]] = field(default_factory=dict)
    modules: frozenset[str] = frozenset()
