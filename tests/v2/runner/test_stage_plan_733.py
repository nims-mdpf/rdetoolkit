"""Acceptance cases for #705.

# RM-05 artifact-stage acceptance

The stage data is an immutable ordered sequence of named stages. The mode handler supplies the order. Planning validates that order before tile iteration and records it on ExecutionPlan so execution uses the same specification.

| API | Partition | Expected | Test ID |
|-----|-----------|----------|---------|
| stage plan | five built-in modes | exact historical order | RM05-P1 |
| stage plan | unknown identifier or unsupported value | catalog 1006 RdeConfigError | RM05-N1 |
| stage plan | duplicate stage | catalog 1006 RdeConfigError | RM05-N2 |
| stage plan | description before another stage | catalog 1006 RdeConfigError | RM05-N3 |
| stage plan | no capability or None | invoice default order | RM05-B1 |
| stage plan | empty provider sequence | all stages omitted | RM05-B2 |
| stage preview | enabled flags, no rawfiles, original-table tile | omission reason and side effects exposed | RM05-P2 |
| stage preview | disabled configuration | disabled_by_config reason | RM05-N4 |
| planner | invalid stage provider | fails before invoking user flow or iterating tiles | RM05-N5 |
| stage plan | mutable provider after planning | frozen order remains selected | RM05-B3 |
| execution | interrupted magic or failing structured export | frozen compatibility artifact corpus passes | RM05-L1 |

Known dependency is that description follows every selected artifact stage. Magic and structured have no global relative ordering because the historical per-mode contract intentionally differs.

"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, strategies as st

from rdetoolkit.api.request import FlowTarget, LegacyCallbackTarget, RunRequest
from rdetoolkit.errors import ERROR_CATALOG, RdeConfigError
from rdetoolkit.modes.install import install_default_handlers
from rdetoolkit.modes.registry import clear, register
from rdetoolkit.modes.stages import ArtifactStage, artifact_stage_order, plan_artifact_stages
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.runner.planner import RunPlanner
from rdetoolkit.types import RdeConfig
from tests.v2.runner.stage_order_helpers import make_plan


@pytest.fixture(autouse=True)
def restore_handlers() -> Any:
    """Keep handler registration isolated between stage-contract tests."""
    clear()
    install_default_handlers()
    yield
    clear()
    install_default_handlers()


class _Handler:
    kind = ModeKind.invoice

    def __init__(self, order: object) -> None:
        self.order = order
        self.iterated = False

    def create_tiles(self, context: object) -> Any:
        self.iterated = True
        message = "planning must not enumerate tiles"
        raise AssertionError(message)

    def artifact_stage_order(self, plan: object) -> object:
        return self.order


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        (ModeKind.invoice, ("thumbnail", "structured", "magic", "description")),
        (ModeKind.smarttable, ("thumbnail", "structured", "magic", "description")),
        (ModeKind.multidatatile, ("magic", "thumbnail", "structured", "description")),
        (ModeKind.excelinvoice, ("magic", "thumbnail", "structured", "description")),
        (ModeKind.rdeformat, ("thumbnail", "description")),
    ],
)
def test_five_mode_order__rm05_p1(mode: ModeKind, expected: tuple[str, ...], tmp_path: Path) -> None:
    """RM05-P1: declared stages retain their historical order."""
    # Given: a built-in mode plan
    plan = make_plan(mode, tmp_path)
    # When: reading its effective stages
    order = artifact_stage_order(plan)
    # Then: execution and the enabled preview expose the same order
    assert order == expected
    assert all(isinstance(spec.name, ArtifactStage) for spec in plan_artifact_stages(plan))
    assert tuple(spec.name.value for spec in plan_artifact_stages(plan) if spec.reason != "omitted_by_mode") == expected


@pytest.mark.parametrize(
    "invalid",
    [
        ("unknown",),
        ("Thumbnail",),
        ("",),
        (1,),
        (None,),
        "magic",
        1,
        {"magic"},
        frozenset({"magic"}),
        {"magic": True},
        iter(("magic",)),
        ("magic", "magic"),
        ("thumbnail", "thumbnail"),
        ("description", "description"),
        ("description", "magic"),
        ("description", "thumbnail"),
        ("description", "structured"),
    ],
)
def test_invalid_stage_declarations__rm05_n1_n2_n3(invalid: object, tmp_path: Path) -> None:
    """RM05-N1/N2/N3: unusable declarations are catalogued configuration errors."""
    # Given: an optional provider returning an invalid declaration
    register(ModeKind.invoice, _Handler(invalid))  # type: ignore[arg-type]
    # When: resolving the selected sequence
    with pytest.raises(RdeConfigError) as caught:
        artifact_stage_order(make_plan(ModeKind.invoice, tmp_path))
    # Then: stage planning uses the public catalog and includes remediation
    assert caught.value.code == 1006
    assert caught.value.name == ERROR_CATALOG[1006].name
    assert "Remediation:" in caught.value.message


@pytest.mark.parametrize("provider_value", [None, ()])
def test_none_and_empty_sequence__rm05_b1_b2(provider_value: object, tmp_path: Path) -> None:
    """RM05-B1/B2: None selects defaults while an empty sequence omits all stages."""
    # Given: a provider at the None or empty boundary
    register(ModeKind.invoice, _Handler(provider_value))  # type: ignore[arg-type]
    # When: resolving it
    plan = make_plan(ModeKind.invoice, tmp_path)
    order = artifact_stage_order(plan)
    # Then: only None requests defaults
    assert order == (("thumbnail", "structured", "magic", "description") if provider_value is None else ())


def test_preview_reasons_and_immutability__rm05_p2_n4(tmp_path: Path) -> None:
    """RM05-P2/N4: side effects and omission reasons are immutable and read-only."""
    # Given: disabled invoice gates and a RDEFormat plan
    plan = make_plan(ModeKind.rdeformat, tmp_path)
    before = sorted(tmp_path.rglob("*"))
    # When: describing the stages without creating outputs
    specs = plan_artifact_stages(plan, has_rawfiles=False)
    by_name = {spec.name.value: spec for spec in specs}
    # Then: unsupported and disabled stages have distinct reasons
    assert by_name["magic"].reason == "omitted_by_mode"
    assert by_name["structured"].reason == "omitted_by_mode"
    assert by_name["thumbnail"].reason == "disabled_by_config"
    assert by_name["description"].enabled is True
    assert by_name["description"].side_effects == ("invoice/invoice.json",)
    assert sorted(tmp_path.rglob("*")) == before
    with pytest.raises(FrozenInstanceError):
        by_name["description"].enabled = False  # type: ignore[misc]


@pytest.mark.parametrize("precompleted", [False, True])
@pytest.mark.parametrize("legacy", [False, True])
def test_magic_rawfile_and_precompleted_gates__rm05_p2(precompleted: bool, legacy: bool, tmp_path: Path) -> None:
    """RM05-P2: strict rawless flows retain magic; legacy and early-exit gates remain."""
    # Given: all stage configuration gates enabled
    config = RdeConfig(system={"magic_variable": True, "save_invoice_to_structured": True, "save_thumbnail_image": True})
    plan = replace(make_plan(ModeKind.invoice, tmp_path), config=config)
    if legacy:
        plan = replace(plan, target=LegacyCallbackTarget(function=None))
    # When: describing a rawless or precompleted tile
    specs = plan_artifact_stages(plan, has_rawfiles=False, precompleted=precompleted)
    # Then: omission reasons follow the execution target and early-exit contract
    by_name = {spec.name.value: spec for spec in specs}
    assert by_name["magic"].reason == ("precompleted_tile" if precompleted else "no_rawfiles" if legacy else None)
    assert by_name["magic"].enabled is (not precompleted and not legacy)
    if precompleted:
        assert not any(spec.enabled for spec in specs)


def test_planning_rejects_invalid_stage_before_tiles__rm05_n5(tmp_path: Path) -> None:
    """RM05-N5: validation happens before tile enumeration or any user flow."""
    # Given: an invalid provider and a target that must never run
    called: list[bool] = []
    handler = _Handler(("invalid",))
    register(ModeKind.invoice, handler)  # type: ignore[arg-type]
    planner = RunPlanner(inputdata_path=tmp_path / "inputdata", unpacked_dir_path=tmp_path / "temp", run_id_factory=lambda: "stages")
    request = RunRequest(root=tmp_path, target=FlowTarget(function=lambda: called.append(True)))
    # When: creating the execution plan
    with pytest.raises(RdeConfigError) as caught:
        planner.create(request, config=RdeConfig(), mode=ModeKind.invoice, data_root=tmp_path)
    # Then: neither user code nor even tile creation ran
    assert caught.value.code == 1006
    assert not called
    assert handler.iterated is False


def test_frozen_plan_keeps_provider_decision__rm05_b3(tmp_path: Path) -> None:
    """RM05-B3: changing the provider after planning cannot change execution order."""

    # Given: a lazy mode provider whose declaration can change
    class LazyHandler(_Handler):
        def create_tiles(self, context: object) -> tuple[()]:
            return ()

    handler = LazyHandler(("magic", "description"))
    register(ModeKind.invoice, handler)  # type: ignore[arg-type]
    planner = RunPlanner(inputdata_path=tmp_path / "inputdata", unpacked_dir_path=tmp_path / "temp", run_id_factory=lambda: "stages")
    request = RunRequest(root=tmp_path, target=FlowTarget(function=lambda: None))
    plan = planner.create(request, config=RdeConfig(), mode=ModeKind.invoice, data_root=tmp_path)
    # When: the handler changes after the plan is accepted
    handler.order = ("thumbnail", "description")
    # Then: execution uses the accepted snapshot
    assert artifact_stage_order(plan) == ("magic", "description")


def test_missing_provider_uses_default__rm05_b1(tmp_path: Path) -> None:
    """RM05-B1: the optional provider remains optional."""
    # Given: no registered mode handler
    clear()
    # When: resolving the order of an otherwise valid plan
    order = artifact_stage_order(make_plan(ModeKind.invoice, tmp_path))
    # Then: the historical invoice default applies
    assert order == ("thumbnail", "structured", "magic", "description")


def test_noncallable_provider_is_catalogued__rm05_n1(tmp_path: Path) -> None:
    """RM05-N1: invalid capability attributes fail with a catalogued error."""
    # Given: a handler with a noncallable capability attribute
    handler = _Handler(None)
    handler.artifact_stage_order = 1  # type: ignore[assignment,method-assign]
    register(ModeKind.invoice, handler)  # type: ignore[arg-type]
    # When: resolving its declaration
    with pytest.raises(RdeConfigError) as caught:
        artifact_stage_order(make_plan(ModeKind.invoice, tmp_path))
    # Then: the boundary reports a configuration error
    assert caught.value.code == 1006


@pytest.mark.parametrize("has_rawfiles", [None, True])
def test_magic_known_and_pending_inputs__rm05_p2(has_rawfiles: bool | None, tmp_path: Path) -> None:
    """RM05-P2: enabled magic separates pending input discovery from known rawfiles."""
    # Given: an enabled magic configuration
    from rdetoolkit.modes.stages import describe_artifact_stages

    config = RdeConfig(system={"magic_variable": True})
    # When: describing the stages directly without constructing an execution target
    specs = describe_artifact_stages(ModeKind.invoice, config, has_rawfiles=has_rawfiles)
    magic = next(spec for spec in specs if spec.name is ArtifactStage.magic)
    # Then: magic is applicable and its pending status is explicit
    assert magic.enabled
    assert magic.reason == ("runtime_inputs_pending" if has_rawfiles is None else None)


@pytest.mark.property
@given(st.lists(st.sampled_from(["thumbnail", "structured", "magic", "description"]), max_size=8))
def test_stage_sequences_obey_uniqueness_and_dependency_invariants__rm05_b3(names: list[str]) -> None:
    """RM05-B3: all generated selections either preserve order or fail validation."""
    # Given: a generated sequence containing only supported stage names
    order = tuple(names)
    register(ModeKind.invoice, _Handler(order))  # type: ignore[arg-type]
    plan = make_plan(ModeKind.invoice, Path("."))
    valid = len(order) == len(set(order)) and ("description" not in order or order[-1] == "description")
    # When: resolving that mode provider
    if valid:
        actual = artifact_stage_order(plan)
        # Then: valid selections retain their exact order
        assert actual == order
    else:
        with pytest.raises(RdeConfigError) as caught:
            artifact_stage_order(plan)
        # Then: invalid selections use a catalogued configuration error
        assert caught.value.code == 1006
