# v2 API Overview

Reference for the public API added in rdetoolkit v2. The narrative explanation
of each concept is in [Nodes](../../concepts/node.md), [Flows](../../concepts/flow.md)
and [Runner](../../concepts/runner.md).

| Module | Contents |
|--------|----------|
| [`rdetoolkit` (decorators)](decorators.md) | `node`, `flow`, `as_node` |
| [`rdetoolkit.types`](types.md) | Reserved types and the v2 configuration model |
| [`rdetoolkit.nodes`](nodes.md) | Built-in nodes |
| [`rdetoolkit.templates`](templates.md) | `ProcessingTemplate` and `slot` |
| [`rdetoolkit.testing`](testing.md) | pytest fixtures and test helpers |
| [`rdetoolkit.plugin`](plugin.md) | Plugin discovery |
| [`rdetoolkit.runner`](runner.md) | `Runner` and configuration loading |
| [`rdetoolkit.report`](report.md) | `RunReport` |
| [`rdetoolkit.errors` (v2)](errors.md) | `RdeError` hierarchy |

The v1-compatible entry point `rdetoolkit.workflows.run` is documented on the
[Workflows](../workflows.md) page, and every error code is listed in the
[Error Catalog](../error_catalog.md).
