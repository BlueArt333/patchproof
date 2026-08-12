"""Shared safety limits for untrusted pull-request input."""

MAX_DIFF_BYTES = 20 * 1024 * 1024
MAX_GIT_STDERR_BYTES = 1024 * 1024


def diff_limit_message() -> str:
    """Return a stable, user-facing message for oversized diffs."""
    return f"diff exceeds the {MAX_DIFF_BYTES // (1024 * 1024)} MiB safety limit"
