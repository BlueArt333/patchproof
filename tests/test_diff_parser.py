import pytest

from patchproof.diff_parser import DiffParseError, parse_unified_diff


def test_parses_files_hunks_and_line_numbers():
    changes = parse_unified_diff(
        """diff --git a/app.py b/app.py
index 1..2 100644
--- a/app.py
+++ b/app.py
@@ -10,2 +10,3 @@ def run():
 context
-old
+new
+second
"""
    )

    assert len(changes.files) == 1
    assert changes.additions == 2
    assert changes.deletions == 1
    assert [line.new_line for line in changes.files[0].added_lines] == [11, 12]
    assert changes.files[0].path == "app.py"


def test_parses_rename_and_binary():
    changes = parse_unified_diff(
        """diff --git a/old.bin b/new.bin
similarity index 100%
rename from old.bin
rename to new.bin
Binary files a/old.bin and b/new.bin differ
"""
    )

    changed = changes.files[0]
    assert changed.status == "renamed"
    assert changed.old_path == "old.bin"
    assert changed.new_path == "new.bin"
    assert changed.binary is True


def test_rejects_invalid_hunk_header():
    patch = "diff --git a/a b/a\n@@ nonsense @@\n"
    try:
        parse_unified_diff(patch)
    except DiffParseError as exc:
        assert "invalid hunk" in str(exc)
    else:
        raise AssertionError("invalid hunk did not fail")


def test_ignores_email_style_preamble():
    changes = parse_unified_diff(
        "From abc Mon Sep 17 00:00:00 2001\nSubject: [PATCH]\n\n"
        "diff --git a/a.txt b/a.txt\n--- a/a.txt\n+++ b/a.txt\n"
        "@@ -0,0 +1 @@\n+hello\n"
    )
    assert changes.files[0].added_lines[0].content == "hello"


def test_rejects_nonempty_input_without_a_git_header():
    try:
        parse_unified_diff("--- a.txt\n+++ a.txt\n@@ -0,0 +1 @@\n+hello\n")
    except DiffParseError as exc:
        assert "not a Git diff" in str(exc)
    else:
        raise AssertionError("non-Git input did not fail")


def test_decodes_git_quoted_utf8_paths():
    changes = parse_unified_diff(
        'diff --git "a/caf\\303\\251.py" "b/caf\\303\\251.py"\n'
        '--- "a/caf\\303\\251.py"\n'
        '+++ "b/caf\\303\\251.py"\n'
    )
    assert changes.files[0].path == "café.py"


def test_decodes_git_quoted_rename_paths_and_simple_escapes():
    changes = parse_unified_diff(
        'diff --git "a/old\\tname.py" "b/caf\\303\\251.py"\n'
        "similarity index 100%\n"
        'rename from "old\\tname.py"\n'
        'rename to "caf\\303\\251.py"\n'
    )
    changed = changes.files[0]
    assert changed.old_path == "old\tname.py"
    assert changed.new_path == "café.py"


def test_git_header_decodes_backslash_exactly_once():
    changes = parse_unified_diff(
        'diff --git "a/foo\\\\n.py" "b/foo\\\\n.py"\n--- "a/foo\\\\n.py"\n+++ "b/foo\\\\n.py"\n'
    )
    assert changes.files[0].path == r"foo\n.py"


def test_unicode_line_separator_remains_inside_added_line():
    changes = parse_unified_diff(
        "diff --git a/a.py b/a.py\n"
        "--- a/a.py\n"
        "+++ b/a.py\n"
        "@@ -0,0 +1 @@\n"
        "+prefix\u2028token = 'not-a-real-secret-value'\n"
    )
    added = changes.files[0].added_lines
    assert len(added) == 1
    assert "token" in added[0].content


def test_rejects_truncated_hunk():
    patch = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1,2 +1,2 @@\n unchanged\n"
    with pytest.raises(DiffParseError, match="counts"):
        parse_unified_diff(patch)
