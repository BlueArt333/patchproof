from pathlib import Path

import pytest

from patchproof.config import ConfigError, load_config, path_matches
from patchproof.models import Severity


def test_defaults_when_pyproject_has_no_section(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    config = load_config(None, tmp_path)
    assert config.fail_on == Severity.HIGH


def test_loads_explicit_config(tmp_path: Path):
    config_path = tmp_path / "custom.toml"
    config_path.write_text(
        "[patchproof]\nfail_on='critical'\nlarge_pr_lines=12\nignore_rules=['PP001']\n",
        encoding="utf-8",
    )
    config = load_config(config_path, tmp_path)
    assert config.fail_on == Severity.CRITICAL
    assert config.large_pr_lines == 12
    assert config.ignore_rules == {"PP001"}


@pytest.mark.parametrize("value", [0, -1, True, "10"])
def test_rejects_invalid_thresholds(tmp_path: Path, value):
    path = tmp_path / "bad.toml"
    rendered = repr(value).lower() if isinstance(value, bool) else repr(value)
    path.write_text(f"large_pr_lines={rendered}\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(path, tmp_path)


def test_rejects_unknown_keys(tmp_path: Path):
    path = tmp_path / "bad.toml"
    path.write_text("surprise=true\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="unknown"):
        load_config(path, tmp_path)


def test_path_globs_are_posix_normalized():
    assert path_matches(r"src\auth\login.py", ["**/auth/*"])


def test_default_sensitive_patterns_cover_root_directories():
    from patchproof.config import Config

    assert path_matches("auth/login.py", Config().sensitive_patterns)
