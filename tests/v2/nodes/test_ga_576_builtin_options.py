"""GA576 EP/BV: builtin artifact options, excluding the deferred ZIP change."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import pytest
from matplotlib.axes import Axes
from PIL import Image

from rdetoolkit.nodes import plot_lines, read_excel, save_csv, save_json
from rdetoolkit.testing import make_output_context
from rdetoolkit.types import OutputContext


def test_excel_options_match_pandas__ga576_ep_1(tmp_path: Path) -> None:
    """GA576-EP-1: selecting a sheet and raw row/column layout matches pandas."""
    # Given: a workbook with a decoy first sheet and an instrument-specific layout
    path = tmp_path / "source.xlsx"
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame({"wrong": [0]}).to_excel(writer, sheet_name="first", index=False)
        pd.DataFrame([["skip", "skip"], [1, 2], [3, 4], [5, 6]]).to_excel(writer, sheet_name="measurements", header=False, index=False)
    # When: using all requested Excel selection options
    actual = read_excel(path, sheet_name="measurements", header=None, skiprows=1, nrows=2, usecols=[1])
    # Then: data selection exactly matches the underlying pandas operation
    expected = pd.read_excel(path, sheet_name="measurements", header=None, skiprows=1, nrows=2, usecols=[1])
    pd.testing.assert_frame_equal(actual, expected)


@pytest.mark.parametrize("header,index", [(False, False), (True, True), (["measurement"], False)])
def test_csv_options_match_pandas__ga576_ep_2(tmp_path: Path, header: bool | list[str], index: bool) -> None:
    """GA576-EP-2: precision, headers and index reproduce v1 template CSV bytes."""
    # Given: a data frame with a fractional measurement
    frame = pd.DataFrame({"value": [1.23456, 2.34567]})
    # When: saving with explicit pandas formatting options
    path = save_csv(frame, make_output_context(tmp_path), "values.csv", float_format="%.2f", header=header, index=index)
    # Then: the node does not invent an extra header or index
    assert path.read_text(encoding="utf-8") == frame.to_csv(float_format="%.2f", header=header, index=index)


@pytest.mark.parametrize("as_facade", [False, True])
@pytest.mark.parametrize("image_name", ["figure.png", "figure.jpg"])
def test_json_text_invoice_and_figure_outputs__ga576_ep_3(tmp_path: Path, as_facade: bool, image_name: str) -> None:
    """GA576-EP-3: canonical nodes write each requested artifact destination."""
    from rdetoolkit.nodes import read_json, save_figure, save_invoice, save_text
    from rdetoolkit.types import InvoiceData

    # Given: output directories, an edited invoice and a caller-owned figure
    out = make_output_context(tmp_path)
    content = {"custom": {"label": "測定"}}
    figure, axes = plt.subplots()
    axes.plot([1, 2], [3, 4])
    # When: writing all supported kinds of artifacts
    try:
        json_path = save_json(content, out, "copy.json", kind="attachment")
        text_path = save_text("日本語\n", out, "notes.txt", kind="attachment")
        invoice_path = save_invoice(InvoiceData(raw=content) if as_facade else content, out)
        figure_path = save_figure(figure, out, image_name, kind="other_image", dpi=75)
        # Then: content/format/destination match the requested contract
        assert read_json(json_path) == content
        assert json_path.parent == text_path.parent == out.attachment
        assert text_path.read_text(encoding="utf-8") == "日本語\n"
        assert invoice_path == out.invoice / "invoice.json"
        assert invoice_path.read_text(encoding="utf-8") == json.dumps(content, indent=4, ensure_ascii=False)
        assert figure_path.parent == out.other_image
        with Image.open(figure_path) as image:
            assert image.width > 10
            assert image.info["dpi"][0] == pytest.approx(75, abs=0.1)
        assert plt.fignum_exists(figure.number)
    finally:
        plt.close(figure)


def test_line_plot_options_are_applied__ga576_ep_4(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA576-EP-4: selected x/y columns and visual settings reach the axes."""
    # Given: a frame whose index is different from the x coordinates
    frame = pd.DataFrame({"time": [1, 10], "signal": [2, 20], "other": [3, 30]})
    observed: dict[str, Any] = {}
    original = Axes.plot

    def record(axes: Axes, *args: Any, **kwargs: Any) -> Any:
        observed["axes"] = axes
        return original(axes, *args, **kwargs)

    monkeypatch.setattr(Axes, "plot", record)
    # When: selecting series and all requested presentation options
    out = make_output_context(tmp_path)
    path = plot_lines(frame, out, "lines.png", x="time", y="signal", title="Measurement", xlabel="Time", ylabel="Intensity", yscale="log", legend=False, figsize=(4, 3), dpi=100, kind="other_image")
    # Then: no x column is plotted as a measurement, and settings are retained
    axes = observed["axes"]
    assert len(axes.lines) == 1
    assert list(axes.lines[0].get_xdata()) == [1, 10]
    assert list(axes.lines[0].get_ydata()) == [2, 20]
    assert axes.get_title() == "Measurement"
    assert axes.get_xlabel() == "Time"
    assert axes.get_ylabel() == "Intensity"
    assert axes.get_yscale() == "log"
    assert axes.get_legend() is None
    assert tuple(axes.figure.get_size_inches()) == (4, 3)
    assert path.parent == out.other_image
    with Image.open(path) as image:
        assert image.info["dpi"][0] == pytest.approx(100, abs=0.1)
    assert not plt.fignum_exists(axes.figure.number)


def test_line_plot_supports_independent_pairs__ga576_ep_4(tmp_path: Path) -> None:
    """GA576-EP-4: independent x/y pairs can share one plot."""
    # Given: measurements with independent horizontal coordinates
    frame = pd.DataFrame({"x1": [1, 2], "y1": [3, 4], "x2": [5, 6], "y2": [7, 8]})
    before = set(plt.get_fignums())
    # When: plotting explicit pairs
    path = plot_lines(frame, make_output_context(tmp_path), "pairs.png", pairs=[("x1", "y1"), ("x2", "y2")])
    # Then: a real image is produced with no leaked pyplot state
    with Image.open(path) as image:
        assert image.width > 10
    assert set(plt.get_fignums()) == before


@pytest.mark.parametrize("selection", [{"x": "x"}, {"x": "x", "y": ["y", "z"]}, {"y": ["y"]}])
def test_line_selection_variants__ga576_ep_4(tmp_path: Path, selection: dict[str, Any]) -> None:
    """GA576-EP-4: automatic columns, explicit column lists and named indexes work."""
    # Given: a frame with a named index and two measurement series
    frame = pd.DataFrame({"x": [1, 2], "y": [3, 4], "z": [5, 6]})
    frame.index.name = "row"
    # When: using different supported selection forms
    path = plot_lines(frame, make_output_context(tmp_path), "selected.png", **selection)
    # Then: a valid image is produced for each form
    with Image.open(path) as image:
        assert image.height > 10


def test_unencodable_text_is_not_published__ga576_neg_2(tmp_path: Path) -> None:
    """GA576-NEG-2: encoding failures never produce a partial text artifact."""
    from rdetoolkit.nodes import save_text

    # Given: text that cannot be represented in the requested encoding
    out = make_output_context(tmp_path)
    # When: saving it with a restrictive codec
    with pytest.raises(UnicodeEncodeError):
        save_text("日本語", out, "invalid.txt", encoding="ascii")
    # Then: there is no misleading output file
    assert not (out.struct / "invalid.txt").exists()


def test_read_json_uses_v1_cp932_rule__ga576_ep_5(tmp_path: Path) -> None:
    """GA576-EP-5: CP932 extension characters round-trip through JSON/text nodes."""
    from rdetoolkit.nodes import read_json, read_text

    # Given: JSON with Japanese extension characters encoded as CP932
    path = tmp_path / "source.json"
    label = "こんにちは世界。日本語の測定データを記録しています。温度と圧力の測定結果①㈱"
    text = json.dumps({"label": label}, ensure_ascii=False)
    path.write_bytes(text.encode("cp932"))
    # When: reading it using the public v2 nodes
    actual = read_json(path)
    decoded = read_text(path)
    # Then: the data matches the v1 character preference rule
    assert actual == {"label": label}
    assert decoded == text


@pytest.mark.parametrize("sheet", ["missing", 10])
def test_missing_excel_sheet_raises__ga576_neg_1(tmp_path: Path, sheet: str | int) -> None:
    """GA576-NEG-1: invalid sheet selection propagates a useful pandas error."""
    # Given: a valid one-sheet workbook
    path = tmp_path / "source.xlsx"
    pd.DataFrame({"x": [1]}).to_excel(path, index=False)
    # When: selecting a nonexistent sheet
    with pytest.raises(ValueError):
        read_excel(path, sheet_name=sheet)
    # Then: reading never changes the source
    assert path.is_file()


@pytest.mark.parametrize("missing", [False, True])
def test_json_read_errors_are_not_suppressed__ga576_neg_2(tmp_path: Path, missing: bool) -> None:
    """GA576-NEG-2: missing and malformed JSON never become empty data."""
    from rdetoolkit.nodes import read_json

    # Given: a missing or malformed JSON source
    path = tmp_path / "source.json"
    if not missing:
        path.write_text("invalid JSON", encoding="utf-8")
    # When: reading it
    with pytest.raises(FileNotFoundError if missing else json.JSONDecodeError):
        read_json(path)
    # Then: no output artifact was generated
    assert not (tmp_path / "metadata.json").exists()


@pytest.mark.parametrize("filename,kind", [("../escape.txt", "struct"), ("output.txt", "invalid")])
def test_text_output_rejects_unsafe_destination__ga576_neg_3(tmp_path: Path, filename: str, kind: Any) -> None:
    """GA576-NEG-3: output validation remains owned by OutputContext."""
    from rdetoolkit.nodes import save_text

    # Given: a noncanonical artifact name or destination kind
    out = make_output_context(tmp_path)
    # When: writing a text artifact
    with pytest.raises(ValueError):
        save_text("text", out, filename, kind=kind)
    # Then: nothing escapes into the parent directory
    assert not (tmp_path / "escape.txt").exists()


@pytest.mark.parametrize("options", [{"x": "missing"}, {"x": "x", "y": "missing"}, {"pairs": []}, {"pairs": [("x", "y")], "x": "x"}, {"pairs": [("x", "y")], "y": "y"}, {"yscale": "invalid"}])
def test_invalid_plot_options_close_internal_figures__ga576_neg_4(tmp_path: Path, options: dict[str, Any]) -> None:
    """GA576-NEG-4: failed plotting must not leak figures or publish an image."""
    # Given: valid data with an invalid plot selection or setting
    frame = pd.DataFrame({"x": [1, 2], "y": [3, 4]})
    out = make_output_context(tmp_path)
    before = set(plt.get_fignums())
    # When: rendering the invalid request
    with pytest.raises((KeyError, ValueError)):
        plot_lines(frame, out, "invalid.png", **options)
    # Then: the node closes its own figure even when rendering fails
    assert set(plt.get_fignums()) == before
    assert not (out.main_image / "invalid.png").exists()
