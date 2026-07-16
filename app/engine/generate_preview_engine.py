"""Generate Preview engine — deliverable list and project validation."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

from app.engine.address_manager import find_address_conflicts
from app.engine.fc_io_generator import FCIOGenerationResult, generate_project_rows
from app.engine.io_summary_engine import summarize_project
from app.engine.plc_module_mapping_engine import build_project_module_mapping
from app.engine.tia_tag_generator import generate_sorted_validated_project_tags
from app.model.device import Device
from app.model.tia_tag import TIATag
from app.model.generate_item import (
    STATUS_ERROR,
    STATUS_NOT_IMPLEMENTED,
    STATUS_READY,
    STATUS_WARNING,
    GenerateItem,
)
from app.model.plc_card_config import PlcCardConfig, default_plc_card_configurations

_CATEGORY_ORDER = (
    "Engineering Data",
    "PLC",
    "EPLAN",
    "Documentation",
)

_ITEM_ORDER = (
    "fc_io_excel",
    "fc_io_preview_data",
    "plc_module_mapping_excel",
    "tia_portal_tag_table",
    "plc_program_source",
    "eplan_import_data",
    "device_list_report",
    "validation_report",
)

_INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')


@dataclass(frozen=True)
class ValidationEntry:
    """One validation warning or error for Generate Preview."""

    severity: str
    message: str
    device_tag: str = ""
    signal_name: str = ""
    plc_address: str = ""
    source: str = ""


@dataclass(frozen=True)
class ProjectGenerationSummary:
    """Project-level counts for Generate Preview header."""

    customer: str
    project_name: str
    revision: str
    device_count: int
    enabled_signal_count: int
    di_count: int
    do_count: int
    ai_count: int
    ao_count: int
    warning_count: int
    error_count: int
    fc_io_row_count: int
    unaddressed_count: int
    duplicate_address_count: int

    @property
    def display_project_name(self) -> str:
        return self.project_name.strip() or "Unnamed Project"


@dataclass
class GeneratePreviewResult:
    """Full Generate Preview payload."""

    items: list[GenerateItem]
    summary: ProjectGenerationSummary
    warnings: list[ValidationEntry] = field(default_factory=list)
    errors: list[ValidationEntry] = field(default_factory=list)
    output_directory: str = ""
    fc_io_result: FCIOGenerationResult | None = None
    tia_tags: list[TIATag] = field(default_factory=list)
    tia_warnings: list[str] = field(default_factory=list)
    tia_errors: list[str] = field(default_factory=list)


def sanitize_file_name(text: str) -> str:
    """Sanitize a Windows file name segment."""
    cleaned = _INVALID_FILENAME_CHARS.sub("_", text.strip())
    cleaned = cleaned.strip(" .")
    return cleaned or "Export"


def build_default_file_name(
    item_id: str,
    project_name: str,
    revision: str,
) -> str:
    """Return default file name for a deliverable item."""
    safe_name = sanitize_file_name(project_name)
    safe_revision = sanitize_file_name(revision)
    templates = {
        "fc_io_excel": (
            f"FC_IO_{safe_name}_{safe_revision}.xlsx"
            if safe_name and safe_revision and safe_name != "Export"
            else (
                f"FC_IO_{safe_name}.xlsx"
                if safe_name and safe_name != "Export"
                else "FC_IO_Export.xlsx"
            )
        ),
        "plc_module_mapping_excel": (
            f"PLC_Module_Mapping_{safe_name}_{safe_revision}.xlsx"
            if safe_name and safe_revision and safe_name != "Export"
            else f"PLC_Module_Mapping_{safe_name}.xlsx"
        ),
        "tia_portal_tag_table": (
            f"TIA_Tags_{safe_name}_{safe_revision}.csv"
            if safe_name and safe_revision and safe_name != "Export"
            else (
                f"TIA_Tags_{safe_name}.csv"
                if safe_name and safe_name != "Export"
                else "TIA_Tags_Export.csv"
            )
        ),
        "plc_program_source": (
            f"PLC_Program_{safe_name}_{safe_revision}.scl"
            if safe_name and safe_revision and safe_name != "Export"
            else f"PLC_Program_{safe_name}.scl"
        ),
        "eplan_import_data": (
            f"EPLAN_Import_{safe_name}_{safe_revision}.xlsx"
            if safe_name and safe_revision and safe_name != "Export"
            else f"EPLAN_Import_{safe_name}.xlsx"
        ),
        "device_list_report": (
            f"Device_List_{safe_name}_{safe_revision}.xlsx"
            if safe_name and safe_revision and safe_name != "Export"
            else f"Device_List_{safe_name}.xlsx"
        ),
        "validation_report": (
            f"Validation_Report_{safe_name}_{safe_revision}.xlsx"
            if safe_name and safe_revision and safe_name != "Export"
            else f"Validation_Report_{safe_name}.xlsx"
        ),
    }
    return templates.get(item_id, f"{item_id}_{safe_name}.xlsx")


def get_default_output_directory(
    *,
    project_file_path: str | Path | None = None,
) -> Path:
    """Return default output directory for generated files."""
    if project_file_path:
        path = Path(project_file_path)
        if path.is_file():
            return path.parent / "output"
        if path.is_dir():
            return path / "output"
    workspace_root = Path(__file__).resolve().parents[2]
    return workspace_root / "output"


def _count_enabled_signals(devices: Sequence[Device]) -> int:
    return sum(
        1
        for device in devices
        for signal in device.signals
        if signal.enabled
    )


def _collect_validation(
    devices: Sequence[Device],
    fc_io_result: FCIOGenerationResult,
    *,
    card_configurations: Sequence[PlcCardConfig] | None = None,
) -> tuple[list[ValidationEntry], list[ValidationEntry], int]:
    """Aggregate validation from FC_IO, address conflicts, and module mapping."""
    warnings: list[ValidationEntry] = []
    errors: list[ValidationEntry] = []
    seen: set[tuple[str, str, str, str]] = set()

    def add_entry(entry: ValidationEntry) -> None:
        key = (
            entry.severity,
            entry.message,
            entry.device_tag,
            entry.signal_name,
        )
        if key in seen:
            return
        seen.add(key)
        if entry.severity == "error":
            errors.append(entry)
        else:
            warnings.append(entry)

    for issue in fc_io_result.errors:
        add_entry(
            ValidationEntry(
                severity="error",
                message=issue.message,
                device_tag=issue.device_tag,
                signal_name=issue.signal_name,
                plc_address=issue.plc_address,
                source="FC_IO",
            )
        )
    for issue in fc_io_result.warnings:
        add_entry(
            ValidationEntry(
                severity="warning",
                message=issue.message,
                device_tag=issue.device_tag,
                signal_name=issue.signal_name,
                plc_address=issue.plc_address,
                source="FC_IO",
            )
        )

    conflicts = find_address_conflicts(devices)
    duplicate_addresses = {item.address for item in conflicts}
    for conflict in conflicts:
        add_entry(
            ValidationEntry(
                severity="error",
                message=(
                    f"PLC address {conflict.address} is assigned to multiple signals."
                ),
                device_tag=conflict.device_tag,
                signal_name=conflict.signal_name,
                plc_address=conflict.address,
                source="Address",
            )
        )

    mapping = build_project_module_mapping(
        devices,
        card_configurations,
    )
    for issue in mapping.errors:
        add_entry(
            ValidationEntry(
                severity="error",
                message=issue.message,
                device_tag=issue.device_tag,
                signal_name=issue.signal_name,
                plc_address=issue.plc_address,
                source="PLC Mapping",
            )
        )
    for issue in mapping.warnings:
        add_entry(
            ValidationEntry(
                severity="warning",
                message=issue.message,
                device_tag=issue.device_tag,
                signal_name=issue.signal_name,
                plc_address=issue.plc_address,
                source="PLC Mapping",
            )
        )

    return warnings, errors, len(duplicate_addresses)


def _fc_io_status(error_count: int, warning_count: int) -> str:
    if error_count > 0:
        return STATUS_ERROR
    if warning_count > 0:
        return STATUS_WARNING
    return STATUS_READY


def _unaddressed_count(fc_io_result: FCIOGenerationResult) -> int:
    return sum(
        1
        for issue in fc_io_result.warnings
        if issue.code == "MISSING_PLC_ADDRESS"
    )


def build_generate_items(
    devices: Sequence[Device],
    *,
    customer: str = "",
    project_name: str = "",
    revision: str = "",
    output_directory: str | Path | None = None,
    card_configurations: Sequence[PlcCardConfig] | None = None,
) -> GeneratePreviewResult:
    """Build deliverable items and validation for Generate Preview."""
    configs = (
        tuple(card_configurations)
        if card_configurations is not None
        else default_plc_card_configurations()
    )
    fc_io_result = generate_project_rows(devices)
    tia_tags, tia_warnings, tia_errors = generate_sorted_validated_project_tags(
        devices
    )
    warnings, errors, duplicate_count = _collect_validation(
        devices,
        fc_io_result,
        card_configurations=configs,
    )
    project_summary = summarize_project(devices)
    enabled_count = _count_enabled_signals(devices)
    unaddressed = _unaddressed_count(fc_io_result)

    summary = ProjectGenerationSummary(
        customer=customer.strip(),
        project_name=project_name.strip(),
        revision=revision.strip(),
        device_count=len(devices),
        enabled_signal_count=enabled_count,
        di_count=int(project_summary.get("DI", 0)),
        do_count=int(project_summary.get("DO", 0)),
        ai_count=int(project_summary.get("AI", 0)),
        ao_count=int(project_summary.get("AO", 0)),
        warning_count=len(warnings),
        error_count=len(errors),
        fc_io_row_count=fc_io_result.total_count,
        unaddressed_count=unaddressed,
        duplicate_address_count=duplicate_count,
    )

    out_dir = Path(output_directory) if output_directory else get_default_output_directory()
    fc_io_file = build_default_file_name("fc_io_excel", project_name, revision)
    fc_io_status = _fc_io_status(len(errors), len(warnings))
    tia_file = build_default_file_name("tia_portal_tag_table", project_name, revision)
    tia_status = _fc_io_status(len(tia_errors), len(tia_warnings))

    items: list[GenerateItem] = [
        GenerateItem(
            item_id="fc_io_excel",
            category="Engineering Data",
            display_name="FC_IO Excel",
            file_name=fc_io_file,
            output_format="XLSX",
            enabled=True,
            selected=True,
            status=fc_io_status,
            warning_count=len(warnings),
            error_count=len(errors),
            description=(
                f"Export {fc_io_result.total_count} FC_IO rows "
                f"(DI {fc_io_result.di_count}, DO {fc_io_result.do_count}, "
                f"AI {fc_io_result.ai_count}, AO {fc_io_result.ao_count})."
            ),
            output_path=str(out_dir / fc_io_file),
            dependencies=["FC_IO Generator"],
        ),
        GenerateItem(
            item_id="fc_io_preview_data",
            category="Engineering Data",
            display_name="FC_IO Preview Data",
            file_name="(no file)",
            output_format="Internal",
            enabled=False,
            selected=False,
            status=STATUS_READY,
            warning_count=len(warnings),
            error_count=len(errors),
            description=(
                "In-memory FC_IO preview data. Open FC_IO Preview to review."
            ),
            dependencies=["FC_IO Generator"],
        ),
        GenerateItem(
            item_id="plc_module_mapping_excel",
            category="PLC",
            display_name="PLC Module Mapping Excel",
            file_name=build_default_file_name(
                "plc_module_mapping_excel", project_name, revision
            ),
            output_format="XLSX",
            enabled=False,
            selected=False,
            status=STATUS_NOT_IMPLEMENTED,
            description="PLC module/channel mapping workbook (future).",
            dependencies=["PLC Module Mapping"],
        ),
        GenerateItem(
            item_id="tia_portal_tag_table",
            category="PLC",
            display_name="TIA Portal Tag Table",
            file_name=tia_file,
            output_format="CSV",
            enabled=True,
            selected=False,
            status=tia_status,
            warning_count=len(tia_warnings),
            error_count=len(tia_errors),
            description=(
                f"Export {len(tia_tags)} TIA Portal tags "
                f"(Bool {sum(1 for tag in tia_tags if tag.data_type == 'Bool')}, "
                f"Int {sum(1 for tag in tia_tags if tag.data_type == 'Int')})."
            ),
            output_path=str(out_dir / tia_file),
            dependencies=["TIA Tag Generator"],
        ),
        GenerateItem(
            item_id="plc_program_source",
            category="PLC",
            display_name="PLC Program Source",
            file_name=build_default_file_name(
                "plc_program_source", project_name, revision
            ),
            output_format="SCL",
            enabled=False,
            selected=False,
            status=STATUS_NOT_IMPLEMENTED,
            description="PLC program source generation (future).",
            dependencies=["FC_IO Generator", "PLC Module Mapping"],
        ),
        GenerateItem(
            item_id="eplan_import_data",
            category="EPLAN",
            display_name="EPLAN Import Data",
            file_name=build_default_file_name(
                "eplan_import_data", project_name, revision
            ),
            output_format="XLSX",
            enabled=False,
            selected=False,
            status=STATUS_NOT_IMPLEMENTED,
            description="EPLAN import data export (future).",
            dependencies=["FC_IO Generator"],
        ),
        GenerateItem(
            item_id="device_list_report",
            category="Documentation",
            display_name="Device List Report",
            file_name=build_default_file_name(
                "device_list_report", project_name, revision
            ),
            output_format="XLSX",
            enabled=False,
            selected=False,
            status=STATUS_NOT_IMPLEMENTED,
            description="Device list documentation report (future).",
            dependencies=["Device Manager"],
        ),
        GenerateItem(
            item_id="validation_report",
            category="Documentation",
            display_name="Validation Report",
            file_name=build_default_file_name(
                "validation_report", project_name, revision
            ),
            output_format="XLSX",
            enabled=False,
            selected=False,
            status=STATUS_NOT_IMPLEMENTED,
            description="Project validation report (future).",
            dependencies=["FC_IO Generator", "PLC Module Mapping"],
        ),
    ]

    items.sort(
        key=lambda item: (
            _CATEGORY_ORDER.index(item.category)
            if item.category in _CATEGORY_ORDER
            else len(_CATEGORY_ORDER),
            _ITEM_ORDER.index(item.item_id)
            if item.item_id in _ITEM_ORDER
            else len(_ITEM_ORDER),
        )
    )

    return GeneratePreviewResult(
        items=items,
        summary=summary,
        warnings=warnings,
        errors=errors,
        output_directory=str(out_dir),
        fc_io_result=fc_io_result,
        tia_tags=list(tia_tags),
        tia_warnings=list(tia_warnings),
        tia_errors=list(tia_errors),
    )


def validate_generate_items(
    devices: Sequence[Device],
    items: Sequence[GenerateItem],
    *,
    card_configurations: Sequence[PlcCardConfig] | None = None,
) -> GeneratePreviewResult:
    """Refresh validation and update item statuses from current project data."""
    if not items:
        return build_generate_items(devices, card_configurations=card_configurations)

    # Rebuild from project; preserve selection and output paths where possible.
    base = build_generate_items(devices, card_configurations=card_configurations)
    selection = {item.item_id: item.selected for item in items}
    paths = {item.item_id: item.output_path for item in items}
    file_names = {item.item_id: item.file_name for item in items}

    refreshed: list[GenerateItem] = []
    for item in base.items:
        updated = replace(
            item,
            selected=selection.get(item.item_id, item.selected),
            file_name=file_names.get(item.item_id, item.file_name),
            output_path=paths.get(item.item_id, item.output_path),
        )
        if updated.item_id == "fc_io_excel" and updated.output_path:
            updated = replace(
                updated,
                output_path=str(
                    Path(updated.output_path).parent / updated.file_name
                ),
            )
        if updated.item_id == "tia_portal_tag_table" and updated.output_path:
            updated = replace(
                updated,
                output_path=str(
                    Path(updated.output_path).parent / updated.file_name
                ),
            )
        refreshed.append(updated)

    base.items = refreshed
    return base


def get_project_generation_summary(
    devices: Sequence[Device],
    *,
    customer: str = "",
    project_name: str = "",
    revision: str = "",
    card_configurations: Sequence[PlcCardConfig] | None = None,
) -> ProjectGenerationSummary:
    """Return project summary counts for Generate Preview."""
    return build_generate_items(
        devices,
        customer=customer,
        project_name=project_name,
        revision=revision,
        card_configurations=card_configurations,
    ).summary
