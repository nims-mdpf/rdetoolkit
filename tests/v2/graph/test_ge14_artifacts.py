"""GE-14 (#720): artifact formats, destinations, path containment and a deterministic manifest.

EP/BV table

| Target | Partition / boundary | Expected | TC |
|---|---|---|---|
| render_graph + DirectorySink | layout both, formats (png, svg) | overlay -> main_image dir, individuals -> output dir, real PNG/SVG bytes, plan x format order | TC-GE14-EP-001 |
| render_graph + DirectorySink | layout overlay, formats (png, html) | PNG -> main_image dir, HTML -> html dir | TC-GE14-EP-002 |
| render_graph + OutputContextSink | default kinds, png/svg/html | main_image -> out.main_image, individual -> out.other_image, html -> out.struct | TC-GE14-EP-003 |
| OutputContextSink | custom kinds mapping | routed to the mapped kinds | TC-GE14-EP-004 |
| GraphResult.manifest_json | same request in two temp dirs (png + html) | byte-identical manifest AND byte-identical HTML | TC-GE14-EP-005 |
| GraphResult.manifest | path source | structured detection dict (selected, candidates, ...), JSON-safe | TC-GE14-EP-006 |
| on_existing | "overwrite" (default), one existing file | replaced, replaced_existing recorded only for it | TC-GE14-EP-007 |
| PlotlyRenderer | limits both / lower only / upper only / log | layout range set (log10 for log); no range without limits | TC-GE14-EP-008 |
| plot_from_dataframe(html=True) | xlim both sides, ylim upper only | HTML JSON carries both ranges (IC-14) | TC-GE14-EP-008 |
| IndividualStrategy | OutputConfig.formats (png, svg, html) / default / html only | one result per image format, same figure; default and html-only -> png | TC-GE14-EP-009 |
| PathValidator | symlink inside the directory | accepted (positive control) | TC-GE14-EP-010 |
| _save_render_results | overlay + individual | overlay first, routed dirs, written through FileWriter | TC-GE14-EP-011 |
| render_graph | format "jpg" | UnsupportedFormatError, nothing created | TC-GE14-NEG-001 |
| render_graph | html for individual figures (DirectorySink / OutputContextSink) | UnsupportedFormatError, no file | TC-GE14-NEG-002 |
| render_graph | (png, bmp) | rejected before the png is written | TC-GE14-NEG-003 |
| PathValidator.validate | symlink into a sibling dir sharing the prefix (/out vs /out2) | ValueError "Security violation" | TC-GE14-NEG-004 |
| DirectorySink | same prefix-collision symlink | OutputPathError, target untouched | TC-GE14-NEG-005 |
| OutputContextSink | symlink escape out of main_image | OutputPathError, nothing written | TC-GE14-NEG-006 |
| OutputContextSink.resolve | "../x.png", "a/b.png", "a\\\\b.png", "..", "", "." | OutputPathError (ValueError) | TC-GE14-NEG-007 |
| render_graph | base_name "../evil" | sanitized: written inside the sink only | TC-GE14-NEG-008 |
| on_existing="error" + OutputContextSink | one existing file | ArtifactCollisionError before rendering, file untouched, nothing else written | TC-GE14-NEG-009 |
| render_graph + OutputContextSink | Plotly hidden, (png, html) | RendererUnavailableError (ImportError) with install hint, no file | TC-GE14-NEG-010 |
| OutputContextSink() | kinds missing a role / unknown kind / not a mapping | PlotRequestError(reason="invalid_spec") | TC-GE14-NEG-011 |
| OutputContextSink() | out is not an OutputContext | TypeError | TC-GE14-NEG-012 |
| _save_render_results | an individual name with ".." | ValueError before the overlay is written | TC-GE14-NEG-013 |
| OutputContextSink | kind directory is a file | OutputPathError "Output path is not a directory" | TC-GE14-NEG-014 |
| PathValidator.resolve_within | separator / ".." / prefix-collision symlink | ValueError with the legacy text, no existence requirement | TC-GE14-NEG-015 |
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import pytest

from rdetoolkit import graph as graph_pkg
from rdetoolkit.graph.api.csv2graph import _save_render_results, plot_from_dataframe
from rdetoolkit.graph.engine import render_graph
from rdetoolkit.graph.exceptions import (
    ArtifactCollisionError,
    OutputPathError,
    PlotRequestError,
    RendererUnavailableError,
    UnsupportedFormatError,
)
from rdetoolkit.graph.io.file_writer import FileWriter
from rdetoolkit.graph.io.path_validator import PathValidator
from rdetoolkit.graph.models import OutputConfig, PlotConfig, PlotMode, RenderCollections, RenderResult
from rdetoolkit.graph.outputs import ArtifactSink, DirectorySink, OutputContextSink
from rdetoolkit.graph.plan import build_plot_plan
from rdetoolkit.graph.renderers.matplotlib_renderer import MatplotlibRenderer
from rdetoolkit.graph.renderers.plotly_renderer import PlotlyRenderer
from rdetoolkit.graph.plan import PlotData
from rdetoolkit.graph.spec import AxisSpec, GraphSpec, OutputSpec
from rdetoolkit.graph.strategies.individual import IndividualStrategy
from rdetoolkit.testing import make_output_context

FIXTURES = Path(__file__).parent / "fixtures"
PLOTLY_HINT = 'pip install "rdetoolkit[plotly]"'
ALLOW = GraphSpec(unit_policy="allow")
OVERLAY_ONLY = GraphSpec(layout="overlay", unit_policy="allow")
INDIVIDUAL_ONLY = GraphSpec(layout="individual", unit_policy="allow")


def _multi_y() -> pd.DataFrame:
    return pd.read_csv(FIXTURES / "multi_unit.csv")


def _files(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


def _hide_plotly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "plotly", None)


# --------------------------------------------------------------------------- positive


def test_directory_sink_routes_images_by_role__tc_ge14_ep_001(tmp_path: Path) -> None:
    """TC-GE14-EP-001: overlay images go to main_image_dir, individual images to output_dir, in plan x format order."""
    # Given: a three-figure plan written as PNG and SVG
    sink = DirectorySink(tmp_path / "other", main_image_dir=tmp_path / "main")
    # When
    result = render_graph(_multi_y(), ALLOW, output=OutputSpec(sink, formats=("png", "svg"), base_name="cell"))
    # Then: six artifacts, plan order then format order, routed by role
    assert [(a.figure_id, a.format, a.role) for a in result.artifacts] == [
        ("overlay", "png", "main_image"), ("overlay", "svg", "main_image"),
        ("s000", "png", "individual"), ("s000", "svg", "individual"),
        ("s001", "png", "individual"), ("s001", "svg", "individual"),
    ]
    assert _files(tmp_path / "main") == ["cell.png", "cell.svg"]
    assert _files(tmp_path / "other") == ["cell_current_(a).png", "cell_current_(a).svg", "cell_voltage_(v).png", "cell_voltage_(v).svg"]
    # And: real content in each format
    for artifact in result.artifacts:
        assert artifact.path is not None
        content = artifact.path.read_bytes()
        assert content.startswith(b"\x89PNG") if artifact.format == "png" else b"<svg" in content


def test_directory_sink_routes_html_to_html_dir__tc_ge14_ep_002(tmp_path: Path) -> None:
    """TC-GE14-EP-002: the overlay HTML goes to html_dir while the overlay PNG goes to main_image_dir."""
    # Given
    sink = DirectorySink(tmp_path / "other", main_image_dir=tmp_path / "main", html_dir=tmp_path / "html")
    # When
    result = render_graph(_multi_y(), OVERLAY_ONLY, output=OutputSpec(sink, formats=("png", "html"), base_name="cell"))
    # Then
    assert [(a.role, a.renderer) for a in result.artifacts] == [("main_image", "matplotlib"), ("html", "plotly")]
    assert _files(tmp_path) == ["html/cell.html", "main/cell.png"]
    assert b"plotly" in (tmp_path / "html" / "cell.html").read_bytes()


def test_output_context_sink_default_routing__tc_ge14_ep_003(tmp_path: Path) -> None:
    """TC-GE14-EP-003: OutputContext routing is main_image / other_image / struct."""
    # Given: an RDE output context
    out = make_output_context(tmp_path)
    sink = OutputContextSink(out)
    # When: overlay PNG+SVG+HTML and individual PNG+SVG (two calls; HTML is overlay-only)
    overlay = render_graph(_multi_y(), OVERLAY_ONLY, output=OutputSpec(sink, formats=("png", "svg", "html"), base_name="cell"))
    individual = render_graph(_multi_y(), INDIVIDUAL_ONLY, output=OutputSpec(sink, formats=("png", "svg"), base_name="cell"))
    # Then: every file is in its OutputContext directory and is returned as such
    assert [a.path for a in overlay.artifacts] == [out.main_image / "cell.png", out.main_image / "cell.svg", out.struct / "cell.html"]
    assert [a.path.parent for a in individual.artifacts if a.path is not None] == [out.other_image] * 4
    assert _files(tmp_path) == [
        "main_image/cell.png", "main_image/cell.svg",
        "other_image/cell_current_(a).png", "other_image/cell_current_(a).svg",
        "other_image/cell_voltage_(v).png", "other_image/cell_voltage_(v).svg",
        "structured/cell.html",
    ]
    assert isinstance(sink, ArtifactSink)


def test_output_context_sink_custom_kinds__tc_ge14_ep_004(tmp_path: Path) -> None:
    """TC-GE14-EP-004: a caller mapping replaces the default destinations."""
    # Given: HTML into the attachment directory, individuals into main_image
    out = make_output_context(tmp_path)
    sink = OutputContextSink(out, kinds={"main_image": "main_image", "individual": "main_image", "html": "attachment"})
    # When
    result = render_graph(_multi_y(), ALLOW, output=OutputSpec(sink, base_name="cell"))
    html = render_graph(_multi_y(), OVERLAY_ONLY, output=OutputSpec(sink, formats=("html",), base_name="cell"))
    # Then
    assert {a.path.parent for a in result.artifacts if a.path is not None} == {out.main_image}
    assert html.artifacts[0].path == out.attachment / "cell.html"
    assert dict(sink.kinds) == {"main_image": "main_image", "individual": "main_image", "html": "attachment"}


def test_manifest_and_html_are_byte_stable_across_directories__tc_ge14_ep_005(tmp_path: Path) -> None:
    """TC-GE14-EP-005: two runs in different directories give the same manifest and the same HTML bytes."""
    # Given: the same request into two unrelated directories
    def run(root: Path) -> tuple[str, bytes]:
        sink = DirectorySink(root / "o", main_image_dir=root / "m")
        result = render_graph(_multi_y(), OVERLAY_ONLY, output=OutputSpec(sink, formats=("png", "html"), base_name="cell"))
        html = next(a.path for a in result.artifacts if a.format == "html")
        assert html is not None
        return result.manifest_json(), html.read_bytes()

    # When
    first_manifest, first_html = run(tmp_path / "first")
    second_manifest, second_html = run(tmp_path / "second" / "deeper")
    # Then: identical bytes; the manifest lists every output in plan x format order by file name
    assert first_manifest == second_manifest
    assert first_html == second_html
    assert str(tmp_path) not in first_manifest
    entries = json.loads(first_manifest)["artifacts"]
    assert [(e["file"], e["role"], e["format"]) for e in entries] == [("cell.png", "main_image", "png"), ("cell.html", "html", "html")]


def test_manifest_records_structured_detection__tc_ge14_ep_006(tmp_path: Path) -> None:
    """TC-GE14-EP-006: the detection decision is a JSON object, not its repr."""
    # Given: a path source read under "auto"
    source = tmp_path / "simple.csv"
    shutil.copyfile(FIXTURES / "simple.csv", source)
    # When
    result = render_graph(source, output=OutputSpec(DirectorySink(tmp_path / "out")))
    detection = result.manifest()["detection"]
    # Then: every decision field is recorded with JSON types
    assert isinstance(detection, dict)
    assert detection["selected"] == "standard"
    assert detection["forced"] is False
    assert set(detection) == {
        "selected", "forced", "candidates", "encoding", "delimiter", "sampled_bytes",
        "sampled_rows", "truncated", "preview_columns", "data_rows",
    }
    assert all(set(candidate) == {"reader_id", "confidence", "evidence"} for candidate in detection["candidates"])
    assert isinstance(detection["candidates"][0]["evidence"], list)
    assert json.loads(result.manifest_json())["detection"] == detection


def test_on_existing_overwrite_is_recorded__tc_ge14_ep_007(tmp_path: Path) -> None:
    """TC-GE14-EP-007: the default overwrite replaces the file and records it only for that artifact."""
    # Given: an existing individual image
    out = make_output_context(tmp_path)
    (out.other_image / "plot_voltage_(v).png").write_bytes(b"old")
    # When
    result = render_graph(_multi_y(), ALLOW, output=OutputSpec(OutputContextSink(out)))
    # Then
    assert [a.replaced_existing for a in result.artifacts] == [False, True, False]
    assert (out.other_image / "plot_voltage_(v).png").read_bytes().startswith(b"\x89PNG")
    assert [e["replaced_existing"] for e in result.manifest()["artifacts"]] == [False, True, False]


@pytest.mark.parametrize(("x_axis", "y_axis", "x_range", "y_range"), [
    (AxisSpec(limits=(0.5, 2.5)), AxisSpec(limits=(3.0, 3.5)), (0.5, 2.5), (3.0, 3.5)),
    (AxisSpec(limits=(1.0, None)), AxisSpec(limits=(None, 4.0)), (1.0, None), (None, 4.0)),
    (AxisSpec(scale="log", limits=(1.0, 100.0)), AxisSpec(), (0.0, 2.0), None),
    (AxisSpec(scale="log", limits=(None, 10.0)), AxisSpec(), (None, 1.0), None),
    (AxisSpec(), AxisSpec(), None, None),
])
def test_plotly_applies_axis_limits_v2_0__tc_ge14_ep_008(x_axis: AxisSpec, y_axis: AxisSpec, x_range: Any, y_range: Any) -> None:
    """TC-GE14-EP-008: HTML honours the plan's axis limits (log axes in log10 units)."""
    # Given: a plan with limits
    frame = pd.DataFrame({"x": [1.0, 2.0, 3.0], "y": [3.0, 3.2, 3.4]})
    plan = build_plot_plan(frame, GraphSpec(layout="overlay", x_axis=x_axis, y_axis=y_axis))
    # When
    fig = PlotlyRenderer().render(plan, plan.figures[0], PlotData(frames=(frame,)))
    # Then
    assert fig.layout.xaxis.range == x_range
    assert fig.layout.yaxis.range == y_range


def test_legacy_html_applies_axis_limits_v2_0__tc_ge14_ep_008(tmp_path: Path) -> None:
    """TC-GE14-EP-008 (IC-14): the legacy facade's HTML honours xlim/ylim like its PNG."""
    # Given/When: an overlay with HTML and limits through plot_from_dataframe
    frame = pd.DataFrame({"x": [1.0, 2.0, 3.0], "y": [3.0, 3.2, 3.4]})
    plot_from_dataframe(frame, tmp_path, html=True, xlim=(0.5, 2.5), ylim=(None, 4.0), name="cell")
    # Then: the HTML figure JSON carries both ranges
    html = (tmp_path / "cell.html").read_text(encoding="utf-8")
    assert '"range":[0.5,2.5]' in html
    assert '"range":[null,4.0]' in html
    assert _files(tmp_path) == ["cell.html", "cell.png"]


def _individual_config(formats: list[str]) -> PlotConfig:
    return PlotConfig(mode=PlotMode.INDIVIDUAL, x_col=0, y_cols=[1, 2], output=OutputConfig(base_name="cell", formats=formats))


@pytest.mark.parametrize(("formats", "expected"), [
    (["png", "svg", "html"], ["png", "svg"]),
    (["SVG", "pdf", "svg"], ["svg", "pdf"]),
    (["png"], ["png"]),
    (["html"], ["png"]),
])
def test_individual_strategy_follows_output_formats_v2_0__tc_ge14_ep_009(formats: list[str], expected: list[str]) -> None:
    """TC-GE14-EP-009: individual figures are written in every requested image format, not only PNG."""
    # Given
    renderer = MatplotlibRenderer()
    # When
    results = IndividualStrategy(renderer).render(_multi_y(), _individual_config(formats))
    # Then: one result per series per image format; the formats of a series share one figure
    assert results is not None
    assert [r.filename for r in results] == [f"cell_{s}.{fmt}" for s in ("voltage_(v)", "current_(a)") for fmt in expected]
    assert [r.format for r in results] == expected * 2
    per_series = [results[i:i + len(expected)] for i in range(0, len(results), len(expected))]
    assert all(len({id(r.figure) for r in group}) == 1 for group in per_series)
    assert len({id(group[0].figure) for group in per_series}) == 2


def test_path_validator_accepts_a_symlink_inside__tc_ge14_ep_010(tmp_path: Path) -> None:
    """TC-GE14-EP-010: containment is path-aware, so a link to a file inside the directory is fine."""
    # Given: out/link.png -> out/real.png
    out = tmp_path / "out"
    out.mkdir()
    (out / "link.png").symlink_to(out / "real.png")
    # When/Then
    assert PathValidator().validate(out, "link.png") == (out / "real.png").resolve()
    assert PathValidator().resolve_within(tmp_path / "missing", "a.png") == (tmp_path / "missing").resolve() / "a.png"


def test_legacy_saver_routes_and_writes_through_file_writer__tc_ge14_ep_011(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE14-EP-011: the legacy seam keeps FileWriter.save_figure(figure, dir, filename, fmt), overlay first."""
    # Given
    saved: list[tuple[Path, str, str]] = []

    def fake_save(self: FileWriter, figure: Any, output_dir: Path, filename: str, format_type: str, **kwargs: Any) -> Path:
        saved.append((Path(output_dir), filename, format_type))
        return Path(output_dir) / filename

    monkeypatch.setattr(FileWriter, "save_figure", fake_save)
    collections = RenderCollections(
        overlay=[RenderResult(object(), "p.png", "png"), RenderResult(object(), "p.html", "html")],
        individual=[RenderResult(object(), "p_a.svg", "svg")],
    )
    # When
    _save_render_results(collections, tmp_path / "o", tmp_path / "m", tmp_path / "h")
    # Then
    assert saved == [
        ((tmp_path / "m").resolve(), "p.png", "png"),
        ((tmp_path / "h").resolve(), "p.html", "html"),
        ((tmp_path / "o").resolve(), "p_a.svg", "svg"),
    ]


def test_ge14_names_are_exported__tc_ge14_ep_012() -> None:
    """TC-GE14-EP-012: the GE-14 surface is public from rdetoolkit.graph and its stub."""
    names = ("ArtifactSink", "DirectorySink", "OutputContextSink", "OutputPathError", "ArtifactCollisionError")
    stub = Path(graph_pkg.__file__).with_suffix(".pyi").read_text(encoding="utf-8")
    assert set(names) <= set(graph_pkg.__all__)
    assert graph_pkg.OutputContextSink is OutputContextSink
    assert graph_pkg.OutputPathError is OutputPathError
    assert all(f"{name} as {name}" in stub for name in names)


# --------------------------------------------------------------------------- negative


def test_unknown_format_is_rejected_before_anything_exists__tc_ge14_neg_001(tmp_path: Path) -> None:
    """TC-GE14-NEG-001: a format no renderer supports fails at planning."""
    with pytest.raises(UnsupportedFormatError) as excinfo:
        render_graph(_multi_y(), ALLOW, output=OutputSpec(DirectorySink(tmp_path / "out"), formats=("jpg",)))
    assert isinstance(excinfo.value, ValueError)
    assert not (tmp_path / "out").exists()
    assert plt.get_fignums() == []


@pytest.mark.parametrize("use_context", [False, True])
def test_html_for_individual_figures_is_rejected__tc_ge14_neg_002(tmp_path: Path, use_context: bool) -> None:
    """TC-GE14-NEG-002: HTML is an overlay-only artifact; asking it for individual figures writes nothing."""
    # Given
    sink: ArtifactSink = OutputContextSink(make_output_context(tmp_path)) if use_context else DirectorySink(tmp_path / "out")
    # When/Then
    with pytest.raises(UnsupportedFormatError, match="html"):
        render_graph(_multi_y(), ALLOW, output=OutputSpec(sink, formats=("png", "html")))
    assert _files(tmp_path) == []


def test_mixed_supported_and_unsupported_formats_write_nothing__tc_ge14_neg_003(tmp_path: Path) -> None:
    """TC-GE14-NEG-003: the supported PNG is not written when BMP in the same request is rejected."""
    with pytest.raises(UnsupportedFormatError, match="bmp"):
        render_graph(_multi_y(), OVERLAY_ONLY, output=OutputSpec(DirectorySink(tmp_path), formats=("png", "bmp")))
    assert _files(tmp_path) == []


def _prefix_collision(tmp_path: Path) -> tuple[Path, Path]:
    """out/link.png -> ../out2/x.png: the target shares the string prefix of out/."""
    out = tmp_path / "out"
    sibling = tmp_path / "out2"
    out.mkdir()
    sibling.mkdir()
    (out / "link.png").symlink_to(sibling / "x.png")
    return out, sibling


def test_path_validator_rejects_a_prefix_collision_v2_0__tc_ge14_neg_004(tmp_path: Path) -> None:
    """TC-GE14-NEG-004: /out2 is not inside /out although "/out2" starts with "/out"."""
    out, _ = _prefix_collision(tmp_path)
    with pytest.raises(ValueError, match="Security violation: 'link.png' would write outside output directory"):
        PathValidator().validate(out, "link.png")


def test_directory_sink_rejects_a_prefix_collision__tc_ge14_neg_005(tmp_path: Path) -> None:
    """TC-GE14-NEG-005: the spec API fails before writing through a link into a prefix-sharing sibling."""
    out, sibling = _prefix_collision(tmp_path)
    with pytest.raises(OutputPathError, match="Security violation"):
        render_graph(_multi_y(), OVERLAY_ONLY, output=OutputSpec(DirectorySink(out), base_name="link"))
    assert not (sibling / "x.png").exists()


def test_output_context_sink_rejects_a_symlink_escape__tc_ge14_neg_006(tmp_path: Path) -> None:
    """TC-GE14-NEG-006: a link inside an OutputContext directory cannot lead outside it."""
    # Given: main_image/cell.png -> <root>/main_image2/x.png
    out = make_output_context(tmp_path / "root")
    escape = tmp_path / "root" / "main_image2"
    escape.mkdir()
    (out.main_image / "cell.png").symlink_to(escape / "x.png")
    # When/Then
    with pytest.raises(OutputPathError, match="Security violation"):
        render_graph(_multi_y(), ALLOW, output=OutputSpec(OutputContextSink(out), base_name="cell"))
    assert _files(tmp_path) == []


@pytest.mark.parametrize("filename", ["../x.png", "a/b.png", "a\\b.png", "..", ""])
def test_output_context_sink_rejects_traversal_names__tc_ge14_neg_007(tmp_path: Path, filename: str) -> None:
    """TC-GE14-NEG-007: names that could address another directory are OutputPathError (a ValueError)."""
    sink = OutputContextSink(make_output_context(tmp_path))
    with pytest.raises(OutputPathError, match="contains path separators") as excinfo:
        sink.resolve("main_image", filename)
    assert isinstance(excinfo.value, ValueError)
    with pytest.raises(OutputPathError):
        sink.write("html", filename, b"x")
    assert _files(tmp_path) == []


def test_output_context_sink_maps_the_context_rule_to_output_path_error__tc_ge14_neg_007(tmp_path: Path) -> None:
    """TC-GE14-NEG-007: "." passes the legacy name check but not OutputContext's basename rule."""
    sink = OutputContextSink(make_output_context(tmp_path))
    with pytest.raises(OutputPathError, match="simple basename") as excinfo:
        sink.resolve("individual", ".")
    assert isinstance(excinfo.value.__cause__, ValueError)


def test_traversal_base_name_is_sanitized__tc_ge14_neg_008(tmp_path: Path) -> None:
    """TC-GE14-NEG-008: a base name with ".." and "/" cannot write outside the sink."""
    result = render_graph(_multi_y(), OVERLAY_ONLY, output=OutputSpec(DirectorySink(tmp_path / "out"), base_name="../evil"))
    assert _files(tmp_path) == [f"out/{result.artifacts[0].path.name}"]  # type: ignore[union-attr]
    assert "/" not in result.manifest()["artifacts"][0]["file"]


def test_on_existing_error_fails_before_rendering__tc_ge14_neg_009(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE14-NEG-009: on_existing="error" names the clash and leaves every destination untouched."""
    # Given: an existing overlay image
    out = make_output_context(tmp_path)
    (out.main_image / "plot.png").write_bytes(b"old")
    rendered: list[object] = []
    monkeypatch.setattr(MatplotlibRenderer, "render", lambda self, *a: rendered.append(a))
    # When/Then
    with pytest.raises(ArtifactCollisionError, match="plot.png") as excinfo:
        render_graph(_multi_y(), ALLOW, output=OutputSpec(OutputContextSink(out), on_existing="error"))
    assert isinstance(excinfo.value, ValueError)
    assert rendered == []
    assert (out.main_image / "plot.png").read_bytes() == b"old"
    assert _files(tmp_path) == ["main_image/plot.png"]


def test_missing_plotly_is_typed_and_actionable__tc_ge14_neg_010(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-GE14-NEG-010: HTML without Plotly fails before the PNG of the same request is written."""
    _hide_plotly(monkeypatch)
    out = make_output_context(tmp_path)
    with pytest.raises(RendererUnavailableError) as excinfo:
        render_graph(_multi_y(), OVERLAY_ONLY, output=OutputSpec(OutputContextSink(out), formats=("png", "html")))
    assert isinstance(excinfo.value, ImportError)
    assert PLOTLY_HINT in str(excinfo.value)
    assert _files(tmp_path) == []


@pytest.mark.parametrize("kinds", [
    {"main_image": "main_image", "individual": "other_image"},
    {"main_image": "main_image", "individual": "other_image", "html": "nowhere"},
    {"main_image": "main_image", "individual": "other_image", "html": "struct", "thumbnail": "thumbnail"},
    ["main_image"],
])
def test_output_context_sink_rejects_invalid_kinds__tc_ge14_neg_011(tmp_path: Path, kinds: Any) -> None:
    """TC-GE14-NEG-011: the role mapping must name exactly the three roles with valid OutputContext kinds."""
    with pytest.raises(PlotRequestError) as excinfo:
        OutputContextSink(make_output_context(tmp_path), kinds=kinds)
    assert excinfo.value.reason == "invalid_spec"


def test_output_context_sink_requires_an_output_context__tc_ge14_neg_012(tmp_path: Path) -> None:
    """TC-GE14-NEG-012: a plain path is not an OutputContext."""
    with pytest.raises(TypeError, match="OutputContext"):
        OutputContextSink(tmp_path)  # type: ignore[arg-type]


def test_legacy_saver_validates_every_name_before_writing_v2_0__tc_ge14_neg_013(tmp_path: Path) -> None:
    """TC-GE14-NEG-013: a bad individual name fails before the overlay image is written."""
    figure, _ = plt.subplots()
    collections = RenderCollections(
        overlay=[RenderResult(figure, "p.png", "png")],
        individual=[RenderResult(figure, "../p_a.png", "png")],
    )
    with pytest.raises(ValueError, match="contains path separators"):
        _save_render_results(collections, tmp_path / "o", tmp_path / "m")
    assert _files(tmp_path) == []


def test_output_context_sink_rejects_a_file_as_directory__tc_ge14_neg_014(tmp_path: Path) -> None:
    """TC-GE14-NEG-014: a kind directory that is a file fails with the legacy text."""
    out = make_output_context(tmp_path)
    out.struct.rmdir()
    out.struct.write_text("x")
    with pytest.raises(OutputPathError, match="Output path is not a directory"):
        render_graph(_multi_y(), OVERLAY_ONLY, output=OutputSpec(OutputContextSink(out), formats=("png", "html")))
    assert _files(tmp_path) == ["structured"]


@pytest.mark.parametrize(("filename", "fragment"), [
    ("a/b.png", "contains path separators"),
    ("..", "contains path separators"),
    ("link.png", "Security violation"),
])
def test_path_validator_resolve_within_rejects__tc_ge14_neg_015(tmp_path: Path, filename: str, fragment: str) -> None:
    """TC-GE14-NEG-015: the shared containment check keeps the legacy messages."""
    out, _ = _prefix_collision(tmp_path)
    with pytest.raises(ValueError, match=fragment):
        PathValidator().resolve_within(out, filename)
