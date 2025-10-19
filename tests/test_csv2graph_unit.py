"""Focused unit tests for local.develop.issue_188.csv2graph."""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

import matplotlib
import pandas as pd
import pytest

# CI / GitHub Actions では実行しない
if os.getenv("CI") or os.getenv("GITHUB_ACTIONS"):
    pytest.skip("Skipping csv2graph unit tests on CI.", allow_module_level=True)

# Ensure plotting uses a headless backend inside tests
matplotlib.use("Agg")  # pragma: no cover - configuration

import matplotlib.pyplot as plt

from local.develop.issue_188.csv2graph import (
    get_column_index,
    parse_header,
    plot_all_graphs,
    plot_from_dataframe,
    process_csv,
)


def write_csv(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
    return path


def test_process_csv_single_header_mode(tmp_path: Path) -> None:
    csv_path = write_csv(
        tmp_path,
        "single_header.csv",
        """
        time (s),current (mA)
        0,1
        1,2
        """,
    )

    df, metadata = process_csv(str(csv_path))

    assert metadata["mode"] == "single_header"
    assert metadata["title"] == "single_header"
    assert metadata["xaxis_label"] == "time (s)"
    assert metadata["yaxis_label"] == "current (mA)"
    assert metadata["legends"] == ["current"]
    assert list(df.columns) == ["time (s)", "current (mA)"]


def test_process_csv_no_header_mode(tmp_path: Path) -> None:
    csv_path = write_csv(
        tmp_path,
        "no_header.csv",
        """
        1,10,0.5
        2,20,0.6
        3,30,0.7
        """,
    )

    df, metadata = process_csv(str(csv_path))

    assert metadata["mode"] == "no_header"
    assert metadata["xaxis_label"] == "x (arb.unit)"
    assert metadata["yaxis_label"] == "y (arb.unit)"
    assert metadata["legends"] == ["y1", "y2"]
    assert list(df.columns) == ["x (arb.unit)", "y1 (arb.unit)", "y2 (arb.unit)"]


def test_process_csv_meta_block_mode(tmp_path: Path) -> None:
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

    df, metadata = process_csv(str(csv_path))

    assert metadata["mode"] == "meta_block"
    assert metadata["title"] == "Meta Block Example"
    assert metadata["xaxis_label"] == "Time (s)"
    assert metadata["yaxis_label"] == "Current (mA)"
    assert metadata["legends"] == ["Series A", "Series B"]
    assert list(df.columns) == ["Time (s)", "Series A (mA)", "Series B (mA)"]


def test_process_csv_meta_block_header_mismatch(tmp_path: Path) -> None:
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

    with pytest.raises(ValueError, match="Length mismatch"):
        process_csv(str(csv_path))


def test_parse_header_humanizes_and_extracts_unit() -> None:
    assert parse_header("series_one: cycle_number (mAh)") == ("Series One", "Cycle Number", "mAh")
    assert parse_header("Voltage (V)") == (None, "Voltage", "V")
    assert parse_header("temperature") == (None, "Temperature", None)


def test_get_column_index_accepts_multiple_notations() -> None:
    df = pd.DataFrame([[0, 1]], columns=["time", "current"])

    assert get_column_index(df, 1) == 1
    assert get_column_index(df, "1") == 1
    assert get_column_index(df, "current") == 1

    with pytest.raises(ValueError, match="Column 'voltage' not found"):
        get_column_index(df, "voltage")

    with pytest.raises(ValueError, match="Invalid column specification"):
        get_column_index(df, 0.5)


def test_plot_from_dataframe_raises_on_mismatched_columns() -> None:
    df = pd.DataFrame(
        {
            "time (s)": [0, 1, 2],
            "series_one: current (mA)": [1, 2, 3],
            "series_two: voltage (V)": [4, 5, 6],
        }
    )

    with pytest.raises(ValueError, match="x_colとy_colの数が一致しません"):
        plot_from_dataframe(
            df=df,
            name="example",
            logy=False,
            html=False,
            x_col=[0, 1],
            y_col=[2],
            return_fig=True,
        )


def test_plot_all_graphs_respects_direction_filter() -> None:
    df = pd.DataFrame(
        {
            "time": [0, 1, 2, 3],
            "value": [1.0, 2.0, 3.0, 4.0],
            "direction": ["Charge", "Discharge", "Charge", "Discharge"],
        }
    )

    fig_filtered = plot_all_graphs(
        df=df,
        name="direction_case",
        xaxis_label="Time",
        yaxis_label="Value",
        legends=["Series"],
        logy=False,
        output_dir=None,
        x_col=0,
        y_cols=[1],
        logx=False,
        html=False,
        direction_cols=[2],
        direction_filter="Charge",
        return_fig=True,
    )

    try:
        assert fig_filtered is not None
        assert len(fig_filtered.axes[0].lines) == 1
    finally:
        if fig_filtered is not None:
            plt.close(fig_filtered)

    fig_all = plot_all_graphs(
        df=df,
        name="direction_case",
        xaxis_label="Time",
        yaxis_label="Value",
        legends=["Series"],
        logy=False,
        output_dir=None,
        x_col=0,
        y_cols=[1],
        logx=False,
        html=False,
        direction_cols=[2],
        direction_filter=None,
        return_fig=True,
    )

    try:
        assert fig_all is not None
        assert len(fig_all.axes[0].lines) == 2
    finally:
        if fig_all is not None:
            plt.close(fig_all)


def test_plot_all_graphs_validates_directories(tmp_path: Path) -> None:
    df = pd.DataFrame({"time": [0, 1], "value": [1, 2]})

    with pytest.raises(FileNotFoundError):
        plot_all_graphs(
            df=df,
            name="missing_dir",
            xaxis_label="Time",
            yaxis_label="Value",
            legends=["Series"],
            logy=False,
            output_dir=str(tmp_path / "missing"),
            x_col=0,
            y_cols=[1],
            return_fig=False,
        )

    existing_output = tmp_path / "output"
    existing_output.mkdir()
    with pytest.raises(FileNotFoundError):
        plot_all_graphs(
            df=df,
            name="missing_main",
            xaxis_label="Time",
            yaxis_label="Value",
            legends=["Series"],
            logy=False,
            output_dir=str(existing_output),
            main_image_dir=str(tmp_path / "main_missing"),
            x_col=0,
            y_cols=[1],
            return_fig=False,
        )
