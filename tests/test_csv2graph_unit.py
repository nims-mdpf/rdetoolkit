"""Focused unit tests for the public csv2graph API."""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

import matplotlib
import pandas as pd
import pytest
from matplotlib import pyplot as plt

# CI / GitHub Actions では実行しない
if os.getenv("CI") or os.getenv("GITHUB_ACTIONS"):
    pytest.skip("Skipping csv2graph unit tests on CI.", allow_module_level=True)

# Ensure plotting uses a headless backend inside tests
matplotlib.use("Agg")  # pragma: no cover - configuration

from rdetoolkit.graph.api.csv2graph import plot_from_dataframe
from rdetoolkit.graph.exceptions import ColumnNotFoundError
from rdetoolkit.graph.normalizers import ColumnNormalizer
from rdetoolkit.graph.parsers import CSVParser
from rdetoolkit.graph.textutils import parse_header


def write_csv(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
    return path


def test_csv_parser_single_header_mode(tmp_path: Path) -> None:
    csv_path = write_csv(
        tmp_path,
        "single_header.csv",
        """
        time (s),current (mA)
        0,1
        1,2
        """,
    )

    df, metadata = CSVParser.parse(csv_path)

    assert metadata["mode"] == CSVParser.DEFAULT_MODE
    assert metadata["title"] == "single_header"
    assert metadata["xaxis_label"] == "time (s)"
    assert metadata["yaxis_label"] == "current (mA)"
    assert metadata["legends"] == ["current"]
    assert list(df.columns) == ["time (s)", "current (mA)"]


def test_csv_parser_no_header_mode(tmp_path: Path) -> None:
    csv_path = write_csv(
        tmp_path,
        "no_header.csv",
        """
        1,10,0.5
        2,20,0.6
        3,30,0.7
        """,
    )

    df, metadata = CSVParser.parse(csv_path)

    assert metadata["mode"] == CSVParser.DEFAULT_MODE
    assert metadata["title"] == "no_header"
    assert metadata["xaxis_label"] == "x (arb.unit)"
    assert metadata["yaxis_label"] == "y (arb.unit)"
    assert metadata["legends"] == ["y1", "y2"]
    assert list(df.columns) == ["x (arb.unit)", "y1 (arb.unit)", "y2 (arb.unit)"]


def test_csv_parser_meta_block_mode(tmp_path: Path) -> None:
    csv_path = write_csv(
        tmp_path,
        "meta_block.csv",
        """
        #title,Meta Block Example
        #dimension,x,y
        #x,Time,s
        #y,Current,mA
        #legend,Series A,Series B
        0,10,12
        1,11,13
        """,
    )

    df, metadata = CSVParser.parse(csv_path)

    assert metadata["mode"] == CSVParser.DEFAULT_MODE
    assert metadata["title"] == "Meta Block Example"
    assert metadata["xaxis_label"] == "Time (s)"
    assert metadata["yaxis_label"] == "Current (mA)"
    assert metadata["legends"] == ["Series A", "Series B"]
    assert list(df.columns) == ["Time (s)", "Series A (mA)", "Series B (mA)"]


def test_csv_parser_meta_block_header_mismatch(tmp_path: Path) -> None:
    csv_path = write_csv(
        tmp_path,
        "meta_mismatch.csv",
        """
        #title,Meta Block Example
        #dimension,x,y
        #x,Time,s
        #y,Current,mA
        #legend,Series A,Series B
        0,10
        1,11
        """,
    )

    df, metadata = CSVParser.parse(csv_path)

    # 足りないデータ列は安全にトリムされる
    assert metadata["legends"] == ["Series A"]
    assert list(df.columns) == ["Time (s)", "Series A (mA)"]


def test_parse_header_humanizes_and_extracts_unit() -> None:
    assert parse_header("series_one: cycle_number (mAh)") == ("Series One", "Cycle Number", "mAh")
    assert parse_header("Voltage (V)") == (None, "Voltage", "V")
    assert parse_header("temperature") == (None, "Temperature", None)


def test_column_normalizer_to_index_variants() -> None:
    df = pd.DataFrame([[0, 1]], columns=["time", "current"])
    normalizer = ColumnNormalizer(df)

    assert normalizer.to_index(1) == 1
    assert normalizer.to_index("current") == 1

    with pytest.raises(ColumnNotFoundError, match="'voltage'"):
        normalizer.to_index("voltage")

    with pytest.raises(TypeError, match="int or str"):
        normalizer.to_index(0.5)  # type: ignore[arg-type]


def test_plot_from_dataframe_raises_on_mismatched_columns(tmp_path: Path) -> None:
    df = pd.DataFrame(
        {
            "time (s)": [0, 1, 2],
            "series_one: current (mA)": [1, 2, 3],
            "series_two: voltage (V)": [4, 5, 6],
        }
    )

    with pytest.raises(ValueError, match="must be equal"):
        plot_from_dataframe(
            df=df,
            output_dir=tmp_path,
            name="example",
            logy=False,
            html=False,
            x_col=[0, 1],
            y_cols=[2],
            return_fig=True,
        )


def test_plot_from_dataframe_respects_direction_filter(tmp_path: Path) -> None:
    df = pd.DataFrame(
        {
            "time": [0, 1, 2, 3],
            "value": [1.0, 2.0, 3.0, 4.0],
            "direction": ["Charge", "Discharge", "Charge", "Discharge"],
        }
    )

    filtered_artifacts = plot_from_dataframe(
        df=df,
        output_dir=tmp_path,
        name="direction_case",
        title="Direction Case",
        x_label="Time",
        y_label="Value",
        logy=False,
        x_col=0,
        y_cols=[1],
        logx=False,
        html=False,
        direction_cols=[2],
        direction_filter=["Charge"],
        no_individual=True,
        return_fig=True,
    )

    assert filtered_artifacts is not None
    filtered_overlay = filtered_artifacts[0]
    assert len(filtered_overlay.figure.axes[0].lines) == 1
    plt.close(filtered_overlay.figure)

    all_artifacts = plot_from_dataframe(
        df=df,
        output_dir=tmp_path,
        name="direction_case",
        title="Direction Case",
        x_label="Time",
        y_label="Value",
        logy=False,
        x_col=0,
        y_cols=[1],
        logx=False,
        html=False,
        direction_cols=[2],
        no_individual=True,
        return_fig=True,
    )

    assert all_artifacts is not None
    overlay = all_artifacts[0]
    assert len(overlay.figure.axes[0].lines) == 2
    plt.close(overlay.figure)


def test_plot_from_dataframe_creates_directories(tmp_path: Path) -> None:
    df = pd.DataFrame({"time": [0, 1], "value": [1, 2]})

    output_dir = tmp_path / "missing"
    main_dir = tmp_path / "main_missing"

    plot_from_dataframe(
        df=df,
        output_dir=output_dir,
        main_image_dir=main_dir,
        name="dir_case",
        title="Dir Case",
        x_label="Time",
        y_label="Value",
        logy=False,
        x_col=0,
        y_cols=[1],
        no_individual=False,
        return_fig=False,
    )

    assert output_dir.is_dir()
    assert main_dir.is_dir()
    assert any(main_dir.glob("dir_case.png"))
    assert list(output_dir.glob("dir_case_*.png"))
