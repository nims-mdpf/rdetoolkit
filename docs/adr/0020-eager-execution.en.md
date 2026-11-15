# ADR-020: Retire the trace approach and move to eager execution

- Status: Accepted
- Date: 2026-06

## Context

The initial v2 design traced flow functions (ran them on proxies) to build a static DAG,
validated it, and then executed it. Evaluation showed that this approach has the following
problems.

- Code that researchers writing structured processing naturally write — branches such as
  `if result == 3:`, f-strings, literal arguments, `for` loops, passing containers around — is
  converted into a wrong DAG without raising an error. Forbidding the patterns one by one cannot
  cover them all.
- It is incompatible with branching on configuration values and with literal arguments, which are
  essential ways of writing structured processing.
- At the expected scale (a few to a few dozen nodes per flow, almost linear processing), the
  benefit of static validation before execution does not justify the cost of implementing and
  learning it.

The move from "trace Python to build a graph" to eager execution has been seen repeatedly in
other Python frameworks as well.

## Decision

Retire building the DAG in advance (tracing and compilation), and run flows as they are, as
ordinary Python functions. Node calls are recorded at run time, and the explanation of a run is
built afterwards from that record.

> Graphs are not written; they are observed.

## Consequences

- Branches, loops, literals, f-strings, default arguments and containers all behave with their
  Python meaning.
- Flows and nodes can be called directly and tested with pytest.
- Complete wiring validation before execution (ExecutionPlan) is lost. In its place, rdetoolkit
  provides static checks of registrations (`nodes lint`), runs that perform domain validation only
  (`run --validate-only`), import-time validation of templates, and the record of the previous run
  (`graph`).
- If performance becomes necessary, the extension point is parallelization per data tile.
  Node-level parallelization is not adopted, because it requires analyzing a DAG before execution
  and contradicts this decision.
- If a feature for assembling flows in a GUI is added in the future, it will be added in a separate
  layer, as a declarative graph representation that people wire explicitly, based on the type
  information in the node registry.
