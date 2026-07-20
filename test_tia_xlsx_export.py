"""Standalone smoke test for TIA Portal V20 XLSX export."""

from __future__ import annotations

from app.export.tia_xlsx_exporter import export_tia_tags
from app.model.tia_tag import STATUS_OK, TIATag


def main() -> None:
    tags = [
        TIATag(
            symbol_name="TEST_DI",
            data_type="Bool",
            logical_address="%I0.0",
            comment="Digital input test",
            status=STATUS_OK,
        ),
        TIATag(
            symbol_name="TEST_DO",
            data_type="Bool",
            logical_address="%Q0.0",
            comment="Digital output test",
            status=STATUS_OK,
        ),
        TIATag(
            symbol_name="TEST_AI",
            data_type="Int",
            logical_address="%IW64",
            comment="Analog input test",
            status=STATUS_OK,
        ),
        TIATag(
            symbol_name="TEST_AO",
            data_type="Int",
            logical_address="%QW64",
            comment="Analog output test",
            status=STATUS_OK,
        ),
    ]

    export_tia_tags(tags, "TIA_V20_Output.xlsx")
    print("TIA_V20_Output.xlsx created successfully")


if __name__ == "__main__":
    main()
