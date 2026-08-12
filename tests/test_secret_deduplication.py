from patchproof.config import Config
from patchproof.diff_parser import parse_unified_diff
from patchproof.rules import analyze


def test_one_added_line_produces_one_secret_finding():
    patch = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -0,0 +1 @@
+token = "ghp_abcdefghijklmnopqrstuvwxyz123456"
"""

    findings = analyze(parse_unified_diff(patch), Config())

    secret_findings = [finding for finding in findings if finding.rule_id == "PP005"]
    assert len(secret_findings) == 1
    assert secret_findings[0].description.startswith("An added line resembles a GitHub token")
