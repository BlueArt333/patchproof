# Optional AI mode: behavior, privacy, and trust

PatchProof's deterministic review works without AI, an API key, a network connection, or the optional `openai` package. AI mode is a deliberate semantic enhancement for maintainers who decide that selected added-line context may be sent to OpenAI.

This document describes the intended PatchProof 0.1 behavior. Review the source and current provider documentation before using AI mode with confidential, regulated, export-controlled, or security-sensitive code.

## Enabling AI

Install the optional dependency, set an API key, and pass `--ai`:

```bash
python -m pip install ".[ai]"
export OPENAI_API_KEY="..."
patchproof review --staged --ai
```

Merely installing the package or setting `OPENAI_API_KEY` does not enable AI. PatchProof makes no model request unless `--ai` is present.

Model selection follows this order:

1. `--model MODEL`
2. `PATCHPROOF_MODEL`
3. `OPENAI_MODEL`
4. PatchProof's default, `gpt-5.6-luna`

Model availability, pricing, rate limits, and behavior depend on the caller's OpenAI account and may change independently of PatchProof.

## What is sent

The request contains a bounded representation of changed files and added lines:

- at most 30 changed files;
- for each file, its repository-relative path and change status;
- at most 80 added lines per file;
- the new-file line number for each included line;
- each line truncated to at most 240 characters.

PatchProof does **not intentionally include** removed lines, unchanged context, unmodified repository files, repository history, or the deterministic PatchProof report in the semantic-review input.

Files matching `exclude_paths` are removed before deterministic or AI analysis. A limited set of credential-like patterns is replaced with `[REDACTED POSSIBLE SECRET]` before the AI payload is built. These controls reduce exposure and cost; they do not anonymize source code or provide comprehensive secret detection. Paths, identifiers, comments, literals, personal data, credentials not matched by the limited patterns, proprietary algorithms, and other sensitive content may still appear in added lines.

## What is not guaranteed

- The built-in redaction patterns are limited and can miss credentials or other sensitive text.
- Ignoring a deterministic rule does not remove matching source text from AI context.
- `exclude_paths` removes matching files from both deterministic and AI analysis, but a broad exclusion can also hide useful findings.
- A limited patch can still reveal confidential architecture or business logic.
- PatchProof cannot control copies made before it receives a diff, network infrastructure outside the process, or provider-side processing governed by your account and agreement.
- `store: false` is not the same as an approved Zero Data Retention arrangement and is not a promise that no provider logs exist.

Do not submit a real secret to test whether PatchProof detects it. If a patch may contain credentials, run the offline review first, rotate exposed credentials, and inspect the exact patch before considering AI mode.

## Request behavior

PatchProof uses OpenAI's Responses API with these constraints:

- `store` is set to `false`;
- no web, shell, file-search, MCP, or other model tools are enabled;
- a request timeout of 45 seconds is used;
- one retry is allowed for a failed request.

According to [OpenAI's current data-control documentation](https://developers.openai.com/api/docs/guides/your-data), API data is not used to train OpenAI models unless the customer explicitly opts in, but abuse-monitoring logs and endpoint-specific application state may still apply. The documentation also distinguishes `store: false` from separately approved controls such as Zero Data Retention. Review that page, your organization's data controls, and your governing agreement for the current rules before use.

PatchProof cannot determine whether your organization has Modified Abuse Monitoring, Zero Data Retention, data residency, or other contractual controls. It makes no claim that a request is eligible for a particular compliance regime.

## How model output is used

The model may propose `AI001` findings. PatchProof treats the response as untrusted:

- every evidence item must reference a path and new-file line present in the parsed patch;
- the evidence must match an actual added line;
- malformed or unsupported content is rejected;
- model-authored text is normalized and neutralized before report rendering;
- model output cannot alter deterministic `PP001`–`PP007` findings.

Every accepted `AI001` finding has fixed `info` severity and `gating: false`. It is advisory: it does not contribute to the risk score, verdict, or configured `fail_on` exit decision. Evidence validation reduces hallucinated locations; it does not prove that the model's interpretation is correct. Review every AI finding against the diff.

PatchProof never uses the model to approve, merge, label, comment on, or otherwise mutate a pull request.

## Failure behavior

AI mode is fail-open by default with respect to model availability: deterministic analysis and rendering continue when the optional package is missing, credentials are unavailable, the network or API fails, the request times out, or the response is invalid.

Use `--require-ai` only when a missing semantic pass should make the command fail. This is useful for a controlled evaluation pipeline, but can make CI dependent on credentials, network availability, rate limits, provider uptime, and account budget.

Neither mode hides deterministic findings. Check the report and command exit status rather than assuming that the presence of `--ai` means a model result was accepted.

## GitHub Actions guidance

Do not provide `OPENAI_API_KEY` to workflows triggered by untrusted fork pull requests. A contributor can control patch content and may be able to induce cost or include content you did not intend to send.

Safer patterns include:

- keep ordinary `pull_request` checks offline;
- run AI review manually or after a trusted maintainer applies an approval label;
- use an environment with required reviewers and a spending limit;
- constrain Action permissions to `contents: read` unless another reviewed step needs more;
- never print the API key, request headers, or full request body to logs;
- do not use `pull_request_target` to checkout or execute untrusted PR code.

GitHub Secrets reduce accidental display; they do not make it safe to expose a secret to attacker-controlled code.

## Cost and availability

OpenAI API usage may incur charges. Context caps bound a single PatchProof request but do not impose an account-wide spending limit, prevent repeated workflow runs, or guarantee a fixed token count. Use OpenAI project-level budgets and rate limits, restrict who may trigger AI review, and monitor usage outside PatchProof.

PatchProof does not include API credits and does not guarantee access to any model.

## Recommended decision checklist

Before using `--ai`, confirm that:

1. You are authorized to send the selected source context to OpenAI.
2. The repository and workflow do not expose the key to untrusted contributors.
3. Your organization's retention, residency, legal, and contractual requirements are satisfied.
4. The chosen model is available and its cost is acceptable.
5. Maintainers understand that AI findings are advisory and cannot affect CI gating.
6. A human will verify AI findings and the original diff remains the source of truth.

When any answer is uncertain, use the offline deterministic mode.
