"""Generate Manager — coordinates project deliverable generation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from app.engine.fc_io_generator import generate_project_rows
from app.export.fc_io_excel_exporter import export_fc_io_workbook
from app.model.device import Device
from app.model.generation_result import (
    GeneratedArtifact,
    GenerationResult,
    GenerationStatus,
)

_PLACEHOLDER_MESSAGE = "Exporter is not connected yet."
_FC_IO_SUCCESS_MESSAGE = "FC_IO Excel generated successfully."


@dataclass
class GenerationOptions:
    """User-selected outputs for a generation run."""

    generate_fc_io: bool = True
    generate_tia_csv: bool = True
    generate_tia_xlsx: bool = True


class GenerateManager:
    """Orchestrates generation of selected engineering artifacts."""

    def generate(
        self,
        output_directory: str,
        options: GenerationOptions,
        devices: list[Device] | None = None,
    ) -> GenerationResult:
        """Generate selected artifacts into output_directory."""
        directory = output_directory.strip()
        if not directory:
            raise ValueError("Output directory must not be blank.")

        output_path = Path(directory)
        output_path.mkdir(parents=True, exist_ok=True)

        result = GenerationResult(output_directory=str(output_path))

        if options.generate_fc_io:
            result.add_artifact(self._generate_fc_io(output_path, devices))

        if options.generate_tia_csv:
            result.add_artifact(
                GeneratedArtifact(
                    artifact_type="TIA_CSV",
                    display_name="TIA Tag CSV",
                    output_path=str(output_path / "TIA_Tags.csv"),
                    status=GenerationStatus.SKIPPED,
                    message=_PLACEHOLDER_MESSAGE,
                )
            )

        if options.generate_tia_xlsx:
            result.add_artifact(
                GeneratedArtifact(
                    artifact_type="TIA_XLSX",
                    display_name="TIA Portal V20 Tags",
                    output_path=str(output_path / "TIA_V20_Tags.xlsx"),
                    status=GenerationStatus.SKIPPED,
                    message=_PLACEHOLDER_MESSAGE,
                )
            )

        return result

    def _generate_fc_io(
        self,
        output_directory: Path,
        devices: Sequence[Device] | None,
    ) -> GeneratedArtifact:
        """Export FC_IO Excel using the existing FC_IO exporter."""
        file_path = output_directory / "FC_IO.xlsx"

        if devices is None or len(devices) == 0:
            return GeneratedArtifact(
                artifact_type="FC_IO",
                display_name="FC_IO Excel",
                output_path=str(file_path),
                status=GenerationStatus.ERROR,
                message="FC_IO export failed: no device data was provided.",
            )

        try:
            fc_io_result = generate_project_rows(devices)
            export_fc_io_workbook(
                file_path,
                devices=devices,
                result=fc_io_result,
            )
        except Exception as exc:  # noqa: BLE001 — keep generation resilient
            return GeneratedArtifact(
                artifact_type="FC_IO",
                display_name="FC_IO Excel",
                output_path=str(file_path),
                status=GenerationStatus.ERROR,
                message=f"FC_IO export failed: {exc}",
            )

        if not file_path.is_file():
            return GeneratedArtifact(
                artifact_type="FC_IO",
                display_name="FC_IO Excel",
                output_path=str(file_path),
                status=GenerationStatus.ERROR,
                message="FC_IO export failed: output file was not created.",
            )

        return GeneratedArtifact(
            artifact_type="FC_IO",
            display_name="FC_IO Excel",
            output_path=str(file_path),
            status=GenerationStatus.SUCCESS,
            message=_FC_IO_SUCCESS_MESSAGE,
        )
