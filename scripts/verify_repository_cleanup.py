"""Verify repository cleanup: tracked sources, ignored outputs, untracked temps."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

MUST_BE_TRACKED = (
    ".gitignore",
    "requirements.txt",
    "test_generate_manager_fc_io.py",
    "test_tia_xlsx_export.py",
    "app/resources/tia_templates/TIA_V20_PLC_Tags_Template.xlsx",
    "output/.gitkeep",
    "output/generated/.gitkeep",
    "output/test/.gitkeep",
    "output/temp/.gitkeep",
)

MUST_BE_IGNORED = (
    "TIA_V20_Output.xlsx",
    "output/generated/sample.xlsx",
    ".tmp_example.txt",
    "example_stdout.txt",
    "example_stderr.txt",
    "FC_IO_test.xlsx",
    "TIA_Tags_test.csv",
    "Generation_Report_test.txt",
)

MUST_NOT_BE_TRACKED = (
    ".tmp_export_acceptance.py",
    ".tmp_export_stderr.txt",
    ".tmp_export_stdout.txt",
    ".tmp_run_export_test.py",
    "TIA_V20_Output.xlsx",
    "_fc_io_test_out.txt",
)


def _run_git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def _is_tracked(path: str) -> bool:
    result = _run_git("ls-files", "--error-unmatch", "--", path)
    return result.returncode == 0


def _is_ignored(path: str) -> bool:
    result = _run_git("check-ignore", "-q", "--", path)
    return result.returncode == 0


def main() -> int:
    failures = 0

    for path in MUST_BE_TRACKED:
        if _is_tracked(path):
            print(f"PASS | tracked: {path}")
        else:
            print(f"FAIL | expected tracked: {path}")
            failures += 1

    for path in MUST_BE_IGNORED:
        if _is_ignored(path):
            print(f"PASS | ignored: {path}")
        else:
            print(f"FAIL | expected ignored: {path}")
            failures += 1

    for path in MUST_NOT_BE_TRACKED:
        if not _is_tracked(path):
            print(f"PASS | not tracked: {path}")
        else:
            print(f"FAIL | expected not tracked: {path}")
            failures += 1

    if failures == 0:
        print()
        print("Repository cleanup verification passed.")
        return 0

    print()
    print(f"Repository cleanup verification failed: {failures} issue(s).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
