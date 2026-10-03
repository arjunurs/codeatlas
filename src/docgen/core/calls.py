"""Tracing calls to the functions and classes in the analyzed code.

A call is named by what it reaches, as pkg.module.func or
pkg.module.Class.method, when it can be traced there; any other call keeps
its bare name.
"""

from __future__ import annotations

import ast
from collections.abc import Sequence
from dataclasses import dataclass

from .modules import STDLIB_MODULES, import_base, unique_suffixes


def trace_calls(
    modules: Sequence[tuple[str, bool, ast.Module]],
) -> dict[str, list[str]]:
    """Map each function and method in the modules to the calls it makes.

    Args:
        modules: Each module's dotted name, whether it is a package
            __init__, and its AST

    Returns:
        Each qualified function name, mapped to the calls it makes, in order
    """
    definitions = [
        (_ModuleDefinitions.from_tree(name, is_package, tree), tree)
        for name, is_package, tree in modules
    ]
    resolver = _CallResolver([module for module, _ in definitions])
    call_graph: dict[str, list[str]] = {}
    for module, tree in definitions:
        visitor = _CallVisitor(module, resolver)
        visitor.visit(tree)
        call_graph.update(visitor.calls)
    return call_graph


_FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)


@dataclass
class _ModuleDefinitions:
    """What a module defines and imports, for resolving the calls made in it.

    Attributes:
        name: Dotted module name
        functions: Names of the module's top-level functions
        classes: Each top-level class's name, mapped to its method names
        imports: Each imported name, mapped to the qualified name it refers to
    """

    name: str
    functions: set[str]
    classes: dict[str, set[str]]
    imports: dict[str, str]

    @classmethod
    def from_tree(
        cls, name: str, is_package: bool, tree: ast.Module
    ) -> _ModuleDefinitions:
        """Collect a module's definitions and imports from its AST."""
        functions = {
            node.name for node in tree.body if isinstance(node, _FUNCTION_NODES)
        }
        classes = {
            node.name: {
                item.name for item in node.body if isinstance(item, _FUNCTION_NODES)
            }
            for node in tree.body
            if isinstance(node, ast.ClassDef)
        }
        imports: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.asname:
                        imports[alias.asname] = alias.name
                    else:
                        top_level = alias.name.split(".")[0]
                        imports[top_level] = top_level
            elif isinstance(node, ast.ImportFrom):
                base = import_base(name, is_package, node.module, node.level)
                if base is None:
                    continue
                for alias in node.names:
                    if alias.name != "*":
                        target = f"{base}.{alias.name}" if base else alias.name
                        imports[alias.asname or alias.name] = target
        return cls(name, functions, classes, imports)


class _CallResolver:
    """Traces a call to the function or class in the analyzed code it reaches."""

    def __init__(self, modules: list[_ModuleDefinitions]) -> None:
        self._known: set[str] = set()
        for module in modules:
            self._known.add(module.name)
            self._known.update(f"{module.name}.{name}" for name in module.functions)
            for class_name, methods in module.classes.items():
                qualified = f"{module.name}.{class_name}"
                self._known.add(qualified)
                self._known.update(f"{qualified}.{method}" for method in methods)
        self._by_suffix = unique_suffixes(self._known)

    def resolve(
        self, module: _ModuleDefinitions, class_name: str | None, func: ast.expr
    ) -> str | None:
        """Name the callee of a call, qualified when it can be traced.

        Args:
            module: The module the call is made in
            class_name: The class whose method makes the call, if any
            func: The call's func expression

        Returns:
            The qualified or bare callee name, or None for a call through an
            expression with no name, such as f()()
        """
        if isinstance(func, ast.Name):
            return self._owner(module, func.id) or func.id
        if not isinstance(func, ast.Attribute):
            return None
        if isinstance(func.value, ast.Name):
            receiver = func.value.id
            methods = module.classes.get(class_name, set()) if class_name else set()
            if receiver in ("self", "cls") and func.attr in methods:
                return f"{module.name}.{class_name}.{func.attr}"
            owner = self._owner(module, receiver)
            if owner and f"{owner}.{func.attr}" in self._known:
                return f"{owner}.{func.attr}"
        return func.attr

    def _owner(self, module: _ModuleDefinitions, name: str) -> str | None:
        """The known function, class, or module a name refers to in a module."""
        if name in module.functions or name in module.classes:
            return f"{module.name}.{name}"
        target = module.imports.get(name)
        if target is None:
            return None
        if target in self._known:
            return target
        if target.split(".")[0] in STDLIB_MODULES:
            return None
        return self._by_suffix.get(target)


class _CallVisitor(ast.NodeVisitor):
    """Records the calls each function in one module makes, in order."""

    def __init__(self, module: _ModuleDefinitions, resolver: _CallResolver) -> None:
        self.calls: dict[str, list[str]] = {}
        self._module = module
        self._resolver = resolver
        self._scope = [module.name]
        self._class: str | None = None
        self._function: str | None = None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit a class, so its methods are named after it."""
        previous_class = self._class
        # Only top-level classes are indexed, so self.x() resolves only there
        self._class = node.name if len(self._scope) == 1 else None
        self._scope.append(node.name)
        self.generic_visit(node)
        self._scope.pop()
        self._class = previous_class

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """Visit a function, recording the calls in its body under its name."""
        previous_function = self._function
        self._function = ".".join([*self._scope, node.name])
        self.calls[self._function] = []
        self._scope.append(node.name)
        for child in node.body:
            self.visit(child)
        self._scope.pop()
        self._function = previous_function

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit an async function definition like a plain one."""
        self.visit_FunctionDef(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Record a call made inside a function, after the calls in its parts."""
        # The callee expression and the arguments are evaluated first
        self.generic_visit(node)
        if self._function is not None:
            callee = self._resolver.resolve(self._module, self._class, node.func)
            calls = self.calls[self._function]
            if callee and callee not in calls:
                calls.append(callee)
