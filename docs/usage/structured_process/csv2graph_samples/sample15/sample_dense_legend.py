# sample_dense_legend.py
# Generate one PNG per dense-legend (32 series) case. Run make_data.py first.
from pathlib import Path
from typing import Any

from rdetoolkit.graph import csv2graph

BASE = Path(__file__).parent

CASES: list[tuple[str, dict[str, Any]]] = [
    # (title / output name, csv2graph options)
    (
        "auto_32_outside_bottom_default",
        {"legend_policy": "auto", "legend_outside_threshold": 8, "max_legend_items": 40},
    ),
    (
        "auto_32_outside_bottom_ncol8",
        {"legend_policy": "auto", "legend_outside_threshold": 8, "max_legend_items": 40, "legend_ncol": 8},
    ),
    (
        "auto_32_outside_right",
        {
            "legend_policy": "auto",
            "legend_outside_threshold": 8,
            "legend_bottom_threshold": None,
            "max_legend_items": 40,
        },
    ),
    (
        "auto_32_inside_boundary_threshold_32",
        {
            "legend_policy": "auto",
            "legend_outside_threshold": 32,
            "legend_bottom_threshold": None,
            "max_legend_items": 40,
        },
    ),
    (
        "auto_32_outside_right_boundary_threshold_31",
        {
            "legend_policy": "auto",
            "legend_outside_threshold": 31,
            "legend_bottom_threshold": None,
            "max_legend_items": 40,
        },
    ),
    (
        "auto_32_bottom_boundary_threshold_32",
        {
            "legend_policy": "auto",
            "legend_outside_threshold": 8,
            "legend_bottom_threshold": 32,
            "max_legend_items": 40,
        },
    ),
    (
        "auto_32_right_boundary_bottom_threshold_33",
        {
            "legend_policy": "auto",
            "legend_outside_threshold": 8,
            "legend_bottom_threshold": 33,
            "max_legend_items": 40,
        },
    ),
    (
        "outside_right_32",
        {"legend_policy": "outside_right", "max_legend_items": 40},
    ),
    (
        "outside_bottom_32_ncol8",
        {"legend_policy": "outside_bottom", "legend_ncol": 8, "max_legend_items": 40},
    ),
    (
        "outside_bottom_32_ncol4",
        {"legend_policy": "outside_bottom", "legend_ncol": 4, "max_legend_items": 40},
    ),
    (
        "hide_32",
        {"legend_policy": "hide", "max_legend_items": 40},
    ),
    (
        "auto_32_hide_over_max_30",
        {"legend_policy": "auto", "legend_outside_threshold": 8, "max_legend_items": 30},
    ),
]

if __name__ == "__main__":
    for case_name, options in CASES:
        csv2graph(
            csv_path=BASE / "data.csv",
            output_dir=BASE,
            mode="overlay",
            x_col="x",
            no_individual=True,
            grid=True,
            title=case_name,
            **options,
        )
        print(f"OK: {case_name}.png")
