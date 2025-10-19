# csv2graph User Manual

## Overview

`csv2graph` is a Python module that automatically generates static graph images (PNG) and interactive HTML graphs (Plotly) from CSV files or Pandas DataFrames. It supports visualization of experimental data such as battery cycle data, X-ray Diffraction (XRD), and X-ray Photoelectron Spectroscopy (XPS).

## Key Features

- **Multiple CSV Format Support**: Standard CSV, transposed CSV, and headerless CSV
- **Flexible Plot Modes**: Overlay plots and individual plots
- **Direction Feature**: Visualize state changes like Charge/Discharge/Rest with color coding
- **Display Controls**: Grid display, axis inversion, axis range specification, logarithmic scale
- **Automatic Header Humanization**: Automatically converts snake_case headers to Title Case
- **Legend Control**: Legend item limit, legend position, additional information display
- **Output Formats**: PNG images (default), interactive HTML (optional)

## CSV Format Support

### standard (Standard CSV)

Standard CSV format with a header row. This is the default format.

```csv
X,Y1,Y2
1,10,20
2,15,25
3,20,30
```

### transpose (Transposed CSV)

Reads row-oriented CSV data with transposition.

```csv
X,1,2,3
Y1,10,15,20
Y2,20,25,30
```

### noheader (Headerless CSV)

CSV file without a header row. Columns are automatically named as `Column_0`, `Column_1`, etc.

```csv
1,10,20
2,15,25
3,20,30
```

## Plot Modes

### overlay (Overlay Plot)

Overlays all series on a single graph. This is the default mode.

- **Representative Image**: Generates an image with all series combined
- **Individual Images**: Also generates individual images for each series (when `no_individual=False`)

### individual (Individual Plot)

Generates each series as a separate graph. The overlay plot is skipped.

## Direction Feature

The Direction feature allows you to visualize state changes like Charge/Discharge/Rest with different colors.

### Specifying Direction Column

```python
csv2graph(
    "battery_data.csv",
    direction_cols="direction",  # Specify direction column
)
```

### Direction Filtering

You can display only specific direction values.

```python
csv2graph(
    "battery_data.csv",
    direction_cols="direction",
    direction_filter=["Charge", "Discharge"],  # Display only Charge and Discharge
)
```

### Customizing Direction Colors

You can specify colors for each direction value.

```python
csv2graph(
    "battery_data.csv",
    direction_cols="direction",
    direction_colors={
        "Charge": "#FF6B6B",
        "Discharge": "#4ECDC4",
        "Rest": "#95E1D3",
    }
)
```

## Display Control Options

### Grid Display

```python
csv2graph("data.csv", grid=True)
```

### Axis Inversion

You can invert the X-axis or Y-axis. Useful for XPS spectra.

```python
csv2graph(
    "xps_data.csv",
    invert_x=True,  # Invert X-axis
    invert_y=False,
)
```

### Axis Range Specification

You can specify the range of axes to display.

```python
csv2graph(
    "data.csv",
    xlim=(0, 100),    # X-axis range: 0-100
    ylim=(0, 50),     # Y-axis range: 0-50
)
```

### Logarithmic Scale

You can display the X-axis or Y-axis in logarithmic scale.

```python
csv2graph(
    "data.csv",
    logx=False,  # X-axis: Linear scale
    logy=True,   # Y-axis: Logarithmic scale
)
```

## Automatic Header Conversion

When CSV headers are in snake_case format, they are automatically converted to Title Case in axis labels and legends.

| Original Header | Converted |
|----------|--------|
| `battery_voltage` | `Battery Voltage` |
| `current_density` | `Current Density` |
| `cycle_number` | `Cycle Number` |
| `discharge_capacity` | `Discharge Capacity` |

Unit notation is also preserved:
- `battery_voltage (V)` → `Battery Voltage (V)`

## Column Specification

### Specifying X and Y Columns

Columns can be specified by integer index, column name, or a list of either.

```python
# Specify by index
csv2graph("data.csv", x_col=0, y_cols=[1, 2, 3])

# Specify by column name
csv2graph("data.csv", x_col="time", y_cols=["voltage", "current"])

# Mixed specification is also possible
csv2graph("data.csv", x_col=0, y_cols=["voltage", 2])
```

### Default Behavior

- `x_col=None`: The first column is used for the X-axis
- `y_cols=None`: All columns except the X column are used for the Y-axis

## Output Control

### Output Directory

```python
csv2graph(
    "data.csv",
    output_dir="plots",           # Base output directory
    main_image_dir="main_plots",  # Directory for overlay plots
)
```

- `output_dir`: Destination for individual plots and HTML output
- `main_image_dir`: Destination for overlay plots (PNG) (only when specified)

### Skipping Individual Plots

To generate only the overlay plot:

```python
csv2graph("data.csv", no_individual=True)
```

### HTML Output

Generates interactive Plotly graphs.

```python
csv2graph("data.csv", html=True)
```

**Note**: The Plotly library must be installed.

### Legend Control

```python
csv2graph(
    "data.csv",
    legend_loc="upper right",     # Legend position
    legend_info="Cell: 18650\n25C",  # Additional information
    max_legend_items=10,           # Maximum number of items
)
```

When the number of legend items exceeds `max_legend_items`, the legend is automatically hidden.

## Python Examples

### Basic CSV Conversion

```python
from rdetoolkit.graph.api import csv2graph

# Simplest usage
csv2graph("data.csv")

# Specify output directory
csv2graph(
    "experiment.csv",
    output_dir="plots",
    logy=True,
    title="Experiment Summary",
)
```

### Column Selection and Individual Plot Generation

```python
from rdetoolkit.graph.api import csv2graph

# Generate both overlay and individual plots
csv2graph(
    "measurements.csv",
    output_dir="overlay_and_series",
    mode="overlay",
    x_col="time_s",
    y_cols=["voltage_v", "current_ma"],
    legend_loc="upper right",
    max_legend_items=5,
)

# Generate only individual plots
csv2graph(
    "multi_sensor.csv",
    output_dir="per_series",
    mode="individual",
    x_col=0,
    y_cols=[1, 2, 3, 4],
    grid=True,
)
```

### Using the Direction Feature

```python
from rdetoolkit.graph.api import csv2graph

# Visualize battery cycle data
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
    html=True,
)
```

### Processing Transposed CSV

```python
from rdetoolkit.graph.api import csv2graph

# Process transposed CSV
csv2graph(
    "transposed_data.csv",
    csv_format="transpose",
    output_dir="plots",
    mode="overlay",
)

# Process headerless CSV
csv2graph(
    "no_header_data.csv",
    csv_format="noheader",
    output_dir="plots",
)
```

### Controlling Output Directories

```python
from rdetoolkit.graph.api import csv2graph

# Save overlay and individual plots to separate directories
csv2graph(
    "series.csv",
    output_dir="other_images",      # For individual plots
    main_image_dir="main_image",    # For overlay plots
    html=True,
    grid=True,
)
```

### Plotting from DataFrame

```python
import pandas as pd
from rdetoolkit.graph.api import plot_from_dataframe

# Load DataFrame
frame = pd.read_csv("processed.csv")
frame["normalized"] = frame["value"] / frame["value"].max()

# Get Figure objects
artifacts = plot_from_dataframe(
    df=frame,
    output_dir="analysis",
    name="processed",
    title="Processed Output",
    x_col="time",
    y_cols=["value", "normalized"],
    return_fig=True,
)

# Custom save processing
for artifact in artifacts:
    artifact.figure.savefig(f"custom_{artifact.filename}", dpi=300)
```

### Visualizing XPS Spectra

```python
from rdetoolkit.graph.api import csv2graph

# Display XPS spectrum with inverted X-axis
csv2graph(
    "xps_spectrum.csv",
    output_dir="xps_plots",
    invert_x=True,
    xlim=(1200, 0),
    x_label="Binding Energy (eV)",
    y_label="Intensity (a.u.)",
    grid=True,
)
```

### Limiting Legend Items

```python
from rdetoolkit.graph.api import csv2graph

# Limit legend for data with many series
csv2graph(
    "multi_series_data.csv",
    output_dir="plots",
    max_legend_items=10,  # Hide legend if exceeds 10 items
    title="Multi-Series Analysis",
)
```

## CLI Examples

### Basic Usage

```bash
# Simplest execution
python -m rdetoolkit.graph.api.csv2graph data.csv

# Specify output directory
python -m rdetoolkit.graph.api.csv2graph experiment.csv --output_dir plots --logy --title "Experiment Summary"
```

### Column Selection and Individual Plots

```bash
# Generate both overlay and individual plots
python -m rdetoolkit.graph.api.csv2graph measurements.csv \
    --output_dir overlay_and_series \
    --mode overlay \
    --x_col time_s \
    --y_cols voltage_v current_ma \
    --legend_loc "upper right" \
    --max_legend_items 5

# Generate only individual plots
python -m rdetoolkit.graph.api.csv2graph multi_sensor.csv \
    --output_dir per_series \
    --mode individual \
    --x_col 0 \
    --y_cols 1 2 3 4 \
    --grid
```

### Using the Direction Feature

```bash
# Visualize battery cycle data
python -m rdetoolkit.graph.api.csv2graph battery_cycles.csv \
    --output_dir battery \
    --direction_cols direction \
    --direction_filter Charge Discharge \
    --legend_info "Cell: 18650\n25C" \
    --html

# Direction color customization (supported only in Python scripts)
```

### Processing Transposed CSV

```bash
# Process transposed CSV
python -m rdetoolkit.graph.api.csv2graph transposed_data.csv \
    --csv_format transpose \
    --output_dir plots \
    --mode overlay

# Process headerless CSV
python -m rdetoolkit.graph.api.csv2graph no_header_data.csv \
    --csv_format noheader \
    --output_dir plots
```

### Controlling Output Directories

```bash
# Save overlay and individual plots to separate directories
python -m rdetoolkit.graph.api.csv2graph series.csv \
    --output_dir other_images \
    --main_image_dir main_image \
    --html \
    --grid
```

### Visualizing XPS Spectra

```bash
# Display XPS spectrum with inverted X-axis
python -m rdetoolkit.graph.api.csv2graph xps_spectrum.csv \
    --output_dir xps_plots \
    --invert_x \
    --xlim 1200 0 \
    --grid
```

### Display Control Options

```bash
# Logarithmic scale and grid display
python -m rdetoolkit.graph.api.csv2graph data.csv \
    --output_dir plots \
    --logy \
    --grid

# Axis range specification
python -m rdetoolkit.graph.api.csv2graph data.csv \
    --output_dir plots \
    --xlim 0 100 \
    --ylim 0 50

# Axis inversion
python -m rdetoolkit.graph.api.csv2graph data.csv \
    --output_dir plots \
    --invert_x \
    --invert_y
```

### Legend Control

```bash
# Limit legend items
python -m rdetoolkit.graph.api.csv2graph multi_series_data.csv \
    --output_dir plots \
    --max_legend_items 10 \
    --legend_loc "upper right"

# Skip individual plots
python -m rdetoolkit.graph.api.csv2graph data.csv \
    --output_dir plots \
    --no_individual
```

## Output Specifications

### File Naming Conventions

#### overlay mode

- **Overlay Plot**: `{title}.png` or `{name}.png`
- **Individual Plots**: `{title}_{series}.png` or `{name}_{series}.png`
- **HTML Output**: `{title}.html` or `{name}.html` (when `html=True`)

#### individual mode

- **Individual Plots**: `{title}_{series}.png` or `{name}_{series}.png`

### Directory Structure

```
output_dir/
├── plot.png              # Overlay plot (overlay mode)
├── plot_series1.png      # Individual plot
├── plot_series2.png      # Individual plot
└── plot.html             # HTML output (when html=True)

main_image_dir/           # Only when main_image_dir is specified
└── plot.png              # Overlay plot (PNG)
```

### Output Formats

- **PNG Images**: Static images with vector quality by Matplotlib
- **HTML**: Interactive graphs by Plotly (Plotly installation required)

### Security

- Built-in validation to prevent path traversal attacks
- File names are automatically sanitized
- Directories are automatically created as needed

## Error Handling

### Common Errors

- **`ColumnNotFoundError`**: Specified column does not exist
- **`ValueError`**: Inconsistent X and Y column configuration
- **`ImportError`**: `html=True` but Plotly is not installed
- **`PlotConfigError`**: dual_axis mode is used (currently disabled)

### Recommendations

- Ensure the output directory exists or can be created
- Install Plotly for HTML output (`pip install plotly`)
