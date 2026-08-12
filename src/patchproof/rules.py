"""Deterministic, evidence-backed review rules."""

from __future__ import annotations

import re
from collections.abc import Callable

from patchproof.config import Config, path_matches
from patchproof.models import ChangeSet, Evidence, Finding, Severity

LOCK_FILES = {
    "cargo.lock",
    "composer.lock",
    "gemfile.lock",
    "go.sum",
    "package-lock.json",
    "pnpm-lock.yaml",
    "poetry.lock",
    "uv.lock",
    "yarn.lock",
}

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"\bgh[opsu]_[A-Za-z0-9]{20,}\b")),
    ("AWS access key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    (
        "hard-coded credential",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret|token|password|passwd)\b\s*[:=]\s*"
            r"[\"'][^\"'\s]{12,}[\"']"
        ),
    ),
)

PERMISSION_WRITE = re.compile(
    r"^\s*(?:actions|checks|contents|deployments|discussions|id-token|issues|packages|pages|"
    r"pull-requests|repository-projects|security-events|statuses)\s*:\s*write\s*(?:#.*)?$",
    re.IGNORECASE,
)
PERMISSION_ALL = re.compile(r"^\s*permissions\s*:\s*write-all\s*(?:#.*)?$", re.IGNORECASE)


def redact_possible_secret(text: str) -> str:
    """Replace a line that resembles a credential before it leaves the process."""
    if any(pattern.search(text) for _, pattern in SECRET_PATTERNS):
        return "[REDACTED POSSIBLE SECRET]"
    return text


def _evidence(path: str, line: int, snippet: str) -> Evidence:
    clean = redact_possible_secret(snippet).strip()
    if len(clean) > 160:
        clean = clean[:157] + "..."
    return Evidence(path=path, line=max(1, line), snippet=clean or "(changed line)")


def _large_change(changes: ChangeSet, config: Config) -> list[Finding]:
    if len(changes.files) < config.large_pr_files and changes.changed_lines < config.large_pr_lines:
        return []
    first = changes.files[0]
    return [
        Finding(
            rule_id="PP001",
            title="Large change set",
            description=(
                f"This patch changes {len(changes.files)} files and {changes.changed_lines} lines. "
                "Large reviews are harder to reason about and easier to approve incorrectly."
            ),
            severity=Severity.MEDIUM,
            evidence=[_evidence(first.path, first.first_changed_line, "first changed file")],
            remediation="Split independent concerns or document why an atomic large change is required.",
        )
    ]


def _sensitive_paths(changes: ChangeSet, config: Config) -> list[Finding]:
    findings: list[Finding] = []
    for file in changes.files:
        if path_matches(file.path, config.sensitive_patterns):
            findings.append(
                Finding(
                    rule_id="PP002",
                    title="Sensitive path changed",
                    description=f"`{file.path}` matches a configured sensitive-path pattern.",
                    severity=Severity.HIGH,
                    evidence=[_evidence(file.path, file.first_changed_line, "sensitive path")],
                    remediation="Request review from the owner of this subsystem and verify least privilege.",
                )
            )
    return findings


def _missing_tests(changes: ChangeSet, config: Config) -> list[Finding]:
    source_files = [
        file for file in changes.files if path_matches(file.path, config.source_patterns)
    ]
    tests_changed = any(path_matches(file.path, config.test_patterns) for file in changes.files)
    if not source_files or tests_changed:
        return []
    evidence = [
        _evidence(
            file.path, file.first_changed_line, "source changed without a matching test change"
        )
        for file in source_files[:5]
    ]
    return [
        Finding(
            rule_id="PP003",
            title="Source changed without tests",
            description=(
                f"{len(source_files)} source file(s) changed, but no path matched the configured "
                "test patterns. This is a review prompt, not proof that tests are missing."
            ),
            severity=Severity.MEDIUM,
            evidence=evidence,
            remediation="Add or update focused tests, or explain why existing coverage is sufficient.",
        )
    ]


def _lock_files(changes: ChangeSet, _: Config) -> list[Finding]:
    findings: list[Finding] = []
    for file in changes.files:
        if file.path.rsplit("/", 1)[-1].lower() in LOCK_FILES:
            findings.append(
                Finding(
                    rule_id="PP004",
                    title="Dependency lock file changed",
                    description=f"`{file.path}` changes resolved third-party dependencies.",
                    severity=Severity.MEDIUM,
                    evidence=[_evidence(file.path, file.first_changed_line, "lock file changed")],
                    remediation="Review package provenance, version deltas, and vulnerability scan results.",
                )
            )
    return findings


def _secrets(changes: ChangeSet, _: Config) -> list[Finding]:
    findings: list[Finding] = []
    seen: set[tuple[str, int, str]] = set()
    for file in changes.files:
        for line in file.added_lines:
            for secret_type, pattern in SECRET_PATTERNS:
                if not pattern.search(line.content):
                    continue
                key = (file.path, line.new_line or 1, secret_type)
                if key in seen:
                    continue
                seen.add(key)
                findings.append(
                    Finding(
                        rule_id="PP005",
                        title="Possible secret added",
                        description=(
                            f"An added line resembles a {secret_type}. The value is redacted in the report."
                        ),
                        severity=Severity.CRITICAL,
                        evidence=[
                            _evidence(file.path, line.new_line or 1, "[REDACTED POSSIBLE SECRET]")
                        ],
                        remediation=(
                            "Remove the value, rotate it if it may be real, and use the repository's secret store."
                        ),
                    )
                )
                break
    return findings


def _workflow_permissions(changes: ChangeSet, _: Config) -> list[Finding]:
    findings: list[Finding] = []
    for file in changes.files:
        if not path_matches(file.path, [".github/workflows/*.yml", ".github/workflows/*.yaml"]):
            continue
        evidence = []
        for line in file.added_lines:
            if PERMISSION_ALL.match(line.content) or PERMISSION_WRITE.match(line.content):
                evidence.append(_evidence(file.path, line.new_line or 1, line.content))
        if evidence:
            findings.append(
                Finding(
                    rule_id="PP006",
                    title="GitHub Actions write permission added",
                    description=(
                        "The workflow adds a write-capable GITHUB_TOKEN permission. This may be intended, "
                        "but it expands impact if the workflow executes untrusted input."
                    ),
                    severity=Severity.HIGH,
                    evidence=evidence[:5],
                    remediation=(
                        "Use job-scoped permissions, keep them read-only by default, and never run fork code "
                        "with pull_request_target privileges."
                    ),
                )
            )
    return findings


def _binary_changes(changes: ChangeSet, _: Config) -> list[Finding]:
    return [
        Finding(
            rule_id="PP007",
            title="Binary file changed",
            description=f"`{file.path}` is binary, so its contents cannot be reviewed from this diff.",
            severity=Severity.LOW,
            evidence=[_evidence(file.path, 1, "binary content")],
            remediation="Verify the artifact source, license, checksum, and reproducible build path.",
        )
        for file in changes.files
        if file.binary
    ]


Rule = Callable[[ChangeSet, Config], list[Finding]]

RULES: tuple[tuple[str, str, Rule], ...] = (
    ("PP001", "Large change set", _large_change),
    ("PP002", "Sensitive path changed", _sensitive_paths),
    ("PP003", "Source changed without tests", _missing_tests),
    ("PP004", "Dependency lock file changed", _lock_files),
    ("PP005", "Possible secret added", _secrets),
    ("PP006", "GitHub Actions write permission added", _workflow_permissions),
    ("PP007", "Binary file changed", _binary_changes),
)


def analyze(changes: ChangeSet, config: Config) -> list[Finding]:
    findings: list[Finding] = []
    for rule_id, _, rule in RULES:
        if rule_id not in config.ignore_rules:
            findings.extend(rule(changes, config))
    findings.sort(
        key=lambda item: (
            -item.severity.rank,
            item.rule_id,
            item.evidence[0].path if item.evidence else "",
            item.evidence[0].line if item.evidence else 0,
        )
    )
    return findings
