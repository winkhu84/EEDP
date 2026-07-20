"""Standalone test for GenerateManager FC_IO exporter integration."""

from __future__ import annotations

from pathlib import Path

from app.engine.generate_manager import GenerateManager, GenerationOptions
from app.engine.recommendation_engine import RecommendationEngine
from app.model.device import Device
from app.model.generation_result import GenerationStatus


def _build_pump_device() -> Device:
    """Create one Pump with its library-recommended signals."""
    device = Device(
        id="1",
        tag="P-101",
        area="PRE",
        category="Equipment",
        type="Pump",
        description="Circulation Pump",
        quantity=1,
    )
    RecommendationEngine().recommend(device)

    # Assign simple unique addresses so FC_IO export is fully usable.
    next_addresses = {
        "DI": ("I0.0", "I0.1", "I0.2"),
        "DO": ("Q0.0", "Q0.1"),
        "AI": (),
        "AO": (),
    }
    counters = {"DI": 0, "DO": 0, "AI": 0, "AO": 0}
    for signal in device.signals:
        io_type = signal.io_type.strip().upper()
        pool = next_addresses.get(io_type, ())
        index = counters.get(io_type, 0)
        if index < len(pool):
            signal.address = pool[index]
            counters[io_type] = index + 1

    return device


def main() -> None:
    devices = [_build_pump_device()]
    options = GenerationOptions(
        generate_fc_io=True,
        generate_tia_csv=True,
        generate_tia_xlsx=True,
    )
    output_directory = "output/generate_manager_test"

    result = GenerateManager().generate(
        output_directory=output_directory,
        options=options,
        devices=devices,
    )

    for artifact in result.artifacts:
        print(
            f"{artifact.artifact_type} | {artifact.status.value} | "
            f"{artifact.output_path} | {artifact.message}"
        )

    print()
    print(f"Success: {result.success_count}")
    print(f"Warning: {result.warning_count}")
    print(f"Error: {result.error_count}")
    print(f"Skipped: {result.skipped_count}")
    print(f"Overall successful: {result.is_successful}")

    by_type = {artifact.artifact_type: artifact for artifact in result.artifacts}
    assert by_type["FC_IO"].status is GenerationStatus.SUCCESS
    assert by_type["TIA_CSV"].status is GenerationStatus.SKIPPED
    assert by_type["TIA_XLSX"].status is GenerationStatus.SKIPPED

    fc_io_path = Path(output_directory) / "FC_IO.xlsx"
    if not fc_io_path.is_file():
        raise AssertionError(f"Expected file does not exist: {fc_io_path}")


if __name__ == "__main__":
    main()
