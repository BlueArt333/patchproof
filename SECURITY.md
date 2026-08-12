# Security Policy

PatchProof processes attacker-controlled diffs and is intended for use in pull-request automation. Security reports are taken seriously, especially when they involve command execution, credential exposure, path traversal, unsafe GitHub Actions behavior, denial of service, or data sent unexpectedly to an external service.

## Supported versions

Until the project reaches a stable release, security fixes are made on the default branch and included in the next release. Once multiple release lines are supported, this section will list them explicitly.

## Reporting a vulnerability

Prefer GitHub's private vulnerability reporting flow:

1. Open the repository's **Security** tab.
2. Choose **Advisories** and **Report a vulnerability**.
3. Include the affected version or commit, impact, reproduction steps, and any proposed mitigation.

Direct link: [report a vulnerability](https://github.com/BlueArt333/patchproof/security/advisories/new).

If private vulnerability reporting is unavailable, open a [GitHub issue](https://github.com/BlueArt333/patchproof/issues) containing only a request for private maintainer contact. Do not include exploit details, tokens, private source code, personal data, or other secrets in a public issue.

You should receive acknowledgement as soon as a maintainer is available. The project will investigate, coordinate a fix and disclosure where appropriate, and credit reporters who want attribution. Timelines depend on severity and maintainer availability; please avoid public disclosure until a fix or coordinated disclosure plan exists.

## Useful report details

- PatchProof version or commit SHA
- Python version and operating system
- Invocation and relevant configuration, with secrets removed
- Minimal malicious or malformed diff
- Expected and observed behavior
- Impact and realistic attack scenario
- Whether GitHub Actions, SARIF upload, or optional AI mode is involved

## Security boundaries

- The default analyzer is local and read-only; it should not execute code from the reviewed patch.
- A finding is a review signal, not proof that code is safe or vulnerable.
- AI mode is optional and sends selected review context to the configured model provider. See [docs/ai-and-privacy.md](docs/ai-and-privacy.md).
- Secret detection and redaction are defense-in-depth. Never rely on them as permission to submit credentials in a diff.
- Repository owners remain responsible for Action permissions, branch protection, dependency pinning, and deciding whether untrusted fork pull requests may invoke paid external services.
- The Action uses built-in defaults unless a `config` input is supplied. An explicit configuration is a trusted policy input because exclusions and suppressions can weaken findings.
- A workflow that uses `./` runs PatchProof from the pull request checkout and is therefore not an independent trust gate against malicious changes to PatchProof itself. For that boundary, run a reviewed release pinned to a full commit SHA from a trusted checkout.

Reports about vulnerabilities in OpenAI, GitHub, Python, or another dependency should also be sent to that upstream project's security channel. PatchProof can still accept a report when its integration makes an upstream issue exploitable in a PatchProof workflow.
