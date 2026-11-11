"""GA590 EP/BV: builtin node options needed for v1 byte-parity rewrites.

| API | Partition / boundary | Expected | Test ID |
|-----|----------------------|----------|---------|
| ``save_figure`` | default | tight bounding box (unchanged) | GA590-EP-1 |
| ``save_figure`` | ``bbox_inches=None`` | full canvas, as v1 ``fig.savefig(path)`` | GA590-EP-1 |
| ``save_figure`` | ``bbox_inches="tight", pad_inches=0`` | matches ``savefig`` with the same options | GA590-EP-1 |
| ``plot_lines`` | ``bbox_inches=None`` | full canvas | GA590-EP-2 |
| ``plot_lines`` | ``labels=`` / 3-tuple pairs | legend shows the given labels | GA590-EP-3 |
| ``plot_lines`` | labels length mismatch / both spellings | ValueError | GA590-EP-4 |
| ``plot_lines`` | 1- or 4-item pair | ValueError | GA590-BV-1 |
| ``plot_lines`` | ``grid`` default / True | grid off / on | GA590-EP-5 |
| ``plot_lines`` | label font size default / explicit | rcParams / explicit | GA590-EP-6 |
| ``save_meta`` | default / ``indent=2`` | 4-space, as v1 ``Meta.writefile`` / 2-space | GA590-EP-7 |
| ``read_excel_fills`` | rgb / indexed / theme / none | ARGB / ARGB / ``theme:N`` / None | GA590-EP-8 |
| ``read_excel_fills`` | header, skiprows, nrows, trailing styled rows | aligned with ``read_excel`` rows | GA590-EP-9 |
| ``read_excel_fills`` | sheet position / column position | same as name / letter | GA590-EP-10 |
| ``read_excel_fills`` | unknown sheet / bad column / negative skiprows | KeyError, IndexError / ValueError | GA590-BV-2 |
| ``unzip_inputs`` | default | files only (unchanged) | GA590-EP-11 |
| ``unzip_inputs`` | ``include_dirs=True`` | directory entries in archive order | GA590-EP-11 |
| ``rdetoolkit.nodes`` | public namespace | no ``typing.cast`` leak | GA590-EP-12 |
"""

from __future__ import annotations

import json
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

import matplotlib as mpl
import matplotlib.pyplot as plt
import openpyxl
import pandas as pd
import pytest
from matplotlib.axes import Axes
from openpyxl.styles import PatternFill
from openpyxl.styles.colors import Color
from PIL import Image

from rdetoolkit.nodes import plot_lines, save_figure, save_meta, unzip_inputs
from rdetoolkit.testing import make_output_context
from rdetoolkit.types import Metadata


def _figure(width: float = 4, height: float = 3) -> plt.Figure:
    figure, axes = plt.subplots(figsize=(width, height))
    axes.plot([1, 2, 3], [3, 1, 2])
    return figure


def _savefig_size(figure: plt.Figure, **kwargs: Any) -> tuple[int, int]:
    buffer = BytesIO()
    figure.savefig(buffer, format="png", dpi=100, **kwargs)
    buffer.seek(0)
    with Image.open(buffer) as image:
        return image.size


def _size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def _record_axes(monkeypatch: pytest.MonkeyPatch) -> dict[str, Axes]:
    observed: dict[str, Axes] = {}
    original = Axes.plot

    def record(axes: Axes, *args: Any, **kwargs: Any) -> Any:
        observed["axes"] = axes
        return original(axes, *args, **kwargs)

    monkeypatch.setattr(Axes, "plot", record)
    return observed


# --- 1. save_figure / plot_lines bounding box -------------------------------


@pytest.mark.parametrize(
    "options",
    [{}, {"bbox_inches": None}, {"bbox_inches": "tight", "pad_inches": 0}, {"bbox_inches": "tight", "pad_inches": 0.5}],
)
def test_save_figure_bounding_box_matches_savefig__ga590_ep_1(tmp_path: Path, options: dict[str, Any]) -> None:
    """GA590-EP-1: save_figure reproduces the canvas of ``fig.savefig`` options."""
    # Given: a caller-owned figure and the canvas savefig would write
    figure = _figure()
    try:
        expected_options = {"bbox_inches": "tight", **options}
        expected = _savefig_size(figure, **expected_options)
        # When: saving through the node with the same options
        path = save_figure(figure, make_output_context(tmp_path), "figure.png", dpi=100, **options)
        # Then: the written canvas has exactly the savefig size
        assert _size(path) == expected
    finally:
        plt.close(figure)


def test_save_figure_full_canvas_matches_v1_default__ga590_ep_1(tmp_path: Path) -> None:
    """GA590-EP-1: ``bbox_inches=None`` writes the whole figure like v1 ``fig.savefig(path)``."""
    # Given: a 4x3 inch figure
    figure = _figure()
    try:
        # When: disabling the tight bounding box
        path = save_figure(figure, make_output_context(tmp_path), "figure.png", dpi=100, bbox_inches=None)
        # Then: the canvas is the exact figure size, unlike the tight default
        assert _size(path) == (400, 300)
        tight = save_figure(figure, make_output_context(tmp_path / "tight"), "figure.png", dpi=100)
        assert _size(tight) != (400, 300)
    finally:
        plt.close(figure)


def test_plot_lines_bounding_box_options__ga590_ep_2(tmp_path: Path) -> None:
    """GA590-EP-2: plot_lines forwards the bounding box options to savefig."""
    # Given: a simple frame
    frame = pd.DataFrame({"x": [1, 2], "y": [3, 4]})
    out = make_output_context(tmp_path)
    # When: rendering without the tight bounding box, and tight without padding
    full = plot_lines(frame, out, "full.png", x="x", figsize=(5, 4), dpi=100, bbox_inches=None)
    padded = plot_lines(frame, out, "padded.png", x="x", figsize=(5, 4), dpi=100)
    unpadded = plot_lines(frame, out, "unpadded.png", x="x", figsize=(5, 4), dpi=100, pad_inches=0)
    # Then: the full canvas is kept and removing the padding shrinks the tight box
    assert _size(full) == (500, 400)
    padded_width, padded_height = _size(padded)
    unpadded_width, unpadded_height = _size(unpadded)
    assert unpadded_width < padded_width
    assert unpadded_height < padded_height


# --- 2. plot_lines labels, grid and font size --------------------------------


@pytest.mark.parametrize(
    "options",
    [
        {"pairs": [("x1", "y1", "first"), ("x2", "y2", "second")]},
        {"pairs": [("x1", "y1"), ("x2", "y2")], "labels": ["first", "second"]},
        {"x": "x1", "y": ["y1", "y2"], "labels": ["first", "second"]},
    ],
)
def test_plot_lines_series_labels__ga590_ep_3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, options: dict[str, Any]) -> None:
    """GA590-EP-3: per-series legend labels can replace the y column names."""
    # Given: two series and a hook on the created axes
    frame = pd.DataFrame({"x1": [1, 2], "y1": [3, 4], "x2": [5, 6], "y2": [7, 8]})
    observed = _record_axes(monkeypatch)
    # When: labelling each series explicitly
    plot_lines(frame, make_output_context(tmp_path), "labels.png", **options)
    # Then: the lines and the legend carry the explicit labels
    axes = observed["axes"]
    assert [line.get_label() for line in axes.lines] == ["first", "second"]
    legend = axes.get_legend()
    assert legend is not None
    assert [text.get_text() for text in legend.get_texts()] == ["first", "second"]


def test_plot_lines_mixed_pair_labels_default_to_column__ga590_ep_3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA590-EP-3: a 2-item pair next to a labelled pair keeps its y column label."""
    # Given: one labelled and one unlabelled pair
    frame = pd.DataFrame({"x1": [1, 2], "y1": [3, 4], "x2": [5, 6], "y2": [7, 8]})
    observed = _record_axes(monkeypatch)
    # When: plotting both
    plot_lines(frame, make_output_context(tmp_path), "mixed.png", pairs=[("x1", "y1", "first"), ("x2", "y2")])
    # Then: only the labelled pair is renamed
    assert [line.get_label() for line in observed["axes"].lines] == ["first", "y2"]


@pytest.mark.parametrize(
    "options",
    [
        {"x": "x1", "y": ["y1", "y2"], "labels": ["only-one"]},
        {"x": "x1", "y": "y1", "labels": ["one", "two"]},
        {"x": "x1", "y": "y1", "labels": []},
        {"pairs": [("x1", "y1", "first")], "labels": ["again"]},
    ],
)
def test_plot_lines_rejects_inconsistent_labels__ga590_ep_4(tmp_path: Path, options: dict[str, Any]) -> None:
    """GA590-EP-4: labels must match the series one to one and have one spelling."""
    # Given: a frame with two series
    frame = pd.DataFrame({"x1": [1, 2], "y1": [3, 4], "y2": [5, 6]})
    before = set(plt.get_fignums())
    # When / Then: an inconsistent label specification is rejected before plotting
    with pytest.raises(ValueError, match="label"):
        plot_lines(frame, make_output_context(tmp_path), "bad.png", **options)
    assert set(plt.get_fignums()) == before


@pytest.mark.parametrize("pair", [("x1",), ("x1", "y1", "label", "extra")])
def test_plot_lines_rejects_malformed_pairs__ga590_bv_1(tmp_path: Path, pair: tuple[str, ...]) -> None:
    """GA590-BV-1: pairs hold exactly an x column, a y column and an optional label."""
    # Given: a pair with too few or too many items
    frame = pd.DataFrame({"x1": [1, 2], "y1": [3, 4]})
    # When / Then: it is rejected with a clear error
    with pytest.raises(ValueError, match="pairs"):
        plot_lines(frame, make_output_context(tmp_path), "bad.png", pairs=[pair])  # type: ignore[list-item]


@pytest.mark.parametrize("grid", [False, True])
def test_plot_lines_grid__ga590_ep_5(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, grid: bool) -> None:
    """GA590-EP-5: the grid is off by default and drawn on request."""
    # Given: a simple frame
    frame = pd.DataFrame({"x": [1, 2], "y": [3, 4]})
    observed = _record_axes(monkeypatch)
    # When: plotting with or without the grid
    options = {"grid": True} if grid else {}
    plot_lines(frame, make_output_context(tmp_path), "grid.png", x="x", **options)
    # Then: the major grid lines follow the option
    axes = observed["axes"]
    assert all(line.get_visible() is grid for line in axes.xaxis.get_gridlines())
    assert all(line.get_visible() is grid for line in axes.yaxis.get_gridlines())


def test_plot_lines_label_font_size_follows_rcparams__ga590_ep_6(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA590-EP-6: without an explicit size the axis labels follow rcParams."""
    # Given: rcParams selecting a non-default label size
    frame = pd.DataFrame({"x": [1, 2], "y": [3, 4]})
    observed = _record_axes(monkeypatch)
    # When: plotting under those rcParams
    with mpl.rc_context({"axes.labelsize": 17}):
        plot_lines(frame, make_output_context(tmp_path), "rc.png", x="x")
    # Then: the configured size is used rather than a fixed 10 points
    axes = observed["axes"]
    assert axes.xaxis.label.get_fontsize() == pytest.approx(17)
    assert axes.yaxis.label.get_fontsize() == pytest.approx(17)


def test_plot_lines_explicit_label_font_size__ga590_ep_6(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA590-EP-6: an explicit label font size overrides rcParams."""
    # Given: rcParams with another label size
    frame = pd.DataFrame({"x": [1, 2], "y": [3, 4]})
    observed = _record_axes(monkeypatch)
    # When: requesting an explicit size
    with mpl.rc_context({"axes.labelsize": 17}):
        plot_lines(frame, make_output_context(tmp_path), "explicit.png", x="x", label_fontsize=8)
    # Then: the explicit size wins
    axes = observed["axes"]
    assert axes.xaxis.label.get_fontsize() == pytest.approx(8)
    assert axes.yaxis.label.get_fontsize() == pytest.approx(8)


# --- 3. save_meta indentation ------------------------------------------------


def test_save_meta_uses_v1_indentation__ga590_ep_7(tmp_path: Path) -> None:
    """GA590-EP-7: metadata.json is written with v1 ``Meta.writefile`` 4-space indentation."""
    # Given: metadata with a unit and a repeated row
    metadata = Metadata(custom={"name": "測定"}, units={"name": "-"}, variable=[{"x": {"value": 1}}])
    # When: saving with the defaults
    path = save_meta(metadata, make_output_context(tmp_path))
    # Then: the bytes match json.dump(indent=4, ensure_ascii=False)
    expected = {"constant": {"name": {"value": "測定", "unit": "-"}}, "variable": [{"x": {"value": 1}}]}
    assert path.read_text(encoding="utf-8") == json.dumps(expected, indent=4, ensure_ascii=False)


@pytest.mark.parametrize("indent", [None, 0, 2])
def test_save_meta_indent_option__ga590_ep_7(tmp_path: Path, indent: int | None) -> None:
    """GA590-EP-7: the indentation can be selected explicitly."""
    # Given: simple metadata
    metadata = Metadata(custom={"a": 1})
    # When: saving with an explicit indentation
    path = save_meta(metadata, make_output_context(tmp_path), indent=indent)
    # Then: json.dumps formatting is applied verbatim
    expected = {"constant": {"a": {"value": 1}}, "variable": []}
    assert path.read_text(encoding="utf-8") == json.dumps(expected, indent=indent, ensure_ascii=False)


# --- 5. read_excel_fills -----------------------------------------------------


def _fill(color: str | Color) -> PatternFill:
    return PatternFill(fill_type="solid", start_color=color, end_color=color)


def _styled_workbook(path: Path) -> None:
    workbook = openpyxl.Workbook()
    decoy = workbook.active
    assert decoy is not None
    decoy.title = "first"
    decoy.append(["decoy"])
    sheet = workbook.create_sheet("samples")
    sheet.append(["Sample list"])
    sheet.append(["name", "value"])
    sheet.append(["a", 1])
    sheet.append(["b", 2])
    sheet.append([None, None])
    sheet.append(["d", 4])
    sheet.append(["e", 5])
    sheet["A3"].fill = _fill("FFFFFF00")
    sheet["A4"].fill = _fill(Color(indexed=10))
    sheet["A6"].fill = _fill(Color(theme=4))
    sheet["B6"].fill = _fill("FF00FF00")
    sheet["A9"].fill = _fill("FF0000FF")  # styled but empty trailing row: pandas drops it
    workbook.save(path)


def test_read_excel_fills_colour_kinds__ga590_ep_8(tmp_path: Path) -> None:
    """GA590-EP-8: rgb, indexed and theme fills are reported; unfilled cells are None."""
    from rdetoolkit.nodes import read_excel_fills

    # Given: a template selecting rows by fill colour
    path = tmp_path / "template.xlsx"
    _styled_workbook(path)
    # When: reading the fills of the first column below the header
    fills = read_excel_fills(path, sheet_name="samples", column="A", skiprows=1)
    # Then: each data row has its colour, aligned with the pandas rows
    assert fills == ["FFFFFF00", "00FF0000", None, "theme:4", None]
    assert len(fills) == len(pd.read_excel(path, sheet_name="samples", skiprows=1))


@pytest.mark.parametrize(
    "options",
    [
        {"skiprows": 1},
        {"skiprows": 1, "header": None},
        {"header": None},
        {"header": 1},
        {"skiprows": 1, "nrows": 2},
        {"skiprows": 1, "nrows": 0},
        {"skiprows": 1, "nrows": 50},
        {"skiprows": 20},
    ],
)
def test_read_excel_fills_rows_align_with_read_excel__ga590_ep_9(tmp_path: Path, options: dict[str, Any]) -> None:
    """GA590-EP-9: one fill per data row produced by ``read_excel`` with the same options."""
    from rdetoolkit.nodes import read_excel, read_excel_fills

    # Given: a styled workbook with blank and trailing styled rows
    path = tmp_path / "template.xlsx"
    _styled_workbook(path)
    # When: reading values and fills with the same row options
    frame = read_excel(path, sheet_name="samples", **options)
    fills = read_excel_fills(path, sheet_name="samples", column="A", **options)
    # Then: the lists line up row by row and can become a column
    assert len(fills) == len(frame)


def test_read_excel_fills_positions__ga590_ep_10(tmp_path: Path) -> None:
    """GA590-EP-10: zero-based sheet and column positions are accepted like pandas."""
    from rdetoolkit.nodes import read_excel_fills

    # Given: the styled workbook
    path = tmp_path / "template.xlsx"
    _styled_workbook(path)
    # When: selecting the sheet and the second column by position
    by_position = read_excel_fills(path, sheet_name=1, column=1, skiprows=1)
    by_name = read_excel_fills(path, sheet_name="samples", column="B", skiprows=1)
    # Then: both spellings select the same cells
    assert by_position == by_name == [None, None, None, "FF00FF00", None]


@pytest.mark.parametrize(
    "options,error",
    [
        ({"sheet_name": "missing", "column": "A"}, KeyError),
        ({"sheet_name": 9, "column": "A"}, IndexError),
        ({"sheet_name": "samples", "column": -1}, ValueError),
        ({"sheet_name": "samples", "column": "1A"}, ValueError),
        ({"sheet_name": "samples", "column": "A", "skiprows": -1}, ValueError),
    ],
)
def test_read_excel_fills_rejects_bad_selection__ga590_bv_2(tmp_path: Path, options: dict[str, Any], error: type[Exception]) -> None:
    """GA590-BV-2: unknown sheets and invalid column or row selections fail clearly."""
    from rdetoolkit.nodes import read_excel_fills

    # Given: the styled workbook
    path = tmp_path / "template.xlsx"
    _styled_workbook(path)
    # When / Then: the invalid selection is rejected
    with pytest.raises(error):
        read_excel_fills(path, **options)


# --- 6. unzip_inputs directories ---------------------------------------------


def _archive_with_directories(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("top/", "")
        archive.writestr("top/data.txt", "measured")
        archive.writestr("top/empty/", "")
        archive.writestr("other/", "")


def test_unzip_inputs_default_returns_files_only__ga590_ep_11(tmp_path: Path) -> None:
    """GA590-EP-11: the default return value is unchanged (files only)."""
    # Given: an archive with explicit and empty directory entries
    source = tmp_path / "input.zip"
    _archive_with_directories(source)
    destination = tmp_path / "output"
    # When: extracting with the default options
    extracted = unzip_inputs(source, destination)
    # Then: only the file is returned, while empty directories still exist on disk
    assert extracted == [(destination / "top/data.txt").resolve()]
    assert (destination / "top/empty").is_dir()


def test_unzip_inputs_include_dirs__ga590_ep_11(tmp_path: Path) -> None:
    """GA590-EP-11: ``include_dirs=True`` keeps directory entries in archive order."""
    # Given: an archive with explicit and empty directory entries
    source = tmp_path / "input.zip"
    _archive_with_directories(source)
    destination = tmp_path / "output"
    # When: requesting directory entries
    extracted = unzip_inputs(source, destination, include_dirs=True)
    # Then: the archive structure is listed in archive order
    base = destination.resolve()
    assert extracted == [base / "top", base / "top/data.txt", base / "top/empty", base / "other"]
    assert [path.is_dir() for path in extracted] == [True, False, True, True]


def test_unzip_inputs_include_dirs_skips_unsafe_directories__ga590_ep_11(tmp_path: Path) -> None:
    """GA590-EP-11: unsafe directory entries are skipped like unsafe files."""
    # Given: an archive whose directory entry escapes the destination
    source = tmp_path / "input.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("../outside/", "")
        archive.writestr("inside/", "")
    destination = tmp_path / "output"
    # When: requesting directory entries
    extracted = unzip_inputs(source, destination, include_dirs=True)
    # Then: only the contained directory is returned and nothing escapes
    assert extracted == [destination.resolve() / "inside"]
    assert not (tmp_path / "outside").exists()


# --- 10. namespace hygiene ---------------------------------------------------


def test_nodes_namespace_does_not_leak_typing_cast__ga590_ep_12() -> None:
    """GA590-EP-12: ``rdetoolkit.nodes.cast`` is not part of the public namespace."""
    import rdetoolkit.nodes as nodes

    # Given / When: inspecting the builtin node package
    # Then: typing.cast is not re-exported, and every public name is listed
    assert not hasattr(nodes, "cast")
    assert "read_excel_fills" in nodes.__all__


# --- 4. build_meta originalName precedence ------------------------------------


@pytest.mark.parametrize(
    "values,expected",
    [
        ({"temperature": 1.5}, 1.5),
        ({"T": 2.5}, 2.5),
        ({"temperature": 1.5, "T": 2.5}, 1.5),
        ({"temperature": None, "T": 2.5}, None),
    ],
)
def test_build_meta_original_name_precedence_matches_v1__ga590_ep_13(tmp_path: Path, values: dict[str, Any], expected: float | None) -> None:
    """GA590-EP-13: the definition key wins; originalName is only a fallback, as in v1 Meta."""
    from rdetoolkit.nodes import build_meta
    from rdetoolkit.rde2util import Meta

    # Given: a definition whose originalName differs from its key
    metadef = tmp_path / "metadata-def.json"
    metadef.write_text(json.dumps({"temperature": {"schema": {"type": "number"}, "originalName": "T"}}), encoding="utf-8")
    # When: building metadata with one or both spellings
    metadata = build_meta(values, metadef)
    # Then: the documented precedence holds and matches v1 Meta.assign_vals
    assert metadata.custom.get("temperature") == expected
    v1 = Meta(metadef)
    v1.assign_vals(values)
    assert v1.to_dict()["constant"].get("temperature", {}).get("value") == expected
