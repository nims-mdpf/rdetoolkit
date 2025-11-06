from pathlib import Path
from rdetoolkit.graph import csv2graph

if __name__ == "__main__":
    csv2graph(
        csv_path=Path("sample8/data.csv"),
        title="XRD",
        legend_info="Sample: LiCoO2\nScan rate: 0.5°/min",
        no_individual=True,
    )
