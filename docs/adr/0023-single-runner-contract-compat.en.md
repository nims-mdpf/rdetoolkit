# ADR-023: Unification into a single Runner and contract-level v1 compatibility

- Status: Accepted
- Date: 2026-07-15
- Absorbs: [ADR-021](0021-conditional-v1-sunset.md)

## Context

Maintaining the v1 and v2 implementations side by side means every bug fix and dependency update
has to be done twice, and the handling of configuration, return values, error policy and the
execution record keeps differing depending on the entry point.

On the other hand, what users depend on is not the v1 implementation itself but the following
public surface.

- The entry point `run(custom_dataset_function=...)` and the argument types of the callback
- The artifact contract: the directory layout, the invoice, raw files and thumbnails, the format
  of `job.failed`, exit codes, and the conversion from `StructuredError` to `job.failed`
- The public APIs that are imported directly: `rde2types`, `rde2util`, `invoicefile`, `errors`, `exceptions`

## Decision

1. **A single Runner**: the flow entry point and the v1 callback entry point are normalized into
   the same execution request and run with the same Runner, error policy, events, RunReport and
   finalization. The v1 execution path is deleted by the v2.0 general release.
2. **Change the unit of compatibility from "code" to "contract"**: the public surface above is
   kept, and is guaranteed by frozen test expectations (contract fixtures) created from v1 run
   results. Byte-for-byte identity with the v1 implementation is not guaranteed.
3. **A single configuration**: inside the Runner, only the v2 configuration model is used. v1
   configuration is converted at the entry point. Settings related to v1 artifacts are also added
   to the v2 configuration, with the same defaults as in v1.
4. **Recording callbacks**: a v1 callback is recorded as a flow. Nodes called inside the callback
   remain in the same call log, so `graph`, `report` and `repro` can be used with the v1 entry
   point as well.

## Consequences

- There is one execution path to maintain, and the error policy, events and reports are consistent
  across all entry points.
- v1 users can keep running without changing their code. The v1 entry point does not emit a
  deprecation warning.
- Differences from v1 are detected within the scope of the frozen contract fixtures, so the
  quality of compatibility depends on how well the fixtures cover it. This is supplemented with
  representative normal and error cases for the five modes, and with programs close to real use.
- At the v1 entry point, the default behavior when a data tile fails stays `fail_fast`, as in v1;
  at the flow entry point it is `continue`. The points where results intentionally differ from v1
  are listed in [Migrating from v1 to v2](../migration_v1_to_v2.md).
