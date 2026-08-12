from patchproof.ai import _available_evidence
from patchproof.diff_parser import parse_unified_diff


def test_ai_payload_is_bounded_and_paths_are_validated():
    additions = "\n".join(f"+line {number}" for number in range(100))
    patch = (
        "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -0,0 +1,100 @@\n" + additions + "\n"
    )
    payload, allowed = _available_evidence(parse_unified_diff(patch))
    assert len(payload[0]["added_lines"]) == 80
    assert ("a.py", 80) in allowed
    assert ("a.py", 81) not in allowed
