from pathlib import Path

from rdetoolkit.graph import csv2graph

if __name__ == "__main__":
    csv2graph(
        csv_path=Path("sample1/data.csv"),
        html=True,  # --html
        output_dir=Path("plots"),
        no_individual=True,
    )
