# Nodes

A node is "a plain function whose calls are recorded". A function with the node
decorator can be called as an ordinary Python function and tested directly from pytest.

## What the node decorator does

The node decorator does only three things.

1. **Registration** — at import time, it registers the node's static metadata (NodeSpec)
   in the node registry. Registered nodes are listed by `rdetoolkit nodes list`.
2. **Recording** — only while the Runner is running, it records each call (the call log).
   Called outside the Runner, nothing is recorded and the node behaves as an ordinary function.
3. **Runtime type checking (optional)** — only when enabled in the configuration, it checks
   arguments and return values against the type annotations.

<!-- test: node-basic -->
```python
from rdetoolkit import node


@node(id="docs.concepts.scale", tags=["math"], version="1.0.0")
def scale(values: list[float], factor: float = 2.0) -> list[float]:
    """Multiply every value by a factor."""
    return [value * factor for value in values]


assert scale([1.0, 2.0]) == [2.0, 4.0]
assert scale([1.0], factor=3.0) == [3.0]
```

All decorator arguments are optional; the decorator can also be applied without parentheses.

| Argument | Default | Meaning |
|----------|---------|---------|
| `id` | `"module_name.function_name"` | Node ID; the name used in the registry and in the call log |
| `tags` | none | Tags for classification, used by `nodes list` and similar commands |
| `version` | `"0.0.0"` | Version of the node implementation (for the call log and documentation) |
| `idempotent` | `False` | Declares that the same input gives the same result (for the call log) |

## Node IDs

- If `id` is given, that value is the ID; otherwise the ID is `"{module name}.{function qualname}"`.
- Registering the same ID twice raises `E2001 DuplicateNodeId` (`RdeRegistryError`) at import time.
- A local function defined inside another function does not get a stable ID across imports,
  so `nodes lint` reports it as `E2005 UnstableNodeId`. Define nodes at module top level.

<!-- test: node-duplicate -->
```python
from rdetoolkit import node
from rdetoolkit.errors import RdeRegistryError


@node(id="docs.concepts.unique")
def first(value: int) -> int:
    return value


try:

    @node(id="docs.concepts.unique")
    def second(value: int) -> int:
        return value

except RdeRegistryError as error:
    code = error.code

assert code == 2001
```

## Inspecting nodes

Load the module that defines your nodes with `--module` to list them, show their details,
and run static checks from the CLI (`concepts_nodes.py` is the file that defines `scale` above).

<!-- test: node-inspect -->
```bash
$ python -m rdetoolkit nodes list --module concepts_nodes
$ python -m rdetoolkit nodes describe docs.concepts.scale --module concepts_nodes
$ python -m rdetoolkit nodes lint --module concepts_nodes
```

<!-- illustration: node-describe-output -->
```text
id: docs.concepts.scale
name: scale
input_schema: {'values': {'type_name': 'list[float]', 'has_default': False, 'default_repr': None}, 'factor': {'type_name': 'float', 'has_default': True, 'default_repr': '2.0'}}
output_schema: ('list[float]',)
tags: ('math',)
version: 1.0.0
idempotent: False
source_location: concepts_nodes:scale
```

`nodes lint` reports arguments without type annotations, unstable IDs and similar problems,
and returns exit code 3 if it finds any. Run it in CI to catch registration mistakes before
anything is executed.

## The call log

Each time a node is called inside the Runner, one record with the following fields is written.

| Field | Content |
|-------|---------|
| `call_id` | `"{node ID}#{sequence number}"`; distinguishes repeated calls to the same node |
| `seq` | Call order across the whole run (deterministic) |
| `iteration_index` | The data tile the call belongs to |
| `parent_flow` | ID of the calling flow |
| `status` / `duration_ms` / `error` | Outcome, elapsed time, and the error on failure |
| `inputs` / `outputs` | A **type summary** of the arguments and return values (type name and the head of the `repr`) |

The call log records when, what, in which order, how many times, how many milliseconds,
and where something failed. It does not track the identity of values. For this reason,
`rdetoolkit graph` draws the order of calls (Call Sequence), not a dataflow diagram
([ADR-022](../adr/0022-call-log-without-lineage.md)).

If you do not want the head of the `repr` recorded, disable it in `rdeconfig.yaml`.

<!-- test: node-config -->
```yaml
provenance:
  repr_head: "off"      # "on" (default) | "off"
  repr_head_len: 80
execution:
  type_check: "warn"    # "off" (default) | "warn" | "strict"
```

!!! warning "Quote `on` / `off`"
    YAML reads unquoted `on` / `off` as booleans, so loading the configuration fails with
    `E1002 ConfigLoadFailed`. Write them as strings: `"on"` / `"off"`.

With `type_check` set to `warn` or `strict`, arguments and return values are checked against
the type annotations at the node call boundary, and a mismatch is handled as
`E3002 NodeTypeMismatch`. With the default `off`, the check costs nothing.

## The boundary between flows and nodes

- No dependency injection happens inside a node. If a node needs an output destination or
  similar, the flow passes it explicitly as an argument. This keeps the data flow visible in
  the code.
- An exception raised inside a node is wrapped in `RdeExecutionError` (code 3001), and the
  call (`call_id`) that failed is recorded in the RunReport and in `job.failed`. The original
  exception is kept unchanged in `__cause__`.

## Built-in nodes

All processing that rdetoolkit provides is registered as built-in nodes (`rdetoolkit.nodes`).
Saving artifacts through built-in nodes is the standard way, and the fact that something was
saved is kept in the call log.

| Category | Nodes |
|----------|-------|
| Reading | `read_text`, `read_csv_with_header`, `read_excel`, `read_excel_fills`, `read_json`, `unzip_inputs` |
| Saving structured data | `save_csv`, `save_json`, `save_text`, `save_invoice` |
| Metadata | `parse_invoice_meta`, `build_meta`, `save_meta` |
| Images | `to_png`, `to_jpeg`, `make_thumbnail`, `save_main_image`, `copy_raw` |
| Graphs | `plot_lines`, `plot_scatter`, `save_figure` |

Built-in nodes work through the same mechanism as the nodes you write and have no special
privileges. For the arguments of each node, see the [API reference](../rdetoolkit/v2/nodes.md).

`as_node` exists for migrating v1 handler classes step by step, but it is meant for migration
only. For its usage, see [Migrating from v1 to v2](../migration_v1_to_v2.md).

## Related pages

- [Flows](flow.md) — the functions that call nodes, and dependency injection
- [Runner](runner.md) — the execution frame that owns the call log
