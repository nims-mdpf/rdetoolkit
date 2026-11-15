"""Fix round 1 / R-5, R-7, R-8, R-9: engine correctness found in review.

* R-5: a legacy ``MatplotlibRenderer.render_*`` call never reuses a plan built for an
  earlier call, so renaming columns in place between two calls is honoured.
* R-7: a diagnostic is attached to the artifacts of the figures it applies to:
  ``unit_mismatch`` to the overlay figure that mixes units, ``unit_unknown`` to the
  overlay sharing the axis, ``filename_collision`` to the figures it renamed.
* R-8: ``numbers.Integral`` column positions (``np.int64``) are accepted and
  normalized to ``int``; ``bool`` stays rejected.
* R-9: two destinations collide only in the same (resolved) directory with the same
  file-name collision key; directories are compared exactly.

EP table:
| TC | Partition | Input | Expected |
|----|-----------|-------|----------|
| TC-FIX1-R5-EP-001 | in-place rename between render_overlay calls | df.columns = [...] | second figure shows the new labels |
| TC-FIX1-R5-EP-002 | in-place rename between render_individual calls | df.columns = [...] | second title / y label use the new header |
| TC-FIX1-R5-EP-003 | one legacy call, N individual figures | collect_render_results | one plan per backend for the whole call |
| TC-FIX1-R7-EP-001 | unit_mismatch, layout both, policy warn/allow | V + A | on the overlay artifact (and manifest), not on s000/s001 |
| TC-FIX1-R7-EP-002 | unit_unknown | V + unit-less, layout both | on the overlay artifact only |
| TC-FIX1-R7-EP-003 | filename_collision | Voltage / voltage | on the two renamed individual artifacts |
| TC-FIX1-R8-EP-001 | np.int64 positions | GraphSpec(x=np.int64(0)), SeriesSpec(y=np.int64(1), direction=np.int16(2)) | stored as int, plan resolves them |
| TC-FIX1-R9-EP-001 | same file name in directories differing by case | custom sink, "Out" / "out" | both written, no collision |

Negative table:
| TC | Partition | Input | Expected |
|----|-----------|-------|----------|
| TC-FIX1-R7-NEG-001 | split overlays do not mix units | unit_policy="split" | unit_mismatch on no artifact, still on the result |
| TC-FIX1-R7-NEG-002 | layout individual | V + A, allow | no artifact carries unit_mismatch |
| TC-FIX1-R8-NEG-001 | bool / np.bool_ / float positions | True, np.True_, 1.0, np.float64(1) | TypeError |
| TC-FIX1-R9-NEG-001 | same directory, names equal by collision key | custom sink naming two files "figure.png" / "FIGURE.png" | ArtifactCollisionError, nothing written |
| TC-FIX1-R9-NEG-002 | same directory, same name | custom sink naming every individual "figure.png" | ArtifactCollisionError, nothing written |
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from rdetoolkit.graph import compat
from rdetoolkit.graph.engine import render_graph
from rdetoolkit.graph.exceptions import ArtifactCollisionError, GraphUserWarning
from rdetoolkit.graph.models import PlotConfig, PlotMode
from rdetoolkit.graph.outputs import ArtifactRole, DirectorySink
from rdetoolkit.graph.plan import build_plot_plan
from rdetoolkit.graph.renderers.matplotlib_renderer import MatplotlibRenderer
from rdetoolkit.graph.result import Artifact
from rdetoolkit.graph.spec import GraphSpec, OutputSpec, SeriesSpec
from rdetoolkit.graph.strategies import collect_render_results


def _codes(artifact: Artifact) -> list[str]:
    return [item.code for item in artifact.diagnostics]


def _va() -> pd.DataFrame:
    return pd.DataFrame({"t (s)": [0, 1, 2], "a (V)": [1.0, 2.0, 3.0], "b (A)": [3.0, 2.0, 1.0]})


# --- R-5 -------------------------------------------------------------------------------


def test_in_place_rename_between_overlay_calls__tc_fix1_r5_ep_001() -> None:
    """TC-FIX1-R5-EP-001: the renderer does not return a plan of the old columns."""
    # Given: one renderer, one frame, one config
    renderer = MatplotlibRenderer()
    df = pd.DataFrame({"t": [0, 1], "a": [1, 2], "b": [2, 1]})
    config = PlotConfig(x_col=0, y_cols=[1, 2])
    first = renderer.render_overlay(df, config)
    # When: the frame's columns are renamed in place and the overlay is drawn again
    df.columns = ["t", "p", "q"]
    second = renderer.render_overlay(df, config)
    # Then: the legend of the second figure names the new columns
    assert [text.get_text() for text in first.axes[0].get_legend().get_texts()] == ["A", "B"]
    assert [text.get_text() for text in second.axes[0].get_legend().get_texts()] == ["P", "Q"]


def test_in_place_rename_between_individual_calls__tc_fix1_r5_ep_002() -> None:
    """TC-FIX1-R5-EP-002: same for render_individual (title and default y label)."""
    renderer = MatplotlibRenderer()
    df = pd.DataFrame({"t": [0, 1], "a": [1, 2]})
    config = PlotConfig(x_col=0, y_cols=[1])
    first = renderer.render_individual(df, config, 1)
    df.columns = ["t", "z"]
    second = renderer.render_individual(df, config, 1)
    assert first.axes[0].get_title() == "Plot - A"
    assert second.axes[0].get_title() == "Plot - Z"


def test_one_legacy_call_plans_once_per_backend__tc_fix1_r5_ep_003(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-FIX1-R5-EP-003: N individual figures of one call still share one plan."""
    # Given: a spy on the legacy planner
    calls: list[Any] = []
    original = compat.plan_from_config

    def spy(*args: Any, **kwargs: Any) -> Any:
        calls.append(kwargs["label_of"])
        return original(*args, **kwargs)

    monkeypatch.setattr(compat, "plan_from_config", spy)
    df = pd.DataFrame({"t": [0, 1], "a": [1, 2], "b": [2, 1], "c": [3, 3]})
    # When: one overlay call with three individual figures
    collections = collect_render_results(df, PlotConfig(x_col=0, y_cols=[1, 2, 3]), PlotMode.OVERLAY)
    # Then: four figures from a single Matplotlib plan
    assert len(collections.overlay) + len(collections.individual) == 4
    assert calls == [compat.legacy_mpl_label]


# --- R-7 -------------------------------------------------------------------------------


@pytest.mark.parametrize("policy", ["warn", "allow"])
def test_unit_mismatch_on_the_overlay_artifact__tc_fix1_r7_ep_001(tmp_path: Path, policy: str) -> None:
    """TC-FIX1-R7-EP-001: the shared-axis diagnostic describes the overlay figure."""
    # Given: V + A plotted overlay + individual
    spec = GraphSpec(layout="both", unit_policy=policy)  # type: ignore[arg-type]
    # When
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", GraphUserWarning)
        result = render_graph(_va(), spec, output=OutputSpec(DirectorySink(tmp_path)))
    # Then: only the overlay artifact carries it, also in the manifest
    assert [(a.figure_id, _codes(a)) for a in result.artifacts] == [("overlay", ["unit_mismatch"]), ("s000", []), ("s001", [])]
    entries = result.manifest()["artifacts"]
    assert [[d["code"] for d in entry["diagnostics"]] for entry in entries] == [["unit_mismatch"], [], []]


def test_unit_unknown_on_the_overlay_artifact__tc_fix1_r7_ep_002(tmp_path: Path) -> None:
    """TC-FIX1-R7-EP-002: the unit-less series shares the overlay axis, not its own."""
    df = pd.DataFrame({"t (s)": [0, 1, 2], "a (V)": [1.0, 2.0, 3.0], "b": [3.0, 2.0, 1.0]})
    result = render_graph(df, GraphSpec(layout="both"), output=OutputSpec(DirectorySink(tmp_path)))
    assert [(a.figure_id, _codes(a)) for a in result.artifacts] == [("overlay", ["unit_unknown"]), ("s000", []), ("s001", [])]


def test_filename_collision_on_the_renamed_artifacts__tc_fix1_r7_ep_003(tmp_path: Path) -> None:
    """TC-FIX1-R7-EP-003: the collision diagnostic stays on the figures it renamed."""
    df = pd.DataFrame({"t": [0, 1], "Voltage": [1.0, 2.0], "voltage": [2.0, 1.0]})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", GraphUserWarning)
        result = render_graph(df, GraphSpec(layout="both"), output=OutputSpec(DirectorySink(tmp_path)))
    assert [(a.figure_id, _codes(a)) for a in result.artifacts] == [
        ("overlay", []), ("s000", ["filename_collision"]), ("s001", ["filename_collision"]),
    ]


def test_split_overlays_carry_no_mismatch__tc_fix1_r7_neg_001(tmp_path: Path) -> None:
    """TC-FIX1-R7-NEG-001: split overlays each hold one unit; the diagnostic stays on the result."""
    result = render_graph(_va(), GraphSpec(layout="both", unit_policy="split"), output=OutputSpec(DirectorySink(tmp_path)))
    assert all("unit_mismatch" not in _codes(a) for a in result.artifacts)
    assert [item.code for item in result.diagnostics] == ["unit_mismatch"]


def test_individual_layout_carries_no_mismatch__tc_fix1_r7_neg_002(tmp_path: Path) -> None:
    """TC-FIX1-R7-NEG-002: no overlay figure, so no artifact mixes units."""
    result = render_graph(_va(), GraphSpec(layout="individual", unit_policy="allow"), output=OutputSpec(DirectorySink(tmp_path)))
    assert [(a.figure_id, _codes(a)) for a in result.artifacts] == [("s000", []), ("s001", [])]


# --- R-8 -------------------------------------------------------------------------------


def test_numpy_integer_positions_are_normalized__tc_fix1_r8_ep_001() -> None:
    """TC-FIX1-R8-EP-001: np.int64 and friends are positions, stored as int."""
    # Given: numpy integer references
    series = SeriesSpec(y=np.int64(1), direction=np.int16(2))  # type: ignore[arg-type]
    spec = GraphSpec(x=np.int64(0), series=(series,), layout="overlay")  # type: ignore[arg-type]
    # When: planning
    frame = pd.DataFrame({"t": [0, 1], "v": [1.0, 2.0], "d": ["A", "B"]})
    plan = build_plot_plan(frame, spec)
    # Then: the references are plain ints and resolve as positions
    assert (type(spec.x), type(series.y), type(series.direction)) == (int, int, int)
    assert (plan.series[0].x_index, plan.series[0].y_index, plan.series[0].direction_index) == (0, 1, 2)


@pytest.mark.parametrize("ref", [True, np.True_, 1.0, np.float64(1)])
def test_bool_and_float_positions_rejected__tc_fix1_r8_neg_001(ref: Any) -> None:
    """TC-FIX1-R8-NEG-001: only integral, non-bool numbers are positions."""
    with pytest.raises(TypeError):
        SeriesSpec(y=ref)
    with pytest.raises(TypeError):
        GraphSpec(x=ref)


# --- R-9 -------------------------------------------------------------------------------


@dataclass(frozen=True)
class _FlatSink:
    """Names every file after its role: one directory per role, a fixed file name."""

    dirs: dict[str, Path]
    names: dict[str, str]

    def resolve(self, role: ArtifactRole, filename: str) -> Path:
        return self.dirs[role] / (self.names[role] + Path(filename).suffix)

    def write(self, role: ArtifactRole, filename: str, content: bytes) -> Path:
        path = self.resolve(role, filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path


def _single() -> pd.DataFrame:
    return pd.DataFrame({"t": [0, 1], "v": [1.0, 2.0]})


def _files(root: Path) -> list[str]:
    return sorted(str(path.relative_to(root)) for path in root.rglob("*") if path.is_file())


def test_same_name_in_directories_differing_by_case__tc_fix1_r9_ep_001(tmp_path: Path) -> None:
    """TC-FIX1-R9-EP-001: Out/figure.png and out/figure.png are different files here."""
    # Given: a case-sensitive filesystem (skip elsewhere) and a sink using "Out" and "out"
    (tmp_path / "probe").write_text("")
    if (tmp_path / "PROBE").exists():
        pytest.skip("case-insensitive filesystem")
    sink = _FlatSink({"main_image": tmp_path / "Out", "individual": tmp_path / "out", "html": tmp_path}, {"main_image": "figure", "individual": "figure", "html": "figure"})
    # When
    result = render_graph(_single(), GraphSpec(layout="both"), output=OutputSpec(sink))
    # Then: both artifacts written, no false collision
    assert [str(a.path.relative_to(tmp_path)) for a in result.artifacts if a.path is not None] == ["Out/figure.png", "out/figure.png"]
    assert _files(tmp_path) == ["Out/figure.png", "out/figure.png", "probe"]


@pytest.mark.parametrize("names", [{"main_image": "figure", "individual": "FIGURE", "html": "x"}, {"main_image": "figure", "individual": "figure", "html": "x"}])
def test_same_directory_same_key_collides__tc_fix1_r9_neg_001_002(tmp_path: Path, names: dict[str, str]) -> None:
    """TC-FIX1-R9-NEG-001/002: one directory, names equal by collision key -> typed error first."""
    sink = _FlatSink({"main_image": tmp_path / "out", "individual": tmp_path / "out", "html": tmp_path}, names)
    with pytest.raises(ArtifactCollisionError):
        render_graph(_single(), GraphSpec(layout="both"), output=OutputSpec(sink))
    assert _files(tmp_path) == []
