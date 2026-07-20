"""Export TIA Portal PLC tags using a Siemens native V20 XLSX template."""

from __future__ import annotations

import shutil
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from pathlib import Path

from app.model.tia_export_profile import (
    TIA_V20_EXPORT_PROFILE,
    TIAExportProfile,
    validate_export_profile,
)
from app.model.tia_tag import TIATag

_SPREADSHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_XML_NS = "http://www.w3.org/XML/1998/namespace"

_TEMPLATE_PATH = (
    Path(__file__).resolve().parents[1]
    / "resources"
    / "tia_templates"
    / "TIA_V20_PLC_Tags_Template.xlsx"
)

_REQUIRED_ZIP_ENTRIES = (
    "[Content_Types].xml",
    "docProps/custom.xml",
    "xl/workbook.xml",
    "xl/styles.xml",
    "xl/_rels/workbook.xml.rels",
    "xl/sharedStrings.xml",
    "xl/worksheets/sheet.xml",
    "xl/worksheets/sheet2.xml",
)

_REPLACE_ZIP_ENTRIES = frozenset(
    {
        "xl/sharedStrings.xml",
        "xl/worksheets/sheet.xml",
        "xl/worksheets/sheet2.xml",
    }
)

ET.register_namespace("x", _SPREADSHEET_NS)


class SharedStringTable:
    """Deduplicated shared-string table for Siemens XLSX packages."""

    def __init__(self) -> None:
        self._strings: list[str] = []
        self._index: dict[str, int] = {}

    def add(self, value: object) -> int:
        text = "" if value is None else str(value)
        existing = self._index.get(text)
        if existing is not None:
            return existing
        index = len(self._strings)
        self._strings.append(text)
        self._index[text] = index
        return index

    def to_xml_bytes(self) -> bytes:
        root = ET.Element(f"{{{_SPREADSHEET_NS}}}sst")
        root.set("uniqueCount", str(len(self._strings)))
        for text in self._strings:
            si = ET.SubElement(root, f"{{{_SPREADSHEET_NS}}}si")
            t_elem = ET.SubElement(si, f"{{{_SPREADSHEET_NS}}}t")
            t_elem.set(f"{{{_XML_NS}}}space", "preserve")
            t_elem.text = text
        return _serialize_spreadsheet_xml(root)


class TIAWorkbookExporter:
    """Build a TIA Portal V20 PLC Tag workbook from a Siemens native template."""

    def __init__(
        self,
        profile: TIAExportProfile | None = None,
        *,
        template_path: Path | None = None,
    ) -> None:
        self._profile = profile or TIA_V20_EXPORT_PROFILE
        errors = validate_export_profile(self._profile)
        if errors:
            raise ValueError("; ".join(errors))
        self._template_path = template_path or _TEMPLATE_PATH

    def export(self, tags: Sequence[TIATag] | None, output_path: str | Path) -> Path:
        """Copy the Siemens template and replace tag worksheet content."""
        if tags is None:
            raise ValueError("tags must not be None.")

        path = self._normalize_output_path(output_path)
        self._validate_template()

        strings = SharedStringTable()
        sheet1_xml = self._build_plc_tags_sheet(tags, strings)
        sheet2_xml = self._build_tag_properties_sheet(strings)
        shared_xml = strings.to_xml_bytes()

        path.parent.mkdir(parents=True, exist_ok=True)
        self._write_package(
            path,
            replacements={
                "xl/sharedStrings.xml": shared_xml,
                "xl/worksheets/sheet.xml": sheet1_xml,
                "xl/worksheets/sheet2.xml": sheet2_xml,
            },
        )
        return path

    def _validate_template(self) -> None:
        if not self._template_path.is_file():
            raise FileNotFoundError(
                f"Siemens TIA V20 template not found: {self._template_path}"
            )

        try:
            with zipfile.ZipFile(self._template_path) as archive:
                names = set(archive.namelist())
        except zipfile.BadZipFile as exc:
            raise ValueError(
                f"Siemens TIA V20 template is not a valid XLSX package: "
                f"{self._template_path}"
            ) from exc

        missing = [name for name in _REQUIRED_ZIP_ENTRIES if name not in names]
        if missing:
            raise ValueError(
                "Siemens TIA V20 template is missing required entries: "
                + ", ".join(missing)
            )

    def _build_plc_tags_sheet(
        self,
        tags: Sequence[TIATag],
        strings: SharedStringTable,
    ) -> bytes:
        rows: list[list[object]] = [list(self._profile.plc_tag_headers)]
        for tag in tags:
            rows.append(
                [
                    tag.symbol_name,
                    self._profile.default_path,
                    tag.data_type,
                    tag.logical_address,
                    tag.comment,
                    _bool_text(self._profile.default_hmi_visible),
                    _bool_text(self._profile.default_hmi_accessible),
                    _bool_text(self._profile.default_hmi_writeable),
                    self._profile.default_typeobject_id,
                    self._profile.default_version_id,
                ]
            )
        return _build_worksheet_xml(rows, strings)

    def _build_tag_properties_sheet(self, strings: SharedStringTable) -> bytes:
        rows = [
            list(self._profile.tag_property_headers),
            [
                self._profile.default_path,
                self._profile.default_belongs_to_unit,
                self._profile.default_accessibility,
            ],
        ]
        return _build_worksheet_xml(rows, strings)

    def _write_package(
        self,
        output_path: Path,
        *,
        replacements: dict[str, bytes],
    ) -> None:
        with tempfile.TemporaryDirectory(prefix=".tmp_tia_xlsx_") as temp_dir:
            temp_path = Path(temp_dir) / output_path.name
            with zipfile.ZipFile(self._template_path, "r") as source:
                with zipfile.ZipFile(
                    temp_path,
                    "w",
                    compression=zipfile.ZIP_DEFLATED,
                ) as target:
                    for info in source.infolist():
                        if info.filename in _REPLACE_ZIP_ENTRIES:
                            continue
                        target.writestr(info, source.read(info.filename))

                    for name, payload in replacements.items():
                        target.writestr(
                            name,
                            payload,
                            compress_type=zipfile.ZIP_DEFLATED,
                        )

            shutil.copy2(temp_path, output_path)

    @staticmethod
    def _normalize_output_path(output_path: str | Path) -> Path:
        text = str(output_path).strip()
        if not text:
            raise ValueError("Output path is empty.")
        path = Path(text)
        if path.suffix.lower() != ".xlsx":
            raise ValueError(
                f"Output extension must be .xlsx, got: {path.suffix or '(none)'}"
            )
        return path


def export_tia_tags(tags: list[TIATag], output_path: str) -> Path:
    """Export TIA tags to a Siemens-compatible TIA Portal V20 XLSX workbook."""
    return TIAWorkbookExporter().export(tags, output_path)


def _bool_text(value: bool) -> str:
    return "True" if value else "False"


def _column_letter(index: int) -> str:
    """Return 1-based Excel column letter (A, B, ...)."""
    result = []
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        result.append(chr(65 + remainder))
    return "".join(reversed(result))


def _build_worksheet_xml(
    rows: Sequence[Sequence[object]],
    strings: SharedStringTable,
) -> bytes:
    root = ET.Element(f"{{{_SPREADSHEET_NS}}}worksheet")
    sheet_data = ET.SubElement(root, f"{{{_SPREADSHEET_NS}}}sheetData")

    for row_number, row_values in enumerate(rows, start=1):
        row_elem = ET.SubElement(sheet_data, f"{{{_SPREADSHEET_NS}}}row")
        row_elem.set("r", str(row_number))
        for column_number, value in enumerate(row_values, start=1):
            cell = ET.SubElement(row_elem, f"{{{_SPREADSHEET_NS}}}c")
            cell.set("r", f"{_column_letter(column_number)}{row_number}")
            cell.set("s", "0")
            cell.set("t", "s")
            value_elem = ET.SubElement(cell, f"{{{_SPREADSHEET_NS}}}v")
            value_elem.text = str(strings.add(value))

    return _serialize_spreadsheet_xml(root)


def _serialize_spreadsheet_xml(root: ET.Element) -> bytes:
    """Serialize spreadsheet XML with UTF-8 BOM and Siemens-style declaration."""
    body = ET.tostring(root, encoding="utf-8")
    return b'\xef\xbb\xbf<?xml version="1.0" encoding="utf-8"?>' + body
