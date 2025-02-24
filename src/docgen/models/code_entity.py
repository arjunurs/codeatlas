"""Code entity model for the documentation generator.

This module defines the CodeEntity class that represents a code entity
(class or function) in the analyzed codebase.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class CodeEntity:
    """Represents a code entity (class or function) in the codebase.

    This class stores information about a code entity including its name,
    documentation, location, and relationships with other entities.

    Attributes:
        name: Name of the entity
        docstring: Documentation string for the entity
        lineno: Line number where the entity is defined
        type: Type of entity ('class' or 'function')
        file_path: Path to the file containing this entity
        methods: List of method names (for classes only)
        parent_class: Name of parent class (for classes only)
    """
    name: str
    docstring: str
    lineno: int
    type: str
    file_path: str
    methods: List[str] = field(default_factory=list)
    parent_class: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate entity attributes after initialization.

        Raises:
            ValueError: If validation fails
        """
        if not self.name:
            raise ValueError("Entity name cannot be empty")
            
        if self.type not in ('class', 'function'):
            raise ValueError("Entity type must be 'class' or 'function'")
            
        if self.lineno < 1:
            raise ValueError("Line number must be positive")
            
        if not self.file_path:
            raise ValueError("File path cannot be empty")
            
        if self.type == 'function' and (self.methods or self.parent_class):
            raise ValueError("Function entities cannot have methods or parent class")
            
        if self.type == 'class':
            if not isinstance(self.methods, list):
                raise ValueError("Methods must be a list")
            if any(not isinstance(m, str) for m in self.methods):
                raise ValueError("Method names must be strings") 