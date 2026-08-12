from pathlib import Path

import pytest

from patchproof.action_support import UnsafeOutputPath, resolve_output_path


def test_action_output_path_resolves_inside_workspace(tmp_path: Path):
    expected = tmp_path / "reports" / "patchproof.md"
    assert resolve_output_path(tmp_path, "reports/patchproof.md") == expected


@pytest.mark.parametrize("value", ["", "../outside.md", "report.md\nverdict=clear"])
def test_action_output_path_rejects_unsafe_values(tmp_path: Path, value: str):
    with pytest.raises(UnsafeOutputPath):
        resolve_output_path(tmp_path, value)


def test_action_output_path_rejects_symlink(tmp_path: Path):
    outside = tmp_path.parent / "outside-report.md"
    outside.write_text("do not overwrite", encoding="utf-8")
    link = tmp_path / "patchproof-report.md"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("creating symbolic links is unavailable on this platform")

    with pytest.raises(UnsafeOutputPath, match="symbolic links"):
        resolve_output_path(tmp_path, link.name)
    assert outside.read_text(encoding="utf-8") == "do not overwrite"
