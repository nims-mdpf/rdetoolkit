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
