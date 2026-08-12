"""Stable Markdown, JSON, and SARIF report renderers."""

from __future__ import annotations

import json
from urllib.parse import quote

from patchproof.models import ReviewReport, Severity

ICONS = {
    Severity.CRITICAL: "🚨",
    Severity.HIGH: "🔴",
    Severity.MEDIUM: "🟠",
    Severity.LOW: "🟡",
    Severity.INFO: "🔵",
}


def _plain_text(value: str) -> str:
    """Neutralize text from diffs or providers before embedding it in Markdown."""
    text = " ".join(value.split())
    replacements = str.maketrans(
        {character: f"&#{ord(character)};" for character in "\\`*_{}[]()#+-.!|@<>"}
    )
    return text.translate(replacements)


def _code_span(value: str) -> str:
    """Return a CommonMark code span with a safe, minimal delimiter."""
    text = " ".join(value.split())
    longest = 0
    current = 0
    for character in text:
        current = current + 1 if character == "`" else 0
        longest = max(longest, current)
    delimiter = "`" * (longest + 1)
    padding = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{delimiter}{padding}{text}{padding}{delimiter}"


def render_markdown(report: ReviewReport) -> str:
    lines = [
        "# PatchProof review",
        "",
        "<!-- patchproof: "
        + json.dumps(
            {"verdict": report.verdict, "risk_score": report.risk_score},
            separators=(",", ":"),
        )
        + " -->",
        "",
        f"**Verdict:** `{report.verdict}` &nbsp; **Risk score:** `{report.risk_score}/100`",
        "",
        f"Reviewed **{report.files_changed}** files: `+{report.additions}` / `-{report.deletions}` lines.",
        "",
    ]
    if not report.findings:
        lines.extend(
            [
                "✅ No configured risk signals were found.",
                "",
                "> PatchProof checks risk signals; it does not prove that a change is correct or secure.",
            ]
        )
        return "\n".join(lines) + "\n"

    lines.extend(["## Findings", ""])
    for finding in report.findings:
        lines.extend(
            [
                f"### {ICONS[finding.severity]} {finding.rule_id}: {_plain_text(finding.title)}",
                "",
                f"**Severity:** `{finding.severity.value}` &nbsp; **Source:** {_code_span(finding.source)} "
                f"&nbsp; **Gating:** `{'yes' if finding.gating else 'no (advisory)'}`",
                "",
                _plain_text(finding.description),
                "",
                "Evidence:",
                "",
            ]
        )
        for evidence in finding.evidence:
            lines.append(
                f"- {_code_span(f'{evidence.path}:{evidence.line}')} — "
                f"{_code_span(evidence.snippet)}"
            )
        lines.extend(["", f"**Suggested action:** {_plain_text(finding.remediation)}", ""])
    lines.extend(
        [
            "---",
            "",
            "> PatchProof checks risk signals; it does not prove that a change is correct or secure.",
        ]
    )
    return "\n".join(lines) + "\n"


def render_json(report: ReviewReport) -> str:
    return json.dumps(report.to_dict(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def render_sarif(report: ReviewReport) -> str:
    rules: dict[str, dict[str, object]] = {}
    results: list[dict[str, object]] = []
    level_map = {
        Severity.CRITICAL: "error",
        Severity.HIGH: "error",
        Severity.MEDIUM: "warning",
        Severity.LOW: "note",
        Severity.INFO: "note",
    }
    for finding in report.findings:
        rules.setdefault(
            finding.rule_id,
            {
                "id": finding.rule_id,
                "name": finding.title.replace(" ", ""),
                "shortDescription": {"text": finding.title},
                "help": {"text": finding.remediation},
                "properties": {"tags": ["code-review", "patchproof", finding.severity.value]},
            },
        )
        locations = [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": quote(evidence.path.replace("\\", "/"), safe="/")},
                    "region": {"startLine": evidence.line},
                },
                "message": {"text": evidence.snippet},
            }
            for evidence in finding.evidence
        ]
        results.append(
            {
                "ruleId": finding.rule_id,
                "level": level_map[finding.severity],
                "message": {"text": finding.description},
                "locations": locations,
                "properties": {
                    "source": finding.source,
                    "severity": finding.severity.value,
                    "gating": finding.gating,
                },
            }
        )
    document = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "PatchProof",
                        "informationUri": "https://github.com/BlueArt333/patchproof",
                        "semanticVersion": "0.1.0",
                        "rules": [rules[key] for key in sorted(rules)],
                    }
                },
                "properties": {
                    "patchproof": {
                        "verdict": report.verdict,
                        "risk_score": report.risk_score,
                    }
                },
                "results": results,
            }
        ],
    }
    return json.dumps(document, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
