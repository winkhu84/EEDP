"""Device Type catalog helpers for the GUI combo.

SignalTemplateLibrary is the membership source of truth.
DEVICE_TYPES is display-order preference and empty-library fallback only.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.common.constants import DEVICE_TYPES


def sanitize_device_type_names(names: Iterable[str] | None) -> tuple[str, ...]:
    """Strip blanks and drop duplicates while preserving first-seen order."""
    seen: set[str] = set()
    cleaned: list[str] = []
    for raw in names or ():
        name = str(raw).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        cleaned.append(name)
    return tuple(cleaned)


def order_device_types(
    names: Iterable[str] | None,
    *,
    preferred_order: tuple[str, ...] = DEVICE_TYPES,
) -> tuple[str, ...]:
    """Place preferred types first, then any extra names in given order."""
    cleaned = sanitize_device_type_names(names)
    remaining = list(cleaned)
    ordered: list[str] = []
    for name in sanitize_device_type_names(preferred_order):
        if name in remaining:
            ordered.append(name)
            remaining.remove(name)
    ordered.extend(remaining)
    return tuple(ordered)


def resolve_gui_device_types(
    library_types: Iterable[str] | None,
    *,
    extra_types: Iterable[str] | None = None,
    fallback: tuple[str, ...] = DEVICE_TYPES,
) -> tuple[str, ...]:
    """Build combo items: library types, or fallback if the library is empty.

    extra_types are appended when missing (custom / imported / unknown).
    """
    cleaned = sanitize_device_type_names(library_types)
    if not cleaned:
        cleaned = sanitize_device_type_names(fallback)
    extras = sanitize_device_type_names(extra_types)
    merged = cleaned + tuple(name for name in extras if name not in cleaned)
    return order_device_types(merged, preferred_order=fallback)
