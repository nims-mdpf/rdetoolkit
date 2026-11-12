# ADR-021: Condition-based sunset of the v1 code path

- Status: Absorbed into ADR-023
- Date: 2026-06

## Context

The initial v2 plan was to keep the v1 implementation (the workflow loop, mode processing and the
pipeline) and provide the v2 Runner alongside it. In that form, the execution path, the
configuration model, the return values and the CLI would exist in two lines, permanently doubling
the maintenance cost.

## Decision

Define the end of the v1 code path not by a deadline but by the following three conditions.

1. v2 templates are adopted as the authoritative form of the official templates.
2. `migrate apply` can convert at least 80% of the official v1 templates without manual fixes.
3. v2 has been in operation for at least two minor releases without serious defects.

Once all three conditions hold, the v1 path enters maintenance mode, and deprecation warnings are
introduced with advance notice.

## Consequences

This decision was absorbed into [ADR-023](0023-single-runner-contract-compat.md). Instead of
keeping the v1 implementation until the conditions hold, ADR-023 fixes the v1 **contract** and
unifies the implementation into a single Runner by the v2.0 general release.

The policy of not emitting a deprecation warning from the v1 entry point
`run(custom_dataset_function=...)` is kept in ADR-023 as well.
