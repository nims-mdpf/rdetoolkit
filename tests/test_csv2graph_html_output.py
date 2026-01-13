"""Test design tables for csv2graph HTML output destinations.

Equivalence Partitioning

| API | Input/State Partition | Rationale | Expected Outcome | Test ID |
| --- | --- | --- | --- | --- |
| `graph.csv2graph` | Custom `output_dir`, `html_output_dir` omitted | HTML should stay beside the CSV by default | HTML dir resolved to CSV directory | `TC-EP-HTML-001` |
| `graph.csv2graph` | Explicit `html_output_dir` provided | Caller override should direct HTML elsewhere | HTML dir resolved to provided path | `TC-EP-HTML-002` |
| `graph.csv2graph` | `html_output_dir` has invalid type | Prevent silent coercion to unexpected paths | Raise `TypeError` with clear message | `TC-EP-HTML-003` |

Boundary Value

| API | Boundary | Rationale | Expected Outcome | Test ID |
| --- | --- | --- | --- | --- |
| `graph.csv2graph` | `html_output_dir` points to an existing file | Guard against non-directory destinations | Raise `ValueError` about invalid directory | `TC-BV-HTML-001` |
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

csv2graph_module = importlib.import_module("rdetoolkit.graph.api.csv2graph")
from rdetoolkit.graph.api.csv2graph import RenderCollections, RenderResult, csv2graph


def _write_csv(csv_path: Path) -> None:
    csv_path.write_text("x,y\n0,1\n1,2\n", encoding="utf-8")


def test_csv2graph_defaults_html_dir_to_csv_parent__tc_ep_html_001(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: CSV under structured/ with output_dir redirected elsewhere
    csv_dir = tmp_path / "data" / "structured"
    csv_dir.mkdir(parents=True)
    csv_path = csv_dir / "data.csv"
    _write_csv(csv_path)
    other_output = tmp_path / "data" / "other_image"
    captured: dict[str, Path | None] = {}

    monkeypatch.setattr(
        csv2graph_module,
        "_collect_render_results",
        lambda _df, _config, _plot_mode: RenderCollections(overlay=[], individual=[]),
    )

    def fake_save(
        collections: RenderCollections,
        output_dir_path: Path,
        main_image_dir_path: Path | None,
        html_output_dir_path: Path | None,
    ) -> None:
        captured["output_dir_path"] = output_dir_path
        captured["main_image_dir_path"] = main_image_dir_path
        captured["html_output_dir_path"] = html_output_dir_path

    monkeypatch.setattr(csv2graph_module, "_save_render_results", fake_save)

    # When: invoking csv2graph with HTML enabled and custom output_dir
    csv2graph(
        csv_path=csv_path,
        output_dir=other_output,
        html=True,
        no_individual=True,
    )

    # Then: HTML output stays next to the CSV while PNG output uses output_dir
    assert captured["output_dir_path"] == other_output
    assert captured["main_image_dir_path"] is None
    assert captured["html_output_dir_path"] == csv_dir


def test_csv2graph_respects_explicit_html_output_dir__tc_ep_html_002(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: CSV with explicit HTML destination override
    csv_dir = tmp_path / "data" / "structured"
    csv_dir.mkdir(parents=True)
    csv_path = csv_dir / "data.csv"
    _write_csv(csv_path)
    other_output = tmp_path / "data" / "other_image"
    explicit_html_dir = tmp_path / "data" / "structured_html"
    captured: dict[str, Path | None] = {}

    monkeypatch.setattr(
        csv2graph_module,
        "_collect_render_results",
        lambda _df, _config, _plot_mode: RenderCollections(overlay=[], individual=[]),
    )

    def fake_save(
        collections: RenderCollections,
        output_dir_path: Path,
        main_image_dir_path: Path | None,
        html_output_dir_path: Path | None,
    ) -> None:
        captured["output_dir_path"] = output_dir_path
        captured["main_image_dir_path"] = main_image_dir_path
        captured["html_output_dir_path"] = html_output_dir_path

    monkeypatch.setattr(csv2graph_module, "_save_render_results", fake_save)

    # When: invoking csv2graph with an explicit html_output_dir
    csv2graph(
        csv_path=csv_path,
        output_dir=other_output,
        html_output_dir=explicit_html_dir,
        html=True,
        no_individual=True,
    )

    # Then: HTML output respects the caller-provided directory
    assert captured["output_dir_path"] == other_output
    assert captured["main_image_dir_path"] is None
    assert captured["html_output_dir_path"] == explicit_html_dir


def test_csv2graph_rejects_invalid_html_output_dir_type__tc_ep_html_003(
    tmp_path: Path,
) -> None:
    # Given: CSV path and an invalid html_output_dir type
    csv_dir = tmp_path / "data" / "structured"
    csv_dir.mkdir(parents=True)
    csv_path = csv_dir / "data.csv"
    _write_csv(csv_path)

    # When: invoking csv2graph with a non-path html_output_dir
    # Then: a TypeError is raised to prevent path coercion
    with pytest.raises(TypeError, match="html_output_dir must be a str, Path, or None"):
        csv2graph(
            csv_path=csv_path,
            output_dir=tmp_path / "data" / "other_image",
            html_output_dir=123,  # type: ignore[arg-type]
            html=True,
            no_individual=True,
        )


class _StubHtmlFigure:
    def write_html(self, *args, **kwargs) -> None:  # pragma: no cover - stub
        return None


def test_csv2graph_raises_when_html_output_dir_is_file__tc_bv_html_001(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: CSV with html_output_dir pointing to an existing file path
    csv_dir = tmp_path / "data" / "structured"
    csv_dir.mkdir(parents=True)
    csv_path = csv_dir / "data.csv"
    _write_csv(csv_path)
    html_file_path = csv_dir / "data.html"
    html_file_path.write_text("placeholder", encoding="utf-8")

    def fake_collect(_df, _config, _plot_mode):
        return RenderCollections(
            overlay=[
                RenderResult(
                    figure=_StubHtmlFigure(),
                    filename="plot.html",
                    format="html",
                ),
            ],
            individual=[],
        )

    monkeypatch.setattr(csv2graph_module, "_collect_render_results", fake_collect)

    # When: invoking csv2graph with html_output_dir targeting a file
    # Then: saving fails because the path is not a directory
    with pytest.raises(ValueError, match="Output path is not a directory"):
        csv2graph(
            csv_path=csv_path,
            output_dir=tmp_path / "data" / "other_image",
            html_output_dir=html_file_path,
            html=True,
            no_individual=True,
        )
