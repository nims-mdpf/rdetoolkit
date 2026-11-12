# ADR-022: Limit the execution record to a call log and do not track value lineage

- Status: Accepted
- Date: 2026-06

## Context

With eager execution ([ADR-020](0020-eager-execution.md)) there is no DAG before execution, so
showing data flow would require tracking the identity of values during the run (inferring which
node's output became which node's input). Examination showed the following.

- In the pandas code that researchers naturally write (`df.dropna()`, column arithmetic, copies),
  outputs and inputs can almost never be linked accurately. The resulting graph would be "an
  inference that looks like data flow but is actually broken", giving users a wrong explanation.
- A table of value identities, managing its invalidation as objects are garbage-collected, and
  walking containers would be the highest-risk part of the v2 implementation.
- At the expected scale, reading the flow function is enough to see how the data moves.

## Decision

v2.0 does not track value lineage. The execution record is limited to a call log that records,
for each node call, "when, what, in what order, how many times, how many milliseconds it took,
where it failed, and what the input and output types were".

## Consequences

- The record is the execution order itself, so it is deterministic and contains no inference.
- The output of `rdetoolkit graph` is the order of calls (the Call Sequence), and the output says
  so explicitly. It does not present itself as a data flow diagram.
- The RunReport, `repro export` and error context (which call failed) all work from the call log
  alone.
- The configuration model has no lineage-related settings (unknown keys are an error at load time).
- Lineage tracking will be reconsidered in a separate ADR, as an option that is off by default,
  only if demand for it is demonstrated. Even then, the default output of `graph` remains the order
  of calls.
