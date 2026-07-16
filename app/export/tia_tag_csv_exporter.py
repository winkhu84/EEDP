"""Export TIA Portal tag tables to CSV."""

from __future__ import annotations

import csv
from collections.abc import Sequence
from pathlib import Path

from app.model.tia_tag import TIATag

_CSV_HEADERS = ("Name", "Data Type", "Logical Address", "Comment")


class TiaTagCsvExportError(Exception):
    """Raised when TIA tag CSV export fails."""


def _normalize_csv_path(file_path: str | Path) -> Path:
    """Validate and normalize a CSV output path."""
    text = str(file_path).strip()
    if not text:
        raise TiaTagCsvExportError("File path is empty.")

    path = Path(text)
    if path.suffix.lower() != ".csv":
        path = path.with_suffix(".csv")

    parent = path.parent
    if str(parent) not in ("", ".") and not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)

    if str(parent) not in ("", ".") and not parent.is_dir():
        raise TiaTagCsvExportError(f"Invalid parent directory: {parent}")

    return path


def export_tia_tags_to_csv(
    tags: Sequence[TIATag],
    file_path: str | Path,
) -> int:
    """Write TIA tags to a UTF-8 CSV file and return exported row count."""
    path = _normalize_csv_path(file_path)

    try:
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\r\n")
            writer.writerow(_CSV_HEADERS)
            row_count = 0
            for tag in tags:
                writer.writerow(
                    [
                        tag.symbol_name,
                        tag.data_type,
                        tag.logical_address,
                        tag.comment,
                    ]
                )
                row_count += 1
    except PermissionError as exc:
        raise TiaTagCsvExportError(
            "Permission denied. The file may be open in Excel or the folder "
            "is read-only."
        ) from exc
    except OSError as exc:
        raise TiaTagCsvExportError(str(exc)) from exc

    return row_count
