from pathlib import Path

from rdetoolkit.graph import csv2graph

if __name__ == "__main__":
    csv2graph(
        csv_path=Path("sample11/data.csv"),
        main_image_dir=Path("sample11/main_image"),  # --main-image-dir
        output_dir=Path("sample11/other_image"),  # --output-dir
    )
