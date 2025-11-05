from pathlib import Path

from rdetoolkit.graph import csv2graph

if __name__ == "__main__":
    csv2graph(
        csv_path=Path("sample1/data.csv"),
        no_individual=True,  # --no-individual
        # output_dir=Path("plots"),  # 必要なら出力先も指定できます
    )
