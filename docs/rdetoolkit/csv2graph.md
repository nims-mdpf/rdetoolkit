# CSV to Graph API

## Overview

The `rdetoolkit.graph.csv2graph` module turns CSV or Pandas data into static Matplotlib images and optional interactive Plotly visuals. The API handles column selection, direction-aware styling, legend management, and on-disk artifact management so that callers can focus on configuring plots rather than reproducing plotting boilerplate.

## Supported CSV Formats

`csv2graph()` reads files through `ParserFactory` and accepts:
- `standard`: CSV with a header row (default).
- `transpose`: Row-oriented CSV that is transposed during parsing.
- `noheader`: Headerless CSV; columns are auto-renamed to `Column_0`, `Column_1`, ....
- `meta_block`: CSV starting with `#` metadata lines, followed by a header row.
- `auto`: detect the format, the encoding and the delimiter from a bounded, read-only sample (at most 64 KiB and 50 rows). A file it is not confident about raises `AmbiguousFormatError` (an `InvalidCSVFormatError` and a `ValueError`) whose message lists the candidates, their evidence and the remedy; it never guesses. Its `decision` attribute is the `DetectionDecision`.
- the id of a reader installed through the `rdetoolkit.graph.readers` entry points.

Pass the desired format with `csv_format=`; the default stays `"standard"`, so automatic detection is not triggered by default. `rdetoolkit plot <csv> --detect` prints the decision of `auto` without plotting. The spec-first `render_graph` (whose default is `reader="auto"`), custom `TableReader`s and `GraphRenderer`s are described in [Graph Engine](../usage/structured_process/graph_engine.md).

## Axis Limits

`xlim`/`ylim` accept one-sided limits: `(0, None)` fixes only the lower bound and `(None, 10)` only the upper bound; the other side stays automatic, in images and in HTML. Reversed bounds invert the axis. A non-finite bound, equal bounds, or a bound `<= 0` on a log axis raise `PlotRequestError` (`reason="invalid_axis_limits"`) before anything is written. The CLI sets one side with `--xmin`, `--xmax`, `--ymin` and `--ymax`.

## Plotting Behaviour

- **Overlay mode (`mode="overlay"`)** plots every series on one Matplotlib figure. When multiple Y-series exist, individual plots are generated; single-series overlays skip them unless you explicitly pass `no_individual=False` (CLI: `--individual`).
- **Individual mode (`mode="individual"`)** skips the combined plot and writes one PNG per series. The `html` flag is ignored in this mode because HTML output is only generated when an overlay figure exists.
- **Dual-axis plots are not supported.** `mode` accepts only `"overlay"` and `"individual"`; `mode="dual_axis"` raises `PlotRequestError` (`reason="invalid_mode"`), and `rdetoolkit plot --mode dual_axis` exits with code 2. `PlotMode.DUAL_AXIS`, `PlotConfigBuilder.set_y2_axis`, `PlotConfig.y2_axis` and `DualAxisStrategy` stay importable for compatibility, but rendering a config with `PlotMode.DUAL_AXIS` or a `y2_axis` raises `PlotRequestError` (`reason="dual_axis_unsupported"`) before any figure or file exists; it never falls back to other figures. To compare series with different units, use `render_graph` with `GraphSpec(unit_policy="split")` (one overlay per unit), `mode="individual"`, or build a Matplotlib figure with `Axes.twinx()` and save it with the `save_figure` node.

Series naming follows the sanitised `title`/`name` parameter; individual plots append the series identifier derived from the column header. Individual names are reserved for every series before the first figure is drawn: names that collide case-insensitively (or after spacing/Unicode normalization) get the series id appended (`_s000`, `_s001`) with a `GraphUserWarning`, and `/`, `\` and `..` in a header become `_`, so no figure of a run overwrites another.

A mixed-unit overlay (for example `voltage (V)` with `current (A)`) without `y_label` is still drawn, with a `GraphUserWarning` and a y label listing every unit; each individual figure is labelled after its own column.

## Output Artifacts

- Matplotlib renders PNG files by default. Additional formats can be supplied through the builder pipeline, but the public API currently emits PNG.
- When `html=True` (and overlay plots are enabled), a Plotly figure is produced. `csv2graph()` saves `{base}.html` next to the source CSV even if `output_dir` points elsewhere; override with `html_output_dir`/`--html-output-dir`. `plot_from_dataframe()` defaults the HTML destination to `output_dir` unless `html_output_dir` is provided.
- Set `main_image_dir` to move non-HTML overlay outputs (for example the representative PNG) into a separate directory. Individual PNGs always live under `output_dir`.
- Directories are created on demand, and filenames are validated to prevent path traversal.
- If `return_fig=True` (available in `plot_from_dataframe()`), no files are written; instead a list of `MatplotlibArtifact` items is returned for the non-HTML artifacts.

## Column Selection

`validate_column_specs()` normalises column specifications before plotting:
- `x_col` and `y_cols` accept integers, column names, lists, or a mixture.
- With `x_col=None`, the first column is used. With `y_cols=None`, every column except the selected x column becomes a y series.
- Direction columns are optional. Provide a single column to reuse it for all series or a list to map per series. Missing entries are padded with `None` so direction filtering can be disabled selectively.

Invalid indices or names raise `ColumnNotFoundError`; mismatched x/y configurations raise `ValueError`.

## Direction-aware Plotting

Direction metadata can split each series into coloured segments:
- `direction_cols`: column(s) containing values such as `Charge`, `Discharge`, or custom labels.
- `direction_filter`: a string or sequence restricting which direction values appear.
- `direction_colors`: mapping from direction values (string or `Direction` enum) to explicit colours. Omitted entries fall back to the Matplotlib tab10 palette.

Both the Matplotlib and Plotly renderers honour these settings. In Matplotlib, the legend lists series names; Plotly groups traces by legendgroup so a single click hides every segment belonging to a series.

## Axis, Legend, and Title Controls

- Axis labels inherit from parsed headers (`parse_header`) and are humanised when headers use snake_case or include units; override with `x_label` / `y_label`.
- `logx`, `logy`, `invert_x`, `invert_y`, `xlim`, `ylim`, and `grid` map directly onto Matplotlib axis configuration. Limits are applied only when both bounds are provided.
- Legends honour `legend_loc` and `max_legend_items`. When the visible series count exceeds `max_legend_items`, the legend is suppressed to keep plots readable.
- `legend_policy` controls where the legend is placed: `"legacy"` (default) preserves the behavior above; `"auto"` picks placement based on item count, `legend_outside_threshold` (above it: outside right), and `legend_bottom_threshold` (at or above it: outside bottom; `None` disables the bottom switch); `"inside"`, `"outside_right"`, and `"outside_bottom"` force a specific placement; `"hide"` suppresses the legend entirely. Use `legend_ncol` to control the number of columns for `"outside_bottom"`.
- With the outside placements the figure canvas is enlarged to make room for the legend, so the plot area keeps its size even when the legend is large.
- The Plotly HTML output honors `legend_policy` as well: `hide` disables the legend and the concrete placements map to the corresponding Plotly legend positions, while `legacy` keeps Plotly's default placement. Unsupported `legend_policy` values raise `ValueError` at configuration time.
- Provide `legend_info` with newline placeholders (`\n`) to render supplemental text near the legend (Matplotlib) or as a Plotly annotation.
- `title` sets the overlay title; individual plots append ` - {series}`. If omitted in `csv2graph()`, the CSV stem becomes the title. `plot_from_dataframe()` also accepts `name` to override the base filename independently of the display title.

## Package Export Inventory

This table is the authoritative list of what `rdetoolkit.graph` exposes at the
package root. Each name belongs to exactly one tier:

- **supported** — GA public API. Listed in `rdetoolkit.graph.__all__`, typed in
  the package stub, covered by compatibility guarantees.
- **compatibility** — kept in `__all__` and the stub because earlier releases
  promised them there. They keep working, but new code should import them from
  the defining module shown in the table; they may be deprecated in a later
  release.
- **private** — implementation helpers. They are not in `__all__`, `dir()` or
  the stub, so a strict type checker rejects `from rdetoolkit.graph import ...`
  for them. The runtime attribute still resolves for backward compatibility,
  but with no stability guarantee. Do not depend on them.

Automated tests fail if this table, the runtime `__all__`, and the package stub
disagree.

<!-- graph-export-inventory:start -->
| Name | Tier | Defining module |
|------|------|-----------------|
| `csv2graph` | supported | `rdetoolkit.graph.api` |
| `plot_from_dataframe` | supported | `rdetoolkit.graph.api` |
| `GraphPlottingError` | supported | `rdetoolkit.graph.exceptions` |
| `ColumnNotFoundError` | supported | `rdetoolkit.graph.exceptions` |
| `InvalidMetadataError` | supported | `rdetoolkit.graph.exceptions` |
| `InvalidCSVFormatError` | supported | `rdetoolkit.graph.exceptions` |
| `DirectionError` | supported | `rdetoolkit.graph.exceptions` |
| `DualAxisError` | supported | `rdetoolkit.graph.exceptions` |
| `PlotConfigError` | supported | `rdetoolkit.graph.exceptions` |
| `RendererError` | supported | `rdetoolkit.graph.exceptions` |
| `PlotMode` | supported | `rdetoolkit.graph.models` |
| `CSVFormat` | supported | `rdetoolkit.graph.models` |
| `Direction` | supported | `rdetoolkit.graph.models` |
| `AxisConfig` | supported | `rdetoolkit.graph.models` |
| `LegendConfig` | supported | `rdetoolkit.graph.models` |
| `DirectionConfig` | supported | `rdetoolkit.graph.models` |
| `OutputConfig` | supported | `rdetoolkit.graph.models` |
| `PlotConfig` | supported | `rdetoolkit.graph.models` |
| `CSVMetadata` | supported | `rdetoolkit.graph.models` |
| `ParsedData` | supported | `rdetoolkit.graph.models` |
| `titleize` | compatibility | `rdetoolkit.graph.textutils` |
| `sanitize_filename` | compatibility | `rdetoolkit.graph.textutils` |
| `to_snake_case` | compatibility | `rdetoolkit.graph.textutils` |
| `parse_header` | compatibility | `rdetoolkit.graph.textutils` |
| `ColumnNormalizer` | compatibility | `rdetoolkit.graph.normalizers` |
| `validate_column_specs` | compatibility | `rdetoolkit.graph.normalizers` |
| `PlotConfigBuilder` | compatibility | `rdetoolkit.graph.config` |
| `apply_matplotlib_config` | compatibility | `rdetoolkit.graph.config` |
| `DEFAULT_FIG_SIZE` | compatibility | `rdetoolkit.graph.config` |
| `DEFAULT_PLOT_PARAMS` | compatibility | `rdetoolkit.graph.config` |
| `normalize_direction_filter` | private | `rdetoolkit.graph.models` |
| `build_direction_config` | private | `rdetoolkit.graph.models` |
| `RenderResult` | private | `rdetoolkit.graph.models` |
| `MatplotlibArtifact` | private | `rdetoolkit.graph.models` |
| `NormalizedColumns` | private | `rdetoolkit.graph.models` |
| `RenderCollections` | private | `rdetoolkit.graph.models` |
| `resolve_column_index` | private | `rdetoolkit.graph.normalizers` |
| `determine_titles` | private | `rdetoolkit.graph.config` |
| `determine_formats` | private | `rdetoolkit.graph.config` |
| `normalize_axis_limits` | private | `rdetoolkit.graph.config` |
| `collect_render_results` | private | `rdetoolkit.graph.strategies` |
| `build_matplotlib_artifacts` | private | `rdetoolkit.graph.strategies` |
<!-- graph-export-inventory:end -->

Type-safe import of the supported API:

```python title="typed_graph_imports.py"
from pathlib import Path

from rdetoolkit.graph import AxisConfig, GraphPlottingError, PlotConfig, PlotMode, csv2graph

config = PlotConfig(mode=PlotMode.OVERLAY, x_axis=AxisConfig(label="time"))
try:
    csv2graph(Path("data.csv"), mode="overlay")
except GraphPlottingError as exc:
    print(f"plot failed: {exc}")
```

## API Reference

::: rdetoolkit.graph.csv2graph

---

::: rdetoolkit.graph.plot_from_dataframe

---

## Usage Examples

### Basic CSV conversion

```python title="basic_csv2graph.py"
from rdetoolkit.graph import csv2graph

csv2graph("data.csv")  # output next to the CSV

csv2graph(
    "experiment.csv",
    output_dir="plots",
    logy=True,
    title="Experiment Summary",
)
```

### Selecting columns and enabling individual plots

```python title="column_selection.py"
from rdetoolkit.graph import csv2graph

csv2graph(
    "measurements.csv",
    output_dir="overlay_and_series",
    mode="overlay",
    x_col="time_s",
    y_cols=["voltage_v", "current_ma"],
    legend_loc="upper right",
    max_legend_items=5,
)

csv2graph(
    "multi_sensor.csv",
    output_dir="per_series",
    mode="individual",  # only individual PNGs are created
    x_col=0,
    y_cols=[1, 2, 3, 4],
    grid=True,
)
```

### Working with direction metadata

```python title="direction_filtering.py"
from rdetoolkit.graph import csv2graph

csv2graph(
    "battery_cycles.csv",
    output_dir="battery",
    direction_cols="direction",
    direction_filter=["Charge", "Discharge"],
    direction_colors={
        "Charge": "#FF6B6B",
        "Discharge": "#4ECDC4",
    },
    legend_info="Cell: 18650\n25C",
    html=True,  # saves battery.html next to the CSV by default
)
```

### Parsing alternate CSV layouts

```python title="transpose_format.py"
from rdetoolkit.graph import csv2graph

csv2graph(
    "transposed_data.csv",
    csv_format="transpose",
    output_dir="plots",
    mode="overlay",
)

csv2graph(
    "no_header_data.csv",
    csv_format="noheader",
    output_dir="plots",
)
```

### Controlling output locations

```python title="main_image_dir.py"
from rdetoolkit.graph import csv2graph

csv2graph(
    "series.csv",
    output_dir="other_images",
    main_image_dir="main_image",  # overlay PNG saved here
    html=True,
    grid=True,
)
```

- Use `html_output_dir` (CLI: `--html-output-dir`) to move the HTML output away from the CSV directory when needed (for example, keep it under `data/structured` while PNGs live in `data/other_image`).

### Plotting from a DataFrame

```python title="dataframe_plotting.py"
import pandas as pd
from rdetoolkit.graph import plot_from_dataframe

frame = pd.read_csv("processed.csv")
frame["normalized"] = frame["value"] / frame["value"].max()

artifacts = plot_from_dataframe(
    df=frame,
    output_dir="analysis",
    name="processed",
    title="Processed Output",
    x_col="time",
    y_cols=["value", "normalized"],
    return_fig=True,
)

for artifact in artifacts:
    artifact.figure.savefig(f"custom_{artifact.filename}", dpi=300)
```

## Error Handling

Common failure modes include:
- `ColumnNotFoundError` when a requested column is missing.
- `ValueError` for inconsistent x/y/direction mappings or when the DataFrame lacks y columns.
- `ImportError` from Plotly when `html=True` but Plotly is not installed.
- `PlotRequestError` (a `PlotConfigError` and a `ValueError`) with `reason="invalid_mode"` for `mode="dual_axis"`, and with `reason="dual_axis_unsupported"` when a legacy `PlotConfig` with `PlotMode.DUAL_AXIS` or a `y2_axis` is rendered. Dual-axis plotting is not supported.
- `PlotRequestError` with `reason="contradictory_switches"` for `mode="individual"` with `no_individual=True`, and with `reason="invalid_axis_limits"` for invalid `xlim`/`ylim`.
- `AmbiguousFormatError` when `csv_format="auto"` cannot decide; `UnknownReaderError` (an `InvalidCSVFormatError`) for an unknown format id; `InvalidCSVFormatError` for an empty file under `auto`.

These errors are raised before any file or directory is created.

Ensure output directories exist or are creatable and that Plotly is installed when HTML output is desired.
