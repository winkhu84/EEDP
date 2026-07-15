"""Parse Excel IO lists into device drafts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.engine.device_manager import DeviceDraft
from app.engine.tag_type_resolver import resolve_device_category, resolve_device_type


@dataclass(frozen=True)
class IoListParseResult:
    """Outcome of parsing an FC_IO worksheet."""

    drafts: tuple[DeviceDraft, ...]
    source_rows: int
    unique_tags: int


class IoListParser:
    """Reads an Excel FC_IO sheet and builds unique DeviceDraft entries.

    Columns (1-based Excel letters):
    D = Area, H = IO Category, I = Tag Name, K = PLC Address, U = Remark
    """

    SHEET_NAME = "FC_IO"

    COL_AREA = 3
    COL_IO_CATEGORY = 7
    COL_TAG = 8
    COL_PLC_ADDRESS = 10
    COL_REMARK = 20

    def parse(self, file_path: str | Path) -> IoListParseResult:
        """Parse the workbook and return one draft per unique tag."""
        path = Path(file_path)
        frame = pd.read_excel(
            path,
            sheet_name=self.SHEET_NAME,
            header=None,
            engine="openpyxl",
        )

        drafts_by_tag: dict[str, DeviceDraft] = {}
        source_rows = 0

        for _, row in frame.iterrows():
            tag = self._cell_text(row, self.COL_TAG)
            if not tag or self._is_header_tag(tag):
                continue

            source_rows += 1
            if tag in drafts_by_tag:
                continue

            area = self._cell_text(row, self.COL_AREA) or "COMMON"
            io_category = self._cell_text(row, self.COL_IO_CATEGORY)
            remark = self._cell_text(row, self.COL_REMARK)
            # PLC address is read for future FC_IO use; not applied to Device yet.
            _ = self._cell_text(row, self.COL_PLC_ADDRESS)

            device_type = resolve_device_type(tag)
            category = resolve_device_category(device_type, io_category)

            drafts_by_tag[tag] = DeviceDraft(
                area=area,
                category=category,
                type=device_type,
                tag=tag,
                description=remark,
                quantity=1,
            )

        return IoListParseResult(
            drafts=tuple(drafts_by_tag.values()),
            source_rows=source_rows,
            unique_tags=len(drafts_by_tag),
        )

    @staticmethod
    def _cell_text(row: pd.Series, column_index: int) -> str:
        if column_index >= len(row):
            return ""
        value = row.iloc[column_index]
        if pd.isna(value):
            return ""
        return str(value).strip()

    @staticmethod
    def _is_header_tag(tag: str) -> bool:
        normalized = tag.strip().lower().replace(" ", "")
        return normalized in {"tag", "tagname", "i"}
