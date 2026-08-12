# Roadmap

PatchProof aims to become a small, dependable review primitive for maintainers: deterministic enough for CI, transparent enough for a contributor to challenge, and useful without a network connection.

This roadmap is directional, not a promise of dates or inclusion. Priorities may change based on maintainer capacity, security findings, and community feedback.

## Foundation: 0.1.x

- Harden unified-diff parsing for renames, deletions, binary files, unusual paths, and truncated input.
- Stabilize Markdown, JSON, and SARIF output contracts.
- Tune the initial evidence-backed rules using public, minimized fixtures.
- Keep the default runtime dependency-free on Python 3.11+.
- Document a read-only, least-privilege GitHub Action workflow.
- Validate optional Responses API enhancement with schema and failure-mode tests.
- Add CI coverage across supported Python versions and major operating systems.

## Review ergonomics: 0.2.x

- Baseline files for adopting PatchProof without blocking on historical findings.
- Inline suppressions or configuration-level exceptions with required rationale.
- Better monorepo path groups and per-path thresholds.
- GitHub code-scanning annotations derived from SARIF.
- A machine-readable schema document and compatibility policy.
- Performance limits and graceful degradation for very large patches.

## Rule quality: 0.3.x

- Calibrated confidence metadata distinct from severity.
- More language-aware signals while preserving deterministic behavior.
- A documented rule-authoring API with stable test fixtures.
- False-positive feedback fixtures that do not collect repository content.
- Rule packs that remain auditable and do not execute reviewed code.

## Optional semantic layer

- Provider-neutral interface around the deterministic report.
- Explicit context previews so users can inspect what would leave the machine.
- Configurable redaction and context budgets.
- Evaluations for faithfulness, evidence citation, prompt injection resistance, and graceful fallback.
- No model-controlled verdicts, severities, CI exits, repository writes, or merges.

## Long-term ideas

- Compare risk across a sequence of commits without losing line-level evidence.
- Export summaries for other forges while keeping GitHub integration first-class.
- Signed provenance for released Action bundles and generated reports.
- A small public corpus of synthetic diffs for reproducible rule evaluation.

## Non-goals

- Replacing human code review, tests, a compiler, or a security scanner
- Executing pull-request code to infer behavior
- Automatically approving or merging pull requests
- Hiding deterministic decisions behind an opaque risk model
- Requiring an OpenAI API key for core analysis

Proposals and priority discussions are welcome in [GitHub Issues](https://github.com/BlueArt333/patchproof/issues).
