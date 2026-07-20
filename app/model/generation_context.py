"""Shared context passed to all generation exporters."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.engine.tia_tag_generator import generate_sorted_validated_project_tags
from app.model.device import Device
from app.model.tia_tag import TIATag


@dataclass
class GenerationContext:
    """Project data and shared cache for one generation run."""

    devices: list[Device]
    output_directory: str
    project_name: str = ""
    generated_at: datetime = field(default_factory=datetime.now)
    tia_tags: list[TIATag] | None = None
    cache: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        """Return validation errors for this generation context."""
        errors: list[str] = []

        if self.devices is None:
            errors.append("devices must not be None.")
        if not self.output_directory.strip():
            errors.append("output_directory must not be blank.")
        if self.generated_at is None:
            errors.append("generated_at must not be None.")
        if self.cache is None:
            errors.append("cache must not be None.")

        return errors

    @property
    def has_devices(self) -> bool:
        """Return True when at least one device is present."""
        return bool(self.devices)

    @property
    def has_tia_tags(self) -> bool:
        """Return True when tia_tags is set and non-empty."""
        return self.tia_tags is not None and len(self.tia_tags) > 0

    def get_cached(self, key: str, default: Any = None) -> Any:
        """Return a cached value or default for a non-blank key."""
        cache_key = key.strip()
        if not cache_key:
            raise ValueError("Cache key must not be blank.")
        return self.cache.get(cache_key, default)

    def set_cached(self, key: str, value: Any) -> None:
        """Store a value in the context cache under a non-blank key."""
        cache_key = key.strip()
        if not cache_key:
            raise ValueError("Cache key must not be blank.")
        self.cache[cache_key] = value

    def get_or_create_tia_tags(self) -> list[TIATag]:
        """Return existing TIA tags or generate them once from devices."""
        if self.tia_tags is not None:
            return self.tia_tags

        tags, _warnings, _errors = generate_sorted_validated_project_tags(self.devices)
        self.tia_tags = tags
        return self.tia_tags
