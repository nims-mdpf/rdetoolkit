"""GE-11 (#717): incompatible physical units never silently share one overlay axis.

Unit policy under test (``rdetoolkit.graph.units``): units come from the header or
``SeriesSpec.unit``; they are compared as normalized text (NFKC, trimmed, collapsed
spaces, arbitrary-unit spellings -> ``"a.u."``) and never converted, so ``mV`` and
``V`` differ. A series without a unit is unknown: it never causes a mismatch, joins
the first unit group and is reported (``unit_unknown``) when it shares an overlay
axis with a known unit. ``GraphSpec.unit_policy`` decides what a mismatch in the
overlay figure does: ``error`` (default) raises, ``split`` plans one overlay per unit
group, ``warn`` keeps one overlay and warns, ``allow`` keeps one overlay silently.

Intentional behaviour change IC-6 (versioned tests end in ``_v2_0``): the legacy
facade (``plot_from_dataframe`` / ``csv2graph``, unit policy ``warn``) warns about a
mixed-unit overlay and labels it with the joined ``label (unit)`` strings, and every
individual figure is labelled after its own column; an explicit ``y_label`` wins.

Assertions inspect plan fields, diagnostics and axis label text, never pixels.

EP table:

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| normalize_unit | None / blank | None | TC-GE11-EP-001 |
| normalize_unit | NFKC (micro sign), spaces, arbitrary spellings, case | normalized text, "a.u.", case kept | TC-GE11-EP-002 |
| group_units | known / unknown / all unknown / empty | first-appearance groups, unknown -> group 0 | TC-GE11-EP-003 |
| build_plot_plan | V + A, default policy (error) | PlotRequestError(unit_mismatch) naming groups + remedies | TC-GE11-EP-004 |
| render_graph | V + A, default policy, DirectorySink | raises before any file exists | TC-GE11-EP-005 |
| build_plot_plan | V + A, split | overlay_g0/overlay_g1, stems, labels, groups | TC-GE11-EP-006 |
| render_graph | V + A, split, DirectorySink / in memory | 4 PNG files; axis labels per figure | TC-GE11-EP-007 |
| build_plot_plan | V + A, warn | one overlay, joined label, 1 GraphUserWarning, warning diagnostic | TC-GE11-EP-008 |
| build_plot_plan | V + A, allow | one overlay, joined label, no warning, info diagnostic | TC-GE11-EP-009 |
| build_plot_plan | same unit (V + V) | one overlay, first label, no diagnostic | TC-GE11-EP-010 |
| build_plot_plan | known + unknown | no mismatch, unit_unknown info, unknown joins group 0 | TC-GE11-EP-011 |
| build_plot_plan | all unknown | one group (None), no diagnostic | TC-GE11-EP-012 |
| build_plot_plan | SeriesSpec.unit override | override decides grouping and the label unit | TC-GE11-EP-013 |
| build_plot_plan | arbitrary-unit spellings | one group "a.u." | TC-GE11-EP-014 |
| build_plot_plan | individual figures (any policy, layout individual) | own label (unit), never affected | TC-GE11-EP-015 |
| build_plot_plan | explicit y label | wins on every figure; does not acknowledge a mismatch | TC-GE11-EP-016 |
| build_plot_plan | several frames | groups span frames frame-major | TC-GE11-EP-017 |
| plot_from_dataframe | V + A (IC-6) | 1 warning, joined overlay label, own individual labels | TC-GE11-EP-018 |
| plot_from_dataframe | explicit y_label / same units | label kept / no warning | TC-GE11-EP-019 |
| csv2graph | multi_unit.csv (IC-6) | one overlay + 2 individual files, 1 warning | TC-GE11-EP-020 |
| render_overlay (direct legacy) | PlotConfig label | label as given, warning | TC-GE11-EP-021 |

BV table:

| API | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| build_plot_plan | mV vs V (same dimension, different text) | mismatch | TC-GE11-BV-001 |
| build_plot_plan | split with one group only | single "overlay" figure, base stem | TC-GE11-BV-002 |
| build_plot_plan | split, unit slugs collide (mV / MV) | stems made unique, collision diagnostic | TC-GE11-BV-003 |
| build_plot_plan | split, equal legend labels in two groups | each figure lists its own series | TC-GE11-BV-004 |
| build_plot_plan | one series only, unknown unit | no diagnostic | TC-GE11-BV-005 |
| build_plot_plan | layout overlay, error policy, V + A | raises (overlay requested explicitly) | TC-GE11-BV-006 |
"""

from __future__ import annotations

import shutil
import warnings
from pathlib import Path

import pandas as pd
import pytest

from rdetoolkit.graph import engine
from rdetoolkit.graph.api.csv2graph import csv2graph, plot_from_dataframe
from rdetoolkit.graph.exceptions import GraphUserWarning, PlotConfigError, PlotRequestError
from rdetoolkit.graph.models import AxisConfig, PlotConfig
from rdetoolkit.graph.outputs import DirectorySink
from rdetoolkit.graph.plan import PlotData, PlotPlan, build_plot_plan
from rdetoolkit.graph.renderers.matplotlib_renderer import MatplotlibRenderer
from rdetoolkit.graph.spec import AxisSpec, GraphSpec, OutputSpec, SeriesSpec
from rdetoolkit.graph.units import ARBITRARY_UNIT, group_units, normalize_unit

FIXTURES = Path(__file__).parent / "fixtures"


def _va() -> pd.DataFrame:
    """time (s), voltage (V), current (A) — the mixed-unit fixture."""
    return pd.read_csv(FIXTURES / "multi_unit.csv")


def _frame(*headers: str) -> pd.DataFrame:
    data = {"time (s)": [0, 1, 2]}
    data.update({header: [1.0 + i, 2.0 + i, 3.0 + i] for i, header in enumerate(headers)})
    return pd.DataFrame(data)


def _codes(plan: PlotPlan) -> list[tuple[str, str, tuple[str, ...]]]:
    return [(item.code, item.severity, item.series_ids) for item in plan.diagnostics]


def _overlays(plan: PlotPlan) -> list[tuple[str, tuple[str, ...], str, str]]:
    return [(f.figure_id, f.series_ids, f.stem, f.y_label) for f in plan.figures if f.kind == "overlay"]


def _graph_warnings(records: list[warnings.WarningMessage]) -> list[str]:
    return [str(record.message) for record in records if issubclass(record.category, GraphUserWarning)]


# --------------------------------------------------------------------------- units.py


@pytest.mark.parametrize("unit", [None, "", "   ", "\t\n"])
def test_normalize_unit_missing_or_blank_is_unknown__tc_ge11_ep_001(unit: str | None) -> None:
    """TC-GE11-EP-001: a missing or blank unit is unknown."""
    # Given/When/Then: None, empty and white-space-only units normalize to None
    assert normalize_unit(unit) is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("V", "V"),
        ("  m   V ", "m V"),
        ("µA", "μA"),  # micro sign -> Greek mu (NFKC)
        ("ｖ", "v"),  # full-width letter -> ASCII (NFKC); case kept
        ("mV", "mV"),
        ("MV", "MV"),
        ("a.u.", ARBITRARY_UNIT),
        ("A.U.", ARBITRARY_UNIT),
        ("a.u", ARBITRARY_UNIT),
        ("arb.", ARBITRARY_UNIT),
        ("arb. units", ARBITRARY_UNIT),
        ("Arb. Unit", ARBITRARY_UNIT),
        ("arbitrary units", ARBITRARY_UNIT),
        ("au", "au"),  # also the astronomical unit: left alone
        ("counts", "counts"),
    ],
)
def test_normalize_unit_compares_text_without_converting__tc_ge11_ep_002(raw: str, expected: str) -> None:
    """TC-GE11-EP-002: normalization is textual only; no unit is ever converted."""
    # Given: a unit spelling / When: normalizing it / Then: the documented text
    assert normalize_unit(raw) == expected


@pytest.mark.parametrize(
    ("units", "expected"),
    [
        ([], ((), ())),
        (["V"], ((0,), ("V",))),
        (["V", "A", "V"], ((0, 1, 0), ("V", "A"))),
        ([None, "V", None, "A"], ((0, 0, 0, 1), ("V", "A"))),
        ([None, None], ((0, 0), (None,))),
    ],
)
def test_group_units_first_appearance_unknown_joins_first__tc_ge11_ep_003(
    units: list[str | None],
    expected: tuple[tuple[int, ...], tuple[str | None, ...]],
) -> None:
    """TC-GE11-EP-003: known units group in first-appearance order; unknown joins group 0."""
    # Given/When: grouping normalized units / Then: indices and group units as documented
    assert group_units(units) == expected


# --------------------------------------------------------------------------- error (default)


def test_default_policy_rejects_voltage_with_current__tc_ge11_ep_004() -> None:
    """TC-GE11-EP-004: V + A in an automatic overlay raises unit_mismatch by default."""
    # Given: the mixed-unit fixture and the default spec
    # When: planning
    with pytest.raises(PlotRequestError) as caught:
        build_plot_plan(_va(), GraphSpec(title="cell"))
    # Then: the typed error (also a ValueError / PlotConfigError) names both groups and the remedies
    error = caught.value
    assert error.reason == "unit_mismatch"
    assert isinstance(error, ValueError)
    assert isinstance(error, PlotConfigError)
    text = str(error)
    for fragment in ("'V'", "'A'", "s000", "s001", "voltage (V)", "current (A)", "unit_policy='split'", "layout='individual'", "unit_policy='allow'"):
        assert fragment in text


@pytest.mark.parametrize(("left", "right"), [("signal (mV)", "signal (V)"), ("p (Pa)", "p (kPa)")])
def test_same_dimension_different_unit_text_is_a_mismatch__tc_ge11_bv_001(left: str, right: str) -> None:
    """TC-GE11-BV-001: no dimension registry and no conversion: mV and V differ."""
    # Given: two series of the same quantity in different units
    # When/Then: the default policy rejects the overlay
    with pytest.raises(PlotRequestError) as caught:
        build_plot_plan(_frame(left, right))
    assert caught.value.reason == "unit_mismatch"


def test_explicit_overlay_layout_still_rejects_mismatch__tc_ge11_bv_006() -> None:
    """TC-GE11-BV-006: an explicitly requested overlay is checked like the automatic one."""
    # Given/When/Then: layout overlay with V + A raises
    with pytest.raises(PlotRequestError) as caught:
        build_plot_plan(_va(), GraphSpec(layout="overlay"))
    assert caught.value.reason == "unit_mismatch"


def test_explicit_y_label_does_not_acknowledge_a_mismatch__tc_ge11_ep_016() -> None:
    """TC-GE11-EP-016: on the spec API only unit_policy acknowledges mixed units."""
    # Given/When/Then: an explicit y label with the default policy still raises
    with pytest.raises(PlotRequestError) as caught:
        build_plot_plan(_va(), GraphSpec(y_axis=AxisSpec(label="Signal")))
    assert caught.value.reason == "unit_mismatch"


def test_default_policy_fails_before_any_file_is_written__tc_ge11_ep_005(tmp_path: Path) -> None:
    """TC-GE11-EP-005: render_graph rejects the request before rendering or writing."""
    # Given: an empty output directory
    out = tmp_path / "out"
    # When: rendering V + A with the default policy
    with pytest.raises(PlotRequestError) as caught:
        engine.render_graph(_va(), GraphSpec(title="cell"), output=OutputSpec(sink=DirectorySink(out), base_name="cell"))
    # Then: nothing exists
    assert caught.value.reason == "unit_mismatch"
    assert not out.exists()


# --------------------------------------------------------------------------- split


def test_split_plans_one_overlay_per_unit_group__tc_ge11_ep_006() -> None:
    """TC-GE11-EP-006: split gives overlay_g0 / overlay_g1 with their own stems and labels."""
    # Given/When: V + A with unit_policy="split"
    plan = build_plot_plan(_va(), GraphSpec(title="cell", unit_policy="split"), base_name="cell")
    # Then: one overlay per unit, then the unchanged individual figures
    assert [f.figure_id for f in plan.figures] == ["overlay_g0", "overlay_g1", "s000", "s001"]
    assert _overlays(plan) == [
        ("overlay_g0", ("s000",), "cell_v", "Voltage (V)"),
        ("overlay_g1", ("s001",), "cell_a", "Current (A)"),
    ]
    assert [f.title for f in plan.figures[:2]] == ["cell", "cell"]
    assert [(f.stem, f.y_label) for f in plan.figures[2:]] == [("cell_voltage_(v)", "Voltage (V)"), ("cell_current_(a)", "Current (A)")]
    # And: the grouping metadata records the split
    assert plan.unit_groups == (("V", ("s000",)), ("A", ("s001",)))
    assert [(s.unit, s.unit_group) for s in plan.series] == [("V", 0), ("A", 1)]
    assert _codes(plan) == [("unit_mismatch", "info", ("s000", "s001"))]
    assert "split" in plan.diagnostics[0].message


def test_split_with_one_unit_group_keeps_the_single_overlay__tc_ge11_bv_002() -> None:
    """TC-GE11-BV-002: compatible units are not split."""
    # Given/When: two voltage series with the split policy
    plan = build_plot_plan(_frame("a: voltage (V)", "b: voltage (V)"), GraphSpec(unit_policy="split"), base_name="cell")
    # Then: the usual overlay figure and base stem
    assert _overlays(plan) == [("overlay", ("s000", "s001"), "cell", "Voltage (V)")]
    assert plan.diagnostics == ()


def test_split_unit_slug_collision_is_made_unique__tc_ge11_bv_003() -> None:
    """TC-GE11-BV-003: split stems go through the stem reservation."""
    # Given/When: mV and MV (different units, same case-folded slug), split, overlay only
    plan = build_plot_plan(_frame("a (mV)", "b (MV)"), GraphSpec(unit_policy="split", layout="overlay"), base_name="cell")
    # Then: both stems are unique and the collision is reported
    assert [f.stem for f in plan.figures] == ["cell_mv_overlay_g0", "cell_mv_overlay_g1"]
    assert [item.code for item in plan.diagnostics] == ["filename_collision", "unit_mismatch"]


def test_split_legend_roles_are_scoped_per_figure__tc_ge11_bv_004() -> None:
    """TC-GE11-BV-004: equal labels in different unit groups are each listed in their own figure."""
    # Given: two series both labelled "A" by their series prefix, in different units
    frame = _frame("a: voltage (V)", "a: current (A)")
    # When: splitting, and when sharing the axis deliberately
    split = build_plot_plan(frame, GraphSpec(unit_policy="split"))
    shared = build_plot_plan(frame, GraphSpec(unit_policy="allow"))
    # Then: split figures each own their legend entry; the shared overlay lists the label once
    assert [s.show_in_legend for s in split.series] == [True, True]
    assert [s.show_in_legend for s in shared.series] == [True, False]
    # And: relabelling keeps the per-figure scope
    assert [s.show_in_legend for s in split.with_labels(["X", "X"]).series] == [True, True]
    assert [s.show_in_legend for s in shared.with_labels(["X", "X"]).series] == [True, False]


def test_split_renders_each_group_with_its_own_axis_label__tc_ge11_ep_007(tmp_path: Path) -> None:
    """TC-GE11-EP-007: split artifacts are written with distinct names and labelled per figure."""
    # Given/When: rendering V + A split into a directory and in memory
    spec = GraphSpec(title="cell", unit_policy="split")
    written = engine.render_graph(_va(), spec, output=OutputSpec(sink=DirectorySink(tmp_path), base_name="cell"))
    in_memory = engine.render_graph(_va(), spec)
    # Then: four PNG files (two overlays, two individual)
    assert sorted(path.name for path in tmp_path.iterdir()) == ["cell_a.png", "cell_current_(a).png", "cell_v.png", "cell_voltage_(v).png"]
    assert [(a.figure_id, a.role) for a in written.artifacts] == [
        ("overlay_g0", "main_image"), ("overlay_g1", "main_image"), ("s000", "individual"), ("s001", "individual"),
    ]
    # And: every figure carries its own unit on the y axis and only its own series
    labels = [(a.figure_id, a.figure.axes[0].get_ylabel(), a.labels) for a in in_memory.artifacts]
    assert labels == [
        ("overlay_g0", "Voltage (V)", ("Voltage",)),
        ("overlay_g1", "Current (A)", ("Current",)),
        ("s000", "Voltage (V)", ("Voltage",)),
        ("s001", "Current (A)", ("Current",)),
    ]


# --------------------------------------------------------------------------- warn / allow


def test_warn_keeps_one_overlay_and_warns_once__tc_ge11_ep_008() -> None:
    """TC-GE11-EP-008: warn = one overlay, joined label, exactly one GraphUserWarning."""
    # Given/When: V + A with unit_policy="warn"
    with warnings.catch_warnings(record=True) as records:
        warnings.simplefilter("always")
        plan = build_plot_plan(_va(), GraphSpec(unit_policy="warn"), base_name="cell")
    # Then: exactly one graph warning naming both units
    messages = _graph_warnings(records)
    assert len(messages) == 1
    assert "'V'" in messages[0] and "'A'" in messages[0]
    # And: one overlay labelled with both units, individual figures labelled after their own column
    assert _overlays(plan) == [("overlay", ("s000", "s001"), "cell", "Voltage (V) / Current (A)")]
    assert [f.y_label for f in plan.figures[1:]] == ["Voltage (V)", "Current (A)"]
    assert plan.unit_groups == (("V", ("s000",)), ("A", ("s001",)))
    assert _codes(plan) == [("unit_mismatch", "warning", ("s000", "s001"))]


def test_allow_keeps_one_overlay_silently__tc_ge11_ep_009() -> None:
    """TC-GE11-EP-009: allow = one overlay, joined label, info diagnostic, no warning."""
    # Given: warnings turned into errors
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        # When: V + A with unit_policy="allow"
        plan = build_plot_plan(_va(), GraphSpec(unit_policy="allow", layout="overlay"))
    # Then: one overlay with both units in the label and an info diagnostic
    assert _overlays(plan) == [("overlay", ("s000", "s001"), "plot", "Voltage (V) / Current (A)")]
    assert _codes(plan) == [("unit_mismatch", "info", ("s000", "s001"))]


def test_explicit_y_label_wins_over_the_joined_label__tc_ge11_ep_016() -> None:
    """TC-GE11-EP-016: an explicit y label is used on every figure."""
    # Given/When: allow with an explicit y label
    plan = build_plot_plan(_va(), GraphSpec(unit_policy="allow", y_axis=AxisSpec(label="Signal")))
    # Then: no derived label anywhere
    assert [f.y_label for f in plan.figures] == ["Signal", "Signal", "Signal"]
    assert plan.origins["y_axis.label"] == "explicit"


# --------------------------------------------------------------------------- compatible / unknown


def test_same_unit_keeps_the_combined_plot__tc_ge11_ep_010() -> None:
    """TC-GE11-EP-010: compatible units preserve the expected combined plot."""
    # Given/When: two voltage series with the default (error) policy
    plan = build_plot_plan(_frame("a: voltage (V)", "b: voltage ( V )"), base_name="cell")
    # Then: one overlay labelled as before, one unit group, no diagnostic
    assert _overlays(plan) == [("overlay", ("s000", "s001"), "cell", "Voltage (V)")]
    assert plan.unit_groups == (("V", ("s000", "s001")),)
    assert plan.diagnostics == ()


def test_known_and_unknown_units_share_without_mismatch__tc_ge11_ep_011() -> None:
    """TC-GE11-EP-011: an unknown unit is assumed compatible and reported, not converted."""
    # Given/When: a voltage series and a series without unit, default policy
    plan = build_plot_plan(_frame("voltage (V)", "signal"), base_name="cell")
    # Then: no mismatch, the unknown series joins the V group, the assumption is reported
    assert _overlays(plan) == [("overlay", ("s000", "s001"), "cell", "Voltage (V)")]
    assert plan.unit_groups == (("V", ("s000", "s001")),)
    assert [(s.unit, s.unit_group) for s in plan.series] == [("V", 0), (None, 0)]
    assert _codes(plan) == [("unit_unknown", "info", ("s001",))]
    assert "no conversion" in plan.diagnostics[0].message


def test_unknown_first_series_split_labels_the_group_by_its_unit__tc_ge11_ep_011() -> None:
    """TC-GE11-EP-011: in a split, a group is labelled by a series carrying its unit."""
    # Given/When: unknown, V, A split
    plan = build_plot_plan(_frame("signal", "voltage (V)", "current (A)"), GraphSpec(unit_policy="split", layout="overlay"))
    # Then: the unknown series joins group 0 (V) and the group label shows V
    assert _overlays(plan) == [
        ("overlay_g0", ("s000", "s001"), "plot_v", "Voltage (V)"),
        ("overlay_g1", ("s002",), "plot_a", "Current (A)"),
    ]
    assert [item.code for item in plan.diagnostics] == ["unit_mismatch", "unit_unknown"]
    assert plan.diagnostics[1].series_ids == ("s000",)


def test_all_unknown_units_form_one_group__tc_ge11_ep_012() -> None:
    """TC-GE11-EP-012: with no known unit there is nothing to compare."""
    # Given/When: two series without units
    plan = build_plot_plan(_frame("y1", "y2"))
    # Then: one unknown group, no mismatch, no diagnostic
    assert plan.unit_groups == ((None, ("s000", "s001")),)
    assert plan.diagnostics == ()
    assert _overlays(plan)[0][3] == "Y1"


def test_single_unknown_series_is_not_reported__tc_ge11_bv_005() -> None:
    """TC-GE11-BV-005: one series shares its axis with nobody."""
    # Given/When/Then: a lone series without unit plans without diagnostics
    assert build_plot_plan(_frame("signal")).diagnostics == ()


def test_series_unit_override_decides_grouping_and_label__tc_ge11_ep_013() -> None:
    """TC-GE11-EP-013: SeriesSpec.unit overrides the header unit (intentionally overridden display)."""
    # Given: the current column declared as V, and a voltage column declared as mV
    agree = GraphSpec(series=(SeriesSpec(y=1), SeriesSpec(y=2, unit="V")))
    disagree = GraphSpec(series=(SeriesSpec(y=1, unit="mV"), SeriesSpec(y=2, unit="mV")), layout="both")
    # When: planning
    agreed = build_plot_plan(_va(), agree)
    overridden = build_plot_plan(_va(), disagree)
    # Then: the override makes the units compatible and is recorded as explicit
    assert agreed.unit_groups == (("V", ("s000", "s001")),)
    assert agreed.origins["series[s001].unit"] == "explicit"
    assert agreed.figures[2].y_label == "Current (V)"
    # And: the axis label shows the declared unit, not the header unit
    assert [f.y_label for f in overridden.figures] == ["Voltage (mV)", "Voltage (mV)", "Current (mV)"]
    # And: an override that disagrees is a mismatch
    with pytest.raises(PlotRequestError) as caught:
        build_plot_plan(_va(), GraphSpec(series=(SeriesSpec(y=1, unit="mV"), SeriesSpec(y=2, unit="V"))))
    assert caught.value.reason == "unit_mismatch"


def test_arbitrary_unit_spellings_share_one_group__tc_ge11_ep_014() -> None:
    """TC-GE11-EP-014: a.u. spellings are one unit."""
    # Given/When: three arbitrary-unit spellings
    plan = build_plot_plan(_frame("a: intensity (a.u.)", "b: intensity (arb. units)", "c: intensity (Arb.)"))
    # Then: one "a.u." group, no mismatch; the first header keeps its spelling in the label
    assert plan.unit_groups == ((ARBITRARY_UNIT, ("s000", "s001", "s002")),)
    assert [s.unit for s in plan.series] == [ARBITRARY_UNIT] * 3
    assert _overlays(plan)[0][3] == "Intensity (a.u.)"


@pytest.mark.parametrize("policy", ["error", "split", "warn", "allow"])
def test_individual_figures_are_never_affected__tc_ge11_ep_015(policy: str) -> None:
    """TC-GE11-EP-015: individual-only layouts plan V + A under every policy."""
    # Given/When: layout individual with any policy (no warning either)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        plan = build_plot_plan(_va(), GraphSpec(layout="individual", unit_policy=policy))  # type: ignore[arg-type]
    # Then: each figure is labelled after its own column; no unit diagnostic
    assert [(f.figure_id, f.y_label) for f in plan.figures] == [("s000", "Voltage (V)"), ("s001", "Current (A)")]
    assert plan.diagnostics == ()


def test_individual_figure_of_current_is_labelled_current__tc_ge11_ep_015() -> None:
    """TC-GE11-EP-015: the drawn individual axis of Current reads 'Current (A)'."""
    # Given: a split plan
    plan = build_plot_plan(_va(), GraphSpec(unit_policy="split"))
    current = next(f for f in plan.figures if f.figure_id == "s001")
    # When: drawing that figure
    figure = MatplotlibRenderer().render(plan, current, PlotData(frames=(_va(),)))
    # Then: its axis label is its own
    assert figure.axes[0].get_ylabel() == "Current (A)"


def test_groups_span_several_frames__tc_ge11_ep_017() -> None:
    """TC-GE11-EP-017: frame-major series are grouped by unit across frames."""
    # Given/When: the mixed-unit frame twice, split
    plan = build_plot_plan([_va(), _va()], GraphSpec(unit_policy="split", layout="overlay"))
    # Then: V series of both frames in g0, A series in g1
    assert plan.unit_groups == (("V", ("s000", "s002")), ("A", ("s001", "s003")))
    assert [f.series_ids for f in plan.figures] == [("s000", "s002"), ("s001", "s003")]


# --------------------------------------------------------------------------- legacy facade (IC-6)


def test_plot_from_dataframe_mixed_units_warn_and_relabel_v2_0(tmp_path: Path) -> None:
    """TC-GE11-EP-018 (IC-6): the facade warns once and labels each figure correctly."""
    # Given: V + A and no y_label
    with warnings.catch_warnings(record=True) as records:
        warnings.simplefilter("always")
        # When: returning figures from the legacy facade
        artifacts = plot_from_dataframe(_va(), output_dir=tmp_path, title="cell", return_fig=True)
    # Then: exactly one warning, the overlay is not mislabelled, individuals carry their own unit
    assert artifacts is not None
    assert len(_graph_warnings(records)) == 1
    assert [(a.filename, a.figure.axes[0].get_ylabel()) for a in artifacts] == [
        ("cell.png", "Voltage (V) / Current (A)"),
        ("cell_voltage_(v).png", "Voltage (V)"),
        ("cell_current_(a).png", "Current (A)"),
    ]


def test_plot_from_dataframe_explicit_y_label_is_kept_v2_0(tmp_path: Path) -> None:
    """TC-GE11-EP-019 (IC-6): an explicit y_label is the way back to one label everywhere."""
    # Given/When: V + A with an explicit y_label
    with warnings.catch_warnings(record=True) as records:
        warnings.simplefilter("always")
        artifacts = plot_from_dataframe(_va(), output_dir=tmp_path, title="cell", y_label="Signal", return_fig=True)
    # Then: every figure uses it; the shared axis is still reported
    assert artifacts is not None
    assert [a.figure.axes[0].get_ylabel() for a in artifacts] == ["Signal", "Signal", "Signal"]
    assert len(_graph_warnings(records)) == 1


def test_plot_from_dataframe_same_units_unchanged_v2_0(tmp_path: Path) -> None:
    """TC-GE11-EP-019: compatible units keep the v1 labels and do not warn."""
    # Given: two voltage series with different labels
    frame = _frame("a: voltage (V)", "b: voltage (V)")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        # When: plotting through the facade
        artifacts = plot_from_dataframe(frame, output_dir=tmp_path, title="cell", return_fig=True)
    # Then: the first column's label everywhere, as in v1
    assert artifacts is not None
    assert [a.figure.axes[0].get_ylabel() for a in artifacts] == ["Voltage (V)"] * 3


def test_csv2graph_mixed_units_writes_the_legacy_artifacts_v2_0(tmp_path: Path) -> None:
    """TC-GE11-EP-020 (IC-6): csv2graph keeps its artifact set and warns once."""
    # Given: the fixture copied into tmp_path (repository-delta guard)
    csv_path = tmp_path / "multi_unit.csv"
    shutil.copy(FIXTURES / "multi_unit.csv", csv_path)
    out = tmp_path / "out"
    # When: plotting with the defaults
    with warnings.catch_warnings(record=True) as records:
        warnings.simplefilter("always")
        csv2graph(csv_path, output_dir=out)
    # Then: one overlay + two individual images (no split on the legacy facade), one warning
    assert sorted(path.name for path in out.iterdir()) == ["multi_unit.png", "multi_unit_current_(a).png", "multi_unit_voltage_(v).png"]
    assert len(_graph_warnings(records)) == 1


def test_direct_render_overlay_keeps_the_config_label__tc_ge11_ep_021() -> None:
    """TC-GE11-EP-021: a hand-built PlotConfig label is explicit; mixed units still warn."""
    # Given: a legacy config with an explicit label
    config = PlotConfig(x_col=0, y_cols=[1, 2], y_axis=AxisConfig(label="Mixed"))
    # When: rendering the overlay directly
    with pytest.warns(GraphUserWarning, match="unit"):
        figure = MatplotlibRenderer().render_overlay(_va(), config)
    # Then: the label is used as given
    assert figure.axes[0].get_ylabel() == "Mixed"
    assert AxisConfig(label="Mixed").label_origin == "explicit"
