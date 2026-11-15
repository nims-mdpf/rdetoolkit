# Plugin Development Guide

A plugin is a way to distribute nodes, templates and file-format declarations as an independent
package. Once installed, they appear in `nodes list --plugin`, `templates list` and `formats list`,
and other projects can use them.

## What a plugin can provide

| Provides | How to write it | Command that discovers it |
|----------|-----------------|---------------------------|
| Nodes | Functions with the node decorator | `rdetoolkit nodes list --plugin` |
| Templates | Skeleton classes that inherit from `ProcessingTemplate` | `rdetoolkit templates list` |
| File formats | The module variable `FORMAT_HANDLERS` (a tuple of `FormatHandler`) | `rdetoolkit formats list` |

A plugin cannot insert processing into the Runner's lifecycle. A plugin's nodes and templates
work through the same mechanism as the ones you write yourself, and have no special privileges.

## 1. Write the provider module

Put the nodes, templates and `FORMAT_HANDLERS` you provide in the module that serves as the
plugin's entry. Here it is called `rdetoolkit_example_plugin.py`.

<!-- test: plugin-provider -->
```python
from typing import final

from rdetoolkit import node
from rdetoolkit.plugin import FormatHandler
from rdetoolkit.templates import ProcessingTemplate, slot
from rdetoolkit.types import InputPaths


@node(id="example_plugin.count_lines")
def count_lines(text: str) -> int:
    """Count the lines of a text file's content."""
    return len(text.splitlines())


class LineCountTemplate(ProcessingTemplate):
    """Skeleton for instruments that write plain-text logs."""

    @slot
    def read(self, paths: InputPaths) -> str: ...

    @final
    def __flow__(self, paths: InputPaths) -> None:
        count_lines(self.read(paths))


FORMAT_HANDLERS = (
    FormatHandler(
        name="Example text log",
        extensions=(".log",),
        target="rdetoolkit_example_plugin:LineCountTemplate",
    ),
)
```

- Prefix node IDs with the package name so that they do not collide with other packages.
  Registering the same ID twice raises `E2001`.
- `FORMAT_HANDLERS` is a declaration (a name, extensions, and a reference shown to users); the
  Runner does not call it automatically.

## 2. Register the entry point

In the package's `pyproject.toml`, register the provider module in the `rdetoolkit.plugins` group.

<!-- test: plugin-entry-point -->
```toml
[project.entry-points."rdetoolkit.plugins"]
example = "rdetoolkit_example_plugin"
```

## 3. Install and check

Once the package is installed (`pip install -e .` during development), the following commands
show what it provides.

<!-- test: plugin-discovery -->
```bash
$ python -m rdetoolkit nodes list --plugin
$ python -m rdetoolkit templates list
$ python -m rdetoolkit formats list
```

<!-- illustration: plugin-discovery-output -->
```text
example_plugin.count_lines
rdetoolkit_example_plugin.LineCountTemplate
Example text log (.log) -> rdetoolkit_example_plugin:LineCountTemplate [example]
```

`formats list` shows, for each file format, its name, extensions and reference, together with
the name of the plugin that provides it (the entry point name). With `--json` it writes a
machine-readable format.

A plugin that fails to import, or whose `FORMAT_HANDLERS` has the wrong form, is skipped with
the reason printed to standard error. This does not affect other plugins or the command itself.
To inspect discovery results from Python, use `rdetoolkit.plugin.discover_plugins()`.

## 4. Use it from the consumer side

Users import a plugin's nodes as ordinary functions and call them from their flows; they
inherit from a template and implement its slots. To create a project skeleton from a template,
use `init --processing-template`.

<!-- test: plugin-usage -->
```bash
$ python -m rdetoolkit templates describe LineCountTemplate
$ python -m rdetoolkit init --processing-template LineCountTemplate --module rdetoolkit_example_plugin
```

`templates describe` shows the names, arguments and return types of the slots. `init` generates
a user class with the slots left as TODOs (`processing.py`), a sample test
(`tests/test_processing.py`) and an entry point (`main.py`).

## Testing a plugin

The nodes and templates of the provider module can be tested in the same way as in the
[Testing Guide](testing.md). Running `nodes lint --module rdetoolkit_example_plugin` in CI
detects missing type annotations and misuse of templates before distribution.

## Related pages

- [Nodes](../concepts/node.md) and [Flows](../concepts/flow.md) — the rules for nodes and templates
- [API reference: rdetoolkit.plugin](../rdetoolkit/v2/plugin.md)
