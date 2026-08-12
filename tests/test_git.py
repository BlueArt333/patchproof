from pathlib import Path

import pytest

from patchproof import git as git_module
from patchproof.git import GitError, _run_git


def test_git_output_is_bounded(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(git_module, "MAX_DIFF_BYTES", 4)

    with pytest.raises(GitError, match="safety limit"):
        _run_git(["--version"], tmp_path)
