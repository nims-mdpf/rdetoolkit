from pathlib import Path

from rdetoolkit.graph.api import csv2graph

if __name__ == "__main__":
    csv2graph(
        csv_path=Path("sample2/data.csv"),
        no_individual=True,  # --no-individual
        # output_dir=Path("plots"),  # 必要なら出力先も指定できます
    )
