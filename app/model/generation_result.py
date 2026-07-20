"""Generation result domain entities for engineering artifact reporting."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class GenerationStatus(Enum):
    """Status of one generated engineering artifact."""

    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"


@dataclass
class GeneratedArtifact:
    """One generated engineering file or output artifact."""

    artifact_type: str
    display_name: str
    output_path: str
    status: GenerationStatus
    message: str = ""

    @property
    def is_successful(self) -> bool:
        """Return True only when this artifact completed successfully."""
        return self.status is GenerationStatus.SUCCESS


@dataclass
class GenerationResult:
    """Aggregated result of a project generation run."""

    output_directory: str
    artifacts: list[GeneratedArtifact] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        """Number of artifacts with SUCCESS status."""
        return sum(
            1
            for artifact in self.artifacts
            if artifact.status is GenerationStatus.SUCCESS
        )

    @property
    def warning_count(self) -> int:
        """Number of artifacts with WARNING status."""
        return sum(
            1
            for artifact in self.artifacts
            if artifact.status is GenerationStatus.WARNING
        )

    @property
    def error_count(self) -> int:
        """Number of artifacts with ERROR status."""
        return sum(
            1
            for artifact in self.artifacts
            if artifact.status is GenerationStatus.ERROR
        )

    @property
    def skipped_count(self) -> int:
        """Number of artifacts with SKIPPED status."""
        return sum(
            1
            for artifact in self.artifacts
            if artifact.status is GenerationStatus.SKIPPED
        )

    @property
    def has_errors(self) -> bool:
        """Return True when at least one artifact has ERROR status."""
        return self.error_count > 0

    @property
    def is_successful(self) -> bool:
        """Return True when generation produced success without errors."""
        return (
            bool(self.artifacts)
            and not self.has_errors
            and self.success_count > 0
        )

    def add_artifact(self, artifact: GeneratedArtifact) -> None:
        """Append one generated artifact to this result."""
        self.artifacts.append(artifact)

    def add_message(self, message: str) -> None:
        """Append a non-blank generation message."""
        text = message.strip()
        if not text:
            return
        self.messages.append(text)
