"""Tracing calls to the functions and classes in the analyzed code.

A call is named by what it reaches, as pkg.module.func or
pkg.module.Class.method, when it can be traced there; any other call keeps
its bare name.
"""

from __future__ import annotations

import ast
from collections.abc import Collection, Iterator, Sequence
from dataclasses import dataclass, field

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
_SCOPE_NODES = (*_FUNCTION_NODES, ast.ClassDef, ast.Lambda)
_PROPERTY_DECORATORS = frozenset({"property", "cached_property"})
_UNION_TYPES = frozenset({"Optional", "Union"})

_FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef

# The class of each name bound in a function, or None when it is not known
_Types = dict[str, str | None]


@dataclass
class _ModuleDefinitions:
    """What a module defines and imports, for resolving the calls made in it.

    Attributes:
        name: Dotted module name
        functions: Each top-level function's name, mapped to its definition
        classes: Each top-level class's name, mapped to its definition
        imports: Each imported name, mapped to the qualified name it refers to
    """

    name: str
    functions: dict[str, _FunctionNode]
    classes: dict[str, ast.ClassDef]
    imports: dict[str, str]

    @classmethod
    def from_tree(
        cls, name: str, is_package: bool, tree: ast.Module
    ) -> _ModuleDefinitions:
        """Collect a module's definitions and imports from its AST."""
        functions = {
            node.name: node for node in tree.body if isinstance(node, _FUNCTION_NODES)
        }
        classes = {
            node.name: node for node in tree.body if isinstance(node, ast.ClassDef)
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


@dataclass
class _ClassInfo:
    """A class in the analyzed code, for following calls through its instances.

    Attributes:
        module: The module that defines it
        node: Its definition
        methods: Each method's name, mapped to its definition
        bases: Its base classes that are in the analyzed code, qualified
        attributes: Each attribute whose class is known, mapped to that class
    """

    module: _ModuleDefinitions
    node: ast.ClassDef
    methods: dict[str, _FunctionNode]
    bases: list[str] = field(default_factory=list)
    attributes: dict[str, str] = field(default_factory=dict)


class _CallResolver:
    """Traces a call to the function or class in the analyzed code it reaches.

    A call through an object is traced when the object's class is known: for
    self and cls, a parameter or attribute annotated with the class, or a
    local or attribute assigned an instance of it (or the result of a
    function whose return annotation names it). A method a class does not
    define is looked up in its base classes. A name whose class is unknown,
    or could be one of several, is not traced.
    """

    def __init__(self, modules: list[_ModuleDefinitions]) -> None:
        self._classes: dict[str, _ClassInfo] = {}
        self._functions: dict[str, tuple[_ModuleDefinitions, _FunctionNode]] = {}
        self._known: set[str] = set()
        for module in modules:
            self._known.add(module.name)
            for name, node in module.functions.items():
                self._functions[f"{module.name}.{name}"] = (module, node)
            for name, node in module.classes.items():
                qualified = f"{module.name}.{name}"
                methods = {
                    item.name: item
                    for item in node.body
                    if isinstance(item, _FUNCTION_NODES)
                }
                self._classes[qualified] = _ClassInfo(module, node, methods)
                for method, item in methods.items():
                    self._functions[f"{qualified}.{method}"] = (module, item)
        self._known.update(self._functions, self._classes)
        self._by_suffix = unique_suffixes(self._known)

        # Bases first, since attributes are also looked up through them
        for info in self._classes.values():
            bases = (self._annotation_class(info.module, b) for b in info.node.bases)
            info.bases = [base for base in bases if base]
        for name, info in self._classes.items():
            info.attributes = self._attribute_classes(name, info)

    def resolve(
        self,
        module: _ModuleDefinitions,
        class_name: str | None,
        func: ast.expr,
        types: _Types,
    ) -> str | None:
        """Name the callee of a call, qualified when it can be traced.

        Args:
            module: The module the call is made in
            class_name: The qualified class whose method makes the call, if any
            func: The call's func expression
            types: The classes of the names bound where the call is made

        Returns:
            The qualified or bare callee name, or None for a call through an
            expression with no name, such as f()()
        """
        if isinstance(func, ast.Name):
            if func.id in types:
                return func.id
            return self._owner(module, func.id) or func.id
        if not isinstance(func, ast.Attribute):
            return None
        if _is_super_call(func.value):
            for base in self._bases(class_name):
                method = self._method(base, func.attr)
                if method:
                    return method
            return func.attr
        receiver = self.class_of(module, class_name, func.value, types)
        if receiver:
            return self._method(receiver, func.attr) or func.attr
        owner = self._dotted(module, func.value, types)
        if owner:
            if f"{owner}.{func.attr}" in self._known:
                return f"{owner}.{func.attr}"
            if owner in self._classes:
                return self._method(owner, func.attr) or func.attr
        return func.attr

    def class_of(
        self,
        module: _ModuleDefinitions,
        class_name: str | None,
        expr: ast.expr,
        types: _Types,
    ) -> str | None:
        """The analyzed class an expression's value is an instance of, if known."""
        if isinstance(expr, ast.Name):
            return types.get(expr.id)
        if isinstance(expr, ast.Attribute):
            owner = self.class_of(module, class_name, expr.value, types)
            return self._attribute(owner, expr.attr) if owner else None
        if isinstance(expr, ast.Await):
            return self.class_of(module, class_name, expr.value, types)
        if isinstance(expr, ast.Call):
            callee = self.resolve(module, class_name, expr.func, types)
            if callee in self._classes:
                return callee
            if callee in self._functions:
                return self._return_class(callee)
        return None

    def local_types(
        self,
        module: _ModuleDefinitions,
        class_name: str | None,
        node: _FunctionNode,
        enclosing: _Types,
    ) -> _Types:
        """The classes of the names a function binds, over those it encloses.

        Args:
            module: The module the function is in
            class_name: The qualified class, when the function is its method
            node: The function's definition
            enclosing: The names bound around it, for a nested function

        Returns:
            Each name visible in the function, mapped to its class or None
        """
        types = dict(enclosing)
        candidates: dict[str, set[str]] = {}
        arguments = node.args
        parameters = [
            *arguments.posonlyargs,
            *arguments.args,
            *([arguments.vararg] if arguments.vararg else []),
            *arguments.kwonlyargs,
            *([arguments.kwarg] if arguments.kwarg else []),
        ]
        for parameter in parameters:
            annotated = self._annotation_class(module, parameter.annotation)
            candidates[parameter.arg] = {annotated} if annotated else set()
        positional = [*arguments.posonlyargs, *arguments.args]
        if class_name and positional and not _is_static(node):
            candidates[positional[0].arg] = {class_name}
        for name, found in candidates.items():
            types[name] = _single(found)

        for name, value, annotation in _bindings(node):
            found = candidates.setdefault(name, set())
            bound = self._annotation_class(module, annotation)
            if bound is None and value is not None:
                bound = self.class_of(module, class_name, value, types)
            if bound:
                found.add(bound)
            types[name] = _single(found)
        return types

    def _attribute_classes(self, class_name: str, info: _ClassInfo) -> dict[str, str]:
        """The classes of a class's attributes, from its body and its methods."""
        candidates: dict[str, set[str]] = {}

        def add(name: str, found: str | None) -> None:
            names = candidates.setdefault(name, set())
            if found:
                names.add(found)

        module = info.module
        for item in info.node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                add(item.target.id, self._annotation_class(module, item.annotation))
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        add(target.id, self.class_of(module, None, item.value, {}))

        for method in info.methods.values():
            positional = [*method.args.posonlyargs, *method.args.args]
            if not positional or _is_static(method):
                continue
            receiver = positional[0].arg
            types = self.local_types(module, class_name, method, {})
            for node in _walk_function(method):
                if isinstance(node, ast.Assign):
                    targets, annotation = node.targets, None
                elif isinstance(node, ast.AnnAssign):
                    targets, annotation = [node.target], node.annotation
                else:
                    continue
                for target in targets:
                    if (
                        isinstance(target, ast.Attribute)
                        and isinstance(target.value, ast.Name)
                        and target.value.id == receiver
                    ):
                        found = self._annotation_class(module, annotation)
                        if found is None and node.value is not None:
                            found = self.class_of(module, class_name, node.value, types)
                        add(target.attr, found)
        return {
            name: found
            for name, classes in candidates.items()
            if (found := _single(classes))
        }

    def _annotation_class(
        self, module: _ModuleDefinitions, annotation: ast.expr | None
    ) -> str | None:
        """The analyzed class a type annotation names, if exactly one."""
        if annotation is None:
            return None
        if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
            try:
                annotation = ast.parse(annotation.value, mode="eval").body
            except SyntaxError:
                return None
        members: list[ast.expr] | None = None
        if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
            members = [annotation.left, annotation.right]
        elif isinstance(annotation, ast.Subscript):
            head = annotation.value
            head_name = head.attr if isinstance(head, ast.Attribute) else None
            if isinstance(head, ast.Name):
                head_name = head.id
            if head_name not in _UNION_TYPES:
                return None
            index = annotation.slice
            members = list(index.elts) if isinstance(index, ast.Tuple) else [index]
        if members is not None:
            found = {self._annotation_class(module, member) for member in members}
            return _single(found - {None})
        named = self._dotted(module, annotation, {})
        return named if named in self._classes else None

    def _return_class(self, function: str) -> str | None:
        """The analyzed class a function's return annotation names, if any."""
        module, node = self._functions[function]
        return self._annotation_class(module, node.returns)

    def _lineage(self, class_name: str) -> list[str]:
        """A class and its analyzed base classes, depth first, nearest first."""
        lineage: list[str] = []
        pending = [class_name]
        while pending:
            current = pending.pop()
            if current in lineage or current not in self._classes:
                continue
            lineage.append(current)
            pending.extend(reversed(self._classes[current].bases))
        return lineage

    def _bases(self, class_name: str | None) -> list[str]:
        """A class's analyzed base classes, in lookup order, without the class."""
        return self._lineage(class_name)[1:] if class_name else []

    def _method(self, class_name: str, name: str) -> str | None:
        """The method a call on the class reaches, defined there or in a base."""
        for current in self._lineage(class_name):
            if name in self._classes[current].methods:
                return f"{current}.{name}"
        return None

    def _attribute(self, class_name: str, name: str) -> str | None:
        """The analyzed class of an attribute or property of a class, if known."""
        for current in self._lineage(class_name):
            info = self._classes[current]
            if name in info.attributes:
                return info.attributes[name]
            method = info.methods.get(name)
            if method is not None:
                if _is_property(method):
                    return self._return_class(f"{current}.{name}")
                return None
        return None

    def _dotted(
        self, module: _ModuleDefinitions, expr: ast.expr, types: _Types
    ) -> str | None:
        """The known module, class, or function a dotted name refers to.

        A name bound in the function hides the module-level one it shadows.
        """
        if isinstance(expr, ast.Name):
            return None if expr.id in types else self._owner(module, expr.id)
        if isinstance(expr, ast.Attribute):
            base = self._dotted(module, expr.value, types)
            if base and f"{base}.{expr.attr}" in self._known:
                return f"{base}.{expr.attr}"
        return None

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


def _single(classes: Collection[str | None]) -> str | None:
    """The one class in a set, or None when there are none or several."""
    if len(classes) != 1:
        return None
    return next(iter(classes))


def _is_super_call(expr: ast.expr) -> bool:
    """Whether an expression is a call to super()."""
    return (
        isinstance(expr, ast.Call)
        and isinstance(expr.func, ast.Name)
        and expr.func.id == "super"
    )


def _decorator_names(node: _FunctionNode) -> set[str]:
    """The names of a function's decorators, as in property or functools.wraps."""
    names = set()
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Call):
            decorator = decorator.func
        if isinstance(decorator, ast.Name):
            names.add(decorator.id)
        elif isinstance(decorator, ast.Attribute):
            names.add(decorator.attr)
    return names


def _is_static(node: _FunctionNode) -> bool:
    """Whether a method is a static method, so it has no self or cls."""
    return "staticmethod" in _decorator_names(node)


def _is_property(node: _FunctionNode) -> bool:
    """Whether a method is a property."""
    return not _PROPERTY_DECORATORS.isdisjoint(_decorator_names(node))


def _walk_function(node: _FunctionNode) -> Iterator[ast.AST]:
    """The nodes in a function's body, without nested functions and classes."""
    pending: list[ast.AST] = list(reversed(node.body))
    while pending:
        current = pending.pop()
        yield current
        children = [
            child
            for child in ast.iter_child_nodes(current)
            if not isinstance(child, _SCOPE_NODES)
        ]
        pending.extend(reversed(children))


def _bindings(
    node: _FunctionNode,
) -> Iterator[tuple[str, ast.expr | None, ast.expr | None]]:
    """The names a function's body binds, in order, with value and annotation.

    A value is None when the name is bound to part of one (a, b = pair) or by
    a loop or an except clause, so its class cannot be known.
    """
    for current in _walk_function(node):
        if isinstance(current, ast.Assign):
            for target in current.targets:
                if isinstance(target, ast.Name):
                    yield target.id, current.value, None
                else:
                    yield from _unknown_names(target)
        elif isinstance(current, ast.AnnAssign) and isinstance(
            current.target, ast.Name
        ):
            yield current.target.id, current.value, current.annotation
        elif isinstance(current, (ast.With, ast.AsyncWith)):
            for item in current.items:
                if isinstance(item.optional_vars, ast.Name):
                    yield item.optional_vars.id, item.context_expr, None
                elif item.optional_vars is not None:
                    yield from _unknown_names(item.optional_vars)
        elif isinstance(current, (ast.For, ast.AsyncFor)):
            yield from _unknown_names(current.target)
        elif isinstance(current, ast.ExceptHandler) and current.name:
            yield current.name, None, None


def _unknown_names(target: ast.expr) -> Iterator[tuple[str, None, None]]:
    """The names an assignment target binds, each with no known value."""
    for node in ast.walk(target):
        if isinstance(node, ast.Name):
            yield node.id, None, None


class _CallVisitor(ast.NodeVisitor):
    """Records the calls each function in one module makes, in order."""

    def __init__(self, module: _ModuleDefinitions, resolver: _CallResolver) -> None:
        self.calls: dict[str, list[str]] = {}
        self._module = module
        self._resolver = resolver
        self._scope = [module.name]
        self._class: str | None = None
        self._function: str | None = None
        self._types: _Types = {}

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit a class, so its methods are named after it."""
        previous_class = self._class
        # Only top-level classes are indexed, so self.x() resolves only there
        self._class = (
            f"{self._module.name}.{node.name}" if len(self._scope) == 1 else None
        )
        self._scope.append(node.name)
        self.generic_visit(node)
        self._scope.pop()
        self._class = previous_class

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """Visit a function, recording the calls in its body under its name."""
        previous_function, previous_types = self._function, self._types
        # A method's first parameter is self or cls; a nested function's is not
        method_of = self._class if previous_function is None else None
        self._types = self._resolver.local_types(
            self._module, method_of, node, previous_types
        )
        self._function = ".".join([*self._scope, node.name])
        self.calls[self._function] = []
        self._scope.append(node.name)
        for child in node.body:
            self.visit(child)
        self._scope.pop()
        self._function, self._types = previous_function, previous_types

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit an async function definition like a plain one."""
        self.visit_FunctionDef(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Record a call made inside a function, after the calls in its parts."""
        # The callee expression and the arguments are evaluated first
        self.generic_visit(node)
        if self._function is not None:
            callee = self._resolver.resolve(
                self._module, self._class, node.func, self._types
            )
            calls = self.calls[self._function]
            if callee and callee not in calls:
                calls.append(callee)
