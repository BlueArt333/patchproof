# Rule reference

PatchProof rules identify review risk in a parsed Git diff. They do not execute changed code, inspect the full repository, or prove that a change is correct, vulnerable, or malicious.

Every finding contains a stable rule ID, severity, description, remediation, and one or more evidence records. Evidence is derived from the patch and includes a repository-relative path, a new-file line number when meaningful, and a bounded snippet. Machine-readable formats carry the same findings as Markdown.

## Severity and gating

Severities communicate review urgency:

| Severity | Intended interpretation |
| --- | --- |
| `info` | Context that may help a reviewer |
| `low` | A limited or weak signal worth noting |
| `medium` | A meaningful review gap or change-management risk |
| `high` | A sensitive change or strong signal requiring deliberate review |
| `critical` | A signal that warrants immediate containment and credential or security review |

By default, `patchproof review` exits non-zero when at least one finding is `high` or `critical`. Configure `fail_on` or use `--fail-on` to select another threshold. `never` reports all findings without gating.

The risk score adds fixed weights for findings whose `gating` field is `true` and caps the result at 100. Advisory findings have `gating: false` and do not affect the risk score, verdict, or exit status. The score is a prioritization aid, not a probability or CVSS score. Multiple related findings can increase it, so always read the evidence.

## Path matching and exclusions

Paths are normalized to forward slashes and matched against configurable shell-style patterns. The following lists can be set in `patchproof.toml`, `.patchproof.toml`, or `[tool.patchproof]`:

- `source_patterns`
- `test_patterns`
- `sensitive_patterns`
- `exclude_paths`

Excluded files are not analyzed by the rules. An exclusion can therefore hide a relevant security or test-coverage signal; keep exclusions narrow and review configuration changes like code changes.

Use [the commented example](../examples/patchproof.toml) as a starting point.

## PP001 — Large change

**Default severity:** `medium`

Triggers when either of these configured limits is reached:

- number of changed files reaches or exceeds `large_pr_files`; or
- number of added plus removed lines exceeds `large_pr_lines`.

Default limits are 20 files and 500 changed lines. The finding summarizes the observed patch size and the configured threshold.

**Why it matters:** Large changes are harder to reason about, review atomically, and revert. Size is not evidence of a defect.

**Suggested response:** Split independent concerns where practical. If the change must remain large, document its boundaries and review plan.

**Tuning:** Adjust the two thresholds for generated-code-heavy repositories or monorepos. Do not raise them merely to silence a one-off change without considering reviewability.

## PP002 — Sensitive path changed

**Default severity:** `high`

Triggers for a changed file matching `sensitive_patterns`. Defaults include GitHub workflow files, authentication and security directories, migration paths, Dockerfiles, and permission-related files.

**Why it matters:** These areas can change privileges, deployment behavior, data shape, or trust boundaries even when the patch is small.

**Suggested response:** Route the change to an appropriate owner and verify permissions, rollback behavior, migration safety, and deployment assumptions relevant to that path.

**Tuning:** Replace or extend `sensitive_patterns` with repository-specific ownership boundaries. A path match indicates sensitivity, not an error.

## PP003 — Source changed without tests

**Default severity:** `medium`

Triggers when at least one changed path matches `source_patterns` and no changed path matches `test_patterns`.

**Why it matters:** A patch that changes behavior without a corresponding test change may leave new behavior or a regression unverified.

**Limitations:** Tests may already cover the behavior, may live in a nonstandard path, or may be intentionally unnecessary for documentation-like source changes. PatchProof examines the diff's paths; it does not run or measure the existing test suite.

**Suggested response:** Point reviewers to existing coverage, add a focused test, or document why a test change is not needed.

**Tuning:** Adapt `source_patterns` and `test_patterns` to the repository layout before using this rule as a merge gate.

## PP004 — Dependency lock file changed

**Default severity:** `medium`

Triggers when the lower-cased basename of a changed path is one of:

```text
Cargo.lock
composer.lock
Gemfile.lock
go.sum
package-lock.json
pnpm-lock.yaml
poetry.lock
uv.lock
yarn.lock
```

Matching is case-insensitive even though the conventional spellings above are shown.

**Why it matters:** A lock-file diff can introduce new transitive code, alter resolved versions, or contain changes that are difficult to inspect in a normal review.

**Suggested response:** Confirm the lock file was regenerated by the intended package manager, connect changes to a manifest update, and inspect package provenance and release notes as appropriate.

**Limitations:** The rule does not contact a registry, resolve packages, identify malware, or distinguish a harmless lock-file normalization from a dependency upgrade.

## PP005 — Possible secret in an added line

**Default severity:** `critical`

Scans added text lines for a small set of high-value credential shapes:

- PEM private-key headers;
- GitHub-style `ghp_`, `gho_`, `ghs_`, or `ghu_` tokens with a sufficiently long body;
- AWS access-key IDs beginning with `AKIA` or `ASIA` and the expected uppercase-alphanumeric length;
- Slack `xox...` token forms;
- quoted assignments to names such as `api_key`, `secret`, `token`, `password`, or `passwd`, with a nontrivial value length.

The evidence snippet is always replaced with `[REDACTED POSSIBLE SECRET]`. The description names only the detected credential shape. The suspected value must never appear in PatchProof's report.

**Why it matters:** Even a short-lived credential in a commit may be copied to forks, caches, logs, or review notifications.

**Immediate response:** Treat a plausible match as exposed. Revoke or rotate it through the issuer, remove it from the patch and relevant history, then investigate access logs and downstream copies. Merely deleting the line in a later commit may be insufficient.

**Limitations:** Pattern matching can produce false positives and cannot find every secret. PatchProof is not a substitute for a dedicated secret scanner or repository-wide history scan. Never put a real credential in a test fixture or bug report.

## PP006 — Broad GitHub Actions write permission

**Default severity:** `high`

Scans added lines in `.github/workflows/*.yml` and `.github/workflows/*.yaml`. It triggers on either:

- `permissions: write-all`; or
- a known permission key assigned `write` for `actions`, `checks`, `contents`, `deployments`, `discussions`, `id-token`, `issues`, `packages`, `pages`, `pull-requests`, `repository-projects`, `security-events`, or `statuses`.

A finding includes at most five matching evidence lines.

**Why it matters:** A workflow's token permissions define what untrusted input or a compromised dependency may be able to change. Some write permissions are legitimate, but each should be intentional and scoped.

**Suggested response:** Set workflow- or job-level `permissions` to the minimum required. Review event type, fork behavior, checkout target, third-party Action pinning, and whether PR-controlled code can run with the granted token.

**Limitations:** This line-oriented check does not fully parse YAML, expand reusable workflows, or prove the effective permission set. It may match text inside a YAML block scalar. GitHub platform defaults and organization policy also affect effective permissions.

## PP007 — Binary change

**Default severity:** `low`

Triggers when the Git patch marks a changed file as binary.

**Why it matters:** PatchProof and normal text review cannot inspect the binary contents or explain how they were produced.

**Suggested response:** Verify provenance, reproducibility, expected file type, size, and any available signature or checksum. Prefer building generated artifacts from reviewed source when the project workflow permits.

**Limitations:** A binary marker is not evidence that the file is unsafe. The rule does not extract archives or execute binary-analysis tools.

## AI001 — Optional semantic risk

**Fixed severity:** `info` (`gating: false`)

`AI001` can appear only when `--ai` is explicitly enabled. It describes a semantic risk proposed by the configured OpenAI model. Every accepted finding must cite a path and new-file line that exactly maps to an actual added line in the parsed patch. Unsupported, malformed, or out-of-range evidence is rejected.

Accepted `AI001` findings are advisory and never participate in the risk score, verdict, or `fail_on` decision. They remain model-generated judgments and should receive human verification. They do not replace or modify `PP001`–`PP007` findings.

See [AI and privacy](ai-and-privacy.md) for the exact context boundary, failure behavior, and data-handling considerations.

## Ignoring a rule

`ignore_rules` controls only deterministic rules `PP001` through `PP007`. Add a stable ID to the list:

```toml
[patchproof]
ignore_rules = ["PP003"]
```

An ignored rule produces no finding and cannot affect the risk score or failure threshold. Prefer narrowing path patterns or fixing the underlying condition when possible. Record the rationale in the repository because broad suppressions can outlive the change that motivated them.

Do not use `ignore_rules` to suppress an exposed credential before rotation.

`AI001` is not controlled by `ignore_rules`; omit `--ai` to disable optional AI findings.
