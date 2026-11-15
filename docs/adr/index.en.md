# Architecture Decision Records (ADR)

A record of the major decisions that shaped the design of rdetoolkit v2, and the reasons for
them. Each ADR consists of "Context", "Decision" and "Consequences".

| ADR | Title | Status |
|-----|-------|--------|
| [ADR-020](0020-eager-execution.md) | Retire the trace approach and move to eager execution | Accepted |
| [ADR-021](0021-conditional-v1-sunset.md) | Condition-based sunset of the v1 code path | Absorbed into ADR-023 |
| [ADR-022](0022-call-log-without-lineage.md) | Limit the execution record to a call log and do not track value lineage | Accepted |
| [ADR-023](0023-single-runner-contract-compat.md) | Unification into a single Runner and contract-level v1 compatibility | Accepted |

ADR-001 to ADR-019 belong to the design examined early in v2 development, in which flow functions
were traced to build a DAG before execution. That design was replaced by ADR-020 and is not part
of the released v2, so those records are not listed here.

## v2 design principles (summary)

- Flows run as ordinary Python. There is no tracing, no compilation and no pre-execution DAG (ADR-020).
- A node is just a function. The decorator only registers it and records its calls.
- The Runner owns the RDE procedures (mode determination, validation, `job.failed`, the directory layout) (ADR-023).
- The execution record is a record of calls; it does not infer data flow (ADR-022).
- Dependency injection happens once, at the flow boundary, based only on type annotations.
- Error codes are gathered in a single catalog, and every error has a remedy.
- rdetoolkit is not a workflow engine. It does not provide scheduling, node-level parallelism, resuming or caching.
