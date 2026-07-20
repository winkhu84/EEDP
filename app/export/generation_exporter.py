"""Abstract exporter interface for GenerateManager engineering artifacts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from app.model.generation_result import GeneratedArtifact


class GenerationExporter(ABC):
    """Reusable contract for one engineering artifact exporter."""

    @property
    @abstractmethod
    def artifact_type(self) -> str:
        """Stable machine-readable artifact type identifier."""

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable artifact name for UI and reports."""

    @property
    @abstractmethod
    def default_filename(self) -> str:
        """Default file name written under the run output directory."""

    @property
    @abstractmethod
    def category(self) -> str:
        """UI grouping category for this exporter."""

    @property
    @abstractmethod
    def sort_order(self) -> int:
        """Display order within the Generate UI (zero-based)."""

    @property
    @abstractmethod
    def is_default_enabled(self) -> bool:
        """Whether this exporter is enabled by default in the Generate UI."""

    @property
    def metadata_key(self) -> str:
        """Stable UI/registry key combining category and artifact type."""
        return f"{self.category}:{self.artifact_type}"

    @abstractmethod
    def export(self, context: Any, output_directory: str) -> GeneratedArtifact:
        """Export one artifact into output_directory and return its result."""

    def build_output_path(self, output_directory: str) -> str:
        """Return the full default output path for this exporter."""
        directory = output_directory.strip()
        if not directory:
            raise ValueError("Output directory must not be blank.")
        return str(Path(directory) / self.default_filename)

    def validate_metadata(self) -> list[str]:
        """Return validation errors for this exporter's metadata."""
        errors: list[str] = []

        if not str(self.artifact_type).strip():
            errors.append("artifact_type must not be blank.")
        if not str(self.display_name).strip():
            errors.append("display_name must not be blank.")

        filename = str(self.default_filename).strip()
        if not filename:
            errors.append("default_filename must not be blank.")
        else:
            if "/" in filename or "\\" in filename:
                errors.append(
                    "default_filename must not contain directory separators."
                )
            if Path(filename).suffix == "":
                errors.append("default_filename must include a file extension.")

        if not str(self.category).strip():
            errors.append("category must not be blank.")

        if type(self.sort_order) is not int:
            errors.append("sort_order must be an integer.")
        elif self.sort_order < 0:
            errors.append("sort_order must be zero or greater.")

        if type(self.is_default_enabled) is not bool:
            errors.append("is_default_enabled must be a bool.")

        return errors
