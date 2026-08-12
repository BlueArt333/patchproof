"""Safe Git subprocess boundary."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

from patchproof.limits import MAX_DIFF_BYTES, MAX_GIT_STDERR_BYTES, diff_limit_message


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


def _stop(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        process.kill()
    process.wait()


def _run_git(args: list[str], cwd: Path) -> str:
    try:
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            process = subprocess.Popen(
                ["git", *args],
                cwd=cwd,
                stdout=stdout,
                stderr=stderr,
            )
            deadline = time.monotonic() + 60
            while process.poll() is None:
                if os.fstat(stdout.fileno()).st_size > MAX_DIFF_BYTES:
                    _stop(process)
                    raise GitError(diff_limit_message())
                if os.fstat(stderr.fileno()).st_size > MAX_GIT_STDERR_BYTES:
                    _stop(process)
                    raise GitError("Git diagnostics exceed the 1 MiB safety limit")
                if time.monotonic() >= deadline:
                    _stop(process)
                    raise GitError("Git diff timed out after 60 seconds")
                time.sleep(0.02)

            stdout_size = os.fstat(stdout.fileno()).st_size
            stderr_size = os.fstat(stderr.fileno()).st_size
            if stdout_size > MAX_DIFF_BYTES:
                raise GitError(diff_limit_message())
            if stderr_size > MAX_GIT_STDERR_BYTES:
                raise GitError("Git diagnostics exceed the 1 MiB safety limit")

            stderr.seek(0)
            diagnostics = stderr.read(MAX_GIT_STDERR_BYTES).decode("utf-8", errors="replace")
            if process.returncode != 0:
                message = diagnostics.strip() or "Git exited with an unknown error"
                raise GitError(message)

            stdout.seek(0)
            return stdout.read(MAX_DIFF_BYTES).decode("utf-8", errors="replace")
    except FileNotFoundError as exc:
        raise GitError("Git is not installed or not available on PATH") from exc


def diff_between(base: str, head: str, cwd: Path) -> str:
    base = _validate_ref(base)
    head = _validate_ref(head)
    return _run_git([*DIFF_ARGS, f"{base}...{head}", "--"], cwd)


def diff_staged(cwd: Path) -> str:
    return _run_git([*DIFF_ARGS, "--cached", "--"], cwd)


def diff_worktree(cwd: Path) -> str:
    return _run_git([*DIFF_ARGS, "--"], cwd)
