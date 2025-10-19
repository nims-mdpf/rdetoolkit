# CSV to Graph API

## Overview

The `rdetoolkit.graph.api.csv2graph` module turns CSV or Pandas data into static Matplotlib images and optional interactive Plotly visuals. The API handles column selection, direction-aware styling, legend management, and on-disk artifact management so that callers can focus on configuring plots rather than reproducing plotting boilerplate.

## Supported CSV Formats

`csv2graph()` reads files through `ParserFactory` and accepts:
- `standard`: CSV with a header row (default).
- `transpose`: Row-oriented CSV that is transposed during parsing.
- `noheader`: Headerless CSV; columns are auto-renamed to `Column_0`, `Column_1`, ....

Pass the desired format with `csv_format="standard" | "transpose" | "noheader"`. Automatic detection is not triggered by default.

## Plotting Behaviour

- **Overlay mode (`mode="overlay"`)** plots every series on one Matplotlib figure. Individual series plots are also produced unless `no_individual=True`.
- **Individual mode (`mode="individual"`)** skips the combined plot and writes one PNG per series. The `html` flag is ignored in this mode because HTML output is only generated when an overlay figure exists.

Series naming follows the sanitised `title`/`name` parameter; individual plots append the series identifier derived from the column header.

## Output Artifacts

- Matplotlib renders PNG files by default. Additional formats can be supplied through the builder pipeline, but the public API currently emits PNG.
- When `html=True` (and overlay plots are enabled), a Plotly figure is produced and saved as `{base}.html` inside `output_dir`.
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
- Provide `legend_info` with newline placeholders (`\n`) to render supplemental text near the legend (Matplotlib) or as a Plotly annotation.
- `title` sets the overlay title; individual plots append ` - {series}`. If omitted in `csv2graph()`, the CSV stem becomes the title. `plot_from_dataframe()` also accepts `name` to override the base filename independently of the display title.

## API Reference

::: rdetoolkit.graph.api.csv2graph.csv2graph

---

::: rdetoolkit.graph.api.csv2graph.plot_from_dataframe

---

## Usage Examples

### Basic CSV conversion

```python title="basic_csv2graph.py"
from rdetoolkit.graph.api import csv2graph

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
from rdetoolkit.graph.api import csv2graph

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
from rdetoolkit.graph.api import csv2graph

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
    html=True,  # saves battery.html alongside PNG in output_dir
)
```

### Parsing alternate CSV layouts

```python title="transpose_format.py"
from rdetoolkit.graph.api import csv2graph

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
from rdetoolkit.graph.api import csv2graph

csv2graph(
    "series.csv",
    output_dir="other_images",
    main_image_dir="main_image",  # overlay PNG saved here
    html=True,
    grid=True,
)
```

### Plotting from a DataFrame

```python title="dataframe_plotting.py"
import pandas as pd
from rdetoolkit.graph.api import plot_from_dataframe

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
- `PlotConfigError` if dual-axis mode is ever surfaced; the strategy currently raises because the feature is disabled.

Ensure output directories exist or are creatable and that Plotly is installed when HTML output is desired.
