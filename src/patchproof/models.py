"""Domain models shared by the parser, rules, and renderers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class Severity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return {
            Severity.INFO: 0,
            Severity.LOW: 1,
            Severity.MEDIUM: 2,
            Severity.HIGH: 3,
            Severity.CRITICAL: 4,
        }[self]

    @property
    def weight(self) -> int:
        return {
            Severity.INFO: 1,
            Severity.LOW: 4,
            Severity.MEDIUM: 10,
            Severity.HIGH: 20,
            Severity.CRITICAL: 30,
        }[self]

    @classmethod
    def parse(cls, value: str) -> Severity:
        try:
            return cls(value.lower())
        except ValueError as exc:
            choices = ", ".join(item.value for item in cls)
            raise ValueError(f"unknown severity {value!r}; choose one of: {choices}") from exc


class LineKind(StrEnum):
    CONTEXT = "context"
    ADD = "add"
    REMOVE = "remove"


@dataclass(frozen=True, slots=True)
class DiffLine:
    kind: LineKind
    content: str
    old_line: int | None
    new_line: int | None


@dataclass(slots=True)
class Hunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    section: str = ""
    lines: list[DiffLine] = field(default_factory=list)


@dataclass(slots=True)
class ChangedFile:
    old_path: str
    new_path: str
    status: str = "modified"
    hunks: list[Hunk] = field(default_factory=list)
    binary: bool = False

    @property
    def path(self) -> str:
        return self.new_path if self.new_path != "/dev/null" else self.old_path

    @property
    def added_lines(self) -> list[DiffLine]:
        return [line for hunk in self.hunks for line in hunk.lines if line.kind == LineKind.ADD]

    @property
    def removed_lines(self) -> list[DiffLine]:
        return [line for hunk in self.hunks for line in hunk.lines if line.kind == LineKind.REMOVE]

    @property
    def first_changed_line(self) -> int:
        for hunk in self.hunks:
            for line in hunk.lines:
                if line.kind == LineKind.ADD and line.new_line is not None:
                    return line.new_line
        return 1


@dataclass(slots=True)
class ChangeSet:
    files: list[ChangedFile]

    @property
    def additions(self) -> int:
        return sum(len(file.added_lines) for file in self.files)

    @property
    def deletions(self) -> int:
        return sum(len(file.removed_lines) for file in self.files)

    @property
    def changed_lines(self) -> int:
        return self.additions + self.deletions

    @property
    def paths(self) -> set[str]:
        return {file.path for file in self.files}


@dataclass(frozen=True, slots=True)
class Evidence:
    path: str
    line: int
    snippet: str


@dataclass(slots=True)
class Finding:
    rule_id: str
    title: str
    description: str
    severity: Severity
    evidence: list[Evidence]
    remediation: str
    source: str = "deterministic"
    gating: bool = True

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["severity"] = self.severity.value
        return data


@dataclass(slots=True)
class ReviewReport:
    files_changed: int
    additions: int
    deletions: int
    findings: list[Finding]
    version: str = "1"

    @property
    def gating_findings(self) -> list[Finding]:
        return [finding for finding in self.findings if finding.gating]

    @property
    def risk_score(self) -> int:
        return min(100, sum(finding.severity.weight for finding in self.gating_findings))

    @property
    def verdict(self) -> str:
        if any(finding.severity.rank >= Severity.HIGH.rank for finding in self.gating_findings):
            return "needs-attention"
        if self.gating_findings:
            return "review"
        return "clear"

    def should_fail(self, threshold: Severity | None) -> bool:
        return threshold is not None and any(
            finding.severity.rank >= threshold.rank for finding in self.gating_findings
        )

    def to_dict(self) -> dict[str, Any]:
        counts = {severity.value: 0 for severity in Severity}
        for finding in self.findings:
            counts[finding.severity.value] += 1
        return {
            "schema_version": self.version,
            "summary": {
                "verdict": self.verdict,
                "risk_score": self.risk_score,
                "files_changed": self.files_changed,
                "additions": self.additions,
                "deletions": self.deletions,
                "finding_counts": counts,
                "gating_findings": len(self.gating_findings),
                "advisory_findings": len(self.findings) - len(self.gating_findings),
            },
            "findings": [finding.to_dict() for finding in self.findings],
        }
