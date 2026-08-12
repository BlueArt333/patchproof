"""Safety helpers used by the bundled GitHub composite Action."""

from __future__ import annotations

import os
import sys
from pathlib import Path


class UnsafeOutputPath(ValueError):
    """Raised when an Action output path can escape or alias the workspace."""


def resolve_output_path(workspace: Path, output_file: str) -> Path:
    """Resolve an output path while rejecting traversal and symbolic links."""
    if not output_file:
        raise UnsafeOutputPath("output-file cannot be empty")
    if "\r" in output_file or "\n" in output_file:
        raise UnsafeOutputPath("output-file cannot contain line breaks")

    root = workspace.resolve(strict=True)
    requested = Path(output_file)
    candidate = requested if requested.is_absolute() else root / requested
    candidate = Path(os.path.abspath(candidate))

    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise UnsafeOutputPath("output-file must stay inside GITHUB_WORKSPACE") from exc
    if not relative.parts:
        raise UnsafeOutputPath("output-file must name a file inside GITHUB_WORKSPACE")

    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise UnsafeOutputPath("output-file path cannot contain symbolic links")

    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise UnsafeOutputPath("output-file must stay inside GITHUB_WORKSPACE") from exc
    if resolved.exists() and not resolved.is_file():
        raise UnsafeOutputPath("output-file must name a regular file")
    return resolved


def main(argv: list[str] | None = None) -> int:
    values = sys.argv[1:] if argv is None else argv
    if len(values) != 2:
        print("usage: python -m patchproof.action_support WORKSPACE OUTPUT_FILE", file=sys.stderr)
        return 2
    try:
        output_path = resolve_output_path(Path(values[0]), values[1])
    except (OSError, UnsafeOutputPath) as exc:
        print(f"patchproof action: {exc}", file=sys.stderr)
        return 2
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
