from pathlib import Path

from rdetoolkit.graph import csv2graph

if __name__ == "__main__":
    # invert_x
    csv2graph(
        csv_path=Path("sample3/data.csv"),
        invert_x=True,  # --invert-x
        no_individual=True,  # --no-individual
        # output_dir=Path("plots"),  # 必要なら出力先も指定できます
    )

    # invert_y
    csv2graph(
        csv_path=Path("sample3/data.csv"),
        invert_y=True,  # --invert-x
        no_individual=True,  # --no-individual
        # output_dir=Path("plots"),  # 必要なら出力先も指定できます
    )
