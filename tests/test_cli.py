import io
import json
from pathlib import Path

from patchproof.cli import main


def test_review_writes_json_before_failing(tmp_path: Path):
    patch = tmp_path / "change.patch"
    patch.write_text(
        """diff --git a/src/auth/a.py b/src/auth/a.py
--- a/src/auth/a.py
+++ b/src/auth/a.py
@@ -0,0 +1 @@
+password = "this-is-a-real-looking-password"
""",
        encoding="utf-8",
    )
    output = tmp_path / "report.json"

    result = main(
        [
            "review",
            "--diff-file",
            str(patch),
            "--format",
            "json",
            "--output",
            str(output),
            "--fail-on",
            "high",
        ]
    )

    assert result == 1
    parsed = json.loads(output.read_text(encoding="utf-8"))
    assert parsed["summary"]["verdict"] == "needs-attention"


def test_empty_patch_is_clear(tmp_path: Path, capsys):
    patch = tmp_path / "empty.patch"
    patch.write_text("", encoding="utf-8")
    result = main(["review", "--diff-file", str(patch), "--format", "json"])
    assert result == 0
    assert json.loads(capsys.readouterr().out)["summary"]["verdict"] == "clear"


def test_base_requires_head(capsys):
    result = main(["review", "--base", "main"])
    assert result == 2
    assert "supplied together" in capsys.readouterr().err


def test_ai_without_key_falls_back(tmp_path: Path, capsys, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    patch = tmp_path / "empty.patch"
    patch.write_text("", encoding="utf-8")
    result = main(["review", "--diff-file", str(patch), "--ai"])
    assert result == 0
    assert "AI review skipped" in capsys.readouterr().err


def test_init_refuses_overwrite(tmp_path: Path, capsys):
    destination = tmp_path / "patchproof.toml"
    destination.write_text("mine=true", encoding="utf-8")
    assert main(["init", "--path", str(destination)]) == 2
    assert destination.read_text(encoding="utf-8") == "mine=true"
    assert "refusing to overwrite" in capsys.readouterr().err


def test_stdout_falls_back_to_utf8_for_legacy_windows_encoding(monkeypatch):
    from patchproof import cli

    raw = io.BytesIO()
    legacy_stdout = io.TextIOWrapper(raw, encoding="ascii")
    monkeypatch.setattr(cli.sys, "stdout", legacy_stdout)

    cli._write_report("中文 ✅\n", None)
    legacy_stdout.flush()

    assert raw.getvalue().endswith("中文 ✅\n".encode())


def test_no_config_ignores_discovered_untrusted_config(tmp_path: Path):
    (tmp_path / "patchproof.toml").write_text(
        '[patchproof]\nfail_on="never"\nignore_rules=["PP005"]\n', encoding="utf-8"
    )
    patch = tmp_path / "change.patch"
    patch.write_text(
        """diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -0,0 +1 @@
+token = "this-is-a-real-looking-password"
""",
        encoding="utf-8",
    )
    output = tmp_path / "report.json"

    result = main(
        [
            "review",
            "--repo",
            str(tmp_path),
            "--diff-file",
            str(patch),
            "--no-config",
            "--format",
            "json",
            "--output",
            str(output),
        ]
    )

    assert result == 1
    assert {item["rule_id"] for item in json.loads(output.read_text())["findings"]} >= {"PP005"}


def test_require_ai_requires_ai(capsys):
    assert main(["review", "--require-ai"]) == 2
    assert "--require-ai requires --ai" in capsys.readouterr().err


def test_model_requires_ai(capsys):
    assert main(["review", "--model", "gpt-test"]) == 2
    assert "--model requires --ai" in capsys.readouterr().err
