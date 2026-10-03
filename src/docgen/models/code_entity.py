"""Code entity model for the documentation generator.

This module defines the CodeEntity class that represents a code entity
(class or function) in the analyzed codebase.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EntityType(Enum):
    """Types of code entities."""

    CLASS = "class"
    FUNCTION = "function"


@dataclass
class CodeEntity:
    """Represents a code entity (class or function) in Python source code.

    Attributes:
        name: Name of the entity
        type: Type of entity (EntityType.CLASS or EntityType.FUNCTION)
        docstring: Entity's docstring
        methods: List of method names for classes, None for functions
        start_line: Starting line number in source file
        end_line: Ending line number in source file
        source: Source code of the entity
        parent_class: Name of parent class for class entities
    """

    name: str
    type: EntityType
    docstring: str
    methods: list[str] | None = None
    start_line: int = 1
    end_line: int = 1
    source: str = ""
    parent_class: str | None = None

    def __post_init__(self):
        """Validate entity attributes after initialization."""
        if not self.name:
            raise ValueError("Entity name cannot be empty")

        if not isinstance(self.start_line, int) or self.start_line <= 0:
            raise ValueError("Start line number must be a positive integer")

        if not isinstance(self.end_line, int) or self.end_line <= 0:
            raise ValueError("End line number must be a positive integer")

        if self.type == EntityType.FUNCTION and self.methods is not None:
            raise ValueError("Function entities cannot have methods")

        if self.end_line < self.start_line:
            raise ValueError("End line cannot be before start line")
