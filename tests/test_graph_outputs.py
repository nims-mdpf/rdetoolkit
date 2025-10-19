from pathlib import Path
import pytest

from rdetoolkit.graph.api.csv2graph import plot_from_dataframe
from rdetoolkit.graph.parsers.parser_factory import ParserFactory
from rdetoolkit.graph.textutils import sanitize_filename
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
                tol=18.5,
            ),
            id=f"{case.name}::{output.artifact}",
        )
        CASE_OUTPUT_PARAMS.append(param)


@pytest.mark.graph_outputs
@pytest.mark.parametrize("graph_case,graph_output", CASE_OUTPUT_PARAMS)
def test_csv2graph_matches_baseline(graph_case: GraphCase, graph_output: GraphOutputCheck):
    # Parse CSV using new API
    parser = ParserFactory.create("standard")
    dataframe = parser.parse(graph_case.csv_path)

    # Convert old parameter names to new API
    case_kwargs = {}
    for key, value in graph_case.plot_kwargs.items():
        if key == "df":
            continue
        elif key == "y_col":
            case_kwargs["y_cols"] = value
        elif key == "direction_col":
            case_kwargs["direction_cols"] = value
        elif key == "xaxis_label":
            case_kwargs["x_label"] = value
        elif key == "yaxis_label":
            case_kwargs["y_label"] = value
        elif key == "mode":
            # Convert old mode values to new API
            if value == "x1y1x2y2":
                case_kwargs["mode"] = "overlay"
            elif value == "dual_axis":
                case_kwargs["mode"] = "overlay"  # No dual_axis in new API yet
            else:
                case_kwargs["mode"] = value
        else:
            case_kwargs[key] = value

    base_kwargs = {
        "df": dataframe,
        "output_dir": Path("."),  # Required parameter
        "logy": False,
        "html": False,
        "mode": case_kwargs.pop("mode", "overlay"),
        "x_col": case_kwargs.pop("x_col", None),
        "y_cols": case_kwargs.pop("y_cols", None),
        "logx": False,
        "direction_cols": case_kwargs.pop("direction_cols", None),
        "direction_filter": None,
        "direction_colors": None,
        "title": case_kwargs.pop("title", None),
        "name": case_kwargs.pop("name", None),
        "x_label": case_kwargs.pop("x_label", None),
        "y_label": case_kwargs.pop("y_label", None),
        "legend_info": None,
        "legend_loc": None,
        "no_individual": False,
        "xlim": None,
        "ylim": None,
        "grid": False,
        "invert_x": False,
        "invert_y": False,
        "return_fig": True,
        "max_legend_items": None,
    }

    # Merge remaining case_kwargs
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


@pytest.mark.graph_outputs
@pytest.mark.skipif("sample27" not in OUTPUT_DIR_CASES, reason="sample27 fixtures missing")
def test_csv2graph_writes_to_specified_directories(tmp_path: Path):
    case = OUTPUT_DIR_CASES["sample27"]

    # Parse CSV using new API
    parser = ParserFactory.create("standard")
    dataframe = parser.parse(case.csv_path)

    output_dir = tmp_path / "output"
    output_dir.mkdir()
    main_image_dir = tmp_path / "main_image"
    main_image_dir.mkdir()

    # Convert old parameter names to new API
    case_kwargs = {}
    for key, value in case.plot_kwargs.items():
        if key == "df":
            continue
        elif key == "y_col":
            case_kwargs["y_cols"] = value
        elif key == "direction_col":
            case_kwargs["direction_cols"] = value
        elif key == "xaxis_label":
            case_kwargs["x_label"] = value
        elif key == "yaxis_label":
            case_kwargs["y_label"] = value
        elif key == "mode":
            # Convert old mode values to new API
            if value == "x1y1x2y2":
                case_kwargs["mode"] = "overlay"
            elif value == "dual_axis":
                case_kwargs["mode"] = "overlay"  # No dual_axis in new API yet
            else:
                case_kwargs["mode"] = value
        elif key == "main_image_dir":
            continue
        elif key == "output_dir":
            continue
        else:
            case_kwargs[key] = value

    base_kwargs = {
        "df": dataframe,
        "output_dir": str(output_dir),
        "main_image_dir": str(main_image_dir),
        "logy": False,
        "html": False,
        "mode": case_kwargs.pop("mode", "overlay"),
        "x_col": case_kwargs.pop("x_col", None),
        "y_cols": case_kwargs.pop("y_cols", None),
        "logx": case_kwargs.pop("logx", False),
        "direction_cols": case_kwargs.pop("direction_cols", None),
        "direction_filter": case_kwargs.pop("direction_filter", None),
        "direction_colors": None,
        "legend_info": case_kwargs.pop("legend_info", None),
        "legend_loc": None,
        "title": case_kwargs.pop("title", None),
        "name": case_kwargs.pop("name", None),
        "x_label": case_kwargs.pop("x_label", None),
        "y_label": case_kwargs.pop("y_label", None),
        "no_individual": False,
        "xlim": case_kwargs.pop("xlim", None),
        "ylim": case_kwargs.pop("ylim", None),
        "grid": case_kwargs.pop("grid", False),
        "invert_x": case_kwargs.pop("invert_x", False),
        "invert_y": case_kwargs.pop("invert_y", False),
        "return_fig": False,
        "max_legend_items": case_kwargs.pop("max_legend_items", None),
    }

    # Merge remaining case_kwargs
    base_kwargs.update(case_kwargs)
    result = plot_from_dataframe(**base_kwargs)
    assert result is None, "plot_from_dataframe should return None when return_fig=False"

    expected_name = case_kwargs.get("name", case.name)
    expected_combined = sanitize_filename(expected_name) + ".png"
    assert (main_image_dir / expected_combined).exists(), f"Combined plot not saved to main_image_dir: {expected_combined}"
    assert not (output_dir / expected_combined).exists(), "Combined plot should not be in the secondary output directory"

    saved_output_files = {f.name for f in output_dir.glob("*.png")}
    saved_main_files = {f.name for f in main_image_dir.glob("*.png")}
    expected_artifacts = {sanitize_filename(output.artifact) for output in case.outputs}

    assert expected_combined in saved_main_files, "Combined plot missing in main_image_dir"

    remaining_expected = expected_artifacts - {expected_combined}
    assert remaining_expected.issubset(saved_output_files), (
        f"Missing individual plots. Expected: {remaining_expected}, Got: {saved_output_files}"
    )
