"""GE-03 (#709): the GraphSpec / PlotPlan / GraphResult domain contract.

The spec API (``render_graph``) takes one backend-neutral, versioned ``GraphSpec``
(no keyword configuration that could contradict it), resolves it into an immutable,
JSON-snapshot-able ``PlotPlan`` that records every decision and its origin, and
returns a ``GraphResult`` whose artifacts each carry a path or an in-memory handle,
a format, the series identity and the diagnostics. The legacy facade
(``csv2graph`` / ``plot_from_dataframe``) keeps its v1 signatures and return values.

Golden plans live in ``tests/v2/graph/golden/``; regenerate them only with
``regenerate_golden_plans()`` from this module, never by hand.

EP table:

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| build_plot_plan | simple / multi-X / multi-Y / direction requests | equals the golden snapshot | TC-GE03-EP-001 |
| PlotPlan.to_dict | any plan | JSON round-trip identical, keys sorted at every level, rebuild identical | TC-GE03-EP-002 |
| PlotPlan.origins | explicit vs omitted title/x/labels/units/style | "explicit" vs "default"/"derived" | TC-GE03-EP-003 |
| render_graph | output=None | one "figure" artifact per figure, path None, labels, caller-owned, no rcParams leak | TC-GE03-EP-004 |
| render_graph | output=OutputSpec(DirectorySink) | figures x formats files, artifact order, role routing, overlay PNG == legacy PNG | TC-GE03-EP-005 |
| GraphResult.manifest_json | written result | schema_version 1, file names only, sorted keys, trailing newline | TC-GE03-EP-006 |
| GraphSpec.layout | auto / overlay / individual / both x 1..3 series | figure ids of the matrix | TC-GE03-EP-007 |
| GraphSpec.label_style / SeriesSpec.label | humanized / header / raw / explicit, duplicate labels | label rule, show_in_legend, color_index | TC-GE03-EP-008 |
| build_plot_plan | several frames | frame-major series | TC-GE03-EP-009 |
| PlotData.segments | direction column with NA, enum, filter | filtered, normalized, first-appearance order | TC-GE03-EP-010 |
| PlotPlan.with_labels | one label per series | labels, legend roles and individual titles recomputed | TC-GE03-EP-011 |
| render_graph | spec-only signature | (source, spec, output); legacy keywords rejected | TC-GE03-EP-012 |
| csv2graph / plot_from_dataframe | v1 defaults, 27 positional arguments, return_fig | v1 artifacts and return values | TC-GE03-EP-013 |
| graph exceptions | the classes of design 3.1 | builtin bases kept | TC-GE03-EP-014 |
| rdetoolkit.graph | public surface | GE-03 names exported, internals not | TC-GE03-EP-015 |
| build_plot_plan | duplicate column labels | addressable by position and by default selection | TC-GE03-EP-016 |
| render_graph | mark line / scatter, axis settings, direction colours | drawn artists follow the plan | TC-GE03-EP-017 |

Negative table:

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| GraphSpec | version 0 / 2 / True / "1" | PlotRequestError(invalid_spec) | TC-GE03-NEG-001 |
| spec types | choice values outside their Literal | PlotRequestError(invalid_spec) | TC-GE03-NEG-002 |
| SeriesSpec / GraphSpec | column ref float / bool / list; non-SeriesSpec entry | TypeError | TC-GE03-NEG-003 |
| build_plot_plan | unknown label, position -1 / n, label on two columns | PlotRequestError(unknown_column / ambiguous_column) | TC-GE03-NEG-004 |
| render_graph | only an x column / no column / no frame | ValueError "at least one y column", nothing written | TC-GE03-NEG-005 |
| render_graph | str / Path / bytes / dict / list with non-frame | TypeError, nothing written | TC-GE03-NEG-006 |
| OutputSpec | no format, empty/non-str format, empty base name, dpi 0 / -1 / True | PlotRequestError(invalid_spec) | TC-GE03-NEG-007 |
| render_graph | format html / jpg | UnsupportedFormatError, no directory created | TC-GE03-NEG-008 |
| render_graph | existing destination with on_existing="error" | ArtifactCollisionError, nothing written | TC-GE03-NEG-009 |
| DirectorySink | separator / ".." / empty name, file as directory, symlink escape | OutputPathError (ValueError, legacy text) | TC-GE03-NEG-010 |
| render_graph | sink mapping two artifacts to one file | ArtifactCollisionError before anything is written | TC-GE03-NEG-011 |
| Artifact | neither / both of path and figure | ValueError | TC-GE03-NEG-012 |
| spec / plan / result types | attribute or mapping assignment, caller mutation | FrozenInstanceError / TypeError / unaffected | TC-GE03-NEG-013 |
| render_graph | export failure on a later figure | nothing written, no figure left open | TC-GE03-NEG-014 |
| PlotPlan.with_labels | label count differs | ValueError "1 labels for 2 series" | TC-GE03-NEG-015 |
| AxisSpec / StyleSpec | limits / figure_size not a pair, rc_params not a mapping | PlotRequestError(invalid_spec) | TC-GE03-NEG-016 |
| GraphSpec | x given with x_default="index" | PlotRequestError(contradictory_switches) | TC-GE03-NEG-017 |

BV table:

| API | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| GraphSpec.layout="auto" | 1 series / 2 series | overlay only / overlay + 2 individual | TC-GE03-BV-001 |
| build_plot_plan | two identical headers | suffixed stems, filename_collision on plan and artifacts | TC-GE03-BV-002 |
| OutputSpec.dpi | 1 | accepted | TC-GE03-BV-003 |
| GraphSpec.x_default="index" | unnamed / named index | x_name "index" / the index name | TC-GE03-BV-004 |
| AxisSpec.limits | (None, None) / one-sided | kept as given in the plan | TC-GE03-BV-005 |
"""

from __future__ import annotations

import dataclasses
import hashlib
import inspect
import json
import shutil
from enum import Enum
from pathlib import Path
from typing import Any

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd
import pytest
from matplotlib.collections import PathCollection
from matplotlib.colors import to_hex
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

import rdetoolkit.graph as graph_pkg
from rdetoolkit.graph import engine
from rdetoolkit.graph.api.csv2graph import csv2graph, plot_from_dataframe
from rdetoolkit.graph.exceptions import (
    AmbiguousFormatError,
    ArtifactCollisionError,
    DuplicateReaderError,
    GraphPlottingError,
    InvalidCSVFormatError,
    OutputPathError,
    PlotConfigError,
    PlotRequestError,
    ReaderPluginError,
    RendererError,
    RendererUnavailableError,
    UnknownReaderError,
    UnsupportedFormatError,
)
from rdetoolkit.graph.models import Direction, MatplotlibArtifact
from rdetoolkit.graph.outputs import DirectorySink
from rdetoolkit.graph.plan import GraphDiagnostic, PlotData, PlotPlan, build_plot_plan
from rdetoolkit.graph.result import Artifact, GraphResult
from rdetoolkit.graph.spec import SPEC_VERSION, AxisSpec, GraphSpec, LegendSpec, OutputSpec, SeriesSpec, StyleSpec

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN = Path(__file__).parent / "golden"


def _copy_fixture(name: str, tmp_path: Path) -> Path:
    target = tmp_path / name
    shutil.copyfile(FIXTURES / name, target)
    return target


def _multi_y() -> pd.DataFrame:
    return pd.read_csv(FIXTURES / "multi_unit.csv")


def _golden_requests() -> dict[str, tuple[Any, GraphSpec, str]]:
    """The four golden plan requests (simple, multi-X, multi-Y, direction)."""
    multi_x = pd.DataFrame({
        "t1 (s)": [0, 1, 2], "a: voltage (V)": [1.0, 2.0, 3.0],
        "t2 (s)": [0, 2, 4], "b: voltage (V)": [3.0, 2.0, 1.0],
    })
    direction = pd.DataFrame({
        "time (s)": [0, 1, 2, 3, 4, 5],
        "capacity (mAh)": [0.0, 1.0, 2.0, 2.0, 1.0, 0.5],
        "state": ["Charge", "Charge", None, "Discharge", "Rest", "Discharge"],
    })
    return {
        "simple": (pd.read_csv(FIXTURES / "simple.csv"), GraphSpec(title="simple"), "simple"),
        "multi_x": (
            multi_x,
            GraphSpec(series=(SeriesSpec(y=1, x=0), SeriesSpec(y="b: voltage (V)", x="t2 (s)", label="B")), layout="both"),
            "mx",
        ),
        "multi_y": (_multi_y(), GraphSpec(title="cell", y_axis=AxisSpec(scale="log", grid=True)), "cell"),
        "direction": (
            direction,
            GraphSpec(
                series=(SeriesSpec(y="capacity (mAh)", direction="state", unit="Ah"),),
                direction_filter=("Charge", "Discharge"),
                direction_colors={"Charge": "red"},
                legend=LegendSpec(policy="auto"),
            ),
            "dir",
        ),
    }


def _golden_text(plan: PlotPlan) -> str:
    return json.dumps(plan.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def regenerate_golden_plans() -> None:
    """Rewrite the golden plan snapshots (explicit helper; never edit them by hand)."""
    GOLDEN.mkdir(exist_ok=True)
    for name, (frames, spec, base) in _golden_requests().items():
        (GOLDEN / f"plan_{name}.json").write_text(_golden_text(build_plot_plan(frames, spec, base_name=base)), encoding="utf-8")


def _assert_sorted_keys(value: Any) -> None:
    if isinstance(value, dict):
        assert list(value) == sorted(value)
        for item in value.values():
            _assert_sorted_keys(item)
    elif isinstance(value, list):
        for item in value:
            _assert_sorted_keys(item)


def _figure_ids(plan: PlotPlan) -> list[str]:
    return [figure.figure_id for figure in plan.figures]


# --------------------------------------------------------------------------- EP


@pytest.mark.parametrize("name", ["simple", "multi_x", "multi_y", "direction"])
def test_plan_matches_golden_snapshot__tc_ge03_ep_001(name: str) -> None:
    """TC-GE03-EP-001: normalized plans are pinned by golden snapshots."""
    # Given: one of the four golden requests
    frames, spec, base = _golden_requests()[name]
    # When: building its plan
    plan = build_plot_plan(frames, spec, base_name=base)
    # Then: the deterministic snapshot equals the committed golden file
    assert _golden_text(plan) == (GOLDEN / f"plan_{name}.json").read_text(encoding="utf-8")


def test_golden_plans_record_the_resolved_decisions__tc_ge03_ep_001() -> None:
    """TC-GE03-EP-001: the golden content itself is what the contract promises."""
    # Given/When: the multi-X and direction plans
    requests = _golden_requests()
    multi_x = build_plot_plan(requests["multi_x"][0], requests["multi_x"][1], base_name="mx")
    direction = build_plot_plan(requests["direction"][0], requests["direction"][1], base_name="dir")
    # Then: per-series x columns, explicit labels and filtered directions are resolved positionally
    assert [(s.x_index, s.y_index, s.label) for s in multi_x.series] == [(0, 1, "A"), (2, 3, "B")]
    assert [f.stem for f in multi_x.figures] == ["mx", "mx_a", "mx_b"]
    assert direction.series[0].directions == ("Charge", "Discharge")
    assert direction.series[0].unit == "Ah"
    assert dict(direction.direction_colors) == {"Charge": "red"}


def test_to_dict_is_json_safe_sorted_and_deterministic__tc_ge03_ep_002() -> None:
    """TC-GE03-EP-002: to_dict round-trips through JSON with sorted keys at every level."""
    # Given: a plan with nested specs, mappings and diagnostics
    frames, spec, base = _golden_requests()["direction"]
    snapshot = build_plot_plan(frames, spec, base_name=base).to_dict()
    # When: serializing and parsing it
    restored = json.loads(json.dumps(snapshot))
    # Then: nothing is lost, keys are sorted everywhere, and a rebuild is identical
    assert restored == snapshot
    _assert_sorted_keys(snapshot)
    assert build_plot_plan(frames, spec, base_name=base).to_dict() == snapshot
    assert snapshot["style"]["figure_size"] == [8.85, 8]
    assert snapshot["style"]["rc_params"]["font.size"] == 20


def test_to_dict_renders_values_without_json_form_as_text__tc_ge03_ep_002() -> None:
    """TC-GE03-EP-002: enum and arbitrary rc values become JSON-safe."""

    class Shade(Enum):
        DARK = "dark"

    # Given: rc params holding an enum, a tuple and an object
    spec = GraphSpec(style=StyleSpec(rc_params={"a.enum": Shade.DARK, "a.tuple": (1, 2), "a.path": Path("p")}))
    # When: snapshotting
    params = build_plot_plan(_multi_y(), spec).to_dict()["style"]["rc_params"]
    # Then: each value has a JSON form
    assert (params["a.enum"], params["a.tuple"], params["a.path"]) == ("dark", [1, 2], "p")


def test_origins_distinguish_explicit_from_default_and_derived__tc_ge03_ep_003() -> None:
    """TC-GE03-EP-003: every resolved decision records where it came from."""
    # Given: a request that omits everything and one that states everything
    implicit = build_plot_plan(_multi_y()).origins
    explicit = build_plot_plan(_multi_y(), GraphSpec(
        x=0, title="T", series=(SeriesSpec(y=1, label="V", unit="mV"), SeriesSpec(y=2)),
        x_axis=AxisSpec(label="X", limits=(0, 1)), y_axis=AxisSpec(label="Y"),
        style=StyleSpec(figure_size=(4, 3), rc_params={"font.size": 9}),
    )).origins
    # Then: omitted values are default/derived, stated values explicit
    assert {key: implicit[key] for key in ("title", "x", "series", "x_axis.label", "y_axis.label", "x_axis.limits", "style.figure_size", "style.rc_params")} == {
        "title": "default", "x": "default", "series": "default", "x_axis.label": "derived", "y_axis.label": "derived",
        "x_axis.limits": "default", "style.figure_size": "default", "style.rc_params": "default",
    }
    assert implicit["series[s000].label"] == "derived"
    assert implicit["series[s000].unit"] == "derived"
    assert {key: explicit[key] for key in ("title", "x", "series", "x_axis.label", "y_axis.label", "x_axis.limits", "style.figure_size", "style.rc_params")} == dict.fromkeys(
        ("title", "x", "series", "x_axis.label", "y_axis.label", "x_axis.limits", "style.figure_size", "style.rc_params"), "explicit",
    )
    assert (explicit["series[s000].label"], explicit["series[s000].unit"]) == ("explicit", "explicit")
    assert (explicit["series[s001].label"], explicit["series[s001].unit"]) == ("derived", "derived")


def test_unit_origin_is_default_without_any_unit__tc_ge03_ep_003() -> None:
    """TC-GE03-EP-003: a header without unit and no explicit unit is an unknown (default) unit."""
    # Given: headers without units
    plan = build_plot_plan(pd.DataFrame({"x": [1, 2], "y": [3, 4]}))
    # Then: the unit is unknown and its origin is default
    assert plan.series[0].unit is None
    assert plan.origins["series[s000].unit"] == "default"
    assert plan.unit_groups == ((None, ("s000",)),)


def test_render_graph_in_memory_returns_caller_owned_figures__tc_ge03_ep_004() -> None:
    """TC-GE03-EP-004: output=None yields one in-memory artifact per figure."""
    # Given: two series (auto layout -> overlay + 2 individual) and the ambient rcParams
    before = dict(mpl.rcParams)
    # When: rendering without an output
    result = engine.render_graph(_multi_y(), GraphSpec(title="cell"))
    # Then: every artifact has a figure handle, no path, the "figure" format and series identity
    assert isinstance(result, GraphResult)
    assert [(a.figure_id, a.kind, a.role, a.format, a.series_ids, a.labels) for a in result.artifacts] == [
        ("overlay", "overlay", "main_image", "figure", ("s000", "s001"), ("Voltage", "Current")),
        ("s000", "individual", "individual", "figure", ("s000",), ("Voltage",)),
        ("s001", "individual", "individual", "figure", ("s001",), ("Current",)),
    ]
    assert all(isinstance(a.figure, Figure) and a.path is None and a.renderer == "matplotlib" for a in result.artifacts)
    assert result.detection is None
    assert dict(mpl.rcParams) == before
    # And: the figures are drawn from the plan and stay drawable by the caller
    overlay = result.artifacts[0].figure
    overlay.canvas.draw()
    assert overlay.axes[0].get_legend() is not None
    assert [text.get_text() for text in overlay.axes[0].get_legend().get_texts()] == ["Voltage", "Current"]
    assert overlay.axes[0].get_ylabel() == "Voltage (V)"
    assert result.artifacts[2].figure.axes[0].get_ylabel() == "Current (A)"
    assert result.artifacts[2].figure.axes[0].get_title() == "cell - Current"


def test_render_graph_writes_every_figure_and_format__tc_ge03_ep_005(tmp_path: Path) -> None:
    """TC-GE03-EP-005: written artifacts follow plan order, then format order, routed by role."""
    # Given: a sink with a separate main-image directory and two formats
    sink = DirectorySink(tmp_path / "out", main_image_dir=tmp_path / "main")
    # When: rendering
    result = engine.render_graph(_multi_y(), GraphSpec(title="cell"), output=OutputSpec(sink, formats=("PNG", "svg", "png"), base_name="cell"))
    # Then: 3 figures x 2 formats, overlay in main/, individuals in out/
    assert [(a.figure_id, a.format, a.role, a.path.parent.name, a.path.name) for a in result.artifacts if a.path] == [
        ("overlay", "png", "main_image", "main", "cell.png"),
        ("overlay", "svg", "main_image", "main", "cell.svg"),
        ("s000", "png", "individual", "out", "cell_voltage_(v).png"),
        ("s000", "svg", "individual", "out", "cell_voltage_(v).svg"),
        ("s001", "png", "individual", "out", "cell_current_(a).png"),
        ("s001", "svg", "individual", "out", "cell_current_(a).svg"),
    ]
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == sorted(a.path.name for a in result.artifacts[2:] if a.path)
    assert all(a.figure is None and not a.replaced_existing for a in result.artifacts)
    assert all(a.path.read_bytes()[:4] == b"\x89PNG" for a in result.artifacts if a.path and a.format == "png")
    assert plt.get_fignums() == []


def test_render_graph_overlay_png_equals_the_legacy_png__tc_ge03_ep_005(tmp_path: Path) -> None:
    """TC-GE03-EP-005: the spec API keeps the legacy house style byte for byte."""
    # Given: the same frame through the legacy facade and the spec API
    frame = _multi_y()
    plot_from_dataframe(frame, tmp_path / "legacy", title="cell")
    # When: rendering through render_graph
    engine.render_graph(frame, GraphSpec(title="cell"), output=OutputSpec(DirectorySink(tmp_path / "spec"), base_name="cell"))
    # Then: overlay and first individual PNG are identical (later individuals get their own y label)
    for name in ("cell.png", "cell_voltage_(v).png"):
        assert hashlib.sha256((tmp_path / "spec" / name).read_bytes()).hexdigest() == hashlib.sha256((tmp_path / "legacy" / name).read_bytes()).hexdigest()


def test_manifest_is_versioned_and_machine_independent__tc_ge03_ep_006(tmp_path: Path) -> None:
    """TC-GE03-EP-006: the manifest records file names, never absolute paths."""
    # Given: a written result
    result = engine.render_graph(_multi_y(), output=OutputSpec(DirectorySink(tmp_path)))
    # When: building the manifest
    text = result.manifest_json()
    manifest = json.loads(text)
    # Then: it is versioned, sorted, newline-terminated and path-free
    assert manifest["schema_version"] == 1
    assert [entry["file"] for entry in manifest["artifacts"]] == ["plot.png", "plot_voltage_(v).png", "plot_current_(a).png"]
    assert manifest["artifacts"][0]["labels"] == ["Voltage", "Current"]
    assert manifest["detection"] is None
    assert str(tmp_path) not in text
    assert text.endswith("}\n")
    assert text == json.dumps(manifest, sort_keys=True, ensure_ascii=False, indent=2) + "\n"


def test_manifest_records_in_memory_artifacts_without_file__tc_ge03_ep_006() -> None:
    """TC-GE03-EP-006: an in-memory artifact has no file entry; a detection value is rendered as text."""
    # Given: an in-memory result
    result = engine.render_graph(pd.DataFrame({"x": [1, 2], "y": [1, 2]}))
    # When: building the manifest, also for a result that carries a detection value
    manifest = result.manifest()
    with_detection = dataclasses.replace(result, detection="standard").manifest()
    # Then: file is None and detection is recorded
    assert manifest["artifacts"][0]["file"] is None
    assert manifest["artifacts"][0]["format"] == "figure"
    assert with_detection["detection"] == "standard"


@pytest.mark.parametrize(("layout", "count", "expected"), [
    ("auto", 1, ["overlay"]),
    ("auto", 2, ["overlay", "s000", "s001"]),
    ("auto", 3, ["overlay", "s000", "s001", "s002"]),
    ("overlay", 1, ["overlay"]),
    ("overlay", 3, ["overlay"]),
    ("individual", 1, ["s000"]),
    ("individual", 3, ["s000", "s001", "s002"]),
    ("both", 1, ["overlay", "s000"]),
    ("both", 2, ["overlay", "s000", "s001"]),
])
def test_layout_series_count_matrix__tc_ge03_ep_007_bv_001(layout: str, count: int, expected: list[str]) -> None:
    """TC-GE03-EP-007 / TC-GE03-BV-001: layout decides the figures; auto adds individuals above one series."""
    # Given: a frame with `count` y columns
    frame = pd.DataFrame({"x": [0, 1], **{f"y{i}": [i, i + 1] for i in range(count)}})
    # When: planning with the layout
    plan = build_plot_plan(frame, GraphSpec(layout=layout))  # type: ignore[arg-type]
    # Then: the figures match the matrix, overlay first
    assert _figure_ids(plan) == expected
    assert all(figure.kind == ("overlay" if figure.figure_id == "overlay" else "individual") for figure in plan.figures)


@pytest.mark.parametrize(("style", "expected"), [
    ("humanized", ["Cycle Count", "Grp", "Voltage"]),
    ("header", ["cycle_count", "grp", "voltage"]),
    ("raw", ["cycle_count (n)", "grp: current (A)", "voltage"]),
])
def test_label_style_rules__tc_ge03_ep_008(style: str, expected: list[str]) -> None:
    """TC-GE03-EP-008: one label rule per label_style, the same for every backend."""
    # Given: headers with unit, series prefix and plain text
    frame = pd.DataFrame({"x": [0, 1], "cycle_count (n)": [1, 2], "grp: current (A)": [3, 4], "voltage": [5, 6]})
    # When: planning with the label style
    plan = build_plot_plan(frame, GraphSpec(label_style=style))  # type: ignore[arg-type]
    # Then: the labels follow the rule and header parts are kept un-humanized
    assert [series.label for series in plan.series] == expected
    assert [(s.header_series, s.header_label, s.unit) for s in plan.series] == [
        (None, "cycle_count", "n"), ("grp", "current", "A"), (None, "voltage", None),
    ]


def test_duplicate_labels_hide_later_legend_entries_and_keep_positional_colors__tc_ge03_ep_008() -> None:
    """TC-GE03-EP-008: legend visibility and colour index are decided once, in the plan."""
    # Given: three series, two with the same explicit label
    spec = GraphSpec(series=(SeriesSpec(y=1, label="A"), SeriesSpec(y=2, label="B"), SeriesSpec(y=3, label="A")))
    # When: planning and rendering in memory
    plan = build_plot_plan(_frame4(), spec)
    overlay = engine.render_graph(_frame4(), spec).artifacts[0].figure
    # Then: the second "A" is not listed again and colours follow plan positions
    assert [(s.label, s.show_in_legend, s.color_index) for s in plan.series] == [("A", True, 0), ("B", True, 1), ("A", False, 2)]
    assert [text.get_text() for text in overlay.axes[0].get_legend().get_texts()] == ["A", "B"]
    palette = [to_hex(color) for color in plt.cm.tab10.colors[:3]]  # type: ignore[attr-defined]
    assert [to_hex(line.get_color()) for line in overlay.axes[0].get_lines()] == palette


def _frame4() -> pd.DataFrame:
    return pd.DataFrame({"x": [0, 1, 2], "a": [1, 2, 3], "b": [3, 2, 1], "c": [2, 2, 2]})


def test_multi_frame_plans_are_frame_major__tc_ge03_ep_009() -> None:
    """TC-GE03-EP-009: several frames are planned frame by frame with the same selections."""
    # Given: two frames
    first = pd.DataFrame({"x": [0, 1], "y": [1, 2], "z": [2, 3]})
    second = pd.DataFrame({"x": [0, 1, 2], "y": [5, 6, 7], "z": [1, 1, 1]})
    # When: planning both
    plan = build_plot_plan([first, second], GraphSpec(layout="overlay"))
    # Then: series ids run frame-major and each series points at its frame
    assert [(s.series_id, s.frame, s.y_name) for s in plan.series] == [("s000", 0, "y"), ("s001", 0, "z"), ("s002", 1, "y"), ("s003", 1, "z")]
    assert [s.show_in_legend for s in plan.series] == [True, True, False, False]
    # And: rendering draws all four series from their own frames
    figure = engine.render_graph([first, second], GraphSpec(layout="overlay")).artifacts[0].figure
    assert [len(line.get_xdata()) for line in figure.axes[0].get_lines()] == [2, 2, 3, 3]


def test_segments_follow_filtered_first_appearance_directions__tc_ge03_ep_010() -> None:
    """TC-GE03-EP-010: PlotData.segments is the single plan-to-rows translation."""
    # Given: a direction column with NA values, enum members and strings
    frame = pd.DataFrame({
        "t": [0, 1, 2, 3, 4, 5],
        "v": [10, 11, 12, 13, 14, 15],
        "d": [Direction.DISCHARGE, "Charge", None, "Discharge", "Rest", float("nan")],
    })
    spec = GraphSpec(series=(SeriesSpec(y="v", direction="d"),), direction_filter=("Charge", "Discharge"))
    plan = build_plot_plan(frame, spec)
    # When: asking for the segments
    segments = PlotData(frames=(frame,)).segments(plan.series[0])
    # Then: NA dropped, enum normalized, filter applied, first-appearance order kept
    assert plan.series[0].directions == ("Discharge", "Charge")
    assert [(direction, list(x), list(y)) for direction, x, y in segments] == [("Discharge", [0, 3], [10, 13]), ("Charge", [1], [11])]


def test_segments_without_direction_and_with_everything_filtered__tc_ge03_ep_010() -> None:
    """TC-GE03-EP-010: no direction column -> one segment; filter removing all -> none."""
    # Given: one plain series and one whose directions are all filtered out
    frame = pd.DataFrame({"t": [0, 1], "v": [1, 2], "d": ["Rest", "Rest"]})
    plan = build_plot_plan(frame, GraphSpec(series=(SeriesSpec(y="v"), SeriesSpec(y="v", direction="d")), direction_filter=("Charge",)))
    data = PlotData(frames=(frame,))
    # When/Then: the plain series is one undirected segment, the filtered one is empty
    ((direction, x_values, y_values),) = data.segments(plan.series[0])
    assert (direction, list(x_values), list(y_values)) == (None, [0, 1], [1, 2])
    assert plan.series[1].directions == ()
    assert data.segments(plan.series[1]) == ()


def test_with_labels_relabels_series_and_titles__tc_ge03_ep_011() -> None:
    """TC-GE03-EP-011: with_labels recomputes legend roles and individual titles, keeps stems."""
    # Given: a two-series plan with individual figures
    plan = build_plot_plan(_multi_y(), GraphSpec(title="cell"))
    # When: relabelling both series with one shared label
    relabelled = plan.with_labels(["same", "same"])
    # Then: labels, legend roles, titles and origins change; stems do not
    assert [(s.label, s.show_in_legend) for s in relabelled.series] == [("same", True), ("same", False)]
    assert [f.title for f in relabelled.figures] == ["cell", "cell - same", "cell - same"]
    assert [f.stem for f in relabelled.figures] == [f.stem for f in plan.figures]
    assert relabelled.origins["series[s001].label"] == "explicit"
    assert plan.series[0].label == "Voltage"


def test_render_graph_accepts_only_a_spec__tc_ge03_ep_012() -> None:
    """TC-GE03-EP-012: advanced callers configure through the spec, never through competing keywords."""
    # Given: the render_graph signature
    parameters = inspect.signature(engine.render_graph).parameters
    # Then: it is (source, spec, *, output) and a legacy keyword is a TypeError
    assert list(parameters) == ["source", "spec", "output"]
    assert parameters["output"].kind is inspect.Parameter.KEYWORD_ONLY
    with pytest.raises(TypeError):
        engine.render_graph(_multi_y(), GraphSpec(), mode="individual")  # type: ignore[call-arg]


def test_csv2graph_default_behaviour_is_unchanged__tc_ge03_ep_013(tmp_path: Path) -> None:
    """TC-GE03-EP-013: csv2graph("file.csv") keeps its documented default behaviour."""
    # Given: a one-series CSV copied into tmp_path
    csv_path = _copy_fixture("simple.csv", tmp_path)
    # When: calling csv2graph with no options
    returned = csv2graph(csv_path)
    # Then: it returns None and writes exactly {stem}.png next to the CSV
    assert returned is None
    assert sorted(p.name for p in tmp_path.iterdir()) == ["simple.csv", "simple.png"]


def test_plot_from_dataframe_positional_return_fig_and_save_semantics__tc_ge03_ep_013(tmp_path: Path) -> None:
    """TC-GE03-EP-013: 27 positional arguments, return_fig list shape and save semantics are kept."""
    # Given: the v1 positional call with return_fig as the 27th argument
    frame = _multi_y()
    positional = [frame, tmp_path / "figs", None, None, False, False, False, "overlay", None, None, None, None, None,
                  "cell", None, None, None, None, None, None, None, False, False, False, None, None, True]
    assert len(positional) == 27
    # When: calling it, and calling the save path
    artifacts = plot_from_dataframe(*positional)
    saved = plot_from_dataframe(frame, tmp_path / "saved", title="cell")
    # Then: return_fig yields MatplotlibArtifacts and writes nothing; save returns None and writes the v1 set
    assert isinstance(artifacts, list)
    assert [(type(a), a.filename, a.metadata) for a in artifacts] == [
        (MatplotlibArtifact, "cell.png", {"format": "png"}),
        (MatplotlibArtifact, "cell_voltage_(v).png", {"format": "png"}),
        (MatplotlibArtifact, "cell_current_(a).png", {"format": "png"}),
    ]
    assert not (tmp_path / "figs").exists()
    assert saved is None
    assert sorted(p.name for p in (tmp_path / "saved").iterdir()) == ["cell.png", "cell_current_(a).png", "cell_voltage_(v).png"]


@pytest.mark.parametrize(("cls", "bases"), [
    (UnknownReaderError, (InvalidCSVFormatError, ValueError)),
    (AmbiguousFormatError, (InvalidCSVFormatError, ValueError)),
    (DuplicateReaderError, (GraphPlottingError, ValueError)),
    (ReaderPluginError, (GraphPlottingError,)),
    (RendererUnavailableError, (RendererError, ImportError)),
    (UnsupportedFormatError, (RendererError, ValueError)),
    (OutputPathError, (GraphPlottingError, ValueError)),
    (ArtifactCollisionError, (GraphPlottingError, ValueError)),
    (PlotRequestError, (PlotConfigError, ValueError)),
])
def test_graph_exceptions_keep_builtin_bases__tc_ge03_ep_014(cls: type[Exception], bases: tuple[type, ...]) -> None:
    """TC-GE03-EP-014: every graph error is also the builtin type the legacy path raised."""
    # Given/When: the class
    # Then: it subclasses each listed base
    assert all(issubclass(cls, base) for base in bases)


def test_ambiguous_format_error_carries_the_decision__tc_ge03_ep_014() -> None:
    """TC-GE03-EP-014: AmbiguousFormatError exposes the decision it could not make."""
    # Given/When: an ambiguous-format error
    decision = object()
    error = AmbiguousFormatError("Ambiguous table format", decision=decision)
    # Then: the decision and message are kept
    assert error.decision is decision
    assert str(error) == "Ambiguous table format"


GE03_EXPORTS = ("render_graph", "build_plot_plan", "GraphSpec", "SeriesSpec", "AxisSpec", "LegendSpec", "StyleSpec",
                "OutputSpec", "PlotPlan", "SeriesPlan", "FigurePlan", "GraphDiagnostic", "PlotData", "GraphResult", "Artifact")


def test_public_surface_exports_ge03_names_only__tc_ge03_ep_015() -> None:
    """TC-GE03-EP-015: the contract is public; internal helpers are not exported."""
    # Given/When: the graph package surface
    exported = set(graph_pkg.__all__)
    # Then: every GE-03 name is exported and resolves to its defining module
    assert set(GE03_EXPORTS) <= exported
    assert graph_pkg.GraphDiagnostic is GraphDiagnostic
    assert graph_pkg.render_graph is engine.render_graph
    assert graph_pkg.PlotPlan is PlotPlan
    stub = (Path(graph_pkg.__file__).with_suffix(".pyi")).read_text(encoding="utf-8")
    assert all(f"{name} as {name}" in stub for name in GE03_EXPORTS)
    # And: internal machinery stays private
    assert exported.isdisjoint({"reserve_stems", "series_stem", "validate_plot_request", "naming", "compat", "_as_frames", "_PlanRenderer", "_plan_to_legacy_config"})


def test_duplicate_column_labels_resolve_positionally__tc_ge03_ep_016() -> None:
    """TC-GE03-EP-016: duplicate labels work when addressed by position or by default selection."""
    # Given: a frame with two columns literally labelled "y"
    frame = pd.DataFrame([[0, 1, 2], [1, 3, 4]], columns=["x", "y", "y"])
    # When: planning by default and by position
    default = build_plot_plan(frame)
    positional = build_plot_plan(frame, GraphSpec(series=(SeriesSpec(y=2),)))
    # Then: the positions are kept and the stems are made unique
    assert [s.y_index for s in default.series] == [1, 2]
    assert positional.series[0].y_index == 2
    assert [f.stem for f in default.figures] == ["plot", "plot_y_s000", "plot_y_s001"]


def test_marks_axes_and_direction_colours_are_drawn_from_the_plan__tc_ge03_ep_017() -> None:
    """TC-GE03-EP-017: mark, axis settings and caller colours reach the drawn figure."""
    # Given: a scatter request with log x, inverted y, x-only grid, limits and a direction colour
    frame = pd.DataFrame({"x": [1, 2, 3, 4], "y": [1, 2, 3, 4], "d": ["Charge", "Charge", "Rest", "Rest"]})
    spec = GraphSpec(
        mark="scatter", title="t", layout="both",
        series=(SeriesSpec(y="y", direction="d"),),
        x_axis=AxisSpec(scale="log", grid=True, limits=(1, 10)), y_axis=AxisSpec(invert=True, label="Y!"),
        direction_colors={"Charge": "red"},
    )
    # When: rendering in memory
    overlay, individual = (a.figure.axes[0] for a in engine.render_graph(frame, spec).artifacts)
    # Then: scatter collections, log x, limits, inverted y, explicit label, title and x-only grid
    assert len(overlay.collections) == 2 and all(isinstance(c, PathCollection) for c in overlay.collections)
    assert to_hex(overlay.collections[0].get_facecolor()[0]) == to_hex("red")
    assert overlay.get_xscale() == "log"
    assert overlay.get_xlim() == (1.0, 10.0)
    assert overlay.yaxis_inverted()
    assert overlay.get_ylabel() == "Y!"
    assert overlay.get_title() == "t"
    assert any(line.get_visible() for line in overlay.xaxis.get_gridlines())
    assert not any(line.get_visible() for line in overlay.yaxis.get_gridlines())
    # And: the individual figure lists one legend entry per direction
    assert individual.get_title() == "t - Y"
    assert [text.get_text() for text in individual.get_legend().get_texts()] == ["Charge", "Rest"]


def test_individual_figure_without_direction_draws_one_line_and_no_legend__tc_ge03_ep_017() -> None:
    """TC-GE03-EP-017: individual figures keep the v1 look (default colour, no legend, no info text)."""
    # Given: two plain series and legend info text
    spec = GraphSpec(legend=LegendSpec(info="note"))
    # When: rendering in memory
    artifacts = engine.render_graph(_multi_y(), spec).artifacts
    individual = artifacts[1].figure.axes[0]
    # Then: one line, the default colour, no legend and no extra text
    assert [type(artist) for artist in individual.get_lines()] == [Line2D]
    assert to_hex(individual.get_lines()[0].get_color()) == to_hex(mpl.rcParams["axes.prop_cycle"].by_key()["color"][0])
    assert individual.get_legend() is None
    assert [text.get_text() for text in individual.texts] == []
    assert "note" in [text.get_text() for text in artifacts[0].figure.axes[0].texts]


def test_individual_figure_with_one_direction_has_no_legend__tc_ge03_ep_017() -> None:
    """TC-GE03-EP-017: like v1, an individual legend needs more than one direction entry."""
    # Given: a single direction value
    frame = pd.DataFrame({"x": [1, 2], "y": [1, 2], "d": ["Charge", "Charge"]})
    # When: rendering the individual figure
    axes = engine.render_graph(frame, GraphSpec(layout="individual", series=(SeriesSpec(y=1, direction=2),))).artifacts[0].figure.axes[0]
    # Then: one line, no legend
    assert len(axes.get_lines()) == 1
    assert axes.get_legend() is None


# --------------------------------------------------------------------------- negative


@pytest.mark.parametrize("version", [0, 2, True, "1"])
def test_unsupported_spec_versions_are_rejected__tc_ge03_neg_001(version: Any) -> None:
    """TC-GE03-NEG-001: only SPEC_VERSION is accepted."""
    # Given/When/Then: constructing a spec with another version fails typed
    with pytest.raises(PlotRequestError) as excinfo:
        GraphSpec(version=version)
    assert excinfo.value.reason == "invalid_spec"
    assert SPEC_VERSION == 1


@pytest.mark.parametrize(("factory", "fragment"), [
    (lambda: GraphSpec(layout="grid"), "layout"),  # type: ignore[arg-type]
    (lambda: GraphSpec(mark="bar"), "mark"),  # type: ignore[arg-type]
    (lambda: GraphSpec(x_default="last"), "x_default"),  # type: ignore[arg-type]
    (lambda: GraphSpec(label_style="title"), "label_style"),  # type: ignore[arg-type]
    (lambda: GraphSpec(unit_policy="convert"), "unit_policy"),  # type: ignore[arg-type]
    (lambda: AxisSpec(scale="ln"), "scale"),  # type: ignore[arg-type]
    (lambda: AxisSpec(tick_format="hex"), "tick_format"),  # type: ignore[arg-type]
    (lambda: LegendSpec(policy="nope"), "Invalid legend policy"),  # type: ignore[arg-type]
    (lambda: OutputSpec(DirectorySink(Path("unused")), on_existing="skip"), "on_existing"),  # type: ignore[arg-type]
    (lambda: GraphSpec(layout=None), "layout"),  # type: ignore[arg-type]
])
def test_choice_values_outside_their_literal_are_rejected__tc_ge03_neg_002(factory: Any, fragment: str) -> None:
    """TC-GE03-NEG-002: runtime callers cannot smuggle an invalid choice past the types."""
    # Given/When/Then: construction fails with invalid_spec naming the field
    with pytest.raises(PlotRequestError, match=fragment) as excinfo:
        factory()
    assert excinfo.value.reason == "invalid_spec"


@pytest.mark.parametrize("factory", [
    lambda: SeriesSpec(y=1.5),  # type: ignore[arg-type]
    lambda: SeriesSpec(y=True),
    lambda: SeriesSpec(y=1, x=[0]),  # type: ignore[arg-type]
    lambda: SeriesSpec(y=1, direction=2.0),  # type: ignore[arg-type]
    lambda: GraphSpec(x=False),
    lambda: GraphSpec(series=(1,)),  # type: ignore[arg-type]
])
def test_wrong_column_reference_types_are_type_errors__tc_ge03_neg_003(factory: Any) -> None:
    """TC-GE03-NEG-003: a column is a position (int) or a label (str); bool is neither."""
    # Given/When/Then
    with pytest.raises(TypeError):
        factory()


@pytest.mark.parametrize(("spec", "reason"), [
    (GraphSpec(series=(SeriesSpec(y="missing"),)), "unknown_column"),
    (GraphSpec(series=(SeriesSpec(y=-1),)), "unknown_column"),
    (GraphSpec(series=(SeriesSpec(y=3),)), "unknown_column"),
    (GraphSpec(x="nope"), "unknown_column"),
    (GraphSpec(series=(SeriesSpec(y=1, direction="d"),)), "unknown_column"),
    (GraphSpec(series=(SeriesSpec(y="y"),)), "ambiguous_column"),
])
def test_unresolvable_columns_are_rejected_before_rendering__tc_ge03_neg_004(spec: GraphSpec, reason: str, tmp_path: Path) -> None:
    """TC-GE03-NEG-004: column references resolve to exactly one position or fail typed."""
    # Given: a frame with three columns, two labelled "y"
    frame = pd.DataFrame([[0, 1, 2]], columns=["x", "y", "y"])
    # When/Then: rendering fails with the reason and writes nothing
    with pytest.raises(PlotRequestError) as excinfo:
        engine.render_graph(frame, spec, output=OutputSpec(DirectorySink(tmp_path / "out")))
    assert excinfo.value.reason == reason
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("frames", [
    pd.DataFrame({"x": [1, 2]}),
    pd.DataFrame(),
    [],
])
def test_requests_without_series_fail_with_the_legacy_message__tc_ge03_neg_005(frames: Any, tmp_path: Path) -> None:
    """TC-GE03-NEG-005: zero series is a ValueError with the legacy text, before any file exists."""
    # Given/When/Then
    with pytest.raises(ValueError, match="at least one y column"):
        engine.render_graph(frames, output=OutputSpec(DirectorySink(tmp_path / "out")))
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("source", ["data.csv", Path("data.csv"), b"a,b", {"x": [1]}, [pd.DataFrame({"x": [1], "y": [2]}), "frame"], 3])
def test_non_frame_sources_are_type_errors__tc_ge03_neg_006(source: Any, tmp_path: Path) -> None:
    """TC-GE03-NEG-006: until readers exist, the source must be DataFrames (a str is not iterated)."""
    # Given/When/Then
    with pytest.raises(TypeError, match="DataFrame"):
        engine.render_graph(source, output=OutputSpec(DirectorySink(tmp_path / "out")))
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("kwargs", [
    {"formats": ()},
    {"formats": ("",)},
    {"formats": (" ",)},
    {"formats": (1,)},
    {"base_name": ""},
    {"dpi": 0},
    {"dpi": -1},
    {"dpi": True},
    {"dpi": 72.0},
])
def test_invalid_output_specs_are_rejected__tc_ge03_neg_007(kwargs: dict[str, Any]) -> None:
    """TC-GE03-NEG-007: an OutputSpec that cannot name or rasterize an artifact is rejected."""
    # Given/When/Then
    with pytest.raises(PlotRequestError) as excinfo:
        OutputSpec(DirectorySink(Path("unused")), **kwargs)
    assert excinfo.value.reason == "invalid_spec"


@pytest.mark.parametrize("fmt", ["html", "jpg"])
def test_unsupported_formats_fail_before_anything_exists__tc_ge03_neg_008(fmt: str, tmp_path: Path) -> None:
    """TC-GE03-NEG-008: a format no renderer covers is rejected at artifact planning."""
    # Given/When/Then
    with pytest.raises(UnsupportedFormatError, match=fmt):
        engine.render_graph(_multi_y(), output=OutputSpec(DirectorySink(tmp_path / "out"), formats=("png", fmt)))
    assert not (tmp_path / "out").exists()
    assert plt.get_fignums() == []


def test_on_existing_error_rejects_before_rendering__tc_ge03_neg_009(tmp_path: Path) -> None:
    """TC-GE03-NEG-009: on_existing="error" fails for an existing destination and writes nothing."""
    # Given: an existing overlay file
    tmp_path.joinpath("plot.png").write_bytes(b"old")
    # When/Then: rendering fails, the old file is untouched and no individual file appears
    with pytest.raises(ArtifactCollisionError, match="already exist"):
        engine.render_graph(_multi_y(), output=OutputSpec(DirectorySink(tmp_path), on_existing="error"))
    assert sorted(p.name for p in tmp_path.iterdir()) == ["plot.png"]
    assert tmp_path.joinpath("plot.png").read_bytes() == b"old"


def test_default_overwrite_is_recorded__tc_ge03_neg_009(tmp_path: Path) -> None:
    """TC-GE03-NEG-009: the default overwrite is never silent: the result and manifest record it."""
    # Given: an existing overlay file
    tmp_path.joinpath("plot.png").write_bytes(b"old")
    # When: rendering with the default policy
    result = engine.render_graph(_multi_y(), output=OutputSpec(DirectorySink(tmp_path)))
    # Then: only the overlay is marked as replaced, and it was rewritten
    assert [a.replaced_existing for a in result.artifacts] == [True, False, False]
    assert [entry["replaced_existing"] for entry in result.manifest()["artifacts"]] == [True, False, False]
    assert tmp_path.joinpath("plot.png").read_bytes()[:4] == b"\x89PNG"


@pytest.mark.parametrize(("filename", "fragment"), [
    ("a/b.png", "contains path separators"),
    ("a\\b.png", "contains path separators"),
    ("..png", "contains path separators"),
    ("", "contains path separators"),
])
def test_directory_sink_rejects_unsafe_names__tc_ge03_neg_010(filename: str, fragment: str, tmp_path: Path) -> None:
    """TC-GE03-NEG-010: unsafe names are OutputPathError with the legacy message, nothing created."""
    # Given/When/Then
    with pytest.raises(OutputPathError, match=fragment):
        DirectorySink(tmp_path / "out").resolve("individual", filename)
    assert not (tmp_path / "out").exists()


def test_directory_sink_rejects_a_file_as_directory_before_rendering__tc_ge03_neg_010(tmp_path: Path) -> None:
    """TC-GE03-NEG-010: an output "directory" that is a file fails before any figure is rendered."""
    # Given: a file where the main-image directory should be
    blocker = tmp_path / "main"
    blocker.write_text("x")
    # When/Then: a ValueError with the legacy text, and no individual file written either
    with pytest.raises(OutputPathError, match="Output path is not a directory") as excinfo:
        engine.render_graph(_multi_y(), output=OutputSpec(DirectorySink(tmp_path / "out", main_image_dir=blocker)))
    assert isinstance(excinfo.value, ValueError)
    assert not (tmp_path / "out").exists()
    assert plt.get_fignums() == []


def test_directory_sink_rejects_a_symlink_escape__tc_ge03_neg_010(tmp_path: Path) -> None:
    """TC-GE03-NEG-010: a destination that resolves outside its directory is a security violation."""
    # Given: out/plot.png is a symlink to a file outside out/
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "plot.png").symlink_to(tmp_path / "outside.png")
    # When/Then
    with pytest.raises(OutputPathError, match="Security violation"):
        engine.render_graph(_multi_y(), output=OutputSpec(DirectorySink(tmp_path / "out")))
    assert not (tmp_path / "outside.png").exists()


def test_directory_sink_routes_roles_and_accepts_str_dirs__tc_ge03_neg_010(tmp_path: Path) -> None:
    """TC-GE03-NEG-010 (positive control): html and main images go to their own directories."""
    # Given: str directories
    sink = DirectorySink(str(tmp_path / "o"), main_image_dir=str(tmp_path / "m"), html_dir=str(tmp_path / "h"))  # type: ignore[arg-type]
    # When/Then: each role maps to its directory, nothing created by resolve
    assert [sink.directory_for(role).name for role in ("main_image", "individual", "html")] == ["m", "o", "h"]
    assert sink.resolve("html", "p.html") == (tmp_path / "h").resolve() / "p.html"
    assert not (tmp_path / "h").exists()
    assert DirectorySink(tmp_path).directory_for("html") == tmp_path


class _OneFileSink:
    """A custom sink that maps every artifact to the same file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.writes = 0

    def resolve(self, role: str, filename: str) -> Path:
        return self.path

    def write(self, role: str, filename: str, content: bytes) -> Path:
        self.writes += 1
        return self.path


def test_destinations_must_be_unique_within_a_run__tc_ge03_neg_011(tmp_path: Path) -> None:
    """TC-GE03-NEG-011: two artifacts may never land on the same file, whatever the sink does."""
    # Given: a sink that collapses every name
    sink = _OneFileSink(tmp_path / "all.png")
    # When/Then: planning fails before any write
    with pytest.raises(ArtifactCollisionError, match="same destination"):
        engine.render_graph(_multi_y(), output=OutputSpec(sink))  # type: ignore[arg-type]
    assert sink.writes == 0


@pytest.mark.parametrize(("path", "figure"), [(None, None), (Path("p.png"), object())])
def test_artifact_needs_exactly_one_of_path_and_figure__tc_ge03_neg_012(path: Path | None, figure: Any) -> None:
    """TC-GE03-NEG-012: every artifact is either a file or an in-memory handle."""
    # Given/When/Then
    with pytest.raises(ValueError, match="exactly one of path or figure"):
        Artifact(figure_id="overlay", kind="overlay", role="main_image", format="png", renderer="matplotlib",
                 series_ids=("s000",), labels=("A",), path=path, figure=figure)


def test_contract_values_are_frozen__tc_ge03_neg_013() -> None:
    """TC-GE03-NEG-013: specs, plans and results cannot be changed after construction."""
    # Given: caller-owned mappings passed into a spec
    colors = {"Charge": "red"}
    params = {"font.size": 9}
    spec = GraphSpec(direction_colors=colors, style=StyleSpec(rc_params=params), series=[SeriesSpec(y=1)], direction_filter=["Charge"])  # type: ignore[arg-type]
    plan = build_plot_plan(_multi_y(), spec)
    # When: the caller mutates its own dicts afterwards
    colors["Charge"] = "blue"
    params["font.size"] = 99
    # Then: the spec is unaffected, sequences became tuples and every mapping is read-only
    assert spec.direction_colors["Charge"] == "red"
    assert spec.style.rc_params["font.size"] == 9
    assert isinstance(spec.series, tuple) and spec.direction_filter == ("Charge",)
    for target, name in ((spec, "title"), (spec.series[0], "y"), (plan, "series"), (plan.series[0], "label"), (plan.figures[0], "stem")):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(target, name, None)
    for mapping in (spec.direction_colors, spec.style.rc_params, plan.origins, plan.direction_colors):
        with pytest.raises(TypeError):
            mapping["x"] = "y"  # type: ignore[index]


def test_failure_after_the_first_figure_writes_nothing__tc_ge03_neg_014(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE03-NEG-014: every figure is rendered and exported before the first write."""
    # Given: an exporter that fails on the second figure
    calls = {"n": 0}
    original = engine._export

    def flaky(fig: Any, fmt: str, dpi: int) -> bytes:
        calls["n"] += 1
        if calls["n"] == 2:
            msg = "disk full"
            raise OSError(msg)
        return original(fig, fmt, dpi)

    monkeypatch.setattr(engine, "_export", flaky)
    # When/Then: the error propagates, nothing is written and no figure stays open
    with pytest.raises(OSError, match="disk full"):
        engine.render_graph(_multi_y(), output=OutputSpec(DirectorySink(tmp_path / "out")))
    assert not (tmp_path / "out").exists()
    assert plt.get_fignums() == []


def test_in_memory_failure_closes_figures_already_rendered__tc_ge03_neg_014(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE03-NEG-014: handles the caller never receives are closed."""
    # Given: a detach step that fails on the second figure
    calls = {"n": 0}
    original = engine._detach

    def flaky(fig: Any) -> None:
        calls["n"] += 1
        if calls["n"] == 2:
            msg = "boom"
            raise RuntimeError(msg)
        original(fig)

    monkeypatch.setattr(engine, "_detach", flaky)
    # When/Then
    with pytest.raises(RuntimeError, match="boom"):
        engine.render_graph(_multi_y())
    assert plt.get_fignums() == []


@pytest.mark.parametrize("labels", [["only"], ["a", "b", "c"], []])
def test_with_labels_rejects_a_wrong_count__tc_ge03_neg_015(labels: list[str]) -> None:
    """TC-GE03-NEG-015: one label per series, with the node error text."""
    # Given: a two-series plan
    plan = build_plot_plan(_multi_y())
    # When/Then
    with pytest.raises(ValueError, match=f"{len(labels)} labels for 2 series"):
        plan.with_labels(labels)


@pytest.mark.parametrize("factory", [
    lambda: AxisSpec(limits=(1.0,)),  # type: ignore[arg-type]
    lambda: AxisSpec(limits=(1.0, 2.0, 3.0)),  # type: ignore[arg-type]
    lambda: StyleSpec(figure_size=(4.0,)),  # type: ignore[arg-type]
    lambda: StyleSpec(rc_params=[("font.size", 9)]),  # type: ignore[arg-type]
    lambda: GraphSpec(direction_colors=["red"]),  # type: ignore[arg-type]
])
def test_malformed_pairs_and_mappings_are_rejected__tc_ge03_neg_016(factory: Any) -> None:
    """TC-GE03-NEG-016: limits and sizes are pairs; rc params and colours are mappings."""
    # Given/When/Then
    with pytest.raises(PlotRequestError) as excinfo:
        factory()
    assert excinfo.value.reason == "invalid_spec"


def test_explicit_x_with_index_default_is_contradictory__tc_ge03_neg_017() -> None:
    """TC-GE03-NEG-017: the spec cannot say both "use column x" and "use the index"."""
    # Given/When/Then
    with pytest.raises(PlotRequestError) as excinfo:
        GraphSpec(x=0, x_default="index")
    assert excinfo.value.reason == "contradictory_switches"


# --------------------------------------------------------------------------- BV


def test_identical_headers_get_suffixed_stems_and_diagnostics__tc_ge03_bv_002(tmp_path: Path) -> None:
    """TC-GE03-BV-002: a collision is resolved in the plan and reported on the result and artifacts."""
    # Given: two identical headers
    frame = pd.DataFrame([[0, 1, 2], [1, 2, 3]], columns=["x", "Voltage", "voltage"])
    # When: rendering
    result = engine.render_graph(frame, output=OutputSpec(DirectorySink(tmp_path), base_name="p"))
    # Then: both individual stems are suffixed, one warning diagnostic, attached to both individual artifacts
    assert [a.path.name for a in result.artifacts if a.path] == ["p.png", "p_voltage_s000.png", "p_voltage_s001.png"]
    assert [(d.code, d.severity, d.series_ids) for d in result.diagnostics] == [("filename_collision", "warning", ("s000", "s001"))]
    assert [len(a.diagnostics) for a in result.artifacts] == [0, 1, 1]
    assert result.manifest()["diagnostics"][0]["code"] == "filename_collision"


def test_dpi_lower_bound_is_accepted__tc_ge03_bv_003(tmp_path: Path) -> None:
    """TC-GE03-BV-003: dpi=1 is the smallest value the spec accepts; a low dpi renders."""
    # Given: the validation boundary (dpi=1 renders no text in Matplotlib, so render at 10)
    assert OutputSpec(DirectorySink(tmp_path), dpi=1).dpi == 1
    # When
    result = engine.render_graph(pd.DataFrame({"x": [1, 2], "y": [1, 2]}), output=OutputSpec(DirectorySink(tmp_path), dpi=10))
    # Then: one small PNG
    assert [a.path.name for a in result.artifacts if a.path] == ["plot.png"]
    assert (tmp_path / "plot.png").stat().st_size > 0


@pytest.mark.parametrize(("index_name", "expected"), [(None, "index"), ("cycle", "cycle")])
def test_index_as_x__tc_ge03_bv_004(index_name: str | None, expected: str) -> None:
    """TC-GE03-BV-004: x_default="index" plots every column against the frame index."""
    # Given: a frame without an x column
    frame = pd.DataFrame({"a": [1, 2, 3], "b": [3, 2, 1]}, index=pd.Index([10, 20, 30], name=index_name))
    # When: planning and rendering against the index
    spec = GraphSpec(x_default="index", layout="individual")
    plan = build_plot_plan(frame, spec)
    figure = engine.render_graph(frame, spec).artifacts[0].figure
    # Then: both columns are series, x is the index
    assert [(s.x_index, s.x_name, s.y_name) for s in plan.series] == [(None, expected, "a"), (None, expected, "b")]
    assert list(figure.axes[0].get_lines()[0].get_xdata()) == [10, 20, 30]


@pytest.mark.parametrize("limits", [(None, None), (0.0, None), (None, 5.0), (5.0, 1.0)])
def test_axis_limits_pass_through_the_plan__tc_ge03_bv_005(limits: tuple[float | None, float | None]) -> None:
    """TC-GE03-BV-005: limits are recorded as given (their validation belongs to GE-13)."""
    # Given/When
    plan = build_plot_plan(_multi_y(), GraphSpec(x_axis=AxisSpec(limits=limits)))
    # Then
    assert plan.x_axis.limits == limits
