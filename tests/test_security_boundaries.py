import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from patchproof.ai import _available_evidence, review_with_openai
from patchproof.cli import main
from patchproof.config import Config, filter_excluded
from patchproof.diff_parser import parse_unified_diff
from patchproof.git import GitError, _validate_ref
from patchproof.models import Evidence, Finding, ReviewReport, Severity
from patchproof.renderers import render_json, render_markdown, render_sarif
from patchproof.rules import analyze

SECRET_PATCH = """diff --git a/generated/credentials.py b/generated/credentials.py
--- a/generated/credentials.py
+++ b/generated/credentials.py
@@ -0,0 +1 @@
+token = "ghp_abcdefghijklmnopqrstuvwxyz123456"
"""


def test_excluded_paths_are_removed_before_any_analysis():
    changes = parse_unified_diff(SECRET_PATCH)
    filtered = filter_excluded(changes, Config(exclude_paths=["generated/*"]))

    assert filtered.files == []
    assert analyze(filtered, Config()) == []
    assert _available_evidence(filtered) == ([], set())


def test_cli_exclusion_changes_report_scope(tmp_path: Path):
    patch_path = tmp_path / "secret.patch"
    patch_path.write_text(SECRET_PATCH, encoding="utf-8")
    config_path = tmp_path / "patchproof.toml"
    config_path.write_text('exclude_paths = ["generated/*"]\n', encoding="utf-8")
    output_path = tmp_path / "report.json"

    result = main(
        [
            "review",
            "--diff-file",
            str(patch_path),
            "--config",
            str(config_path),
            "--format",
            "json",
            "--output",
            str(output_path),
        ]
    )

    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert result == 0
    assert report["summary"]["files_changed"] == 0
    assert report["findings"] == []


def test_ai_payload_redacts_possible_credentials():
    payload, allowed = _available_evidence(parse_unified_diff(SECRET_PATCH))

    assert allowed == {("generated/credentials.py", 1)}
    assert payload[0]["added_lines"][0]["text"] == "[REDACTED POSSIBLE SECRET]"
    assert "abcdefghijklmnopqrstuvwxyz" not in json.dumps(payload)


def test_ai_finding_evidence_is_redacted(monkeypatch):
    class FakeResponses:
        @staticmethod
        def create(**_kwargs):
            return SimpleNamespace(
                output_text=json.dumps(
                    {
                        "findings": [
                            {
                                "title": "<img src=x> @all Credential risk",
                                "description": "[Click](https://invalid.example) for instructions.",
                                "path": "generated/credentials.py",
                                "line": 1,
                                "remediation": "# Load it from a secret store.",
                            }
                        ]
                    }
                )
            )

    class FakeOpenAI:
        def __init__(self, **_kwargs):
            self.responses = FakeResponses()

    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))

    findings = review_with_openai(parse_unified_diff(SECRET_PATCH), model="test-model")

    assert findings[0].evidence[0].snippet == "[REDACTED POSSIBLE SECRET]"
    assert findings[0].remediation == "# Load it from a secret store."
    assert "abcdefghijklmnopqrstuvwxyz" not in str(findings[0].to_dict())
    assert findings[0].severity is Severity.INFO
    assert findings[0].gating is False
    rendered = render_markdown(
        ReviewReport(files_changed=1, additions=1, deletions=0, findings=findings)
    )
    assert "<img" not in rendered
    assert "@all" not in rendered
    assert "[Click](" not in rendered
    assert "Gating:** `no (advisory)`" in rendered


@pytest.mark.parametrize(
    "ref",
    ["--output=/tmp/pwn", "main..evil", "main\nother", "$(touch pwn)", ""],
)
def test_git_ref_validation_rejects_unsafe_values(ref: str):
    with pytest.raises(GitError):
        _validate_ref(ref)


def test_cli_rejects_conflicting_input_modes(tmp_path: Path, capsys):
    patch_path = tmp_path / "empty.patch"
    patch_path.write_text("", encoding="utf-8")

    result = main(
        [
            "review",
            "--base",
            "main",
            "--head",
            "HEAD",
            "--diff-file",
            str(patch_path),
        ]
    )

    assert result == 2
    assert "cannot be combined" in capsys.readouterr().err


def test_all_renderers_expose_machine_readable_summary():
    report = ReviewReport(files_changed=0, additions=0, deletions=0, findings=[])

    markdown = render_markdown(report)
    sarif = json.loads(render_sarif(report))

    assert '<!-- patchproof: {"verdict":"clear","risk_score":0} -->' in markdown
    assert sarif["runs"][0]["properties"]["patchproof"] == {
        "verdict": "clear",
        "risk_score": 0,
    }


def test_advisory_findings_never_affect_gating_outputs():
    report = ReviewReport(
        files_changed=1,
        additions=1,
        deletions=0,
        findings=[
            Finding(
                rule_id="AI001",
                title="Advisory",
                description="Model suggestion.",
                severity=Severity.HIGH,
                evidence=[Evidence("src/app.py", 1, "changed()")],
                remediation="Verify manually.",
                source="openai:test",
                gating=False,
            )
        ],
    )

    assert report.risk_score == 0
    assert report.verdict == "clear"
    assert report.should_fail(Severity.INFO) is False
    parsed = json.loads(render_json(report))
    assert parsed["summary"]["gating_findings"] == 0
    assert parsed["summary"]["advisory_findings"] == 1
    assert parsed["findings"][0]["gating"] is False
