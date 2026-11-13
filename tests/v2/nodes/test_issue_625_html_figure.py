"""Issue #625: builtin node writing an interactive plotly HTML figure.

| Node | Case | Expected | ID |
|------|------|----------|----|
| ``save_html_figure`` | default options | ``structured/<filename>`` full HTML, CDN plotly.js | I625-EP-1 |
| ``save_html_figure`` | same figure written twice | byte-identical files (stable div id) | I625-EP-2 |
| ``save_html_figure`` | ``div_id=`` given | the given id is used | I625-EP-3 |
| ``save_html_figure`` | ``kind`` / ``full_html`` / ``include_plotlyjs`` | passed through | I625-EP-4 |
| ``save_html_figure`` | dict figure | accepted like ``plotly.io.to_html``, deterministic | I625-EP-5 |
| ``save_html_figure`` | filename with spaces / non-ASCII | derived id is a safe HTML id | I625-BV-1 |
| ``save_html_figure`` | filenames whose stems sanitize alike | fragments on one page keep distinct ids | I625-BV-2 |
| ``save_html_figure`` | plotly not installed | ImportError naming the ``plotly`` extra | I625-NEG-1 |
| ``rdetoolkit.nodes`` | import without plotly | import succeeds, plotly not imported | I625-NEG-2 |
| ``run_flow`` | flow calling the node | call log records the node | I625-EP-6 |
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

plotly_go = pytest.importorskip("plotly.graph_objects")

from rdetoolkit.nodes import save_html_figure  # noqa: E402
from rdetoolkit.testing import make_output_context  # noqa: E402

_DIV_ID = re.compile(r'<div id="([^"]+)" class="plotly-graph-div"')


def _figure() -> Any:
    return plotly_go.Figure(data=[plotly_go.Scatter(x=[1, 2, 3], y=[1, 4, 9], name="signal")])


def test_writes_full_html_under_structured_by_default__i625_ep_1(tmp_path: Path) -> None:
    """I625-EP-1: defaults write a full HTML page loading plotly.js from the CDN."""
    # Given: an output context and a plotly figure
    out = make_output_context(tmp_path)
    # When: saving it with the default options
    path = save_html_figure(_figure(), out, "chart.html")
    # Then: a full page sits under structured/ with a filename-derived div id
    assert path == out.struct / "chart.html"
    html = path.read_text(encoding="utf-8")
    assert "<html" in html
    assert html.rstrip().endswith("</html>")
    assert re.search(r'<script [^>]*src="https://cdn\.plot\.ly/plotly-[^"]+\.min\.js"', html)
    assert _DIV_ID.findall(html) == ["plotly-chart-3e67baf8"]


def test_repeated_writes_are_byte_identical__i625_ep_2(tmp_path: Path) -> None:
    """I625-EP-2: the derived div id makes the artifact deterministic."""
    # Given: the same figure saved into two separate output trees
    first = save_html_figure(_figure(), make_output_context(tmp_path / "a"), "chart.html")
    # When: saving it a second time
    second = save_html_figure(_figure(), make_output_context(tmp_path / "b"), "chart.html")
    # Then: both files have exactly the same bytes
    assert first.read_bytes() == second.read_bytes()


def test_explicit_div_id_is_used__i625_ep_3(tmp_path: Path) -> None:
    """I625-EP-3: a caller-supplied div id replaces the derived one."""
    # Given/When: saving with an explicit div id
    path = save_html_figure(_figure(), make_output_context(tmp_path), "chart.html", div_id="eis-nyquist")
    # Then: the chart div carries that id
    assert _DIV_ID.findall(path.read_text(encoding="utf-8")) == ["eis-nyquist"]


def test_options_are_passed_through__i625_ep_4(tmp_path: Path) -> None:
    """I625-EP-4: kind, full_html and include_plotlyjs reach the written artifact."""
    # Given: an output context
    out = make_output_context(tmp_path)
    # When: writing a fragment without plotly.js into another output kind
    path = save_html_figure(_figure(), out, "chart.html", kind="other_image", full_html=False, include_plotlyjs=False)
    # Then: the fragment is a bare div without a page wrapper or plotly.js reference
    html = path.read_text(encoding="utf-8")
    assert path == out.other_image / "chart.html"
    assert html.lstrip().startswith("<div")
    assert "<html" not in html
    assert "cdn.plot.ly" not in html
    assert _DIV_ID.findall(html) == ["plotly-chart-3e67baf8"]


def test_dict_figure_is_accepted__i625_ep_5(tmp_path: Path) -> None:
    """I625-EP-5: the dict form of a figure is accepted, as by ``plotly.io.to_html``."""
    # Given: the dict form of a figure
    spec = {"data": [{"type": "scatter", "x": [1, 2, 3], "y": [1, 4, 9]}]}
    # When: saving it twice
    first = save_html_figure(spec, make_output_context(tmp_path / "a"), "chart.html")
    second = save_html_figure(spec, make_output_context(tmp_path / "b"), "chart.html")
    # Then: the chart is written with the derived id, deterministically
    html = first.read_text(encoding="utf-8")
    assert _DIV_ID.findall(html) == ["plotly-chart-3e67baf8"]
    assert '"y":[1,4,9]' in html
    assert first.read_bytes() == second.read_bytes()


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("my chart (1).html", "plotly-my-chart-1-f8316b93"),
        ("sample_01-a.html", "plotly-sample_01-a-cef4ea63"),
        ("測定.html", "plotly-figure-be95c65c"),
        ("x.y.html", "plotly-x-y-d24d662f"),
    ],
)
def test_derived_div_id_is_a_safe_html_id__i625_bv_1(tmp_path: Path, filename: str, expected: str) -> None:
    """I625-BV-1: characters outside [A-Za-z0-9_-] never reach the div id."""
    # Given/When: saving under a filename with spaces, punctuation or non-ASCII
    path = save_html_figure(_figure(), make_output_context(tmp_path), filename)
    # Then: the derived id is a plain, quote-free identifier
    assert _DIV_ID.findall(path.read_text(encoding="utf-8")) == [expected]


@pytest.mark.parametrize("filenames", [("測定.html", "解析.html"), ("a b.html", "a-b.html"), ("chart.html", "chart.htm")])
def test_fragments_of_different_files_keep_distinct_ids__i625_bv_2(tmp_path: Path, filenames: tuple[str, str]) -> None:
    """I625-BV-2: fragments concatenated into one page never share a div id."""
    # Given: two filenames whose stems sanitize to the same slug
    out = make_output_context(tmp_path)
    # When: writing a fragment for each and joining them into one page
    page = "".join(
        save_html_figure(_figure(), out, name, full_html=False, include_plotlyjs=False).read_text(encoding="utf-8")
        for name in filenames
    )
    # Then: each Plotly.newPlot targets its own element
    ids = _DIV_ID.findall(page)
    assert len(ids) == 2
    assert len(set(ids)) == 2


def test_missing_plotly_names_the_extra__i625_neg_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """I625-NEG-1: without plotly, the node says how to install the extra."""
    # Given: an interpreter state where plotly cannot be imported
    monkeypatch.setitem(sys.modules, "plotly", None)
    monkeypatch.setitem(sys.modules, "plotly.io", None)
    out = make_output_context(tmp_path)
    # When/Then: the node raises an ImportError naming rdetoolkit[plotly]
    with pytest.raises(ImportError, match=re.escape("rdetoolkit[plotly]")):
        save_html_figure({"data": []}, out, "chart.html")
    # And: nothing is written
    assert not (out.struct / "chart.html").exists()


def test_nodes_import_does_not_require_plotly__i625_neg_2() -> None:
    """I625-NEG-2: rdetoolkit.nodes imports cleanly with plotly unavailable."""
    # Given: a fresh interpreter in which plotly cannot be imported
    script = (
        "import sys\n"
        "sys.modules['plotly'] = None\n"
        "import rdetoolkit.nodes as nodes\n"
        "assert callable(nodes.save_html_figure)\n"
        "print('plotly' in sys.modules and sys.modules['plotly'] is not None)\n"
    )
    # When: importing the builtin nodes
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=60, check=False)
    # Then: the import succeeds and plotly was never loaded
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.strip() == "False"


def test_call_log_records_the_node__i625_ep_6(tmp_path: Path) -> None:
    """I625-EP-6: a flow writing the chart shows the node in its call log."""
    from rdetoolkit import flow
    from rdetoolkit.core.calllog import CallLogRecorder
    from rdetoolkit.types import OutputContext

    # Given: a flow that writes an interactive chart
    @flow
    def chart_flow(out: OutputContext) -> None:
        save_html_figure(_figure(), out, "chart.html")

    out = make_output_context(tmp_path)
    # When: running it with a call-log recorder active
    with CallLogRecorder() as recorder:
        chart_flow(out)
    # Then: the builtin node call is recorded inside the flow
    records = [record for record in recorder.records if record.node_id.endswith("save_html_figure")]
    assert len(records) == 1
    assert records[0].parent_flow is not None
    assert (out.struct / "chart.html").exists()
