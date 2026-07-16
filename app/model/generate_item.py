"""Generate deliverable item domain entity."""

from __future__ import annotations

from dataclasses import dataclass, field

STATUS_READY = "READY"
STATUS_WARNING = "WARNING"
STATUS_ERROR = "ERROR"
STATUS_NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


@dataclass
class GenerateItem:
    """One output deliverable shown in Generate Preview."""

    item_id: str
    category: str
    display_name: str
    file_name: str
    output_format: str
    enabled: bool = True
    selected: bool = False
    status: str = STATUS_READY
    warning_count: int = 0
    error_count: int = 0
    description: str = ""
    output_path: str = ""
    dependencies: list[str] = field(default_factory=list)

    @property
    def is_generatable(self) -> bool:
        return self.enabled and self.status != STATUS_NOT_IMPLEMENTED
