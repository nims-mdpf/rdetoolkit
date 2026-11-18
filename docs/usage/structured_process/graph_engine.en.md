# Graph Engine: GraphSpec, readers and renderers

## Overview

`render_graph` is the spec-first entry point behind `csv2graph` and `rdetoolkit plot`.
You describe *what* to plot with a `GraphSpec`, *where* to write with an `OutputSpec`,
and the engine resolves a `PlotPlan`, renders every figure and returns a `GraphResult`
that lists every artifact it produced. `csv2graph`, `plot_from_dataframe` and
`rdetoolkit plot` keep their v1 signatures; see [Visualizing CSV as Graphs](csv2graph.en.md).

The engine has two extension seams, both usable without changing rdetoolkit:

- a **table reader** (`TableReader`) turns a file into a table;
- a **renderer** (`GraphRenderer`) turns a planned figure into bytes.

Everything named on this page is importable from `rdetoolkit.graph`.

## The flow of one call

1. **Load**: a DataFrame (or a list of DataFrames, or a `TableData`) is used as is; a
   path is read by a table reader (`reader="auto"` by default, see below).
2. **Plan**: `build_plot_plan` resolves the `GraphSpec` against the table: columns,
   x/y pairs, labels, units, figure layout and file names. An invalid request raises
   `PlotRequestError` (a `ValueError`; its `reason` attribute tells the cases apart).
3. **Plan the artifacts**: each format and figure kind is assigned a renderer, optional
   dependencies are checked, destinations are validated and file names are reserved.
4. **Render, export, write**: nothing touches the file system before step 3 is
   complete, and nothing is written before every figure has rendered.

## GraphSpec and OutputSpec

| Field | Meaning |
|---|---|
| `GraphSpec.x`, `GraphSpec.series` | The x column and one `SeriesSpec` per y column (by 0-based position or by name). Empty `series` plots every other column. |
| `GraphSpec.layout` | `"auto"`, `"overlay"`, `"individual"` or `"both"` |
| `GraphSpec.mark` | `"line"` or `"scatter"` |
| `GraphSpec.x_axis`, `GraphSpec.y_axis` | `AxisSpec`: `label`, `scale` (`"linear"` / `"log"`), `limits`, `grid`, `invert`, `tick_format` |
| `GraphSpec.legend` | `LegendSpec`: item limit and placement policy |
| `GraphSpec.unit_policy` | `"error"` (default), `"split"`, `"warn"` or `"allow"`; see [Units](#units) |
| `GraphSpec.style` | `StyleSpec`: `figure_size` and Matplotlib `rc_params`, applied to this call's figures only |
| `OutputSpec.sink` | Where artifacts go: `DirectorySink` or `OutputContextSink` |
| `OutputSpec.formats` | For example `("png",)`, `("png", "svg")` or `("png", "html")` |
| `OutputSpec.base_name` | File name stem (`"plot"` by default) |
| `OutputSpec.on_existing` | `"overwrite"` (default, recorded per artifact) or `"error"` |
| `OutputSpec.dpi` | Raster resolution (300 by default) |

`AxisSpec.limits` accepts one-sided limits: `(0, None)` fixes only the lower bound.
Reversed bounds invert the axis; a non-finite bound, equal bounds or a bound `<= 0` on
a log axis raise `PlotRequestError` (`reason="invalid_axis_limits"`).

Without `output=`, `render_graph` writes nothing and returns caller-owned figure
handles in `Artifact.figure`.

## Output destinations

| Sink | Overlay images | Individual images | HTML |
|---|---|---|---|
| `DirectorySink(output_dir, main_image_dir=None, html_dir=None)` | `main_image_dir` (or `output_dir`) | `output_dir` | `html_dir` (or `output_dir`) |
| `OutputContextSink(out)` | `main_image` | `other_image` | `struct` |

`OutputContextSink` writes through the `OutputContext` of a flow, so graph files obey
the same ownership rules as every other node output. Destinations are checked by name
and by real path (symlink targets included); one outside its directory raises
`OutputPathError`. With `on_existing="error"`, an existing file raises
`ArtifactCollisionError` before anything is rendered.

## Formats and renderers

| Format | Overlay | Individual | Builtin renderer |
|---|---|---|---|
| `png`, `svg`, `pdf` | yes | yes | Matplotlib |
| `html` | yes | no | Plotly (optional dependency) |

Any other combination raises `UnsupportedFormatError` before anything is written.
HTML without Plotly installed raises `RendererUnavailableError`, an `ImportError` that
names `pip install "rdetoolkit[plotly]"`, also before anything is written.

## Table readers and format detection

With `reader="auto"` (the default of `render_graph`) the reader is chosen in this order:

1. a reader that claims the file suffix (`TableReader.extensions`), from the `readers=`
   registry you pass, the builtin readers or the installed entry points. Two claimants
   are an `AmbiguousFormatError`, never a guess;
2. otherwise content detection (`detect_table_format`): a read-only sample of at most
   64 KiB and 50 rows decides between the builtin readers `standard`, `transpose`,
   `noheader` and `meta_block`, and detects the encoding and the delimiter. If no
   candidate is confident, `AmbiguousFormatError` lists the candidates with their
   evidence and names the remedy; an empty file raises `InvalidCSVFormatError`.

`reader="<id>"` names a reader explicitly, and `reader=` also accepts a `TableReader`
instance. The decision is returned as `GraphResult.detection` (a `DetectionDecision`
whose `explain()` gives a readable summary). On the command line,
`rdetoolkit plot data.csv --detect` prints the same decision without plotting, and
`--csv-format auto` plots with it. The default of `csv2graph` and `rdetoolkit plot` stays
`standard`.

### Installing a reader as a plugin

A distribution can publish readers in the entry-point group `rdetoolkit.graph.readers`.
The entry-point name is the reader id; the target is a `TableReader` instance or a
zero-argument callable returning one. A reader class is such a callable: it is
instantiated with no arguments, and a constructor that fails or needs arguments raises
`ReaderPluginError` naming the entry point. For example, in `pyproject.toml`:
`[project.entry-points."rdetoolkit.graph.readers"]` with
`"vendor.instrument" = "vendor_pkg.readers:READER"`. Entry points are listed only when a
reader is looked up (`discover_readers()`), never at import time, and an id that clashes
with a builtin reader, with `"auto"` or with another entry point raises
`DuplicateReaderError` instead of picking one. A registry passed as `readers=` always
takes precedence.

## Example: a custom table reader

The script below defines a reader for a fictional `.instrument` format, registers it
in a `ReaderRegistry` and plots a file through `render_graph`. Under `reader="auto"` the
reader is selected because it claims the `.instrument` suffix.

```python title="docs/usage/structured_process/graph_engine_samples/custom_reader.py"
--8<-- "docs/usage/structured_process/graph_engine_samples/custom_reader.py"
```

## Example: a custom renderer

The script below defines a dependency-free renderer that writes one small SVG per figure
and injects it through a `RendererRegistry`. Every artifact goes to the first registered
renderer whose `RendererCapabilities` declare its format and figure kind; a format no
registered renderer declares raises `UnsupportedFormatError`.

```python title="docs/usage/structured_process/graph_engine_samples/custom_renderer.py"
--8<-- "docs/usage/structured_process/graph_engine_samples/custom_renderer.py"
```

Both scripts are executed by the test suite, so they stay in step with the API.

## Units

Units are read from headers such as `voltage (V)` and compared as text; nothing is
converted (`mV` and `V` differ, and a column without a unit is assumed compatible).

| `unit_policy` | An overlay mixing units |
|---|---|
| `"error"` (default of `render_graph`) | `PlotRequestError` (`reason="unit_mismatch"`) before anything is drawn |
| `"split"` | One overlay per unit (stems `plot_v`, `plot_a`, ...) |
| `"warn"` | One overlay with a joined y label (`V (V) / I (A)`) and a `GraphUserWarning` |
| `"allow"` | One overlay with a joined y label, without a warning |

With `"split"`, `"warn"` and `"allow"` the mismatch is recorded as a `unit_mismatch` diagnostic of the plan
and the manifest.

`csv2graph`, `plot_from_dataframe` and `rdetoolkit plot` keep drawing the overlay, warn,
and label the y axis with every unit. Dual-axis plots are not supported; use
`unit_policy="split"` or individual figures instead.

## File names

Individual figure names are reserved for every series before the first figure is
drawn. Two series whose names differ only by case, spacing or Unicode normalization
both get their series id appended (`plot_voltage_s000.png`, `plot_voltage_s001.png`)
and a `filename_collision` diagnostic; `/`, `\` and `..` in a header become `_`. No
artifact of a run overwrites another one.

## The manifest

`GraphResult.artifacts` lists one `Artifact` per written file (or per in-memory figure)
in plan order: figure id, kind, role, format, renderer, series ids, labels, path and
`replaced_existing`. `GraphResult.manifest()` and `manifest_json()` give the same
information as a versioned, machine-independent document (file names only, stable key
order, the detection as an object). The engine never writes the manifest itself; write
`manifest_json()` wherever you need it. The same request gives the same manifest text
whatever the output directory.
