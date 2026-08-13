# PatchProof

**Evidence-first pull-request risk review, from a zero-dependency offline core.**

[简体中文](README.zh-CN.md) · [Rules](docs/rules.md) · [AI and privacy](docs/ai-and-privacy.md) · [Contributing](CONTRIBUTING.md)

PatchProof reads a Git unified diff and turns review risk into findings a maintainer can verify: a stable rule ID, severity, affected path and line, a bounded evidence snippet, and a concrete next step. It emits Markdown for people, JSON for automation, and SARIF for code-scanning systems.

The default installation has no third-party runtime dependencies, needs no account or API key, runs locally, and does not make network requests. OpenAI's Responses API is available as an explicit, optional semantic pass; deterministic analysis remains available when AI is disabled or unavailable.

> **Project status:** Alpha. The command line is usable for evaluation, but rules and machine-readable schemas may evolve before a stable release.

## Why PatchProof?

Review tools often give a score without showing their work, or require sending an entire patch to a hosted service. PatchProof takes a narrower approach:

- **Evidence first:** findings point to changed files and lines instead of making unsupported claims.
- **Deterministic by default:** the same diff and configuration produce the same core decision.
- **Offline and dependency-light:** the Python 3.11+ core uses only the standard library.
- **Automation-ready:** Markdown, versioned JSON, and SARIF come from one report model.
- **Safe CI posture:** the supplied GitHub Action analyzes a checked-out diff and is read-only by default.
- **AI is advisory:** semantic review is opt-in, cannot rewrite deterministic findings, and never controls the risk score, verdict, or CI exit status.

PatchProof is a review prioritization tool. It does not replace tests, linters, compilers, threat modeling, dedicated secret scanners, or a human reviewer.

## Quick start

Install the latest published release:

```bash
python -m pip install patchproof
```

For development from a checkout:

```bash
git clone https://github.com/BlueArt333/patchproof.git
cd patchproof
python -m pip install -e ".[dev]"
```

Review what is staged for the next commit:

```bash
patchproof review --staged
```

Review a branch against its base:

```bash
git fetch origin main
patchproof review --base origin/main --head HEAD
```

Write a machine-readable report:

```bash
patchproof review --staged --format json --output patchproof-report.json
```

Run `patchproof review --help` for every option, `patchproof rules` for the built-in catalog, or `patchproof init` to write a commented starter configuration.

## Inputs and outputs

`patchproof review` accepts one input mode at a time:

```text
--base REF --head REF    compare two Git revisions
--diff-file PATH         read an existing unified-diff file
--staged                 analyze the Git index
--worktree               analyze unstaged changes (the default)
```

Use `--repo PATH` to run Git operations and automatic configuration discovery from another repository directory.

Use `--output -` (the default) for standard output or provide a path. Available formats are:

| Format | Intended use |
| --- | --- |
| `markdown` | Terminal output, CI job summaries, and review notes |
| `json` | Stable structured input for scripts and dashboards |
| `sarif` | Import into systems that understand SARIF 2.1.0 |

The configured failure threshold is independent of the renderer. By default, a finding at `high` or `critical` severity makes the review command fail. Override it for one run with `--fail-on`, or set `fail_on = "never"` when PatchProof should report without gating.

## Built-in review signals

The initial rules focus on changes that deserve deliberate human attention:

| ID | Signal |
| --- | --- |
| `PP001` | Patch meets or exceeds a configured file-count or changed-line threshold |
| `PP002` | A changed path matches a sensitive-area pattern |
| `PP003` | Source changes are present without a test-file change |
| `PP004` | A dependency lock file changed |
| `PP005` | An added line resembles a credential or secret |
| `PP006` | A GitHub Actions workflow adds broadly writable permissions |
| `PP007` | The patch contains a binary change that text review cannot inspect |

These are risk signals, not verdicts about correctness or malicious intent. See [the rule reference](docs/rules.md) for evidence behavior, limitations, and tuning advice.

## Configuration

PatchProof looks for `patchproof.toml`, `.patchproof.toml`, and then `[tool.patchproof]` in `pyproject.toml`. An explicit `--config PATH` takes precedence. Generate a starter file with:

```bash
patchproof init
```

A minimal configuration is:

```toml
[patchproof]
fail_on = "high"
large_pr_files = 20
large_pr_lines = 500
ignore_rules = []
```

Path patterns for source, tests, sensitive areas, and exclusions are configurable. Start from [examples/patchproof.toml](examples/patchproof.toml), and keep exclusions narrow: excluded paths receive no findings.

Use `--no-config` when reviewing an untrusted branch with the built-in defaults. Automatic discovery reads configuration from the reviewed checkout; such a configuration can change exclusions and suppressions.

## Optional AI review

Install the optional client and provide credentials through the environment:

```bash
python -m pip install "patchproof[ai]"
export OPENAI_API_KEY="..."
patchproof review --staged --ai
```

PowerShell equivalent:

```powershell
$env:OPENAI_API_KEY = "..."
patchproof review --staged --ai
```

AI mode is never enabled merely because a key exists. It requires `--ai`. Select a model with `--model`, `PATCHPROOF_MODEL`, or `OPENAI_MODEL`; the explicit CLI option has priority.

Before enabling AI on proprietary or security-sensitive code, read [AI and privacy](docs/ai-and-privacy.md). In particular:

- selected patch context leaves the local machine;
- `store: false` is requested, but it is not a promise of zero retention;
- model output is untrusted and accepted only with evidence that maps back to the parsed patch;
- accepted AI findings are fixed-severity advisory notes and cannot gate CI;
- API use may cost money and is governed by your OpenAI account settings and current terms;
- deterministic review still works without the optional package, credentials, or network.

## GitHub Actions

The repository includes a read-only Action and an example workflow. Without a `config` input, the Action uses built-in defaults and does not discover configuration from the pull-request checkout. Treat any explicit `config` path as trusted policy. A minimal consumer workflow should grant only `contents: read` and must not expose paid API credentials to untrusted fork pull requests.

When referencing a third-party Action in production, pin it to a reviewed full commit SHA. The placeholder below is intentionally not runnable until replaced:

```yaml
name: PatchProof

on:
  pull_request:

permissions:
  contents: read

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<reviewed-full-commit-sha>
        with:
          fetch-depth: 0
      - uses: BlueArt333/patchproof@<reviewed-full-commit-sha>
        with:
          base: ${{ github.event.pull_request.base.sha }}
          head: ${{ github.event.pull_request.head.sha }}
          fail-on: high
```

The default path reads repository history and writes a report; it does not approve, merge, label, comment on, or modify a pull request. Review the workflow in your own security context before enabling optional AI or SARIF upload permissions.

## Interpreting a report

Every deterministic finding includes:

- a stable `rule_id` for configuration and downstream tooling;
- a severity that communicates review urgency, not exploitability certainty;
- evidence attached to a changed path and line when available;
- remediation framed as a verification step.

The risk score is a compact prioritization aid, capped at 100. It is not a probability, CVSS score, or assurance level. The original diff remains the source of truth.

## Development and governance

- [CONTRIBUTING.md](CONTRIBUTING.md) — setup, tests, rule design, and pull-request expectations
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — Contributor Covenant 2.1
- [SECURITY.md](SECURITY.md) — private vulnerability reporting and security boundaries
- [ROADMAP.md](ROADMAP.md) — direction and explicit non-goals
- [CHANGELOG.md](CHANGELOG.md) — user-visible changes

## License

PatchProof is available under the [MIT License](LICENSE).

PatchProof is an independent open-source project and is not endorsed by OpenAI or GitHub. OpenAI, GitHub, and their respective product names are trademarks of their owners.
