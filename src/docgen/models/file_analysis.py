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
    
    This class stores information extracted from a Python file including
    its entities (classes and functions), imports, and content.
    
    Attributes:
        file_path: Absolute path to the analyzed file
        entities: List of code entities found in the file
        imports: List of import statements
        content: Raw content of the file
        _skip_validation: Whether to skip validation (for testing)
    """
    
    file_path: str
    entities: List[CodeEntity]
    imports: List[str]
    content: str
    _skip_validation: bool = False
    
    def __post_init__(self) -> None:
        """Validate analysis attributes after initialization.
        
        Raises:
            ValueError: If validation fails
        """
        if self._skip_validation:
            return
            
        if not self.file_path:
            raise ValueError("File path cannot be empty")
            
        if not os.path.isabs(self.file_path):
            raise ValueError("File path must be absolute")
            
        if not self.file_path.endswith('.py'):
            raise ValueError("File must be a Python file")
            
        if not isinstance(self.entities, list):
            raise ValueError("Entities must be a list")
            
        if any(not isinstance(e, CodeEntity) for e in self.entities):
            raise ValueError("All entities must be CodeEntity instances")
            
        if not isinstance(self.imports, list):
            raise ValueError("Imports must be a list")
            
        if any(not isinstance(i, str) for i in self.imports):
            raise ValueError("All imports must be strings")
            
        if not isinstance(self.content, str):
            raise ValueError("Content must be a string")
    
    @property
    def module_name(self) -> str:
        """Get the module name from the file path.
        
        Returns:
            Module name derived from the file path
        """
        basename = os.path.basename(self.file_path)
        if basename == '__init__.py':
            return os.path.basename(os.path.dirname(self.file_path))
        return os.path.splitext(basename)[0]
    
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