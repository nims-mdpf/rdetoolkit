r"""GE-02 (#708): unique, deterministic figure filenames that never overwrite each other.

Intentional behaviour change (design IC-3, versioned tests end in ``_v2_0``): individual
figure stems that collide under the case-insensitive, NFC-normalized collision key all
get ``_{series_id}`` appended (``p_voltage_s000``, ``p_voltage_s001``) instead of
overwriting one shared file, and ``/``, ``\`` and ``..`` in a header or base name are
sanitized instead of failing after the overlay was already written. A stem whose key is
unique stays byte-identical to the v1 name.

EP table:

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| series_stem | header that needs no sanitizing (plain, series prefix, unit, Unicode) | byte-identical to the v1 formula | TC-GE02-EP-001 |
| series_stem / sanitize_stem | header containing / \ * ? : " < > pipe or .. | sanitized; never a separator or ".." | TC-GE02-EP-002 |
| reserve_stems | all keys unique | stems unchanged, no diagnostic | TC-GE02-EP-003 |
| reserve_stems | case / NFC-NFD collision group | every member suffixed with its series id, one warning diagnostic | TC-GE02-EP-004 |
| reserve_stems | empty candidate stem / empty or duplicate series id / non-str | ValueError / TypeError, nothing reserved | TC-GE02-EP-005 |
| plot_from_dataframe | Voltage/voltage, A B/A_B, s: a (V)/s: b (A), NFC/NFD, a/b + a_b, .. | one distinct file per series + overlay, GraphUserWarning | TC-GE02-EP-006 |
| plot_from_dataframe | header "a/b" in overlay mode (v1 failed after p.png was written) | p.png and p_a_b.png written | TC-GE02-EP-007 |
| plot_from_dataframe | base name containing ".." | sanitized overlay and individual stems | TC-GE02-EP-008 |
| csv2graph | CSV with duplicate and empty headers (y, y.1, Unnamed: 3, Unnamed: 4) | 5 distinct files, contents distinct | TC-GE02-EP-009 |
| IndividualStrategy | DataFrame with two columns literally labelled "y" / two empty labels | two distinct RenderResult names | TC-GE02-EP-010 |
| IndividualStrategy | names reserved before the first render (naming failure, ambiguous label) | renderer never called | TC-GE02-EP-011 |
| IndividualStrategy | y columns given by label | same reserved names as positional specs | TC-GE02-EP-010 |
| plot_from_dataframe | return_fig with a collision | in-memory artifact names unique | TC-GE02-EP-012 |
| GraphDiagnostic | value contract | frozen, code/severity/message/series_ids | TC-GE02-EP-013 |

BV table:

| API | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| reserve_stems | zero candidates | ((), ()) | TC-GE02-BV-001 |
| plot_from_dataframe | one series | legacy name, no warning | TC-GE02-BV-002 |
| IndividualStrategy | two identical headers | two suffixed files, distinct contents | TC-GE02-BV-003 |
| IndividualStrategy | 30 identical headers | 30 distinct names s000..s029, distinct contents | TC-GE02-BV-004 |
| reserve_stems | natural stem equal to another series' suffixed stem | suffixed one is suffixed again, natural kept | TC-GE02-BV-005 |
| reserve_stems | suffix chain needed twice (natural "x_s000" and "x_s000_s000") | still unique, terminates | TC-GE02-BV-006 |
| plot_from_dataframe | two runs into different directories | identical name lists | TC-GE02-BV-007 |
| reserve_stems | property: arbitrary candidate lists | unique under key, stable, unique keys untouched | TC-GE02-BV-008 |
"""

from __future__ import annotations

import dataclasses
import hashlib
import shutil
import unicodedata
import warnings
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from hypothesis import given, settings, strategies as st

from rdetoolkit.graph.api.csv2graph import csv2graph, plot_from_dataframe
from rdetoolkit.graph.exceptions import GraphUserWarning
from rdetoolkit.graph.models import OutputConfig, PlotConfig, PlotMode
from rdetoolkit.graph.naming import (
    GraphDiagnostic,
    collision_key,
    reserve_stems,
    sanitize_stem,
    series_stem,
)
from rdetoolkit.graph.renderers.matplotlib_renderer import MatplotlibRenderer
from rdetoolkit.graph.strategies.individual import IndividualStrategy
from rdetoolkit.graph.textutils import parse_header, sanitize_filename, to_snake_case

FIXTURES = Path(__file__).parent / "fixtures"
NFC_E = unicodedata.normalize("NFC", "café")
NFD_E = unicodedata.normalize("NFD", "café")


def _legacy_stem(base: str, header: str) -> str:
    """The v1 individual stem formula (strategies/individual.py before GE-02)."""
    parsed_series, _, _ = parse_header(header)
    return f"{sanitize_filename(base) or 'plot'}_{to_snake_case(parsed_series or header)}"


def _frame(headers: list[str]) -> pd.DataFrame:
    """A frame with an x column and one y column per header, each with distinct data."""
    data: dict[int, list[float]] = {0: [0.0, 1.0, 2.0]}
    for position, _ in enumerate(headers, start=1):
        data[position] = [float(position), float(position * 2 + 1), float(position * 3 + 2)]
    frame = pd.DataFrame(data)
    frame.columns = ["x", *headers]
    return frame


def _files(directory: Path) -> list[str]:
    return sorted(p.name for p in directory.iterdir()) if directory.exists() else []


def _digests(directory: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(directory.iterdir())}


def _plot(frame: pd.DataFrame, out: Path, **kwargs: Any) -> Any:
    return plot_from_dataframe(frame, out, title="p", **kwargs)


def _strategy_config(headers_count: int, *, base_name: str = "p") -> PlotConfig:
    return PlotConfig(
        mode=PlotMode.INDIVIDUAL,
        x_col=0,
        y_cols=list(range(1, headers_count + 1)),
        title="p",
        output=OutputConfig(base_name=base_name),
    )


# --- series_stem / sanitize_stem -------------------------------------------------------


@pytest.mark.parametrize(
    "header",
    [
        "Voltage",
        "voltage (V)",
        "Battery Voltage",
        "1cyc: capacity_calculated (mAh)",
        "s: a (V)",
        "y.1",
        "Unnamed: 3",
        "電圧 (V)",
        NFD_E,
        "",
    ],
)
def test_series_stem_matches_legacy_formula__tc_ge02_ep_001(header: str) -> None:
    # Given: a header that contains no path separator, reserved character or ".."
    parsed_series, _, _ = parse_header(header)
    # When: deriving the candidate stem
    stem = series_stem("p", parsed_series, header)
    # Then: it is byte-identical to the v1 file stem
    assert stem == _legacy_stem("p", header)


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("a/b", "p_a_b"),
        ("a\\b", "p_a_b"),
        ("..", "p__"),
        ("a..b", "p_a_b"),
        ("...", "p__."),
        ("x (a:b)", "p_x_(a_b)"),
        ('q*?"<>|', "p_q______"),
    ],
)
def test_series_stem_sanitizes_unsafe_headers_v2_0__tc_ge02_ep_002(header: str, expected: str) -> None:
    # Given: a header with path separators, reserved characters or ".."
    parsed_series, _, _ = parse_header(header)
    # When: deriving the candidate stem
    stem = series_stem("p", parsed_series, header)
    # Then: it is sanitized and can never address another directory
    assert stem == expected
    assert "/" not in stem
    assert "\\" not in stem
    assert ".." not in stem


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("plot", "plot"), ("a/b", "a_b"), ("a..b", "a_b"), ("....", "__"), ("", "")],
)
def test_sanitize_stem_replaces_separators_and_dot_pairs__tc_ge02_ep_002(raw: str, expected: str) -> None:
    # Given: a raw stem / When: sanitizing it
    result = sanitize_stem(raw)
    # Then: separators and ".." pairs are replaced, nothing else changes
    assert result == expected


@pytest.mark.parametrize("base", ["", "/", "..", "?"])
def test_series_stem_falls_back_to_plot_for_empty_base__tc_ge02_ep_002(base: str) -> None:
    # Given: a base name that sanitizes to nothing but underscores or to nothing
    # When: deriving a stem
    stem = series_stem(base, None, "v")
    # Then: an empty base falls back to "plot"; a non-empty one is kept sanitized
    expected_base = sanitize_stem(base) or "plot"
    assert stem == f"{expected_base}_v"
    assert ".." not in stem


# --- reserve_stems ---------------------------------------------------------------------


def test_reserve_stems_keeps_unique_stems__tc_ge02_ep_003() -> None:
    # Given: candidates whose collision keys are all distinct
    candidates = [("s000", "p_a"), ("s001", "p_b"), ("s002", "p_c")]
    # When: reserving them
    stems, diagnostics = reserve_stems(candidates)
    # Then: every stem is kept byte-identical and no diagnostic is produced
    assert stems == ("p_a", "p_b", "p_c")
    assert diagnostics == ()


@pytest.mark.parametrize(
    ("first", "second"),
    [("p_voltage", "p_Voltage"), (f"p_{NFC_E}", f"p_{NFD_E}"), ("p_STRASSE", "p_straße")],
)
def test_reserve_stems_suffixes_every_member_of_a_collision_group_v2_0__tc_ge02_ep_004(
    first: str, second: str,
) -> None:
    # Given: two stems that differ only by case or Unicode normalization
    candidates = [("s000", first), ("s001", "p_other"), ("s002", second)]
    # When: reserving them
    stems, diagnostics = reserve_stems(candidates)
    # Then: both members get their own series id, the unrelated stem is untouched
    assert stems == (f"{first}_s000", "p_other", f"{second}_s002")
    assert len({collision_key(s) for s in stems}) == 3
    # And: exactly one warning diagnostic names the group
    assert len(diagnostics) == 1
    diag = diagnostics[0]
    assert diag.code == "filename_collision"
    assert diag.severity == "warning"
    assert diag.series_ids == ("s000", "s002")
    assert first in diag.message
    assert f"{first}_s000" in diag.message


@pytest.mark.parametrize(
    ("candidates", "exc_type", "fragment"),
    [
        ([("s000", "")], ValueError, "empty"),
        ([("", "p_a")], ValueError, "series id"),
        ([("s000", "p_a"), ("s000", "p_b")], ValueError, "duplicate series id"),
        ([("s000", "p/a")], ValueError, "path separator"),
        ([("s000", "p..a")], ValueError, "path separator"),
        ([("s000", 1)], TypeError, "str"),
        ([(0, "p_a")], TypeError, "str"),
    ],
)
def test_reserve_stems_rejects_invalid_candidates__tc_ge02_ep_005(
    candidates: list[tuple[Any, Any]], exc_type: type[Exception], fragment: str,
) -> None:
    # Given: a candidate list that cannot name a file safely
    # When: reserving it
    with pytest.raises(exc_type, match=fragment):
        reserve_stems(candidates)
    # Then: the error is raised before anything is returned (no partial reservation)


def test_reserve_stems_empty_input__tc_ge02_bv_001() -> None:
    # Given: no candidates / When: reserving / Then: nothing reserved, nothing reported
    assert reserve_stems([]) == ((), ())


def test_reserve_stems_natural_name_equal_to_suffixed_name__tc_ge02_bv_005() -> None:
    # Given: "v" and "V" collide, and a third series is naturally named like the
    # suffixed name of the first
    candidates = [("s000", "p_v"), ("s001", "p_V"), ("s002", "p_v_s000")]
    # When: reserving them
    stems, diagnostics = reserve_stems(candidates)
    # Then: the natural name is kept and the suffixed one is suffixed again
    assert stems == ("p_v_s000_s000", "p_V_s001", "p_v_s000")
    assert len({collision_key(s) for s in stems}) == 3
    assert [d.series_ids for d in diagnostics] == [("s000", "s001"), ("s000", "s002")]
    assert all(d.code == "filename_collision" for d in diagnostics)


def test_reserve_stems_suffix_chain_terminates__tc_ge02_bv_006() -> None:
    # Given: naturals that occupy the first two suffix levels of a colliding stem
    candidates = [
        ("s000", "x"), ("s001", "X"), ("s002", "x_s000"), ("s003", "x_s000_s000"),
    ]
    # When: reserving them
    stems, _ = reserve_stems(candidates)
    # Then: the colliding member keeps growing its own id until it is unique
    assert stems == ("x_s000_s000_s000", "X_s001", "x_s000", "x_s000_s000")
    # And: the reservation is repeatable
    assert reserve_stems(candidates)[0] == stems


_STEM_ALPHABET = st.sampled_from(["p", "P", "_", "s000", "s001", "v", "V", NFC_E, NFD_E, "ß", "ss"])


@pytest.mark.property
@settings(max_examples=200, deadline=None)
@given(parts=st.lists(st.lists(_STEM_ALPHABET, min_size=1, max_size=4), max_size=12))
def test_reserve_stems_property_unique_stable_and_minimal__tc_ge02_bv_008(parts: list[list[str]]) -> None:
    # Given: arbitrary candidate stems built from colliding fragments
    candidates = [(f"s{i:03d}", "".join(p)) for i, p in enumerate(parts)]
    # When: reserving them twice
    stems, diagnostics = reserve_stems(candidates)
    again, diagnostics_again = reserve_stems(candidates)
    # Then: the result is stable and unique under the collision key
    assert (stems, diagnostics) == (again, diagnostics_again)
    assert len(stems) == len(candidates)
    assert len({collision_key(s) for s in stems}) == len(stems)
    # And: every final stem extends its own candidate; unique keys are untouched
    keys = [collision_key(c) for _, c in candidates]
    for (series_id, candidate), stem, key in zip(candidates, stems, keys, strict=True):
        assert stem.startswith(candidate)
        if keys.count(key) == 1:
            assert stem == candidate
        else:
            suffix = stem[len(candidate):]
            assert suffix
            assert suffix == f"_{series_id}" * (len(suffix) // len(f"_{series_id}"))
    # And: one diagnostic per initial collision group at least
    initial_groups = {k for k in keys if keys.count(k) > 1}
    assert len(diagnostics) >= len(initial_groups)


def test_graph_diagnostic_value_contract__tc_ge02_ep_013() -> None:
    # Given: a diagnostic / When: inspecting it
    diag = GraphDiagnostic(code="filename_collision", severity="warning", message="m", series_ids=("s000",))
    # Then: it is an immutable value with the documented defaults
    assert dataclasses.is_dataclass(diag)
    with pytest.raises(dataclasses.FrozenInstanceError):
        diag.code = "other"  # type: ignore[misc]
    assert GraphDiagnostic(code="c", severity="info", message="m").series_ids == ()


# --- facade: plot_from_dataframe / csv2graph ------------------------------------------


@pytest.mark.parametrize(
    ("headers", "expected_individual"),
    [
        (["Voltage", "voltage"], ["p_voltage_s000.png", "p_voltage_s001.png"]),
        (["A B", "A_B"], ["p_a_b_s000.png", "p_a_b_s001.png"]),
        (["s: a (V)", "s: b (A)"], ["p_s_s000.png", "p_s_s001.png"]),
        ([NFC_E, NFD_E], [f"p_{NFC_E}_s000.png", f"p_{NFD_E}_s001.png"]),
        (["a/b", "a_b"], ["p_a_b_s000.png", "p_a_b_s001.png"]),
        (["..", "_"], ["p___s000.png", "p___s001.png"]),
    ],
)
def test_colliding_series_get_separate_files_v2_0__tc_ge02_ep_006(
    tmp_path: Path, headers: list[str], expected_individual: list[str],
) -> None:
    # Given: two series whose v1 stems collide (or are unsafe)
    frame = _frame(headers)
    out = tmp_path / "out"
    main = tmp_path / "main"
    # When: plotting overlay + individual figures
    with pytest.warns(GraphUserWarning, match="filename_collision") as record:
        _plot(frame, out, main_image_dir=main)
    # Then: one overlay plus one individual file per series, nothing overwritten
    assert _files(main) == ["p.png"]
    assert _files(out) == sorted(expected_individual)
    assert len(_files(out)) == len(headers)
    # And: every individual file holds a different figure
    assert len(set(_digests(out).values())) == len(headers)
    # And: exactly one collision warning was emitted for the group
    graph_warnings = [str(w.message) for w in record if issubclass(w.category, GraphUserWarning)]
    assert len([text for text in graph_warnings if "filename_collision" in text]) == 1
    # And (GE-11): headers with different units add exactly one unit warning, others none
    unit_warnings = [text for text in graph_warnings if "different units" in text]
    assert len(unit_warnings) == (1 if headers == ["s: a (V)", "s: b (A)"] else 0)
    assert len(graph_warnings) == 1 + len(unit_warnings)


def test_unsafe_header_no_longer_fails_after_overlay_was_written_v2_0__tc_ge02_ep_007(tmp_path: Path) -> None:
    # Given: a header with a path separator (v1 wrote p.png, then raised ValueError)
    frame = _frame(["a/b"])
    out = tmp_path / "out"
    # When: plotting
    with warnings.catch_warnings():
        warnings.simplefilter("error", GraphUserWarning)
        _plot(frame, out, no_individual=False)
    # Then: both the overlay and the sanitized individual file exist
    assert _files(out) == ["p.png", "p_a_b.png"]


def test_dot_pair_in_base_name_is_sanitized_v2_0__tc_ge02_ep_008(tmp_path: Path) -> None:
    # Given: a base file name containing ".." (v1 raised ValueError at write time)
    frame = _frame(["v"])
    out = tmp_path / "out"
    # When: plotting
    plot_from_dataframe(frame, out, title="t", name="a..b", no_individual=False)
    # Then: the overlay and individual stems share the sanitized base
    assert _files(out) == ["a_b.png", "a_b_v.png"]


def test_duplicate_and_empty_headers_from_csv__tc_ge02_ep_009(tmp_path: Path) -> None:
    # Given: a CSV whose header has a duplicated "y" and two empty names
    # (pandas reads them as y, y.1, Unnamed: 3, Unnamed: 4)
    csv_path = tmp_path / "p.csv"
    shutil.copyfile(FIXTURES / "duplicate_labels.csv", csv_path)
    out = tmp_path / "out"
    main = tmp_path / "main"
    # When: plotting with the default reader
    with pytest.warns(GraphUserWarning, match="filename_collision"):
        csv2graph(csv_path, output_dir=out, main_image_dir=main)
    # Then: four individual files (the two empty headers no longer share p_unnamed.png)
    assert _files(main) == ["p.png"]
    assert _files(out) == ["p_unnamed_s002.png", "p_unnamed_s003.png", "p_y.1.png", "p_y.png"]
    assert len(set(_digests(out).values())) == 4
    # And: nothing was written next to the CSV
    assert _files(tmp_path) == ["main", "out", "p.csv"]


@pytest.mark.parametrize(("label", "expected_stem"), [("y", "p_y"), ("", "p_")])
def test_strategy_handles_literal_duplicate_labels__tc_ge02_ep_010(label: str, expected_stem: str) -> None:
    # Given: a DataFrame with two columns carrying the same label, addressed by position
    frame = _frame([label, label])
    strategy = IndividualStrategy(MatplotlibRenderer())
    # When: rendering individual figures
    with pytest.warns(GraphUserWarning, match="filename_collision"):
        results = strategy.render(frame, _strategy_config(2))
    # Then: two separately addressable results
    assert results is not None
    assert [r.filename for r in results] == [f"{expected_stem}_s000.png", f"{expected_stem}_s001.png"]


def test_strategy_reserves_names_before_first_render__tc_ge02_ep_011(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: a naming step that fails, and a renderer that records its calls
    calls: list[int] = []

    def _spy(self: MatplotlibRenderer, df: pd.DataFrame, config: PlotConfig, col: int, pos: int) -> Any:
        calls.append(col)
        return None

    def _fail(candidates: Any) -> Any:
        msg = "naming failed"
        raise ValueError(msg)

    monkeypatch.setattr(MatplotlibRenderer, "render_individual", _spy)
    monkeypatch.setattr("rdetoolkit.graph.strategies.individual.reserve_stems", _fail)
    strategy = IndividualStrategy(MatplotlibRenderer())
    # When: rendering
    with pytest.raises(ValueError, match="naming failed"):
        strategy.render(_frame(["a", "b"]), _strategy_config(2))
    # Then: no figure was rendered before naming was decided
    assert calls == []


def test_return_fig_artifacts_have_unique_names_v2_0__tc_ge02_ep_012(tmp_path: Path) -> None:
    # Given: colliding headers and an in-memory request
    out = tmp_path / "out"
    # When: plotting with return_fig
    with pytest.warns(GraphUserWarning):
        artifacts = _plot(_frame(["Voltage", "voltage"]), out, return_fig=True)
    # Then: three separately addressable in-memory artifacts, nothing written
    names = [a.filename for a in artifacts]
    assert names == ["p.png", "p_voltage_s000.png", "p_voltage_s001.png"]
    assert not out.exists()


def test_single_series_keeps_legacy_name_without_warning__tc_ge02_bv_002(tmp_path: Path) -> None:
    # Given: one series / When: plotting with collision warnings turned into errors
    out = tmp_path / "out"
    with warnings.catch_warnings():
        warnings.simplefilter("error", GraphUserWarning)
        _plot(_frame(["Voltage (V)"]), out, no_individual=False)
    # Then: the v1 names are produced unchanged
    assert _files(out) == ["p.png", f"{_legacy_stem('p', 'Voltage (V)')}.png"]
    assert _files(out) == ["p.png", "p_voltage_(v).png"]


def test_two_identical_headers_get_two_files__tc_ge02_bv_003(tmp_path: Path) -> None:
    # Given: two series with literally identical headers, addressed by position
    # (the facade's name-based column resolution cannot address them yet; GE-06)
    strategy = IndividualStrategy(MatplotlibRenderer())
    # When: rendering and saving each individual figure
    with pytest.warns(GraphUserWarning):
        results = strategy.render(_frame(["v", "v"]), _strategy_config(2))
    assert results is not None
    for result in results:
        result.figure.savefig(tmp_path / result.filename)
    # Then: two distinct files with different contents
    assert _files(tmp_path) == ["p_v_s000.png", "p_v_s001.png"]
    assert len(set(_digests(tmp_path).values())) == 2


def test_thirty_identical_headers__tc_ge02_bv_004(tmp_path: Path) -> None:
    # Given: thirty series with the same header and distinct data
    frame = _frame(["v"] * 30)
    strategy = IndividualStrategy(MatplotlibRenderer())
    # When: rendering and saving each figure
    with pytest.warns(GraphUserWarning) as record:
        results = strategy.render(frame, _strategy_config(30))
    assert results is not None
    for result in results:
        result.figure.savefig(tmp_path / result.filename)
    # Then: thirty files s000..s029, all different, one warning for the one group
    assert [r.filename for r in results] == [f"p_v_s{i:03d}.png" for i in range(30)]
    assert len(_files(tmp_path)) == 30
    assert len(set(_digests(tmp_path).values())) == 30
    assert len([w for w in record if issubclass(w.category, GraphUserWarning)]) == 1


def test_naming_is_deterministic_across_runs__tc_ge02_bv_007(tmp_path: Path) -> None:
    # Given: the same colliding request run twice into different directories
    headers = ["Voltage", "voltage", "A B", "A_B", "c"]
    names: list[list[str]] = []
    for run in ("first", "second"):
        out = tmp_path / run
        with pytest.warns(GraphUserWarning):
            _plot(_frame(headers), out)
        names.append(_files(out))
    # When / Then: both runs produce the same naming plan
    assert names[0] == names[1]
    assert names[0] == [
        "p.png", "p_a_b_s002.png", "p_a_b_s003.png", "p_c.png",
        "p_voltage_s000.png", "p_voltage_s001.png",
    ]


def test_strategy_resolves_named_y_columns_before_naming__tc_ge02_ep_010() -> None:
    # Given: y columns addressed by label rather than position
    frame = _frame(["Voltage", "voltage"])
    config = dataclasses.replace(_strategy_config(2), y_cols=["Voltage", "voltage"])
    strategy = IndividualStrategy(MatplotlibRenderer())
    # When: rendering individual figures
    with pytest.warns(GraphUserWarning, match="filename_collision"):
        results = strategy.render(frame, config)
    # Then: names are reserved exactly as for positional specs
    assert results is not None
    assert [r.filename for r in results] == ["p_voltage_s000.png", "p_voltage_s001.png"]


def test_strategy_rejects_ambiguous_named_y_column_before_render__tc_ge02_ep_011(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a label that matches two columns, and a renderer that records its calls
    calls: list[int] = []
    monkeypatch.setattr(
        MatplotlibRenderer, "render_individual", lambda self, df, config, col, pos: calls.append(col),
    )
    frame = _frame(["a", "y", "y"])
    config = dataclasses.replace(_strategy_config(3), y_cols=["a", "y"])
    # When: rendering
    with pytest.raises(ValueError, match="resolved to non-integer index"):
        IndividualStrategy(MatplotlibRenderer()).render(frame, config)
    # Then: nothing was rendered, not even the unambiguous first series
    assert calls == []
