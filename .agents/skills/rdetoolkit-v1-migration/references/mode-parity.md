# Frozen mode parity

`scripts/check_mode_parity.py` runs 24 exact pytest node IDs from
`tests/v2/contract/test_unified_matrix.py` in a source checkout. A missing node
ID is a collection error; a skipped, xfailed or unexpectedly passing case makes
the gate fail, so unavailable evidence never becomes a success claim.

| Evidence | Cases | Assertion |
| --- | --- | --- |
| Synthetic success | Five modes | Runner success, tile counts, invoices, directory layout, raw and artifact SHA-256 |
| Real-input canary success | Five modes | Same full observation, including image and thumbnail bytes |
| User and validation errors | Five modes × two outcomes | Failed status, invocation counts, `job.failed`, documented v1/v2 error translation |
| Three-tile fail-fast | ExcelInvoice, MultiDataTile, SmartTable | Frozen artifact content and `job.failed`; tile after failure absent |
| Three-tile continue | MultiDataTile | Frozen full artifacts; partial status, later tile runs, no `job.failed` |

The expectations under `tests/v2/contract/fixtures/expected/` were recorded
from v1; their `source.commit` names the v1 revision. The gate runs the v2
Runner against them and never regenerates them. Contents of `data/logs/` differ
between v1 and v2 and are excluded; the directory itself is still compared.

This is a toolkit compatibility gate, not evidence that a user's callback,
inputs or output format migrated correctly. Compare the project's own v1 and
v2 data roots as described in the Skill, keeping the original v1 result as the
oracle.

## Per-mode review points

| Mode | Required project review |
| --- | --- |
| Invoice | v2 validates the invoice before the callback runs. Compare invalid invoices and schema failures through the error translation table, not only the numeric code. |
| ExcelInvoice | Preserve workbook grouping, archive/file assignment and row counts. The v2 `continue` policy is new; v1 parity exists for fail-fast only. |
| MultiDataTile | Preserve ordering and tile indices; test empty, one and multiple inputs. Map legacy `ignore_errors` explicitly to the intended v2 policy. |
| SmartTable | Preserve row material, metadata columns, archive selection and `save_table_file`. The v2 `continue` policy has no v1 oracle. |
| RDEFormat | Preserve archive components, existing structured files and images, and copy semantics. The real-input canaries cover artifacts the synthetic inputs lack. |

`tests/v2/contract/flow_error_table.py` defines the intentionally changed flow
error semantics. The legacy callback entry keeps its own frozen regression
matrix; this gate does not replace or remove it.
