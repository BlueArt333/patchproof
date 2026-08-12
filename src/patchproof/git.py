"""Safe Git subprocess boundary."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


class GitError(RuntimeError):
    """Raised when Git cannot produce a requested diff."""


SAFE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/@{}+~^:-]*$")


def _validate_ref(value: str) -> str:
    if value.startswith("-") or not SAFE_REF.fullmatch(value) or ".." in value:
        raise GitError(f"unsafe or invalid Git ref: {value!r}")
    return value


DIFF_ARGS = [
    "-c",
    "diff.suppressBlankEmpty=false",
    "diff",
    "--no-ext-diff",
    "--no-textconv",
    "--no-color",
    "--src-prefix=a/",
    "--dst-prefix=b/",
    "--find-renames",
]


def _run_git(args: list[str], cwd: Path) -> str:
    try:
        process = subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except FileNotFoundError as exc:
        raise GitError("Git is not installed or not available on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitError("Git diff timed out after 60 seconds") from exc
    if process.returncode != 0:
        message = process.stderr.strip() or "Git exited with an unknown error"
        raise GitError(message)
    return process.stdout


def diff_between(base: str, head: str, cwd: Path) -> str:
    base = _validate_ref(base)
    head = _validate_ref(head)
    return _run_git([*DIFF_ARGS, f"{base}...{head}", "--"], cwd)


def diff_staged(cwd: Path) -> str:
    return _run_git([*DIFF_ARGS, "--cached", "--"], cwd)


def diff_worktree(cwd: Path) -> str:
    return _run_git([*DIFF_ARGS, "--"], cwd)
