# csv2graph Sample Gallery

This gallery lets you explore the main `csv2graph` options with real sample data. Reproduce the sample directory layout shown in each section and you can run the commands exactly as written.

Every sample's CSV file is available for direct download on this page. Pre-rendered images and helper scripts are included when they add context.

## Sample 1: Basic Overlay Only

This minimal example plots XRD intensity data and uses `--no-individual` so that only the overlay image is produced (pass `--individual` to force per-series images even on single-series CSVs).

### Data Overview

The dataset emulates XRD intensity measurements.

```bash
2theta (deg),Intensity (counts)
10.0,204.9671
10.02,198.6174
10.04,206.4769
10.06,215.2303
10.08,197.6585
10.1,197.6586
10.12,215.7921
10.14,207.6743
...
```

- [data.csv](./csv2graph_samples/sample1/data.csv)

=== "Generated Plot"
    ![Overlay: xrd_sample](./csv2graph_samples/sample1/data.png){ width="700" }

### Directory Layout

```bash
sample1/
|-- data.csv
|-- data.png
`-- sample.py
```

### How to Run

Switch between the Python script and CLI examples using the tabs below.

=== "Python"
    ```python
    # sample.py
    from pathlib import Path

    from rdetoolkit.graph import csv2graph

    if __name__ == "__main__":
        csv2graph(
            csv_path=Path("sample1/data.csv"),
            no_individual=True,  # --no-individual
        )
    ```

=== "CLI"
  ```bash
  rdetoolkit csv2graph 'sample1/data.csv' --no-individual
  ```

### Option Details

- `no_individual=True`, `--no-individual`: Skip individual plots and emit only the overlay image.

## Sample 2: Log-Scale Y Axis

This sample uses synthetic diode I-V data to show how `--logy` plots the Y axis on a logarithmic scale while setting a custom title.

### Data Overview

The dataset approximates the I-V characteristics of a diode.

```bash
Voltage (V),Current (A)
0.0,9.999999999999999e-19
0.0008008008008008008,1.735937164947776e-14
0.0016016016016016017,3.5020091083020285e-14
0.0024024024024024027,5.298738950880688e-14
0.0032032032032032033,7.095468793459339e-14
0.004004004004004004,8.891763700246374e-14
0.0048048048048048045,1.0684102478227538e-13
0.005605605605605606,1.2485910126202743e-13
...
```

- [data.csv](./csv2graph_samples/sample2/data.csv)

=== "Generated Plot"
![Overlay: I–V_Curve_of_a_Diode_(log scale)](./csv2graph_samples/sample2/I–V_Curve_of_a_Diode_log_scale.png){ width="700" }

### Directory Layout

```bash
sample2/
|-- data.csv
`-- sample_log_scale.py
```

### How to Run

Switch between the Python script and CLI examples using the tabs below.

=== "Python"
    ```python
    # sample_log_scale.py
    from pathlib import Path

    from rdetoolkit.graph import csv2graph

    if __name__ == "__main__":
        csv2graph(
            csv_path=Path("sample2/data.csv"),
            logy=True,
            title="I-V_Curve_of_a_Diode_(log scale)",
        )
    ```

=== "CLI"
    ```bash
    rdetoolkit csv2graph sample2/data.csv \
      --logy \
      --no-individual \
      --title "I-V_Curve_of_a_Diode_(log scale)"
    ```

### Option Details

- `no_individual=True`, `--no-individual`: Skip individual plots and emit only the overlay image.
- `--logy` / `logy=True`: Plot the Y axis on a logarithmic scale.

> The sample dataset does not cover logarithmic X axes, but you can enable it with `--logx` / `logx=True`.

## Sample 3: Axis Inversion (X/Y)

This example demonstrates `--invert-x` and `--invert-y` using XRD data.

### Data Overview

The dataset emulates XRD intensity measurements.

```bash
2theta (deg),Intensity (counts)
10.0,204.9671
10.02,198.6174
10.04,206.4769
10.06,215.2303
10.08,197.6585
10.1,197.6586
10.12,215.7921
10.14,207.6743
...
```

- [data.csv](./csv2graph_samples/sample3/data.csv)

=== "Generated Plot"
    ![Overlay](./csv2graph_samples/sample3/data.png){ width="700" }

### Directory Layout

Before running the sample, the directory contains:

```bash
sample3/
|-- data.csv
`-- sample_invert.py
```

### Inverting the X Axis

Switch between the Python script and CLI examples using the tabs below.

=== "Python"
    ```python
    # sample_invert.py
    from pathlib import Path

    from rdetoolkit.graph import csv2graph

    if __name__ == "__main__":
        # invert_x
        csv2graph(
            csv_path=Path("sample3/data.csv"),
            invert_x=True,  # --invert-x
            no_individual=True,  # --no-individual
        )
    ```

=== "CLI"
    ```bash
    rdetoolkit csv2graph 'sample3/data.csv' --invert-x --no-individual
    ```

#### Inverting the Y Axis

=== "Python"
    ```python
    # sample_invert.py
    from pathlib import Path
    from rdetoolkit.graph import csv2graph

    if __name__ == "__main__":
        # invert_y
        csv2graph(
            csv_path=Path("sample3/data.csv"),
            invert_y=True,  # --invert-y
            no_individual=True,
        )
    ```

=== "CLI"
    ```bash
    rdetoolkit csv2graph 'sample3/data.csv' --invert-y --no-individual
    ```

### Option Details

- `invert_x=True`, `--invert-x`: Flip the overlay horizontally.
- `invert_y=True`, `--invert-y`: Flip the overlay vertically.
- `no_individual=True`: Skip individual plots and emit only the overlay image.

## Sample 4: Overlaying Multiple X/Y Pairs

This sample plots three joint torque signals by pairing multiple X and Y columns and exports both the overlay and per-series plots.

### Data Overview

Synthetic three-joint (J1-J3) angle/velocity/torque data generated from near-monotonic angles with a linear model plus small noise.

```bash
Phase-U:volt(V),Phase-U:curr(A),Phase-U:power(kW),Phase-V:volt(V),Phase-V:curr(A),Phase-V:power(kW),Phase-W:volt(V),Phase-W:curr(A),Phase-W:power(kW)
230.1,10.02,2.126,231.0,10.11,2.116,229.7,10.15,2.13
230.1,9.94,2.109,231.1,10.26,2.138,229.8,10.06,2.118
230.2,9.83,2.077,231.0,10.09,2.096,229.3,10.05,2.075
230.4,10.14,2.161,231.0,10.27,2.135,229.4,10.27,2.176
...
```

- [data.csv](./csv2graph_samples/sample4/data.csv)

=== "Generated Plot"
    ![Overlay: 3 Joint Torque vs Angle](./csv2graph_samples/sample4/Angle-Dependent-Torque.png){ width="700" }

=== "Individual Plot 1"
    ![J1 Torque vs Angle](./csv2graph_samples/sample4/Angle-Dependent-Torque_j1.png){ width="700" }

=== "Individual Plot 2"
    ![J2 Torque vs Angle](./csv2graph_samples/sample4/Angle-Dependent-Torque_j2.png){ width="700" }

=== "Individual Plot 3"
    ![J3 Torque vs Angle](./csv2graph_samples/sample4/Angle-Dependent-Torque_j3.png){ width="700" }

### Directory Layout

Before running the sample, the directory contains:

```bash
sample4/
|-- data.csv
`-- sample_pair_plot.py
```

### How to Run

Switch between the Python script and CLI examples using the tabs below.

=== "Python"
    ```python
    # sample_pair_plot.py
    from pathlib import Path

    from rdetoolkit.graph import csv2graph

    if __name__ == "__main__":
        csv2graph(
            csv_path=Path("sample4/data.csv"),
            mode="overlay",
            x_col=[1, 4, 7],
            y_cols=[0, 3, 6],
            title="Angle-Dependent-Torque",
        )
    ```

=== "CLI"
    ```bash
    rdetoolkit csv2graph sample4/data.csv \
        --mode overlay \
        --x-col 1 --x-col 4 --x-col 7 \
        --y-cols 0 --y-cols 3 --y-cols 6 \
        --title "Angle-Dependent-Torque"
    ```

### Option Details

- `--mode overlay`: Overlay all series in a single figure (equivalent to the legacy x1y1x2y2 mode).
- `--x-col 1 --x-col 4 --x-col 7`: Specify three X columns (0-based indices 1, 4, 7). Each pairs with the corresponding Y column below.
- `--y-cols 0 --y-cols 3 --y-cols 6`: Specify the matching Y columns (indices 0, 3, 6) to form three series.
- `--title "Angle-Dependent Torque"`: Set the plot title and filename stem.

## Sample 5: One X Column with Many Y Series

This Raman spectroscopy example pairs one X column with multiple Y series and customises the plot title.

### Data Overview

Dummy Raman spectroscopy data. The horizontal axis is `Raman Shift (cm^-1)` and the Y series represent `Intensity (counts)` at positions `Pos0`-`Pos10`.

```bash
Raman Shift (cm^-1),Pos0: Intensity (counts),Pos1: Intensity (counts),Pos2: Intensity (counts),Pos3: Intensity (counts),Pos4: Intensity (counts),Pos5: Intensity (counts),Pos6: Intensity (counts),Pos7: Intensity (counts),Pos8: Intensity (counts),Pos9: Intensity (counts),Average: Intensity (counts)
100.0,117.0,124.0,134.0,135.0,111.0,126.0,132.0,116.0,126.0,114.0,124.0
101.551,117.0,126.0,106.0,138.0,110.0,127.0,134.0,146.0,134.0,116.0,125.0
103.102,126.0,139.0,110.0,150.0,119.0,134.0,128.0,128.0,116.0,141.0,129.0
104.652,100.0,108.0,90.0,119.0,118.0,145.0,106.0,117.0,144.0,117.0,116.0
106.203,102.0,87.0,114.0,125.0,117.0,108.0,112.0,117.0,133.0,136.0,115.0
...
```

- [data.csv](./csv2graph_samples/sample5/data.csv)

=== "Overlay Plot"
    ![Overlay: raman](./csv2graph_samples/sample5/data.png){ width="700" }

### Directory Layout

Before running the sample, the directory contains:

```bash
sample5/
|-- data.csv
`-- sample_custom_title.py
```

### How to Run

Switch between the Python script and CLI examples using the tabs below.

=== "Python"
    ```python
    # sample_custom_title.py
    from pathlib import Path

    from rdetoolkit.graph import csv2graph

    if __name__ == "__main__":
        csv2graph(
            csv_path=Path("sample5/data.csv"),
            mode="overlay",
            x_col=[1, 4, 7],
            y_cols=[0, 3, 6],
            title="Angle-Dependent-Torque",
        )
    ```

=== "CLI"
    ```bash
    rdetoolkit csv2graph sample5/data.csv \
      --x-col 0 \
      --y-cols 1 --y-cols 2 --y-cols 3 --y-cols 4 --y-cols 5 \
      --no-individual \
      --title "Angle-Dependent-Torque"
    ```

### Option Details

- `--x-col 0`: Use column 0 for the X axis. One declaration automatically pairs it with all specified Y columns.
- `--y-cols 1 ... 5`: Plot five Y series (columns 1-5).
- `--no-individual`: Output only the combined plot and skip individual PNGs.
- `--title`: Provide a custom plot title.

## Sample 6: Limiting Legend Entries

This Raman spectroscopy sample caps the number of legend items via `--max-legend-items`.

### Data Overview

Dummy Raman spectroscopy data with `Raman Shift (cm^-1)` on the X axis and `Intensity (counts)` for positions `Pos0`-`Pos10`.

```
Raman Shift (cm^-1),Pos0: Intensity (counts),Pos1: Intensity (counts),Pos2: Intensity (counts),Pos3: Intensity (counts),Pos4: Intensity (counts),Pos5: Intensity (counts),Pos6: Intensity (counts),Pos7: Intensity (counts),Pos8: Intensity (counts),Pos9: Intensity (counts),Average: Intensity (counts)
100.0,117.0,124.0,134.0,135.0,111.0,126.0,132.0,116.0,126.0,114.0,124.0
101.551,117.0,126.0,106.0,138.0,110.0,127.0,134.0,146.0,134.0,116.0,125.0
103.102,126.0,139.0,110.0,150.0,119.0,134.0,128.0,128.0,116.0,141.0,129.0
104.652,100.0,108.0,90.0,119.0,118.0,145.0,106.0,117.0,144.0,117.0,116.0
106.203,102.0,87.0,114.0,125.0,117.0,108.0,112.0,117.0,133.0,136.0,115.0
...
```

- [data.csv](./csv2graph_samples/sample6/data.csv)

=== "Generated Plot"
    ![Overlay: raman_max_legend_items](./csv2graph_samples/sample6/data.png){ width="700" }

### Directory Layout

Before running the sample, the directory contains:

```bash
sample6/
|-- data.csv
`-- sample_max_legend_items.py
```

### How to Run

Switch between the Python script and CLI examples using the tabs below.

=== "Python"
    ```python
    # sample_max_legend_items.py
    from pathlib import Path

    from rdetoolkit.graph import csv2graph

    if __name__ == "__main__":
        csv2graph(
            "sample6/data.csv",
            x_col=0,
            y_cols=[1, 2, 3, 4, 5],
            no_individual=True,
            max_legend_items=3,
        )
    ```

=== "CLI"
    ```bash
    rdetoolkit csv2graph sample6/data.csv \
      --x-col 0 \
      --y-cols 1 --y-cols 2 --y-cols 3 --y-cols 4 --y-cols 5 \
      --no-individual \
      --max-legend-items 3
    ```

### Option Details

- `--x-col 0`: Use column 0 for the X axis so every declared Y column automatically pairs with it.
- `--y-cols ...`: Enumerate the five Y series (columns 1-5).
- `--no-individual`: Produce only the combined overlay PNG and skip per-series PNGs.
- `--max-legend-items 3`: Show at most three legend entries; remaining items are hidden to keep the plot readable.

## Sample 7: Multi-Channel Charge/Discharge Overlay

This advanced example colours series by state labels spread across multiple columns while redirecting the output directory.

> No pre-rendered images are bundled with this sample. Run the code to generate outputs.

### Data Overview

The dataset mimics multi-channel charge/discharge measurements.

```
state_ch1,time_ch1[s],step_index_ch1,current_ch1[A],capacity_ch1[mAh],voltage_ch1[V],state_ch2,time_ch2[s],step_index_ch2,current_ch2[A],capacity_ch2[mAh],voltage_ch2[V],state_ch3,time_ch3[s],step_index_ch3,current_ch3[A],capacity_ch3[mAh],voltage_ch3[V],state_ch4,time_ch4[s],step_index_ch4,current_ch4[A],capacity_ch4[mAh],voltage_ch4[V],state_ch5,time_ch5[s],step_index_ch5,current_ch5[A],capacity_ch5[mAh],voltage_ch5[V],state_ch6,time_ch6[s],step_index_ch6,current_ch6[A],capacity_ch6[mAh],voltage_ch6[V]
Charge,0.0,1,1.0248357076505616,0.0,3.1464269673816196,Discharge,0.0,1,-0.9246489863932321,0.0,3.26398992423171,Discharge,0.0,1,-0.9703987550711959,0.0,3.301646178292083,Discharge,0.0,1,-0.8373920481516945,0.0,3.2405780651132403,Discharge,0.0,1,-1.0452295606856536,0.0,3.289520156004168,Discharge,0.0,1,-1.1267131011336096,0.0,3.2782242976855556
Charge,2.0,1,0.9930867849414408,0.5693531709169787,3.1401720080365,Discharge,2.0,1,-0.9528697682537017,0.0,3.2612743372332664,Discharge,2.0,1,-1.079386898465995,0.0,3.3142719992060634,Discharge,2.0,1,-0.9061484473317185,0.0,3.2529616227280664,Discharge,2.0,1,-0.9533585647953902,0.0,3.2768224979535368,Discharge,2.0,1,-1.0899924167596289,0.0,3.27788892249149
...
```

- [data.csv](./csv2graph_samples/sample7/data.csv)

### How to Run

Switch between the Python script and CLI examples using the tabs below.

=== "Python"
    ```python
    from pathlib import Path

    from rdetoolkit.graph import csv2graph

    if __name__ == "__main__":
        csv2graph(
            Path("sample7/data.csv"),
            x_col=[1, 7, 13, 19, 25, 31],
            y_cols=[5, 11, 17, 23, 29, 35],
            direction_cols=[0, 6, 12, 18, 24, 30],
            max_legend_items=5,
            title="Charge_Rest_Discharge",
            output_dir=Path("./custom_output"),
        )
    ```

=== "CLI"
    ```bash
    rdetoolkit csv2graph sample7/data.csv \
      --x-col 1 --x-col 7 --x-col 13 --x-col 19 --x-col 25 --x-col 31 \
      --y-cols 5 --y-cols 11 --y-cols 17 --y-cols 23 --y-cols 29 --y-cols 35 \
      --direction-cols 0 --direction-cols 6 --direction-cols 12 \
      --direction-cols 18 --direction-cols 24 --direction-cols 30 \
      --logx --logy --max-legend-items 5 \
      --title "Charge_Rest_Discharge" \
      --output-dir ./custom_output
    ```

### Option Details

- `--output-dir ./custom_output`: Store generated PNG/HTML outputs in a custom folder instead of alongside the CSV.
- `--title "Charge_Rest_Discharge"`: Set the plot title and filename stem (for example, `Charge_Rest_Discharge.png`).
- `--mode overlay`: Overlay all series in a single figure, pairing each X column with the corresponding Y column.
- `--x-col 1` `--x-col 7 ... 43`: Enumerate the X-axis columns (0-based). Here there are six series using columns 1, 7, 13, 19, 25, and 31.
- `--y-cols 5 --y-cols 11 ... 47`: List the matching Y columns (5, 11, 17, 23, 29, 35) in the same order as the X columns.
- `--direction-cols 0`, `--direction-cols 6 ... 42`: Provide the state/phase columns that control colouring or segmentation per series. Supply as many direction columns as Y series.
- `--max-legend-items 5`: Limit the legend to five entries so that additional series are hidden automatically.

## Sample 8: Supplementary Legend Information

This sample appends extra metadata near the legend via `--legend-info` for Raman spectroscopy data.

### Data Overview

Dummy Raman spectroscopy data with `Raman Shift (cm^-1)` on the X axis and `Intensity (counts)` for `Pos0`-`Pos10`.

```
Raman Shift (cm^-1),Pos0: Intensity (counts),Pos1: Intensity (counts),Pos2: Intensity (counts),Pos3: Intensity (counts),Pos4: Intensity (counts),Pos5: Intensity (counts),Pos6: Intensity (counts),Pos7: Intensity (counts),Pos8: Intensity (counts),Pos9: Intensity (counts),Average: Intensity (counts)
100.0,117.0,124.0,134.0,135.0,111.0,126.0,132.0,116.0,126.0,114.0,124.0
101.551,117.0,126.0,106.0,138.0,110.0,127.0,134.0,146.0,134.0,116.0,125.0
103.102,126.0,139.0,110.0,150.0,119.0,134.0,128.0,128.0,116.0,141.0,129.0
104.652,100.0,108.0,90.0,119.0,118.0,145.0,106.0,117.0,144.0,117.0,116.0
106.203,102.0,87.0,114.0,125.0,117.0,108.0,112.0,117.0,133.0,136.0,115.0
...
```

- [data.csv](./csv2graph_samples/sample8/data.csv)

=== "Generated Plot"
    ![Overlay: raman_max_legend_items](./csv2graph_samples/sample8/sample_legend_info.png){ width="700" }

### Directory Layout

Before running the sample, the directory contains:

```bash
sample8/
|-- data.csv
`-- sample_legend_info.py
```

### How to Run

=== "Python"
    ```python
    # sample_legend_info.py
    from pathlib import Path
    from rdetoolkit.graph import csv2graph

    if __name__ == "__main__":
        csv2graph(
            csv_path=Path("sample8/data.csv"),
            title="sample_legend_info",
            legend_info="Sample: Raman Map\nLaser: 532 nm",
            no_individual=True,
        )
    ```

=== "CLI"
    ```bash
    rdetoolkit csv2graph sample8/data.csv \
      --title "sample_legend_info" \
      --legend-info "Sample: Raman Map\nLaser: 532 nm" \
      --no-individual
    ```

### Option Details
- `legend_info`: Append arbitrary text near the legend (or in the upper right). Use `\n` to insert line breaks.
- `no_individual=True`: Generate only the overlay image and skip individual plots.

## Sample 9: Displaying Grid Lines

This XRD example enables grid lines with `--grid` to make peak locations easier to read.

### Data Overview

The dataset uses synthetic XRD intensity values.

```csv
2theta (deg),Intensity (counts)
10.0,204.9671
10.02,198.6174
...
```

- [data.csv](./csv2graph_samples/sample9/data.csv)

=== "Generated Plot"
    ![Overlay: raman_max_legend_items](./csv2graph_samples/sample9/data.png){ width="700" }

### Directory Layout

Before running the sample, the directory contains:

```bash
sample9/
|-- cmd.md
|-- data.csv
`-- sample_grid.py
```

### How to Run

=== "Python"
    ```python
    # sample_grid.py
    from pathlib import Path
    from rdetoolkit.graph import csv2graph

    if __name__ == "__main__":
        csv2graph(
            csv_path=Path("sample9/data.csv"),
            grid=True,                # --grid
            no_individual=True,
        )
    ```

=== "CLI"
    ```bash
    rdetoolkit csv2graph sample9/data.csv \
      --grid \
      --no-individual
    ```

### Option Details

- `grid=True`, `--grid`: Draw horizontal and vertical grid lines to improve readability.
- `no_individual=True`: Skip individual plots and generate only the overlay image.

## Sample 10: Narrowing the Display Range (xlim/ylim)

This sample zooms in on peak regions by combining `--xlim` and `--ylim` with XRD data.

### Data Overview

The dataset reuses XRD intensity values and shows how to restrict the visible range.

```csv
2theta (deg),Intensity (counts)
10.0,204.9671
10.02,198.6174
...
```

- [data.csv](./csv2graph_samples/sample10/data.csv)

=== "Generated Plot"
    ![Overlay: raman_max_legend_items](./csv2graph_samples/sample10/data.png){ width="700" }

### Directory Layout

Before running the sample, the directory contains:

```bash
sample10/
|-- cmd.md
|-- data.csv
`-- sample_lim.py
```

### How to Run

=== "Python"
    ```python
    # sample_lim.py
    from pathlib import Path
    from rdetoolkit.graph import csv2graph

    if __name__ == "__main__":
        csv2graph(
            csv_path=Path("sample10/data.csv"),
            xlim=(15, 30),     # --xlim 15 30
            ylim=(180, 240),   # --ylim 180 240
            no_individual=True,
        )
    ```

=== "CLI"
    ```bash
    rdetoolkit csv2graph sample10/data.csv \
      --xlim 15 30 \
      --ylim 180 240 \
      --no-individual
    ```

### Option Details

- `--xlim <min> <max>`, `xlim=(<min>, <max>)`: Restrict the X-axis range (same units as the CSV). The example displays only 2theta from 15 degrees to 30 degrees.
- `--ylim <min> <max>`, `ylim=(<min>, <max>)`: Restrict the Y-axis range (same units as the dataset). The example keeps intensities between 180 and 240 counts.
- `--no-individual`: Produce only the overlay image and skip individual plots.

Zooming the range helps inspect peaks in detail and hide noisy regions.

## Sample 11: Separating Overlay and Individual Outputs

This example saves the overlay image and individual series outputs in different directories via `--main-image-dir` and `--output-dir`.

### Data Overview

The dataset reuses synthetic XRD intensity data and demonstrates splitting output destinations.

```csv
2theta (deg),Intensity (counts)
10.0,204.9671
10.02,198.6174
...
```

- [data.csv](./csv2graph_samples/sample11/data.csv)

=== "Overlay Plot"
    ![Overlay: main](./csv2graph_samples/sample11/main_image/data.png){ width="700" }

=== "Individual Plot"
    ![Overlay: other](./csv2graph_samples/sample11/other_image/data_intensity_(counts).png){ width="700" }

### Directory Layout

```bash
$ ls -l sample11/
total 472
-rw-r--r--@ 1 user  staff  44132 10 26 23:33 data.csv
-rw-r--r--@ 1 user  staff    290 10 27 12:46 switch_output_directory.py
```

### How to Run

=== "Python"
    ```python
    # sample11/switch_output_directory.py
    from pathlib import Path
    from rdetoolkit.graph import csv2graph

    if __name__ == "__main__":
        csv2graph(
            csv_path=Path("sample11/data.csv"),
            main_image_dir=Path("sample11/main_image"),   # --main-image-dir
            output_dir=Path("sample11/other_image"),      # --output-dir
        )
    ```

=== "CLI"
    ```bash
    rdetoolkit csv2graph sample11/data.csv \
      --main-image-dir sample11/main_image \
      --output-dir sample11/other_image
    ```

### Output Structure After Running

```bash
sample11/
|-- data.csv
|-- main_image # directory for the overlay image
|   `-- data.png
|-- other_image # directory for individual plots
|   `-- data_intensity_(counts).png
`-- switch_output_directory.py
```

### Option Details

- `--main-image-dir`: Choose where the overlay image is saved. By default it matches `--output-dir`.
- `--output-dir`: Choose where individual PNG and HTML outputs are saved. Without this option, outputs live next to the input CSV.

Separating the directories keeps report-ready overlays and detailed analysis plots organised.

## Sample 12: Generating Plotly HTML Outputs

This sample enables interactive Plotly HTML output with `--html`.

### Data Overview

Synthetic XRD intensity data used to demonstrate the Plotly export option.

```csv
2theta (deg),Intensity (counts)
10.0,204.9671
10.02,198.6174
...
```

- [data.csv](./csv2graph_samples/sample12/data.csv)

=== "Individual Plot"
    ![Overlay: png](./csv2graph_samples/sample12/data.png){ width="700" }

### Directory Layout

```bash
sample12/
|-- data.csv
`-- output_html.py
```

### How to Run

=== "Python"
    ```python
    from pathlib import Path
    from rdetoolkit.graph import csv2graph

    if __name__ == "__main__":
        csv2graph(
            csv_path=Path("sample12/data.csv"),
            html=True,                 # --html
            output_dir=Path("plots"),
            no_individual=True,
        )
    ```

=== "CLI"
    ```bash
    rdetoolkit csv2graph sample12/data.csv \
      --html \
      --no-individual
    ```

### Directory After Execution

```bash
sample12/
|-- data.csv
|-- data.html # generated
|-- data.png # generated
`-- output_html.py
```

### Option Details

- `--html`: Produce interactive Plotly HTML files (`*.html`). Open them in a browser to zoom and inspect traces.
- `--no-individual`: Skip per-series plots and keep only the combined output (the HTML goes to the same directory).

Plotly output requires the Plotly library. If it is missing, you will see the following error message:

```bash
ImportError: Plotly is required for HTML output but is not installed. Install it with: pip install plotly
Unexpected error: Plotly is required for HTML output but is not installed. Install it with: pip install plotly
Aborted!
```
