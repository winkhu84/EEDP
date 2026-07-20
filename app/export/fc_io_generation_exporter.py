"""FC_IO Excel adapter for the GenerationExporter interface."""

from __future__ import annotations

from pathlib import Path

from app.engine.fc_io_generator import generate_project_rows
from app.export.fc_io_excel_exporter import export_fc_io_workbook
from app.export.generation_exporter import GenerationExporter
from app.model.generation_context import GenerationContext
from app.model.generation_result import GeneratedArtifact, GenerationStatus

_SUCCESS_MESSAGE = "FC_IO Excel generated successfully."


class FCIOGenerationExporter(GenerationExporter):
    """Wrap existing FC_IO generation and Excel export behind GenerationExporter."""

    @property
    def artifact_type(self) -> str:
        return "FC_IO"

    @property
    def display_name(self) -> str:
        return "FC_IO Excel"

    @property
    def default_filename(self) -> str:
        return "FC_IO.xlsx"

    @property
    def category(self) -> str:
        return "Engineering"

    @property
    def sort_order(self) -> int:
        return 10

    @property
    def is_default_enabled(self) -> bool:
        return True

    def export(
        self,
        context: GenerationContext,
        output_directory: str,
    ) -> GeneratedArtifact:
        """Generate FC_IO.xlsx from context devices using existing FC_IO APIs."""
        output_path = self.build_output_path(output_directory)
        file_path = Path(output_path)

        if not context.has_devices:
            return GeneratedArtifact(
                artifact_type=self.artifact_type,
                display_name=self.display_name,
                output_path=output_path,
                status=GenerationStatus.ERROR,
                message="FC_IO export failed: no device data was provided.",
            )

        try:
            fc_io_result = generate_project_rows(context.devices)
            export_fc_io_workbook(
                file_path,
                devices=context.devices,
                result=fc_io_result,
            )
        except Exception as exc:  # noqa: BLE001 — keep generation resilient
            return GeneratedArtifact(
                artifact_type=self.artifact_type,
                display_name=self.display_name,
                output_path=output_path,
                status=GenerationStatus.ERROR,
                message=f"FC_IO export failed: {exc}",
            )

        if not file_path.is_file():
            return GeneratedArtifact(
                artifact_type=self.artifact_type,
                display_name=self.display_name,
                output_path=output_path,
                status=GenerationStatus.ERROR,
                message="FC_IO export failed: output file was not created.",
            )

        return GeneratedArtifact(
            artifact_type=self.artifact_type,
            display_name=self.display_name,
            output_path=output_path,
            status=GenerationStatus.SUCCESS,
            message=_SUCCESS_MESSAGE,
        )
