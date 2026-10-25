# sample_legend_policy.py
# Generate one PNG per legend_policy case. Run make_data.py first.
from pathlib import Path
from typing import Any

from rdetoolkit.graph import csv2graph

BASE = Path(__file__).parent

CASES: list[tuple[str, Path, dict[str, Any]]] = [
    # (title / output name, csv, csv2graph options)
    (
        "legacy_many",
        BASE / "data.csv",
        {"legend_policy": "legacy", "legend_loc": "upper right", "max_legend_items": 30},
    ),
    (
        "auto_inside_few",
        BASE / "data_few.csv",
        {"legend_policy": "auto", "legend_outside_threshold": 8, "max_legend_items": 20},
    ),
    (
        "auto_outside_right_many",
        BASE / "data.csv",
        {"legend_policy": "auto", "legend_outside_threshold": 8, "max_legend_items": 30},
    ),
    (
        "outside_right_many",
        BASE / "data.csv",
        {"legend_policy": "outside_right", "max_legend_items": 30},
    ),
    (
        "outside_bottom_many",
        BASE / "data.csv",
        {"legend_policy": "outside_bottom", "legend_ncol": 4, "max_legend_items": 30},
    ),
    (
        "hide_many",
        BASE / "data.csv",
        {"legend_policy": "hide", "max_legend_items": 30},
    ),
    (
        "auto_hide_over_max",
        BASE / "data.csv",
        {"legend_policy": "auto", "legend_outside_threshold": 8, "max_legend_items": 5},
    ),
]

if __name__ == "__main__":
    for case_name, csv_path, options in CASES:
        csv2graph(
            csv_path=csv_path,
            output_dir=BASE,
            mode="overlay",
            x_col="x",
            no_individual=True,
            grid=True,
            title=case_name,
            **options,
        )
        print(f"OK: {case_name}.png")
