"""File analysis model for the documentation generator.

This module defines the FileAnalysis class that represents the analysis results
of a Python source file.
"""

from dataclasses import dataclass, field
from typing import List, Optional
import os

from .code_entity import CodeEntity

@dataclass
class FileAnalysis:
    """Represents the analysis results of a Python source file.

    Attributes:
        file_path: Path to the analyzed file
        entities: List of code entities found in the file
        imports: List of import statements
        content: Raw file content
        error: Optional error message if analysis failed
        _skip_validation: Whether to skip validation (for testing)
    """
    file_path: str
    entities: List['CodeEntity']
    imports: List[str]
    content: str
    error: Optional[str] = None
    _skip_validation: bool = field(default=False, repr=False)

    def __post_init__(self):
        """Validate file analysis attributes after initialization."""
        if not self._skip_validation:
            if not self.file_path:
                raise ValueError("File path cannot be empty")

            if not os.path.exists(self.file_path):
                raise ValueError(f"File does not exist: {self.file_path}")

            if not self.content and not self.file_path.endswith("__init__.py"):
                raise ValueError("Content cannot be empty except for __init__.py files")

            if not isinstance(self.entities, list):
                raise ValueError("Entities must be a list")

            if not isinstance(self.imports, list):
                raise ValueError("Imports must be a list")

            if not isinstance(self.content, str):
                raise ValueError("Content must be a string")

            if self.error is not None and not isinstance(self.error, str):
                raise ValueError("Error must be a string if provided")

            for entity in self.entities:
                if not isinstance(entity, CodeEntity):
                    raise ValueError("All entities must be instances of CodeEntity")
    
    @property
    def module_name(self) -> str:
        """Get the module name from the file path.
        
        Returns:
            Module name derived from the file path
        """
        return os.path.splitext(os.path.basename(self.file_path))[0]
    
    @property
    def classes(self) -> List[CodeEntity]:
        """Get all class entities in the file.
        
        Returns:
            List of class entities
        """
        return [e for e in self.entities if e.type == 'class']
    
    @property
    def functions(self) -> List[CodeEntity]:
        """Get all function entities in the file.
        
        Returns:
            List of function entities
        """
        return [e for e in self.entities if e.type == 'function']
    
    def get_entity_by_name(self, name: str) -> Optional[CodeEntity]:
        """Get an entity by its name.
        
        Args:
            name: Name of the entity to find
            
        Returns:
            The entity if found, None otherwise
        """
        for entity in self.entities:
            if entity.name == name:
                return entity
        return None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FileAnalysis):
            return NotImplemented
        return (
            self.file_path == other.file_path
            and self.entities == other.entities
            and self.imports == other.imports
            and self.content == other.content
            and self.error == other.error
        )

    def __repr__(self) -> str:
        return (
            f"FileAnalysis(file_path='{self.file_path}', "
            f"entities={self.entities}, "
            f"imports={self.imports}, "
            f"content='{self.content[:50]}...', "
            f"error={self.error})"
        ) 