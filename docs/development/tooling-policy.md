# Repository automation and search policy

This policy covers repository tooling for rdetoolkit v2. Repository maintainers
(the reviewers named by `.github/CODEOWNERS`) own changes to this policy and must
review any proposal to restore external AI automation or a generated code index.
Local migration Skills and correctness tests run without an external LLM service
or AI API credentials.

## PR-Agent: removed before GA (#674)

The Qodo job and its unused `.pr_agent.toml` configuration are removed. This
follows [PR #654](https://github.com/nims-mdpf/rdetoolkit/pull/654), whose author
states that the workflow is no longer used, and uses the same workflow deletion.
No third-party PR-Agent action or provider credential is required by CI.

### Audit evidence

At `develop/v2` commit `9bf240e2`, `.github/workflows/pr-agent.yaml`:

- Used the moving `qodo-ai/pr-agent@main` ref. Its action and transitive
  dependencies were not reproducibly pinned to a reviewed revision.
- Ran for `pull_request` opened/reopened/synchronize, `issue_comment`
  created/edited (without a PR-only or trusted-author filter), and manual dispatch.
- Supplied `OPENAI_KEY` and `GITHUB_TOKEN`, with issue and pull-request write
  permissions; automatic review, description and improvement were enabled.
- Had no checkout or explicit shell execution step. This is not evidence that
  comment text already allowed arbitrary shell commands; the privileged action's
  handling of untrusted text and its dependencies was not established.

The configuration selected OpenAI models (`gpt-4.1` with fallbacks), included
patch context (five lines before and three after), and enabled review labels.
PR diffs, surrounding repository code, PR descriptions/comments and repository
configuration must therefore be treated as potential provider-bound data. The
moving action ref prevents a defensible fixed inventory of transmitted payloads.
There was no checked-in provider authorization, data classification rule, dedicated
service owner, retention/logging agreement or audited dependency revision. A
broad CODEOWNERS entry alone does not approve external data transmission.

Fork PR events normally withhold repository secrets and restrict their token,
but this does not establish a safe policy for issue-comment events, same-repository
PRs or manual runs. Prompt injection in PR/comment text can affect AI output;
output must never authorize privileged operations. Removal eliminates this job's
secret access, external data transmission and issue/PR write permissions for all
of these event paths.

| Event scenario | Behavior after removal | Verification |
| --- | --- | --- |
| Fork or same-repository PR, including synchronize | No PR-Agent job/action | Retired-path and all-workflow dependency guards |
| Trusted or untrusted comment on a PR or issue, created or edited | No PR-Agent job/action | Same guards; no comment parser remains |
| Manual dispatch | No PR-Agent workflow to dispatch | Retired-path guard |
| No external AI credentials configured | Local tests and CI do not depend on PR-Agent | All-workflow credential/action guards and full test suite |

Deleting repository files does not erase historical Actions logs or provider
records and does not revoke an existing API key. Administrators should inventory
the old credential's consumers, remove the repository secret if unused, and
revoke a dedicated obsolete key at the provider. Historical log access, retention
and any previously transmitted research data require the repository owner's
review against the applicable provider agreement. This source change makes no
claim that those administrative actions have been performed.

### Requirements for any future opt-in automation

A separate reviewed PR must name the service owner and obtain an explicit
maintainer/data-owner decision on the provider, allowed data classes, payload,
purpose, logging, retention/deletion and provider training policy. Nonpublic,
embargoed or restricted research material is excluded unless its data owner has
explicitly approved that exact provider and use. Public repository visibility
alone is not authorization for provider transmission.

The implementation must pin an audited immutable action SHA and record its
transitive dependency/update review strategy; use a dedicated revocable credential;
and scope GitHub permissions and credential-bearing jobs to the minimum approved
operation. It must test fork, same-repository, comment-author and manual-trigger
cases, require explicit opt-in for provider-bound work, and treat PR bodies,
comments, diffs and model output as untrusted data. Never check out or execute
untrusted PR code in a credential-bearing job, interpolate event text into shell
commands, or allow model output to select privileged commands. Logs must omit
credentials, prompts and research data, with an agreed retention/access policy.
Correctness gates must remain usable with the integration absent. Updating these
retirement guards is part of that reviewed policy change, not an incidental CI fix.

## Generated code index: retired (#675)

The supported source of truth is versioned Python code/public APIs, checked-in
documentation and verified Skills. Repository and editor code search can inspect
those sources directly. Do not derive current runtime API guidance from indexed
copies of old agent Markdown under `src/rdetoolkit/`.

### Consumer inventory and decision

At the same base revision, a repository-wide search including hidden tracked
configuration found the following references to the generated JSONL index:

| Area inspected | Evidence |
| --- | --- |
| `tools/build_index.py` | Producer only: wrote `docs/search/rdetoolkit_code_index.jsonl`; no reader |
| `.github/workflows/build-index.yml` | Invoked the producer and attempted to commit/push its output; failures were hidden by `|| echo "no push"` |
| Generated JSONL | Its own record for the generator; not a consumer |
| `mkdocs.yml`, documentation and overrides | Native MkDocs `search` plugin; no JSONL reader or link |
| Runtime/CLI, tools/scripts, tests, agent instructions, build/release workflows and package configuration | No reader, supported command, schema contract or release dependency |

The artifact was last changed by commit `2ef1c956` (2025-08-05) and still recorded
obsolete source layouts such as the former monolithic `invoicefile.py`. No
supported in-repository consumer was identified. Out-of-repository private uses
cannot be inferred from this inventory and are not a maintained interface.

Remove the generator, JSONL artifact and self-committing workflow together. Keep
MkDocs' native search plugin as the documentation search implementation. This
removes an unused source snapshot and the push loop/hidden push failure mechanism;
it does not introduce a replacement index or new write-capable CI job.

Reintroduction requires a demonstrated consumer, named maintenance owner, versioned
schema and compatibility contract, deterministic generation, and tests of that
consumer. Prefer read-only `generate + check for drift` CI that reports differences;
do not silently push generated commits. Release archives must contain only the
intended supported assets.

## Verification

The automated guards in `tests/v2/tooling/test_repository_tooling_policy.py` check
that all five retired files remain absent, no workflow (including a renamed one)
references PR-Agent or its provider credential, no supported code/docs/agent
command refers to retired index files, and native documentation search stays enabled.
The guards run within the normal v2/full pytest suite; no network/provider call is
made. The full suite and documentation build verify that removal does not break
runtime tests, commands or documentation search generation. Inspect wheel/sdist
contents during release verification to ensure no retired/generated assets return.
