# Contributing to PatchProof

Thank you for helping make pull-request review more explainable and useful. PatchProof welcomes bug reports, documentation improvements, new deterministic checks, portability fixes, and focused design proposals.

## Before you start

- Search [existing issues](https://github.com/BlueArt333/patchproof/issues) before opening a new one.
- For a bug, include a minimal unified diff or repository fixture that reproduces it. Remove credentials and proprietary code first.
- For a substantial feature or behavior change, open an issue before investing in an implementation so the scope and compatibility impact can be discussed.
- Report suspected vulnerabilities through the process in [SECURITY.md](SECURITY.md), not in a public issue containing exploit details.

## Development setup

PatchProof requires Python 3.11 or newer. Its runtime core intentionally has no third-party dependencies.

```bash
git clone https://github.com/BlueArt333/patchproof.git
cd patchproof
python -m venv .venv
```

Activate the virtual environment, then install the project and development tools:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Run the local checks before sending a pull request:

```bash
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

AI-related changes may additionally use the optional dependency:

```bash
python -m pip install -e ".[ai,dev]"
```

Tests must not call a paid or live model API. Use a fake client and fixed responses for AI contract tests.

## Design constraints

These constraints are part of PatchProof's product contract:

1. **Evidence before opinion.** Every finding needs a stable rule ID, severity, concrete evidence, and remediation.
2. **Deterministic decisions.** Rules, risk score, verdict, failure threshold, and exit status must be reproducible without AI.
3. **Offline core.** The default install must retain zero third-party runtime dependencies and must not make network requests.
4. **Opt-in AI.** Semantic enhancement must be an optional layer, fail safely, and never silently alter deterministic findings.
5. **Read-only by default.** Do not add repository mutation, PR approval, merging, or comment publication to the default path.
6. **Stable machine output.** JSON and SARIF schema changes need compatibility consideration and tests. Sort any otherwise unordered output.
7. **Untrusted input.** Treat diffs, paths, configuration, model output, and GitHub event text as attacker-controlled.
8. **Cross-platform behavior.** Keep path handling and command examples usable on Linux, macOS, and Windows where practical.

## Adding or changing a rule

A rule contribution should include:

- a short, stable ID that will not be repurposed later;
- a concise title and remediation that tell a maintainer what to verify;
- the narrowest severity justified by the evidence;
- evidence tied to changed paths or line numbers where possible;
- positive, negative, boundary, rename, and excluded-path tests as applicable;
- documentation in [docs/rules.md](docs/rules.md);
- a changelog entry when user-visible behavior changes.

Avoid checks based only on a vague keyword when a structural signal is available. A rule should identify review risk, not claim that a vulnerability definitely exists.

## Pull requests

Keep pull requests focused and explain the behavior being changed. In the description, include:

- the problem and intended outcome;
- the rule or output contract affected;
- tests run and their results;
- any compatibility, security, privacy, or false-positive trade-offs;
- before/after output when a renderer changes.

By submitting a contribution, you agree that it may be distributed under the project's [MIT License](LICENSE).

All participants must follow the [Code of Conduct](CODE_OF_CONDUCT.md).
