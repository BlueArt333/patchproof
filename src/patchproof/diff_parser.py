"""A small, dependency-free parser for Git unified diffs."""

from __future__ import annotations

import re

from patchproof.models import ChangedFile, ChangeSet, DiffLine, Hunk, LineKind

HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: ?(.*))?$")


class DiffParseError(ValueError):
    """Raised when a patch contains an invalid hunk header."""


def _decode_git_path(path: str) -> str:
    """Decode Git's quoted octal byte escapes without corrupting Unicode text."""
    value = path.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        value = value[1:-1]
    output = bytearray()
    index = 0
    simple_escapes = {
        "n": b"\n",
        "r": b"\r",
        "t": b"\t",
        "\\": b"\\",
        '"': b'"',
    }
    while index < len(value):
        if (
            value[index] == "\\"
            and index + 3 < len(value)
            and all(character in "01234567" for character in value[index + 1 : index + 4])
        ):
            output.append(int(value[index + 1 : index + 4], 8))
            index += 4
            continue
        if value[index] == "\\" and index + 1 < len(value) and value[index + 1] in simple_escapes:
            output.extend(simple_escapes[value[index + 1]])
            index += 2
            continue
        output.extend(value[index].encode("utf-8"))
        index += 1
    return output.decode("utf-8", errors="replace")


def _strip_git_prefix(path: str) -> str:
    path = _decode_git_path(path)
    if path in {"/dev/null", "dev/null"}:
        return "/dev/null"
    return path[2:] if path.startswith(("a/", "b/")) else path


def _header_tokens(line: str) -> list[str]:
    """Tokenize a Git header while preserving its C-style escape sequences."""
    tokens: list[str] = []
    current: list[str] = []
    quoted = False
    escaped = False
    for character in line:
        if character.isspace() and not quoted:
            if current:
                tokens.append("".join(current))
                current = []
            continue
        current.append(character)
        if character == '"' and not escaped:
            quoted = not quoted
        escaped = character == "\\" and not escaped
    if current:
        tokens.append("".join(current))
    if quoted:
        raise DiffParseError(f"invalid Git diff header: {line}")
    return tokens


def _paths_from_header(line: str) -> tuple[str, str]:
    tokens = _header_tokens(line)
    if len(tokens) < 4:
        raise DiffParseError(f"invalid Git diff header: {line}")
    return _strip_git_prefix(tokens[2]), _strip_git_prefix(tokens[3])


def parse_unified_diff(text: str) -> ChangeSet:
    files: list[ChangedFile] = []
    current_file: ChangedFile | None = None
    current_hunk: Hunk | None = None
    old_line = new_line = 0

    def validate_hunk() -> None:
        if current_hunk is None:
            return
        observed_old = sum(
            line.kind in {LineKind.CONTEXT, LineKind.REMOVE} for line in current_hunk.lines
        )
        observed_new = sum(
            line.kind in {LineKind.CONTEXT, LineKind.ADD} for line in current_hunk.lines
        )
        if observed_old != current_hunk.old_count or observed_new != current_hunk.new_count:
            raise DiffParseError("hunk line counts do not match its header")

    for raw_line in text.split("\n"):
        raw_line = raw_line.removesuffix("\r")
        if raw_line.startswith("diff --git "):
            validate_hunk()
            old_path, new_path = _paths_from_header(raw_line)
            current_file = ChangedFile(old_path=old_path, new_path=new_path)
            files.append(current_file)
            current_hunk = None
            continue

        if current_file is None:
            continue

        if raw_line.startswith("new file mode "):
            current_file.status = "added"
            continue
        if raw_line.startswith("deleted file mode "):
            current_file.status = "deleted"
            continue
        if raw_line.startswith("rename from "):
            current_file.status = "renamed"
            current_file.old_path = _decode_git_path(raw_line.removeprefix("rename from "))
            continue
        if raw_line.startswith("rename to "):
            current_file.status = "renamed"
            current_file.new_path = _decode_git_path(raw_line.removeprefix("rename to "))
            continue
        if raw_line.startswith("Binary files ") or raw_line.startswith("GIT binary patch"):
            current_file.binary = True
            continue

        match = HUNK_HEADER.match(raw_line)
        if match:
            old_start, old_count, new_start, new_count, section = match.groups()
            validate_hunk()
            current_hunk = Hunk(
                old_start=int(old_start),
                old_count=int(old_count or "1"),
                new_start=int(new_start),
                new_count=int(new_count or "1"),
                section=section or "",
            )
            current_file.hunks.append(current_hunk)
            old_line = current_hunk.old_start
            new_line = current_hunk.new_start
            continue

        if raw_line.startswith("@@"):
            raise DiffParseError(f"invalid hunk header: {raw_line}")
        if current_hunk is None or raw_line == r"\ No newline at end of file":
            continue

        prefix, content = raw_line[:1], raw_line[1:]
        if prefix == "+":
            current_hunk.lines.append(DiffLine(LineKind.ADD, content, None, new_line))
            new_line += 1
        elif prefix == "-":
            current_hunk.lines.append(DiffLine(LineKind.REMOVE, content, old_line, None))
            old_line += 1
        elif prefix == " ":
            current_hunk.lines.append(DiffLine(LineKind.CONTEXT, content, old_line, new_line))
            old_line += 1
            new_line += 1
    validate_hunk()

    if text.strip() and not files:
        raise DiffParseError("input is not a Git diff; expected at least one 'diff --git' header")
    return ChangeSet(files=files)
