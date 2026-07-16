"""FC_IO generator — builds and validates project FC_IO rows."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from app.common.constants import PROJECT_AREAS
from app.engine.io_summary_engine import summarize_project
from app.model.device import Device
from app.model.fc_io_row import FCIORow

_VALID_IO_TYPES = ("DI", "DO", "AI", "AO")
_AREA_ORDER = {name: index for index, name in enumerate(PROJECT_AREAS)}
_IO_ORDER = {name: index for index, name in enumerate(_VALID_IO_TYPES)}
_TAG_PART_RE = re.compile(r"(\d+)")


@dataclass(frozen=True)
class FCIOIssue:
    """Validation warning or error for FC_IO generation."""

    severity: str  # "warning" | "error"
    message: str
    code: str = ""
    area: str = ""
    device_tag: str = ""
    signal_name: str = ""
    io_type: str = ""
    plc_address: str = ""


@dataclass(frozen=True)
class FCIOGenerationResult:
    """Generated FC_IO rows plus validation outcomes."""

    rows: tuple[FCIORow, ...]
    warnings: tuple[FCIOIssue, ...]
    errors: tuple[FCIOIssue, ...]
    di_count: int
    do_count: int
    ai_count: int
    ao_count: int

    @property
    def total_count(self) -> int:
        return len(self.rows)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    @property
    def error_count(self) -> int:
        return len(self.errors)


def generate_device_rows(device: Device) -> list[FCIORow]:
    """Create FC_IO rows for all enabled signals on one device."""
    rows: list[FCIORow] = []
    for index, signal in enumerate(device.signals):
        if not signal.enabled:
            continue
        rows.append(
            FCIORow(
                area=device.area,
                device_type=device.type,
                device_tag=device.tag,
                device_description=device.description,
                signal_name=signal.name,
                io_type=signal.io_type.strip().upper(),
                plc_address=signal.address.strip(),
                required=signal.required,
                signal_description=signal.description,
                remark=signal.remark,
                terminal=signal.terminal,
                cable=signal.cable,
                signal_order=index,
            )
        )
    return rows


def generate_project_rows(
    devices: Sequence[Device],
) -> FCIOGenerationResult:
    """Generate, sort, and validate FC_IO rows for the whole project."""
    rows: list[FCIORow] = []
    for device in devices:
        rows.extend(generate_device_rows(device))

    sorted_rows = sort_fc_io_rows(rows)
    return validate_fc_io_rows(sorted_rows, devices=devices)


def natural_tag_key(tag: str) -> tuple:
    """Natural numeric sort key (P-2 < P-10 < P-101)."""
    parts = _TAG_PART_RE.split(tag or "")
    key: list[object] = []
    for part in parts:
        if not part:
            continue
        if part.isdigit():
            key.append(int(part))
        else:
            key.append(part.casefold())
    return tuple(key)


def sort_fc_io_rows(rows: Sequence[FCIORow]) -> list[FCIORow]:
    """Sort by Area → Device Type → Tag (natural) → I/O Type → signal order."""

    def sort_key(row: FCIORow) -> tuple:
        area_rank = _AREA_ORDER.get(row.area.strip().upper(), len(_AREA_ORDER) + 1)
        io_rank = _IO_ORDER.get(row.io_type.strip().upper(), len(_IO_ORDER) + 1)
        return (
            area_rank,
            row.device_type.casefold(),
            natural_tag_key(row.device_tag),
            io_rank,
            row.signal_order,
        )

    return sorted(rows, key=sort_key)


def sort_devices(devices: Sequence[Device]) -> list[Device]:
    """Sort devices by Area → Device Type → Tag (natural)."""

    def sort_key(device: Device) -> tuple:
        area_rank = _AREA_ORDER.get(device.area.strip().upper(), len(_AREA_ORDER) + 1)
        return (
            area_rank,
            device.type.casefold(),
            natural_tag_key(device.tag),
        )

    return sorted(devices, key=sort_key)


def _count_by_io(rows: Sequence[FCIORow]) -> dict[str, int]:
    counts = {"DI": 0, "DO": 0, "AI": 0, "AO": 0}
    for row in rows:
        key = row.io_type.strip().upper()
        if key in counts:
            counts[key] += 1
    return counts


def validate_fc_io_rows(
    rows: Sequence[FCIORow],
    *,
    devices: Sequence[Device] | None = None,
) -> FCIOGenerationResult:
    """Validate FC_IO rows. Never raises for validation failures."""
    warnings: list[FCIOIssue] = []
    errors: list[FCIOIssue] = []

    tag_counts = Counter(row.device_tag for row in rows if row.device_tag.strip())
    duplicate_tags = {tag for tag, count in tag_counts.items() if count > 1}

    # Duplicate device tags across distinct devices (project-level).
    if devices is not None:
        device_tag_counts = Counter(device.tag for device in devices if device.tag.strip())
        for tag, count in device_tag_counts.items():
            if count > 1:
                warnings.append(
                    FCIOIssue(
                        severity="warning",
                        code="DUPLICATE_DEVICE_TAG",
                        message=f"Duplicate Device Tag: {tag}",
                        device_tag=tag,
                    )
                )

    address_map: dict[str, list[FCIORow]] = defaultdict(list)
    for row in rows:
        if not row.device_tag.strip():
            warnings.append(
                FCIOIssue(
                    severity="warning",
                    code="BLANK_DEVICE_TAG",
                    message="Blank Device Tag",
                    area=row.area,
                    signal_name=row.signal_name,
                    io_type=row.io_type,
                )
            )
        elif row.device_tag in duplicate_tags and devices is None:
            warnings.append(
                FCIOIssue(
                    severity="warning",
                    code="DUPLICATE_DEVICE_TAG",
                    message=f"Duplicate Device Tag: {row.device_tag}",
                    area=row.area,
                    device_tag=row.device_tag,
                    signal_name=row.signal_name,
                    io_type=row.io_type,
                )
            )

        if not row.signal_name.strip():
            warnings.append(
                FCIOIssue(
                    severity="warning",
                    code="BLANK_SIGNAL_NAME",
                    message="Blank Signal Name",
                    area=row.area,
                    device_tag=row.device_tag,
                    io_type=row.io_type,
                )
            )

        io_type = row.io_type.strip().upper()
        if io_type not in _VALID_IO_TYPES:
            errors.append(
                FCIOIssue(
                    severity="error",
                    code="INVALID_IO_TYPE",
                    message=f"Invalid I/O Type: {row.io_type or '(blank)'}",
                    area=row.area,
                    device_tag=row.device_tag,
                    signal_name=row.signal_name,
                    io_type=row.io_type,
                )
            )

        area = row.area.strip().upper()
        if area and area not in _AREA_ORDER:
            warnings.append(
                FCIOIssue(
                    severity="warning",
                    code="UNSUPPORTED_AREA",
                    message=f"Unsupported Area: {row.area}",
                    area=row.area,
                    device_tag=row.device_tag,
                    signal_name=row.signal_name,
                    io_type=row.io_type,
                )
            )

        if not row.plc_address.strip():
            warnings.append(
                FCIOIssue(
                    severity="warning",
                    code="MISSING_PLC_ADDRESS",
                    message="Enabled Signal without PLC Address",
                    area=row.area,
                    device_tag=row.device_tag,
                    signal_name=row.signal_name,
                    io_type=row.io_type,
                )
            )
        else:
            address_map[row.plc_address.strip().upper()].append(row)

    for address, occupants in sorted(address_map.items()):
        if len(occupants) < 2:
            continue
        detail = "; ".join(
            f"{item.device_tag} / {item.signal_name}" for item in occupants
        )
        for item in occupants:
            errors.append(
                FCIOIssue(
                    severity="error",
                    code="DUPLICATE_PLC_ADDRESS",
                    message=f"Duplicate PLC Address {address}: {detail}",
                    area=item.area,
                    device_tag=item.device_tag,
                    signal_name=item.signal_name,
                    io_type=item.io_type,
                    plc_address=item.plc_address,
                )
            )

    counts = _count_by_io(rows)

    if devices is not None:
        project_summary = summarize_project(devices)
        mismatches: list[str] = []
        for io_type in _VALID_IO_TYPES:
            expected = int(project_summary.get(io_type, 0))
            actual = counts[io_type]
            if expected != actual:
                mismatches.append(f"{io_type}: Project={expected}, FC_IO={actual}")
        if mismatches:
            warnings.append(
                FCIOIssue(
                    severity="warning",
                    code="SUMMARY_MISMATCH",
                    message=(
                        "FC_IO totals do not match Project I/O Summary: "
                        + "; ".join(mismatches)
                    ),
                )
            )

    return FCIOGenerationResult(
        rows=tuple(rows),
        warnings=tuple(warnings),
        errors=tuple(errors),
        di_count=counts["DI"],
        do_count=counts["DO"],
        ai_count=counts["AI"],
        ao_count=counts["AO"],
    )


def row_severity(
    row: FCIORow,
    warnings: Sequence[FCIOIssue],
    errors: Sequence[FCIOIssue],
) -> str | None:
    """Return 'error', 'warning', or None for a row based on validation issues."""
    for issue in errors:
        if _issue_matches_row(issue, row):
            return "error"
    for issue in warnings:
        if _issue_matches_row(issue, row):
            return "warning"
    return None


def _issue_matches_row(issue: FCIOIssue, row: FCIORow) -> bool:
    if issue.plc_address and issue.signal_name:
        return (
            issue.device_tag == row.device_tag
            and issue.signal_name == row.signal_name
            and issue.plc_address.strip().upper() == row.plc_address.strip().upper()
        )
    if issue.signal_name:
        return (
            issue.device_tag == row.device_tag
            and issue.signal_name == row.signal_name
        )
    if issue.device_tag and not issue.signal_name and not issue.plc_address:
        # Device-level issue (e.g. duplicate tag) — mark all rows for that tag.
        return issue.device_tag == row.device_tag
    # Global issues (summary mismatch) do not highlight specific rows.
    return False
