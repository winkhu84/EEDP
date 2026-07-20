"""Generate Manager — coordinates project deliverable generation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.engine.fc_io_generator import generate_project_rows
from app.engine.tia_tag_generator import generate_sorted_validated_project_tags
from app.export.fc_io_excel_exporter import export_fc_io_workbook
from app.export.tia_tag_csv_exporter import export_tia_tags_to_csv
from app.export.tia_xlsx_exporter import export_tia_tags
from app.model.device import Device
from app.model.generation_result import (
    GeneratedArtifact,
    GenerationResult,
    GenerationStatus,
)
from app.model.tia_tag import TIATag

_FC_IO_SUCCESS_MESSAGE = "FC_IO Excel generated successfully."
_TIA_CSV_SUCCESS_MESSAGE = "TIA Tag CSV generated successfully."
_TIA_XLSX_SUCCESS_MESSAGE = "TIA Portal V20 tag workbook generated successfully."
_REPORT_SUCCESS_MESSAGE = "Generation report created successfully."
_REPORT_FILE_NAME = "Generation_Report.txt"


@dataclass
class GenerationOptions:
    """User-selected outputs for a generation run."""

    generate_fc_io: bool = True
    generate_tia_csv: bool = True
    generate_tia_xlsx: bool = True
    create_run_subdirectory: bool = True


class GenerateManager:
    """Orchestrates generation of selected engineering artifacts."""

    def generate(
        self,
        output_directory: str,
        options: GenerationOptions,
        devices: list[Device] | None = None,
    ) -> GenerationResult:
        """Generate selected artifacts into a resolved run directory."""
        directory = output_directory.strip()
        if not directory:
            raise ValueError("Output directory must not be blank.")

        parent_path = Path(directory)
        parent_path.mkdir(parents=True, exist_ok=True)
        run_directory = self._resolve_run_directory(
            parent_path,
            create_subdirectory=options.create_run_subdirectory,
        )

        result = GenerationResult(output_directory=str(run_directory))
        tia_tag_cache: dict[str, Any] = {}

        if options.generate_fc_io:
            result.add_artifact(self._generate_fc_io(run_directory, devices))

        if options.generate_tia_csv:
            result.add_artifact(
                self._generate_tia_csv(run_directory, devices, tia_tag_cache)
            )

        if options.generate_tia_xlsx:
            result.add_artifact(
                self._generate_tia_xlsx(run_directory, devices, tia_tag_cache)
            )

        engineering_artifacts = list(result.artifacts)
        result.add_artifact(
            self._create_generation_report(run_directory, engineering_artifacts)
        )

        return result

    def _resolve_run_directory(
        self,
        output_directory: Path,
        *,
        create_subdirectory: bool,
    ) -> Path:
        """Return the directory that will receive generated artifacts."""
        if not create_subdirectory:
            return output_directory

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        candidates = [stamp, *(f"{stamp}_{index:02d}" for index in range(1, 100))]
        for name in candidates:
            candidate = output_directory / name
            try:
                candidate.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                continue
            return candidate

        raise RuntimeError(
            "Unable to create a unique timestamped generation run directory."
        )

    def _create_generation_report(
        self,
        run_directory: Path,
        engineering_artifacts: Sequence[GeneratedArtifact],
    ) -> GeneratedArtifact:
        """Write Generation_Report.txt summarizing engineering artifacts only."""
        report_path = run_directory / _REPORT_FILE_NAME
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        success_count = sum(
            1
            for artifact in engineering_artifacts
            if artifact.status is GenerationStatus.SUCCESS
        )
        warning_count = sum(
            1
            for artifact in engineering_artifacts
            if artifact.status is GenerationStatus.WARNING
        )
        error_count = sum(
            1
            for artifact in engineering_artifacts
            if artifact.status is GenerationStatus.ERROR
        )
        skipped_count = sum(
            1
            for artifact in engineering_artifacts
            if artifact.status is GenerationStatus.SKIPPED
        )
        overall_successful = (
            bool(engineering_artifacts)
            and error_count == 0
            and success_count > 0
        )

        lines = [
            "EEDP Generation Report",
            f"Generated At: {generated_at}",
            f"Output Directory: {run_directory}",
            "",
            "Artifacts:",
        ]
        for artifact in engineering_artifacts:
            file_name = Path(artifact.output_path).name
            lines.append(
                f"{artifact.artifact_type} | {artifact.status.value} | "
                f"{file_name} | {artifact.message}"
            )

        lines.extend(
            [
                "",
                "Summary:",
                f"Success: {success_count}",
                f"Warning: {warning_count}",
                f"Error: {error_count}",
                f"Skipped: {skipped_count}",
                f"Overall Successful: {overall_successful}",
                "",
            ]
        )

        try:
            report_path.write_text("\n".join(lines), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001 — keep generation resilient
            return GeneratedArtifact(
                artifact_type="GENERATION_REPORT",
                display_name="Generation Report",
                output_path=str(report_path),
                status=GenerationStatus.ERROR,
                message=f"Generation report failed: {exc}",
            )

        if not report_path.is_file():
            return GeneratedArtifact(
                artifact_type="GENERATION_REPORT",
                display_name="Generation Report",
                output_path=str(report_path),
                status=GenerationStatus.ERROR,
                message="Generation report failed: report file was not created.",
            )

        return GeneratedArtifact(
            artifact_type="GENERATION_REPORT",
            display_name="Generation Report",
            output_path=str(report_path),
            status=GenerationStatus.SUCCESS,
            message=_REPORT_SUCCESS_MESSAGE,
        )

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

    def _generate_tia_csv(
        self,
        output_directory: Path,
        devices: Sequence[Device] | None,
        tia_tag_cache: dict[str, Any],
    ) -> GeneratedArtifact:
        """Export TIA Tag CSV using the existing tag generator and CSV exporter."""
        file_path = output_directory / "TIA_Tags.csv"

        if devices is None or len(devices) == 0:
            return GeneratedArtifact(
                artifact_type="TIA_CSV",
                display_name="TIA Tag CSV",
                output_path=str(file_path),
                status=GenerationStatus.ERROR,
                message="TIA CSV export failed: no device data was provided.",
            )

        try:
            tags = self._get_or_build_tia_tags(devices, tia_tag_cache)
            export_tia_tags_to_csv(tags, file_path)
        except Exception as exc:  # noqa: BLE001 — keep generation resilient
            return GeneratedArtifact(
                artifact_type="TIA_CSV",
                display_name="TIA Tag CSV",
                output_path=str(file_path),
                status=GenerationStatus.ERROR,
                message=f"TIA CSV export failed: {exc}",
            )

        if not file_path.is_file():
            return GeneratedArtifact(
                artifact_type="TIA_CSV",
                display_name="TIA Tag CSV",
                output_path=str(file_path),
                status=GenerationStatus.ERROR,
                message="TIA CSV export failed: output file was not created.",
            )

        return GeneratedArtifact(
            artifact_type="TIA_CSV",
            display_name="TIA Tag CSV",
            output_path=str(file_path),
            status=GenerationStatus.SUCCESS,
            message=_TIA_CSV_SUCCESS_MESSAGE,
        )

    def _generate_tia_xlsx(
        self,
        output_directory: Path,
        devices: Sequence[Device] | None,
        tia_tag_cache: dict[str, Any],
    ) -> GeneratedArtifact:
        """Export TIA V20 XLSX using the Siemens template-based exporter."""
        file_path = output_directory / "TIA_V20_Tags.xlsx"

        if devices is None or len(devices) == 0:
            return GeneratedArtifact(
                artifact_type="TIA_XLSX",
                display_name="TIA Portal V20 Tags",
                output_path=str(file_path),
                status=GenerationStatus.ERROR,
                message="TIA XLSX export failed: no device data was provided.",
            )

        try:
            tags = self._get_or_build_tia_tags(devices, tia_tag_cache)
            export_tia_tags(list(tags), str(file_path))
        except FileNotFoundError as exc:
            return GeneratedArtifact(
                artifact_type="TIA_XLSX",
                display_name="TIA Portal V20 Tags",
                output_path=str(file_path),
                status=GenerationStatus.ERROR,
                message=(
                    "TIA XLSX export failed: Siemens template file was not found. "
                    f"({exc})"
                ),
            )
        except Exception as exc:  # noqa: BLE001 — keep generation resilient
            return GeneratedArtifact(
                artifact_type="TIA_XLSX",
                display_name="TIA Portal V20 Tags",
                output_path=str(file_path),
                status=GenerationStatus.ERROR,
                message=f"TIA XLSX export failed: {exc}",
            )

        if not file_path.is_file():
            return GeneratedArtifact(
                artifact_type="TIA_XLSX",
                display_name="TIA Portal V20 Tags",
                output_path=str(file_path),
                status=GenerationStatus.ERROR,
                message="TIA XLSX export failed: output file was not created.",
            )

        return GeneratedArtifact(
            artifact_type="TIA_XLSX",
            display_name="TIA Portal V20 Tags",
            output_path=str(file_path),
            status=GenerationStatus.SUCCESS,
            message=_TIA_XLSX_SUCCESS_MESSAGE,
        )

    @staticmethod
    def _get_or_build_tia_tags(
        devices: Sequence[Device],
        cache: dict[str, Any],
    ) -> list[TIATag]:
        """Generate project TIA tags once per generate() call and reuse them."""
        if "tags" in cache:
            return cache["tags"]
        if "error" in cache:
            raise cache["error"]

        try:
            tags, _warnings, _errors = generate_sorted_validated_project_tags(devices)
        except Exception as exc:  # noqa: BLE001
            cache["error"] = exc
            raise

        cache["tags"] = tags
        return tags
