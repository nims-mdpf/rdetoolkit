# Flows

A flow is a function that the Runner calls once per data tile. A function with the flow
decorator **runs as an ordinary Python function**. There is no step that builds a graph in
advance; `if` statements, `for` statements, default arguments, literals and f-strings all
behave with their normal Python meaning ([ADR-020](../adr/0020-eager-execution.md)).

## What the flow decorator does

1. **Registration** — it registers the flow in the flow registry (listed by `rdetoolkit flows list`).
2. **Direct calls** — a call such as `pipeline(paths, out)` is an ordinary function call.
   Arguments are bound by the normal Python rules.
3. **Connection to the Runner** — only when called from the Runner, it reads the type
   annotations of the arguments and injects the runtime values (dependency injection, below).

Calling one flow from another is also just a function call. Nodes called in the inner flow
are recorded in the same call log, with the inner flow as their `parent_flow`.

| Argument | Default | Meaning |
|----------|---------|---------|
| `id` | `"module_name.function_name"` | Flow ID; becomes the `flow_id` of the RunReport |
| `error_code` | none | Converts an exception from the body into the error code written to `job.failed` |
| `error_message` | none | Likewise, the message; can embed `{error}` / `{error_type}` |

`error_code` / `error_message` correspond to v1's `catch_exception_with_message`.
For how to rewrite v1 code, see [Migrating from v1 to v2](../migration_v1_to_v2.md).

## Reserved types and dependency injection

The Runner can pass only the following five **reserved types** to a flow.

| Recommended argument name | Type (`rdetoolkit.types`) | Content |
|---------------------------|---------------------------|---------|
| `paths` | `InputPaths` | Input paths of the current data tile (`inputdata`, `rawfiles`, and so on) |
| `out` | `OutputContext` | Artifact directories (`struct`, `meta`, `main_image`, and so on) |
| `config` | `RdeConfig` | Runtime configuration |
| `invoice` | `InvoiceData` | The parsed invoice |
| `iteration` | `IterationInfo` | Data tile number (`index`), total count (`total`) and mode (`mode`) |

Injection is decided once, at the flow boundary, in this order.

1. The argument's type annotation is one of the reserved types → that value is injected.
   **The argument name is free.**
2. The argument has a default value → nothing is injected and the Python default is used.
3. Neither → the run fails with `E2003 UnresolvableFlowParam` before it starts.

Annotating more than one argument with the same reserved type raises
`E2006 DuplicateReservedTypeAnnotation`. No injection happens inside a node, so when a node
uses an output destination or similar, the flow passes it as an argument.

<!-- test: flow-injection -->
```python
from rdetoolkit import flow
from rdetoolkit.testing import run_flow
from rdetoolkit.types import InputPaths, IterationInfo, RdeConfig

seen = {}


@flow(id="docs.concepts.injection")
def inspect_tile(files: InputPaths, cfg: RdeConfig, tile: IterationInfo, threshold: float = 0.5) -> None:
    seen["inputs"] = [path.name for path in files.rawfiles]
    seen["policy"] = cfg.execution.on_iteration_error
    seen["tile"] = (tile.index, tile.total, tile.mode)
    seen["threshold"] = threshold


fixture_dir = workdir / "injection"
fixture_dir.mkdir()
(fixture_dir / "sample.txt").write_text("sample", encoding="utf-8")
report = run_flow(inspect_tile, fixture_dir)
assert report.status == "success"
assert seen == {"inputs": ["sample.txt"], "policy": "continue", "tile": (0, 1, "invoice"), "threshold": 0.5}
```

An argument that cannot be injected is reported as a configuration error before the flow is called.

<!-- test: flow-unresolvable -->
```python
from rdetoolkit import flow
from rdetoolkit.testing import run_flow
from rdetoolkit.types import InputPaths


@flow(id="docs.concepts.unresolvable")
def needs_threshold(paths: InputPaths, threshold) -> None:
    raise AssertionError("never called")


fixture_dir = workdir / "unresolvable"
fixture_dir.mkdir()
(fixture_dir / "sample.txt").write_text("sample", encoding="utf-8")
report = run_flow(needs_threshold, fixture_dir)
assert report.status == "failed"
assert report.error["code"] == 2003
```

## Calling a flow directly in tests

A flow is an ordinary function, so once you build the reserved-type values with the builders
in `rdetoolkit.testing`, you can call it without the Runner.

<!-- test: flow-direct -->
```python
import pandas as pd

from rdetoolkit import flow
from rdetoolkit.nodes import save_csv
from rdetoolkit.testing import make_input_paths, make_output_context
from rdetoolkit.types import InputPaths, OutputContext


@flow(id="docs.concepts.direct")
def write_table(paths: InputPaths, out: OutputContext) -> None:
    rows = [{"name": path.name, "size": path.stat().st_size} for path in paths.rawfiles]
    save_csv(pd.DataFrame(rows), out, "files.csv")


paths = make_input_paths(workdir / "direct", files=["a.txt"])
out = make_output_context(workdir / "direct-out")
write_table(paths, out)
assert (out.struct / "files.csv").read_text(encoding="utf-8").splitlines() == ["name,size", "a.txt,0"]
```

For details on writing tests, see the [testing guide](../guides/testing.md).

## ProcessingTemplate — skeleton and slots

When you process the same kind of measurement data repeatedly, you will want to share the
skeleton of the processing. `ProcessingTemplate` declares "a pre-wired flow" and "slots that
the user fills in": the template author writes the skeleton, and the user writes only the slots.
A template is syntactic sugar over a flow; execution, recording and testing work the same way
as for an ordinary flow.

<!-- test: flow-template -->
```python
from typing import final

from rdetoolkit.templates import ProcessingTemplate, slot
from rdetoolkit.testing import run_flow
from rdetoolkit.types import InputPaths


class CountingTemplate(ProcessingTemplate):
    """Skeleton owned by the template author."""

    @slot
    def count(self, paths: InputPaths) -> int: ...

    @final
    def __flow__(self, paths: InputPaths) -> None:
        total = self.count(paths)
        assert total >= 0


class TextFileCount(CountingTemplate):
    """What a template user writes: only the slot."""

    def count(self, paths: InputPaths) -> int:
        return len(list(paths.inputdata.glob("*.txt")))


fixture_dir = workdir / "template"
fixture_dir.mkdir()
(fixture_dir / "sample.txt").write_text("sample", encoding="utf-8")
assert run_flow(TextFileCount, fixture_dir).status == "success"
```

Template misuse is detected when the class is defined (at import), not at run time.

| Code | Name | Cause |
|------|------|-------|
| E2101 | TemplateSlotMissing | A required slot is not implemented |
| E2102 | TemplateSlotSignatureMismatch | The slot's argument names or type annotations do not match the declaration |
| E2103 | TemplateFinalOverride | The skeleton (`__flow__`) was overridden |
| E2104 | TemplateDeepInheritance | The user class was subclassed further (only one level of inheritance is allowed) |
| E2105 | TemplateCtorNotDefault | The class cannot be constructed without arguments (receive parameters through `config.custom`) |

To pass values between slots, the skeleton passes a return value explicitly to the next slot.
Keeping state on `self` is flagged by `nodes lint` as `W1101 TemplateSelfStateUsage`.
A slot is effectively just a method, so you can test it directly, as in `TextFileCount().count(paths)`.

Registered templates can be found from the CLI and used to generate a project skeleton.

<!-- illustration: flow-template-cli -->
```bash
$ python -m rdetoolkit templates list
$ python -m rdetoolkit templates describe <template-name>
$ python -m rdetoolkit init --processing-template <template-name> --module <provider-module>
$ python -m rdetoolkit run --flow modules.processing:MyProcessing
```

You can try the skeleton generation steps in level 1 of the [v2 tutorial](../tutorial_v2.md).

## Related pages

- [Nodes](node.md) — the recorded functions that flows call
- [Runner](runner.md) — the execution frame that calls flows
