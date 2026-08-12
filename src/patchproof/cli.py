"""Command-line interface for PatchProof."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from patchproof import __version__
from patchproof.ai import AIReviewError, review_with_openai
from patchproof.config import Config, ConfigError, filter_excluded, load_config
from patchproof.diff_parser import DiffParseError, parse_unified_diff
from patchproof.git import GitError, diff_between, diff_staged, diff_worktree
from patchproof.models import ReviewReport, Severity
from patchproof.renderers import render_json, render_markdown, render_sarif
from patchproof.rules import RULES, analyze

FORMATTERS = {"markdown": render_markdown, "json": render_json, "sarif": render_sarif}
EXAMPLE_CONFIG = """# PatchProof configuration
[patchproof]
fail_on = "high"
large_pr_files = 20
large_pr_lines = 500
ignore_rules = []

# Glob patterns are matched against repository-relative POSIX paths.
sensitive_patterns = [
  ".github/workflows/*",
  "auth/*",
  "**/auth/*",
  "security/*",
  "**/security/*",
  "migrations/*",
  "**/migrations/*",
  "Dockerfile*",
  "**/Dockerfile*",
  "permissions.*",
  "**/permissions.*",
]
"""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="patchproof",
        description="Evidence-first pull request risk checks for open-source maintainers.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    review = subparsers.add_parser("review", help="analyze a Git diff")
    source = review.add_mutually_exclusive_group()
    source.add_argument(
        "--diff-file", type=Path, help="read a unified diff from a file; use - for stdin"
    )
    source.add_argument("--staged", action="store_true", help="review staged changes")
    source.add_argument("--worktree", action="store_true", help="review unstaged changes (default)")
    review.add_argument("--base", help="base Git ref; requires --head")
    review.add_argument("--head", help="head Git ref; requires --base")
    review.add_argument("--repo", type=Path, default=Path.cwd(), help="repository directory")
    config_source = review.add_mutually_exclusive_group()
    config_source.add_argument("--config", type=Path, help="TOML configuration path")
    config_source.add_argument(
        "--no-config", action="store_true", help="use built-in defaults; disable discovery"
    )
    review.add_argument(
        "--fail-on",
        choices=[severity.value for severity in Severity] + ["never"],
        help="override the configured failure threshold",
    )
    review.add_argument("--format", choices=sorted(FORMATTERS), default="markdown")
    review.add_argument(
        "--output", type=Path, help="write report to this path; omit or use - for stdout"
    )
    review.add_argument("--ai", action="store_true", help="add a bounded OpenAI semantic review")
    review.add_argument("--model", help="OpenAI model used with --ai")
    review.add_argument(
        "--require-ai",
        action="store_true",
        help="fail when optional AI review fails instead of falling back",
    )

    init = subparsers.add_parser("init", help="write a starter configuration")
    init.add_argument("--path", type=Path, default=Path("patchproof.toml"))
    init.add_argument("--force", action="store_true", help="overwrite an existing file")

    subparsers.add_parser("rules", help="list built-in deterministic rules")
    return parser


def _read_diff(args: argparse.Namespace) -> str:
    if bool(args.base) != bool(args.head):
        raise ValueError("--base and --head must be supplied together")
    if args.base and (args.diff_file is not None or args.staged or args.worktree):
        raise ValueError("--base/--head cannot be combined with another input mode")
    if args.diff_file is not None:
        if str(args.diff_file) == "-":
            return sys.stdin.read()
        return args.diff_file.read_text(encoding="utf-8", errors="replace")
    if args.base and args.head:
        return diff_between(args.base, args.head, args.repo)
    if args.staged:
        return diff_staged(args.repo)
    return diff_worktree(args.repo)


def _write_report(content: str, output: Path | None) -> None:
    if output is None or str(output) == "-":
        try:
            sys.stdout.write(content)
        except UnicodeEncodeError:
            if not hasattr(sys.stdout, "buffer"):
                raise
            sys.stdout.buffer.write(content.encode("utf-8"))
            sys.stdout.buffer.flush()
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8", newline="\n")


def _emit_github_metadata(report: ReviewReport) -> None:
    output_path = os.getenv("GITHUB_OUTPUT")
    if output_path:
        with Path(output_path).open("a", encoding="utf-8") as handle:
            handle.write(f"verdict={report.verdict}\n")
            handle.write(f"risk-score={report.risk_score}\n")


def _run_review(args: argparse.Namespace) -> int:
    if args.require_ai and not args.ai:
        raise ValueError("--require-ai requires --ai")
    if args.model and not args.ai:
        raise ValueError("--model requires --ai")
    config = Config() if args.no_config else load_config(args.config, args.repo)
    if args.fail_on is not None:
        config.fail_on = None if args.fail_on == "never" else Severity.parse(args.fail_on)
    changes = filter_excluded(parse_unified_diff(_read_diff(args)), config)
    findings = analyze(changes, config)
    if args.ai:
        try:
            findings.extend(review_with_openai(changes, args.model))
        except AIReviewError as exc:
            if args.require_ai:
                raise
            print(f"patchproof: AI review skipped: {exc}", file=sys.stderr)
    findings.sort(
        key=lambda item: (
            -item.severity.rank,
            item.rule_id,
            item.evidence[0].path if item.evidence else "",
        )
    )
    report = ReviewReport(
        files_changed=len(changes.files),
        additions=changes.additions,
        deletions=changes.deletions,
        findings=findings,
    )
    _write_report(FORMATTERS[args.format](report), args.output)
    _emit_github_metadata(report)
    return 1 if report.should_fail(config.fail_on) else 0


def _run_init(args: argparse.Namespace) -> int:
    if args.path.exists() and not args.force:
        raise ValueError(f"refusing to overwrite {args.path}; pass --force to replace it")
    args.path.parent.mkdir(parents=True, exist_ok=True)
    args.path.write_text(EXAMPLE_CONFIG, encoding="utf-8", newline="\n")
    print(f"Wrote {args.path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "review":
            return _run_review(args)
        if args.command == "init":
            return _run_init(args)
        if args.command == "rules":
            print(
                json.dumps(
                    [{"id": rule_id, "title": title} for rule_id, title, _ in RULES], indent=2
                )
            )
            return 0
        raise AssertionError(f"unexpected command: {args.command}")
    except (AIReviewError, ConfigError, DiffParseError, GitError, OSError, ValueError) as exc:
        print(f"patchproof: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
