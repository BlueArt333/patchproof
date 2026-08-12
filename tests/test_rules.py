from pathlib import Path

from patchproof.config import Config
from patchproof.diff_parser import parse_unified_diff
from patchproof.rules import analyze


def _fixture() -> str:
    return (Path(__file__).parent / "fixtures" / "risky.patch").read_text(encoding="utf-8")


def test_risky_patch_hits_expected_rules_and_redacts_secret():
    findings = analyze(parse_unified_diff(_fixture()), Config())
    ids = [finding.rule_id for finding in findings]

    assert "PP002" in ids
    assert "PP003" in ids
    assert "PP004" in ids
    assert "PP005" in ids
    assert "PP006" in ids
    assert "PP007" in ids
    secret = next(finding for finding in findings if finding.rule_id == "PP005")
    assert secret.evidence[0].snippet == "[REDACTED POSSIBLE SECRET]"
    assert "abcdefghijklmnopqrstuvwxyz" not in str(secret.to_dict())


def test_secret_rule_scans_added_lines_only():
    patch = """diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1 +1 @@
-token = "ghp_abcdefghijklmnopqrstuvwxyz123456"
+token = os.environ["TOKEN"]
"""
    ids = {finding.rule_id for finding in analyze(parse_unified_diff(patch), Config())}
    assert "PP005" not in ids


def test_workflow_read_permission_is_not_flagged():
    patch = """diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml
--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -1 +1,3 @@
 name: CI
+permissions:
+  contents: read
"""
    ids = [finding.rule_id for finding in analyze(parse_unified_diff(patch), Config())]
    assert "PP006" not in ids


def test_rule_ignore_list_is_respected():
    config = Config(ignore_rules={"PP002", "PP005"})
    ids = [finding.rule_id for finding in analyze(parse_unified_diff(_fixture()), config)]
    assert "PP002" not in ids
    assert "PP005" not in ids


def test_tests_suppress_missing_test_prompt():
    patch = """diff --git a/src/a.py b/src/a.py
--- a/src/a.py
+++ b/src/a.py
@@ -0,0 +1 @@
+answer = 42
diff --git a/tests/test_a.py b/tests/test_a.py
--- a/tests/test_a.py
+++ b/tests/test_a.py
@@ -0,0 +1 @@
+def test_answer(): assert answer == 42
"""
    ids = [finding.rule_id for finding in analyze(parse_unified_diff(patch), Config())]
    assert "PP003" not in ids


def test_secret_redaction_applies_to_findings_from_other_rules():
    secret = "this-is-a-long-secret-value"
    patch = f"""diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml
--- a/.github/workflows/ci.yml
++ b/.github/workflows/ci.yml
@@ -0,0 +1 @@
+contents: write # token = \"{secret}\"
"""
    findings = analyze(parse_unified_diff(patch), Config())
    assert {finding.rule_id for finding in findings} >= {"PP005", "PP006"}
    assert secret not in str([finding.to_dict() for finding in findings])
    assert all(
        evidence.snippet == "[REDACTED POSSIBLE SECRET]"
        for finding in findings
        for evidence in finding.evidence
        if finding.rule_id in {"PP005", "PP006"}
    )
