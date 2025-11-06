from pathlib import Path

from rdetoolkit.graph import csv2graph

if __name__ == "__main__":
    csv2graph(
        csv_path=Path("sample9/data.csv"),
        grid=True,  # --grid
        no_individual=True,  # --no-individual
    )
