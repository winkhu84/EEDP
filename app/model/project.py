"""Project domain entity."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.model.area import Area


@dataclass
class Project:
    """Top-level EEDP project."""

    customer: str
    project_name: str
    revision: str
    areas: list[Area] = field(default_factory=list)
