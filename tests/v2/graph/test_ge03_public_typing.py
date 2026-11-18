"""GE-03 (#709): the public graph contract is typed for consumers (mypy --strict).

A standalone consumer module is type-checked against the installed package in a
subprocess, outside the repository configuration, so a stale ``.pyi`` stub cannot
hide behind the implementation. The positive snippet doubles as the documented
example of the spec API.

EP table:

| Consumer | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| example | spec + plan + render_graph + result fields, both output modes | mypy --strict clean | TC-GE03-TYPE-EP-001 |
| example | the same example executed | runs, artifacts as typed | TC-GE03-TYPE-EP-002 |

Negative table:

| Consumer | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| GraphSpec | layout outside the Literal | [arg-type] | TC-GE03-TYPE-NEG-001 |
| SeriesSpec | float column reference | [arg-type] | TC-GE03-TYPE-NEG-002 |
| render_graph | legacy keyword (mode=) | [call-arg] | TC-GE03-TYPE-NEG-003 |
| Artifact.path | used as str without narrowing | [assignment] | TC-GE03-TYPE-NEG-004 |
| OutputSpec | sink that is not an ArtifactSink | [arg-type] | TC-GE03-TYPE-NEG-005 |
| render_graph | output passed positionally | "Too many positional arguments" | TC-GE03-TYPE-NEG-006 |
| PlotPlan | assignment to a frozen field | [misc] | TC-GE03-TYPE-NEG-007 |
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

EXAMPLE = '''from pathlib import Path

import pandas as pd
from matplotlib.figure import Figure

from rdetoolkit.graph import (
    Artifact,
    AxisSpec,
    FigurePlan,
    GraphDiagnostic,
    GraphResult,
    GraphSpec,
    LegendSpec,
    OutputSpec,
    PlotData,
    PlotPlan,
    SeriesPlan,
    SeriesSpec,
    StyleSpec,
    build_plot_plan,
    render_graph,
)
from rdetoolkit.graph.outputs import DirectorySink


def main(output_dir: Path) -> GraphResult:
    frame = pd.DataFrame({"time (s)": [0, 1, 2], "voltage (V)": [1.0, 2.0, 3.0], "state": ["Charge", "Charge", "Rest"]})
    spec = GraphSpec(
        x="time (s)",
        series=(SeriesSpec(y="voltage (V)", direction="state", label="V"),),
        layout="both",
        title="cell",
        y_axis=AxisSpec(scale="log", limits=(0.5, None)),
        legend=LegendSpec(policy="auto"),
        direction_colors={"Charge": "red"},
        style=StyleSpec(figure_size=(4.0, 3.0)),
    )
    plan: PlotPlan = build_plot_plan(frame, spec, base_name="cell")
    first: SeriesPlan = plan.series[0]
    figures: tuple[FigurePlan, ...] = plan.figures
    segments = PlotData(frames=(frame,)).segments(first)
    snapshot: dict[str, object] = plan.with_labels(["Voltage"]).to_dict()
    diagnostics: tuple[GraphDiagnostic, ...] = plan.diagnostics
    assert figures and segments and snapshot is not None and diagnostics == ()

    in_memory = render_graph(frame, spec)
    handle = in_memory.artifacts[0].figure
    assert isinstance(handle, Figure)

    result = render_graph(frame, spec, output=OutputSpec(DirectorySink(output_dir), formats=("png", "svg"), base_name="cell"))
    for artifact in result.artifacts:
        checked: Artifact = artifact
        if checked.path is not None:
            name: str = checked.path.name
            assert name.startswith("cell")
        series_ids: tuple[str, ...] = checked.series_ids
        assert checked.format in ("png", "svg") and series_ids
    manifest_text: str = result.manifest_json()
    assert manifest_text.endswith("\\n")
    return result
'''


def _check(tmp_path: Path, source: str) -> subprocess.CompletedProcess[str]:
    consumer = tmp_path / "consumer.py"
    consumer.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "--ignore-missing-imports", "--no-incremental", str(consumer)],
        cwd=tmp_path, capture_output=True, text=True, check=False,
    )


def test_spec_api_example_is_typed_for_consumers__tc_ge03_type_ep_001(tmp_path: Path) -> None:
    """TC-GE03-TYPE-EP-001: the documented example passes mypy --strict against the installed stubs."""
    # Given: the example as a standalone consumer module
    # When: type-checking it outside the repository configuration
    result = _check(tmp_path, EXAMPLE)
    # Then: every exported type, field and keyword is available and consistent
    assert result.returncode == 0, result.stdout + result.stderr


def test_spec_api_example_runs__tc_ge03_type_ep_002(tmp_path: Path) -> None:
    """TC-GE03-TYPE-EP-002: the typed example is also executable."""
    # Given: the example source
    namespace: dict[str, object] = {}
    exec(compile(EXAMPLE, "example.py", "exec"), namespace)  # noqa: S102 - the example is a literal in this module
    # When: running it
    result = namespace["main"](tmp_path)  # type: ignore[operator]
    # Then: overlay + individual, two formats each (stems follow the header, not the label)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["cell.png", "cell.svg", "cell_voltage_(v).png", "cell_voltage_(v).svg"]
    assert len(result.artifacts) == 4  # type: ignore[attr-defined]


@pytest.mark.parametrize(("source", "diagnostic"), [
    ('from rdetoolkit.graph import GraphSpec\nGraphSpec(layout="grid")\n', "[arg-type]"),
    ('from rdetoolkit.graph import SeriesSpec\nSeriesSpec(y=1.5)\n', "[arg-type]"),
    ('import pandas as pd\nfrom rdetoolkit.graph import render_graph\nrender_graph(pd.DataFrame(), mode="overlay")\n', "[call-arg]"),
    ('import pandas as pd\nfrom rdetoolkit.graph import render_graph\np: str = render_graph(pd.DataFrame()).artifacts[0].path\n', "[assignment]"),
    ('from rdetoolkit.graph import OutputSpec\nOutputSpec(sink=1)\n', "[arg-type]"),
    # The error code of this message differs across mypy releases ([misc] / [call-arg]); match the text.
    ('import pandas as pd\nfrom rdetoolkit.graph import GraphSpec, render_graph\nrender_graph(pd.DataFrame(), GraphSpec(), None)\n', 'Too many positional arguments for "render_graph"'),
    ('import pandas as pd\nfrom rdetoolkit.graph import build_plot_plan\nplan = build_plot_plan(pd.DataFrame())\nplan.mark = "line"\n', "[misc]"),
])
def test_invalid_spec_api_usage_is_rejected__tc_ge03_type_neg(tmp_path: Path, source: str, diagnostic: str) -> None:
    """TC-GE03-TYPE-NEG-001..007: the stubs keep useful constraints for consumers."""
    # Given: a consumer misusing the public contract
    # When: type-checking it
    result = _check(tmp_path, source)
    # Then: mypy reports the precise error code
    assert result.returncode == 1, result.stdout + result.stderr
    assert diagnostic in result.stdout, result.stdout
