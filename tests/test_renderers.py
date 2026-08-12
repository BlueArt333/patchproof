import json

from patchproof.models import Evidence, Finding, ReviewReport, Severity
from patchproof.renderers import render_json, render_markdown, render_sarif


def _report() -> ReviewReport:
    return ReviewReport(
        files_changed=1,
        additions=2,
        deletions=1,
        findings=[
            Finding(
                rule_id="PP999",
                title="Example",
                description="An example finding.",
                severity=Severity.HIGH,
                evidence=[Evidence("src/`odd`.py", 7, "print('hello')")],
                remediation="Review it.",
            )
        ],
    )


def test_json_is_stable_and_has_summary():
    parsed = json.loads(render_json(_report()))
    assert parsed["summary"]["verdict"] == "needs-attention"
    assert parsed["summary"]["risk_score"] == 20


def test_markdown_escapes_inline_code_path():
    text = render_markdown(_report())
    assert "``src/`odd`.py:7``" in text


def test_sarif_is_valid_shape():
    parsed = json.loads(render_sarif(_report()))
    run = parsed["runs"][0]
    assert parsed["version"] == "2.1.0"
    assert run["results"][0]["ruleId"] == "PP999"
    assert run["results"][0]["locations"][0]["physicalLocation"]["region"]["startLine"] == 7


def test_markdown_neutralizes_untrusted_finding_and_evidence_text():
    report = _report()
    finding = report.findings[0]
    finding.title = "<img src=x> @all"
    finding.description = "## forged heading"
    finding.remediation = "[click](https://invalid.example)"
    finding.evidence = [Evidence("src/`odd`.py", 7, "```\n## forged\n```")]

    text = render_markdown(report)

    assert "<img" not in text
    assert "@all" not in text
    assert "\n## forged heading" not in text

    assert "[click](" not in text
    assert "```` ``` ## forged ``` ````" in text


def test_sarif_encodes_repository_paths_as_uris():
    report = _report()
    report.findings[0].evidence = [Evidence("src/café #1.py", 7, "changed")]

    uri = json.loads(render_sarif(report))["runs"][0]["results"][0]["locations"][0][
        "physicalLocation"
    ]["artifactLocation"]["uri"]
    assert uri == "src/caf%C3%A9%20%231.py"
