from pathlib import Path

from rdetoolkit.graph import csv2graph

if __name__ == "__main__":
    csv2graph(
        csv_path=Path("sample10/data.csv"),
        xlim=(15, 30),  # --xlim 15 30
        ylim=(180, 240),  # --ylim 180 240
        no_individual=True,
    )
