from pathlib import Path
import pytest

from local.develop.issue_188.csv2graph import (
    process_csv,
    plot_from_dataframe,
    sanitize_filename,
)
from tests.fixtures.csv2graph import (
    GRAPH_CASES,
    GraphCase,
    GraphOutputCheck,
    baseline_directory,
)


if not GRAPH_CASES:
    pytest.skip("No csv2graph regression fixtures found", allow_module_level=True)


CASE_OUTPUT_PARAMS: list = []
OUTPUT_DIR_CASES: dict[str, GraphCase] = {}

for case in GRAPH_CASES:
    if {"output_dir", "main_image_dir"} & case.plot_kwargs.keys():
        OUTPUT_DIR_CASES[case.name] = case
        continue

    for output in case.outputs:
        param = pytest.param(
            case,
            output,
            marks=pytest.mark.mpl_image_compare(
                baseline_dir=str(baseline_directory()),
                filename=output.baseline.name,
                style="default",
            ),
            id=f"{case.name}::{output.artifact}",
        )
        CASE_OUTPUT_PARAMS.append(param)


@pytest.mark.parametrize("graph_case,graph_output", CASE_OUTPUT_PARAMS)
def test_csv2graph_matches_baseline(graph_case: GraphCase, graph_output: GraphOutputCheck):
    dataframe, metadata = process_csv(str(graph_case.csv_path))

    base_kwargs = {
        "df": dataframe,
        "name": Path(graph_output.artifact).stem,
        "logy": False,
        "html": False,
        "output_dir": None,
        "main_image_dir": None,
        "xaxis_label": metadata.get("xaxis_label"),
        "yaxis_label": metadata.get("yaxis_label"),
        "mode": metadata.get("mode"),
        "x_col": None,
        "y_col": None,
        "logx": False,
        "direction_col": None,
        "direction_filter": None,
        "legend_info": None,
        "title": None,
        "no_individual": False,
        "xlim": None,
        "ylim": None,
        "grid": False,
        "invert_x": False,
        "invert_y": False,
        "return_fig": True,
        "max_legend_items": None,
    }

    case_kwargs = {
        key: value
        for key, value in graph_case.plot_kwargs.items()
        if key != "df"
    }
    base_kwargs.update(case_kwargs)
    artifacts = plot_from_dataframe(**base_kwargs)
    assert artifacts, "plot_from_dataframe returned no matplotlib artifacts"

    matched_artifact = None
    for artifact in artifacts:
        if artifact.filename == graph_output.artifact:
            matched_artifact = artifact
            break

    if matched_artifact is None:
        available = ", ".join(a.filename for a in artifacts)
        pytest.fail(
            f"Artifact '{graph_output.artifact}' not produced by plot_from_dataframe."
            f" Available: {available}"
        )

    return matched_artifact.figure


@pytest.mark.skipif("sample27" not in OUTPUT_DIR_CASES, reason="sample27 fixtures missing")
def test_csv2graph_writes_to_specified_directories(tmp_path: Path):
    case = OUTPUT_DIR_CASES["sample27"]

    dataframe, metadata = process_csv(str(case.csv_path))

    output_dir = tmp_path / "other_image"
    main_image_dir = tmp_path / "main_image"
    output_dir.mkdir()
    main_image_dir.mkdir()

    base_kwargs = {
        "df": dataframe,
        "name": case.plot_kwargs.get("name", case.name),
        "logy": False,
        "html": False,
        "output_dir": str(output_dir),
        "main_image_dir": str(main_image_dir),
        "xaxis_label": metadata.get("xaxis_label"),
        "yaxis_label": metadata.get("yaxis_label"),
        "mode": metadata.get("mode"),
        "x_col": case.plot_kwargs.get("x_col"),
        "y_col": case.plot_kwargs.get("y_col"),
        "logx": case.plot_kwargs.get("logx", False),
        "direction_col": case.plot_kwargs.get("direction_col"),
        "direction_filter": case.plot_kwargs.get("direction_filter"),
        "legend_info": case.plot_kwargs.get("legend_info"),
        "title": case.plot_kwargs.get("title"),
        "no_individual": False,
        "xlim": case.plot_kwargs.get("xlim"),
        "ylim": case.plot_kwargs.get("ylim"),
        "grid": case.plot_kwargs.get("grid", False),
        "invert_x": case.plot_kwargs.get("invert_x", False),
        "invert_y": case.plot_kwargs.get("invert_y", False),
        "return_fig": False,
        "max_legend_items": case.plot_kwargs.get("max_legend_items"),
    }

    result = plot_from_dataframe(**base_kwargs)
    assert result is None, "plot_from_dataframe should return None when return_fig=False"

    expected_combined = sanitize_filename(case.plot_kwargs.get("name", case.name)) + ".png"
    assert (main_image_dir / expected_combined).exists(), "Combined plot not saved in main_image_dir"

    expected_individual = {
        sanitize_filename(output.artifact) for output in case.outputs if output.artifact != expected_combined
    }
    saved_files = {f.name for f in output_dir.glob("*.png")}
    assert expected_individual.issubset(saved_files), "Missing individual plots in output_dir"
