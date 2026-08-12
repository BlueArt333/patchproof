# Changelog

All notable changes to PatchProof will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project intends to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html) once its public API and report schemas stabilize.

## [Unreleased]

### Added

- Initial evidence-first unified-diff review engine.
- Deterministic signals for large changes, sensitive paths, missing test changes, lock files, possible secrets, broad workflow permissions, and binary patches.
- Markdown, versioned JSON, and SARIF 2.1.0 report formats.
- TOML configuration, built-in rule catalog, and configurable severity failure threshold.
- Read-only-by-default GitHub Action integration.
- Optional, advisory-only OpenAI Responses API semantic review with validated patch evidence.
- English and Simplified Chinese documentation plus project governance files.

### Security

- Offline core does not execute reviewed code or require network access.
- Optional model calls are explicit and use `store: false`; their remaining data-handling boundaries are documented separately.
- Action report paths are confined to the workspace and symbolic-link aliases are rejected.
- Model-authored report text is neutralized and cannot control gating outputs.

No release has been published from this changelog yet.
