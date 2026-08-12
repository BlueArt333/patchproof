"""Configuration loading and path matching."""

from __future__ import annotations

import fnmatch
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from patchproof.models import ChangeSet, Severity


@dataclass(slots=True)
class Config:
    fail_on: Severity | None = Severity.HIGH
    large_pr_files: int = 20
    large_pr_lines: int = 500
    source_patterns: list[str] = field(
        default_factory=lambda: [
            "*.py",
            "*.js",
            "*.jsx",
            "*.ts",
            "*.tsx",
            "*.java",
            "*.go",
            "*.rs",
            "*.rb",
            "*.php",
            "*.cs",
            "*.cpp",
            "*.c",
            "*.h",
        ]
    )
    test_patterns: list[str] = field(
        default_factory=lambda: [
            "tests/*",
            "test/*",
            "spec/*",
            "**/tests/*",
            "**/test/*",
            "**/spec/*",
            "*_test.*",
            "test_*.*",
            "*.test.*",
            "*.spec.*",
        ]
    )
    sensitive_patterns: list[str] = field(
        default_factory=lambda: [
            ".github/workflows/*",
            "auth/*",
            "**/auth/*",
            "security/*",
            "**/security/*",
            "migrations/*",
            "**/migrations/*",
            "Dockerfile*",
            "**/Dockerfile*",
            "permissions.*",
            "**/permissions.*",
        ]
    )
    exclude_paths: list[str] = field(
        default_factory=lambda: ["vendor/*", "**/vendor/*", "dist/*", "**/dist/*"]
    )
    ignore_rules: set[str] = field(default_factory=set)


class ConfigError(ValueError):
    """Raised when a configuration file is invalid."""


def path_matches(path: str, patterns: list[str]) -> bool:
    normalized = path.replace("\\", "/")
    return any(fnmatch.fnmatchcase(normalized, pattern) for pattern in patterns)


def filter_excluded(changes: ChangeSet, config: Config) -> ChangeSet:
    """Return a change set with configured excluded paths removed."""
    return ChangeSet(
        files=[file for file in changes.files if not path_matches(file.path, config.exclude_paths)]
    )


def _as_string_list(value: Any, name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigError(f"{name} must be an array of strings")
    return value


def load_config(path: Path | None, cwd: Path | None = None) -> Config:
    cwd = cwd or Path.cwd()
    explicit = path is not None
    if path is None:
        candidates = [cwd / "patchproof.toml", cwd / ".patchproof.toml", cwd / "pyproject.toml"]
        path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        return Config()
    if explicit and not path.is_file():
        raise ConfigError(f"configuration file not found: {path}")

    with path.open("rb") as handle:
        document = tomllib.load(handle)

    if path.name == "pyproject.toml":
        data = document.get("tool", {}).get("patchproof")
        if data is None:
            return Config()
    else:
        data = document.get("patchproof", document)
    if not isinstance(data, dict):
        raise ConfigError("PatchProof configuration must be a TOML table")

    config = Config()
    allowed = {
        "fail_on",
        "large_pr_files",
        "large_pr_lines",
        "source_patterns",
        "test_patterns",
        "sensitive_patterns",
        "exclude_paths",
        "ignore_rules",
    }
    unknown = sorted(set(data) - allowed - {"version"})
    if unknown:
        raise ConfigError(f"unknown configuration keys: {', '.join(unknown)}")

    if "fail_on" in data:
        value = data["fail_on"]
        config.fail_on = None if value == "never" else Severity.parse(str(value))
    for name in ("large_pr_files", "large_pr_lines"):
        if name in data:
            value = data[name]
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ConfigError(f"{name} must be a positive integer")
            setattr(config, name, value)
    for name in (
        "source_patterns",
        "test_patterns",
        "sensitive_patterns",
        "exclude_paths",
    ):
        if name in data:
            setattr(config, name, _as_string_list(data[name], name))
    if "ignore_rules" in data:
        config.ignore_rules = set(_as_string_list(data["ignore_rules"], "ignore_rules"))
    return config
