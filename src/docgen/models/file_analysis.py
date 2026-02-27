"""File analysis model for the documentation generator.

This module defines the FileAnalysis class that represents the analysis results
of a Python source file.
"""

from dataclasses import dataclass, field
from pathlib import PurePosixPath

from .code_entity import CodeEntity, EntityType


@dataclass
class FileAnalysis:
    """Represents the analysis results of a Python source file.

    This class is a pure data container and does not perform filesystem checks.
    File existence should be verified by the caller (e.g., CodeAnalyzer) before
    creating FileAnalysis instances.

    Attributes:
        file_path: Path to the analyzed file (does not need to exist on disk)
        entities: List of code entities found in the file
        imports: List of import statements
        content: Raw file content
        error: Optional error message if analysis failed
        _skip_validation: Whether to skip validation (for testing)
    """

    file_path: str
    entities: list["CodeEntity"]
    imports: list[str]
    content: str
    error: str | None = None
    _skip_validation: bool = field(default=False, repr=False)

    def __post_init__(self):
        """Validate file analysis attributes after initialization.

        Note: This does NOT check if the file exists. File existence should be
        verified by the caller before creating a FileAnalysis instance.
        """
        if not self._skip_validation:
            if not self.file_path:
                raise ValueError("File path cannot be empty")

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
        return PurePosixPath(self.file_path).stem

    @property
    def classes(self) -> list[CodeEntity]:
        """Get all class entities in the file.

        Returns:
            List of class entities
        """
        return [e for e in self.entities if e.type == EntityType.CLASS]

    @property
    def functions(self) -> list[CodeEntity]:
        """Get all function entities in the file.

        Returns:
            List of function entities
        """
        return [e for e in self.entities if e.type == EntityType.FUNCTION]

    @property
    def is_empty(self) -> bool:
        """Check if the file has no content.

        Returns:
            True if the file has no content, False otherwise
        """
        return not self.content.strip()

    @property
    def has_error(self) -> bool:
        """Check if the file analysis has an error.

        Returns:
            True if the file analysis has an error, False otherwise
        """
        return self.error is not None

    @property
    def is_init_file(self) -> bool:
        """Check if the file is an __init__.py file.

        Returns:
            True if the file is an __init__.py file, False otherwise
        """
        return PurePosixPath(self.file_path).name == "__init__.py"

    def get_entity_by_name(self, name: str) -> CodeEntity | None:
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
