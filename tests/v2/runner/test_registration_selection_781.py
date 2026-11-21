"""Issue #781: one template supports several registration modes.

``registration: {selection: auto, supported_modes, fallback_mode}`` lets a
template accept SmartTable input and plain MultiDataTile input with one static
configuration. Every execution still resolves exactly one mode; fixed requests,
ambiguous inputs and unsupported detected modes stay errors.

EP table:

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| ``ConfigNormalizer`` | valid auto / fixed sections | accepted, fields preserved | TC-781-CFG-P |
| ``ConfigNormalizer`` | malformed sections | 1002 naming the problem | TC-781-CFG-N |
| ``ConfigNormalizer`` | registration + explicit ``system.extended_mode`` | 1002 | TC-781-CFG-DUAL |
| ``decide_mode`` | every pair of the five modes | declarable iff one detectable + one fallback; selection per input | TC-781-PAIR |
| ``decide_mode`` | ZIP-only input | never RDEFormat without explicit intent | TC-781-ZIP |
| ``decide_mode`` | duplicate control files | 1007 | TC-781-DUP |
| ``decide_mode`` | fixed request + conflicting input | 1005 / 1008 | TC-781-FIXED |
| ``decide_mode`` | callback contract with / without registration | declared policy / frozen v1 precedence | TC-781-CB |
| ``load_config`` | registration in ``data/tasksupport/rdeconfig.yml`` | survives v1-model discovery | TC-781-TASKSUPPORT |
| ``compute_config_digest`` | absent / distinct policies, YAML round trip | old digests kept, policies distinct, replayable | TC-781-DIGEST |
| ``workflows.run(flow=...)`` | RDE_SEM SmartTable and MultiDataTile inputs | artifacts identical to the v1 callback oracle | TC-781-SEM |
| ``preview_registration`` | same inputs | the decision and tile count the run uses | TC-781-PREVIEW |
"""

from __future__ import annotations

import itertools
import json
import os
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from rdetoolkit import flow, workflows
from rdetoolkit.config.normalize import ConfigNormalizer
from rdetoolkit.domain.mode_selection import ModeDecision, ModeKind, decide_mode
from rdetoolkit.errors import RdeConfigError
from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath
from rdetoolkit.runner.config_loader import compute_config_digest, config_for_replay, load_config
from rdetoolkit.runner.preview import preview_registration
from rdetoolkit.types import InputPaths, OutputContext, RdeConfig
from tests.v2.contract.fixtures import _generate

_SEM_POLICY = {"selection": "auto", "supported_modes": ["multidatatile", "smarttable"], "fallback_mode": "multidatatile"}
_DETECTABLE = (ModeKind.excelinvoice, ModeKind.smarttable)
_INDICATOR = {ModeKind.smarttable: "smarttable_rows.csv", ModeKind.excelinvoice: "batch_excel_invoice.xlsx"}


def _normalize(source: dict[str, Any], tmp_path: Path) -> RdeConfig:
    return ConfigNormalizer().normalize(source, root=tmp_path, origin="v2")


def _inputs(tmp_path: Path, *names: str) -> Path:
    inputdata = tmp_path / "inputdata"
    inputdata.mkdir()
    for name in names:
        if name.endswith(".zip"):
            with zipfile.ZipFile(inputdata / name, "w") as archive:
                archive.writestr("0001/structured/data.csv", "x")
        else:
            (inputdata / name).write_bytes(b"x")
    return inputdata


def _decide(registration: dict[str, Any], tmp_path: Path, *names: str, contract: str = "v2") -> ModeDecision:
    return decide_mode(_normalize({"registration": registration}, tmp_path), _inputs(tmp_path, *names), contract=contract)  # type: ignore[arg-type]


def _code(action: Callable[[], object]) -> int | str:
    with pytest.raises(RdeConfigError) as caught:
        action()
    return caught.value.code


@pytest.mark.parametrize(
    "registration",
    [
        _SEM_POLICY,
        {"selection": "auto", "supported_modes": ["invoice"], "fallback_mode": "invoice"},
        {"selection": "auto", "supported_modes": ["rdeformat", "smarttable", "excelinvoice"], "fallback_mode": "rdeformat"},
        {"selection": "fixed", "mode": "smarttable"},
    ],
)
def test_valid_sections_are_preserved__tc_781_cfg_p(tmp_path: Path, registration: dict[str, Any]) -> None:
    # Given / When: a well-formed registration section
    config = _normalize({"registration": registration}, tmp_path)
    # Then: it is kept as declared and system.extended_mode stays unset
    assert config.registration is not None
    assert config.registration.model_dump(exclude_none=True) == registration
    assert "extended_mode" not in config.system.model_fields_set


@pytest.mark.parametrize(
    ("registration", "problem"),
    [
        ({"selection": "auto", "fallback_mode": "invoice"}, "non-empty registration.supported_modes"),
        ({"selection": "auto", "supported_modes": [], "fallback_mode": "invoice"}, "non-empty registration.supported_modes"),
        ({"selection": "auto", "supported_modes": ["invoice", "invoice"], "fallback_mode": "invoice"}, "more than once"),
        ({"selection": "auto", "supported_modes": ["invoice", "smarttable"]}, "requires registration.fallback_mode"),
        ({"selection": "auto", "supported_modes": ["smarttable"], "fallback_mode": "invoice"}, "not in registration.supported_modes"),
        ({"selection": "auto", "supported_modes": ["smarttable"], "fallback_mode": "smarttable"}, "cannot be a fallback"),
        ({"selection": "auto", "supported_modes": ["invoice", "multidatatile"], "fallback_mode": "invoice"}, "multidatatile, which no input file selects"),
        ({"selection": "auto", "mode": "invoice", "supported_modes": ["invoice"], "fallback_mode": "invoice"}, "does not take registration.mode"),
        ({"selection": "fixed"}, "requires registration.mode"),
        ({"selection": "fixed", "mode": "invoice", "fallback_mode": "invoice"}, "takes only registration.mode"),
    ],
)
def test_malformed_sections_are_config_errors__tc_781_cfg_n(tmp_path: Path, registration: dict[str, Any], problem: str) -> None:
    # Given / When: a section that does not define exactly one outcome per input
    with pytest.raises(RdeConfigError) as caught:
        _normalize({"registration": registration}, tmp_path)
    # Then: a catalogued config error explains which rule is broken
    assert caught.value.code == 1002
    assert problem in str(caught.value)


@pytest.mark.parametrize(
    ("registration", "field"),
    [
        ({"selection": "magic", "mode": "invoice"}, "registration.selection"),
        ({"selection": "fixed", "mode": "MultiDataTile"}, "registration.mode"),
        ({"selection": "fixed", "mode": "invoice", "extra": True}, "registration.extra"),
    ],
)
def test_unknown_values_are_config_errors__tc_781_cfg_n(tmp_path: Path, registration: dict[str, Any], field: str) -> None:
    # Given / When: an unknown policy, a legacy alias, or an unknown key
    with pytest.raises(RdeConfigError) as caught:
        _normalize({"registration": registration}, tmp_path)
    # Then: the field is named; the new section accepts canonical names only
    assert caught.value.code == 1002
    assert field in str(caught.value)


@pytest.mark.parametrize("mode", ["invoice", "multidatatile", None])
def test_registration_and_extended_mode_cannot_both_declare__tc_781_cfg_dual(tmp_path: Path, mode: str | None) -> None:
    # Given: an explicit system.extended_mode next to a registration section
    source = {"system": {"extended_mode": mode}, "registration": _SEM_POLICY}
    if mode is None:
        # Then: null means "not set", which is not a second declaration
        assert _normalize(source, tmp_path).registration is not None
        return
    # Then: neither silently wins
    assert _code(lambda: _normalize(source, tmp_path)) == 1002


def _pair_policy(pair: tuple[ModeKind, ModeKind]) -> dict[str, Any] | None:
    fallbacks = [mode for mode in pair if mode not in _DETECTABLE]
    if len(fallbacks) != 1:
        return None
    return {"selection": "auto", "supported_modes": [mode.value for mode in pair], "fallback_mode": fallbacks[0].value}


def _fallback_inputs(mode: ModeKind) -> tuple[str, ...]:
    return {ModeKind.invoice: ("one.txt",), ModeKind.multidatatile: ("a.tif", "b.tif"), ModeKind.rdeformat: ("export.zip",)}[mode]


@pytest.mark.parametrize("pair", list(itertools.combinations(ModeKind, 2)), ids=lambda pair: "+".join(mode.value for mode in pair))
def test_every_mode_pair__tc_781_pair(tmp_path: Path, pair: tuple[ModeKind, ModeKind]) -> None:
    """A pair is declarable iff exactly one member has its own input file.

    Two detectable modes leave no fallback; two non-detectable modes leave one
    unreachable. For a declarable pair, its indicator file selects the
    detectable mode, no indicator selects the fallback, the other indicator is
    unsupported (1009), and both indicators together are ambiguous (1007).
    """
    policy = _pair_policy(pair)
    if policy is None:
        # Then: the template declaration itself is rejected
        assert _code(lambda: _normalize({"registration": {"selection": "auto", "supported_modes": [m.value for m in pair], "fallback_mode": pair[0].value}}, tmp_path)) == 1002
        return
    detectable = next(mode for mode in pair if mode in _DETECTABLE)
    other = next(mode for mode in _DETECTABLE if mode is not detectable)
    fallback = ModeKind(policy["fallback_mode"])
    cases = {
        "indicator": (_INDICATOR[detectable],),
        "fallback": _fallback_inputs(fallback),
        "other": (_INDICATOR[other],),
        "both": (_INDICATOR[detectable], _INDICATOR[other]),
    }
    outcomes = {}
    for name, files in cases.items():
        case_root = tmp_path / name
        case_root.mkdir()
        try:
            outcomes[name] = _decide(policy, case_root, *files).chosen_mode
        except RdeConfigError as exc:
            outcomes[name] = exc.code
    assert outcomes == {"indicator": detectable, "fallback": fallback, "other": 1009, "both": 1007}


def test_decision_explains_the_policy__tc_781_pair(tmp_path: Path) -> None:
    # Given / When: the RDE_SEM policy with plain files
    decision = _decide(_SEM_POLICY, tmp_path, "a.tif", "b.tif")
    # Then: the versioned decision names policy, source, supported set and fallback
    payload = decision.to_dict()
    assert payload["schema_version"] == "2"
    assert payload["chosen_mode"] == "multidatatile"
    assert payload["reason_codes"] == ["fallback_mode"]
    assert payload["configured_mode"] is None
    assert payload["selection"] == {"policy": "auto", "source": "registration", "supported_modes": ["multidatatile", "smarttable"], "fallback_mode": "multidatatile"}


def test_unsupported_detection_names_the_rejected_mode__tc_781_pair(tmp_path: Path) -> None:
    # Given: an ExcelInvoice workbook uploaded to the SmartTable/MultiDataTile template
    with pytest.raises(RdeConfigError) as caught:
        _decide(_SEM_POLICY, tmp_path, _INDICATOR[ModeKind.excelinvoice])
    # Then: the catalogued rejection names the file, the mode and the supported set
    assert caught.value.code == 1009
    assert "batch_excel_invoice.xlsx indicates excelinvoice" in str(caught.value)
    assert caught.value.detail == {"evidence": [{"mode": "excelinvoice", "filename": "batch_excel_invoice.xlsx", "indicator": "excelinvoice_filename"}]}


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ({}, ModeKind.invoice),
        ({"registration": {"selection": "auto", "supported_modes": ["invoice", "smarttable"], "fallback_mode": "invoice"}}, ModeKind.invoice),
        ({"registration": _SEM_POLICY}, ModeKind.multidatatile),
        ({"registration": {"selection": "auto", "supported_modes": ["rdeformat", "smarttable"], "fallback_mode": "rdeformat"}}, ModeKind.rdeformat),
    ],
)
def test_zip_alone_never_implies_rdeformat__tc_781_zip(tmp_path: Path, source: dict[str, Any], expected: ModeKind) -> None:
    # Given: only a ZIP archive
    inputdata = _inputs(tmp_path, "export.zip")
    # When: selecting under each policy
    decision = decide_mode(_normalize(source, tmp_path), inputdata)
    # Then: RDEFormat only when the template names it as its fallback
    assert decision.chosen_mode is expected


@pytest.mark.parametrize("names", [("smarttable_a.csv", "smarttable_b.csv"), ("a_excel_invoice.xlsx", "b_excel_invoice.xlsx")])
def test_duplicate_control_files_are_ambiguous__tc_781_dup(tmp_path: Path, names: tuple[str, str]) -> None:
    registration = {"selection": "auto", "supported_modes": ["invoice", "smarttable", "excelinvoice"], "fallback_mode": "invoice"}
    assert _code(lambda: _decide(registration, tmp_path, *names)) == 1007


@pytest.mark.parametrize(
    ("mode", "names", "expected"),
    [
        ("multidatatile", ("smarttable_rows.csv",), 1005),
        ("invoice", ("batch_excel_invoice.xlsx",), 1005),
        ("smarttable", ("a.txt",), 1008),
        ("rdeformat", ("a.txt",), 1008),
    ],
)
def test_fixed_selection_keeps_strict_errors__tc_781_fixed(tmp_path: Path, mode: str, names: tuple[str, ...], expected: int) -> None:
    # Given / When: registration.mode conflicting with or missing its input
    code = _code(lambda: _decide({"selection": "fixed", "mode": mode}, tmp_path, *names))
    # Then: the #705 strict errors are unchanged
    assert code == expected


def test_fixed_selection_matches_extended_mode__tc_781_fixed(tmp_path: Path) -> None:
    # Given: the same fixed request through the new and the legacy field
    inputdata = _inputs(tmp_path, "a.tif", "b.tif")
    new = decide_mode(_normalize({"registration": {"selection": "fixed", "mode": "multidatatile"}}, tmp_path), inputdata)
    old = decide_mode(_normalize({"system": {"extended_mode": "multidatatile"}}, tmp_path), inputdata)
    # Then: only the declared source differs
    assert (new.chosen_mode, new.configured_mode, new.reason_codes) == (old.chosen_mode, old.configured_mode, old.reason_codes)
    assert (new.selection.policy, old.selection.policy) == ("fixed", "fixed")
    assert (new.selection.source, old.selection.source) == ("registration", "system.extended_mode")


def test_callback_contract__tc_781_cb(tmp_path: Path) -> None:
    # Given: an ExcelInvoice workbook and a MultiDataTile template
    inputdata = _inputs(tmp_path, _INDICATOR[ModeKind.excelinvoice])
    legacy = _normalize({"system": {"extended_mode": "MultiDataTile"}}, tmp_path)
    # When / Then: without registration the frozen v1 precedence and W1001 apply
    decision = decide_mode(legacy, inputdata, contract="v1")
    assert (decision.chosen_mode, decision.warning_codes, decision.selection.policy) == (ModeKind.excelinvoice, (1001,), "legacy")
    # When / Then: an opted-in callback template gets its declared policy instead
    assert _code(lambda: decide_mode(_normalize({"registration": _SEM_POLICY}, tmp_path), inputdata, contract="v1")) == 1009


def test_v1_template_section_named_registration_stays_custom__tc_781_tasksupport(tmp_path: Path) -> None:
    # Given: a v1 template whose own settings section happens to be called registration
    data = tmp_path / "data"
    (data / "tasksupport").mkdir(parents=True)
    (data / "tasksupport" / "rdeconfig.yaml").write_text(yaml.safe_dump({"registration": {"operator": "lab-a"}}), encoding="utf-8")
    # When: discovering it
    config = load_config(tmp_path, data_root=data)
    # Then: without `selection` it is not a policy and keeps its pre-#781 meaning
    assert config.registration is None
    assert config.custom == {"registration": {"operator": "lab-a"}}


@pytest.mark.parametrize(
    ("base", "override", "expected"),
    [
        ({"registration": _SEM_POLICY}, {"registration": {"selection": "fixed", "mode": "multidatatile"}}, ("fixed", "registration")),
        ({"registration": _SEM_POLICY}, {"registration": None, "system": {"extended_mode": "multidatatile"}}, ("fixed", "system.extended_mode")),
        ({"system": {"extended_mode": "MultiDataTile"}}, {"system": {"extended_mode": None}, "registration": _SEM_POLICY}, ("auto", "registration")),
        ({"registration": _SEM_POLICY}, {"system": {"extended_mode": "multidatatile"}}, 1002),
        ({"system": {"extended_mode": "MultiDataTile"}}, {"registration": _SEM_POLICY}, 1002),
    ],
)
def test_overrides_switch_policy_explicitly__tc_781_cfg_dual(tmp_path: Path, base: dict[str, Any], override: dict[str, Any], expected: object) -> None:
    # Given: a project config and a run override
    (tmp_path / "rdeconfig.yaml").write_text(yaml.safe_dump(base), encoding="utf-8")
    (tmp_path / "inputdata").mkdir()
    # When: loading with the override
    try:
        config = load_config(tmp_path, override)
    except RdeConfigError as exc:
        # Then: a half-switched declaration names the null escape hatch
        assert (exc.code, "set the other to null" in str(exc)) == (expected, True)
        return
    # Then: an override replaces the policy whole instead of merging into it
    selection = decide_mode(config, tmp_path / "inputdata").selection
    assert (selection.policy, selection.source) == expected


def test_callback_runs_under_a_policy__tc_781_cb(tmp_path: Path) -> None:
    # Given: an RDE_SEM-like v1 callback template that adopted the policy
    data = _sem_workspace(tmp_path, "multidatatile", {"system": _SYSTEM, "registration": _SEM_POLICY})
    # When: the public callback entry runs
    result = json.loads(_run_in(tmp_path, lambda: workflows.run(custom_dataset_function=_callback)))
    # Then: the fallback registers one tile per file, with no override warning
    assert [status["status"] for status in result["statuses"]] == ["success", "success"]
    assert sum(1 for name in _artifacts(data) if name.endswith("structured/files.txt")) == 2
    events = [json.loads(line) for path in (data / "logs").glob("events_*.jsonl") for line in path.read_text(encoding="utf-8").splitlines()]
    assert events
    assert not [event for event in events if event.get("code") == 1001 or event.get("payload", {}).get("code") == 1001]


def test_tasksupport_discovery_keeps_registration__tc_781_tasksupport(tmp_path: Path) -> None:
    # Given: the v1 layout structured programs ship, with a registration section
    data = tmp_path / "data"
    (data / "tasksupport").mkdir(parents=True)
    (data / "tasksupport" / "rdeconfig.yaml").write_text(yaml.safe_dump({"system": {"save_raw": True}, "registration": _SEM_POLICY, "sem": {"manufacturer": "tiff_exif"}}), encoding="utf-8")
    # When: discovering it through the v1 configuration model
    config = load_config(tmp_path, data_root=data)
    # Then: the policy reaches the Runner and template sections stay custom
    assert config.registration is not None
    assert config.registration.model_dump(exclude_none=True) == _SEM_POLICY
    assert config.custom == {"sem": {"manufacturer": "tiff_exif"}}
    assert "registration" not in config.custom


#: Digests computed by the release before #781; reports and repro archives carry them.
_PRE_781_DIGESTS = {
    "default": "sha256:b8d2bdd4a8ca0559e3cd129368e7804417080dad31886d6ef506ad977fb75825",
    "multidatatile": "sha256:02f0b931577d11eb31047d8fe8004eefa75fe4768132b712a0e304386620709d",
}


def test_digest_identity__tc_781_digest(tmp_path: Path) -> None:
    # Given: existing configurations and two policies with different outcomes
    plain = RdeConfig()
    explicit = RdeConfig(system={"extended_mode": "multidatatile"})
    sem = _normalize({"registration": _SEM_POLICY}, tmp_path)
    invoice_fallback = _normalize({"registration": {"selection": "auto", "supported_modes": ["invoice", "smarttable"], "fallback_mode": "invoice"}}, tmp_path)
    # Then: unchanged configurations keep their pre-#781 digest, distinct policies differ
    assert compute_config_digest(plain) == _PRE_781_DIGESTS["default"]
    assert compute_config_digest(explicit) == _PRE_781_DIGESTS["multidatatile"]
    assert len({compute_config_digest(plain), compute_config_digest(sem), compute_config_digest(invoice_fallback)}) == 3
    # And: the archived YAML form replays to the same identity
    for compact in (True, False):
        replayed = _normalize(yaml.safe_load(yaml.safe_dump(config_for_replay(sem, compact=compact))), tmp_path)
        assert compute_config_digest(replayed) == compute_config_digest(sem)


_SYSTEM = {"save_raw": True, "save_thumbnail_image": False, "magic_variable": False}


def _sem_workspace(root: Path, case: str, config: dict[str, Any]) -> Path:
    data = _generate.build_smarttable_workspace(root)
    (data / "tasksupport" / "rdeconfig.yml").write_text(yaml.safe_dump(config), encoding="utf-8")
    if case == "multidatatile":
        for path in (data / "inputdata").iterdir():
            path.unlink()
        (data / "inputdata" / "image_a.tif").write_bytes(b"A")
        (data / "inputdata" / "image_b.tif").write_bytes(b"B")
    return data


def _callback(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath) -> None:
    _ = srcpaths
    (Path(resource_paths.struct) / "files.txt").write_text("\n".join(sorted(path.name for path in resource_paths.rawfiles)), encoding="utf-8")


@flow
def _sem_flow(paths: InputPaths, out: OutputContext) -> None:
    (out.struct / "files.txt").write_text("\n".join(sorted(path.name for path in paths.rawfiles)), encoding="utf-8")


def _artifacts(data: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(data)): path.read_bytes()
        for path in sorted(data.rglob("*"))
        if path.is_file() and path.relative_to(data).parts[0] not in {"logs", "tasksupport"}
    }


def _run_in(root: Path, action: Callable[[], Any]) -> Any:
    previous = Path.cwd()
    os.chdir(root)
    try:
        return action()
    finally:
        os.chdir(previous)


@pytest.mark.parametrize(("case", "tiles"), [("smarttable", 3), ("multidatatile", 2)])
def test_rde_sem_template_matches_v1_oracle__tc_781_sem(tmp_path: Path, case: str, tiles: int) -> None:
    """The RDE_SEM ZEISS/JEOL FE regression, against the original v1 behavior.

    The oracle is the v1 callback contract with the template's historic
    ``extended_mode: MultiDataTile``, whose SmartTable precedence is frozen.
    """
    # Given: the same inputs, once with the historic config and once with the policy
    oracle = _sem_workspace(tmp_path / "oracle", case, {"system": {"extended_mode": "MultiDataTile", **_SYSTEM}})
    strict = _sem_workspace(tmp_path / "strict", case, {"system": {"extended_mode": "MultiDataTile", **_SYSTEM}})
    candidate = _sem_workspace(tmp_path / "candidate", case, {"system": _SYSTEM, "registration": _SEM_POLICY})
    # When: the v1 callback runs the oracle and the v2 flow runs the other two
    assert _run_in(oracle.parent, lambda: workflows.run(custom_dataset_function=_callback))
    strict_report = _run_in(strict.parent, lambda: workflows.run(flow=_sem_flow))
    report = _run_in(candidate.parent, lambda: workflows.run(flow=_sem_flow))
    # Then: the historic config conflicts under the strict flow contract (the reported bug) ...
    if case == "smarttable":
        assert strict_report.status == "failed"
        assert strict_report.error is not None
        assert strict_report.error["code"] == 1005
    # ... while the declared policy reproduces every v1 artifact byte for byte
    assert report.status == "success", report.error
    artifacts = _artifacts(candidate)
    assert artifacts == _artifacts(oracle)
    assert sum(1 for name in artifacts if name.endswith("structured/files.txt")) == tiles


@pytest.mark.parametrize(("case", "mode", "tiles"), [("smarttable", "smarttable", 3), ("multidatatile", "multidatatile", 2)])
def test_preview_matches_execution__tc_781_preview(tmp_path: Path, case: str, mode: str, tiles: int) -> None:
    # Given: the RDE_SEM policy and either input shape
    data = _sem_workspace(tmp_path, case, {"system": _SYSTEM, "registration": _SEM_POLICY})
    # When: explaining, then running
    preview = preview_registration(tmp_path).to_dict()
    report = _run_in(tmp_path, lambda: workflows.run(flow=_sem_flow))
    # Then: the explanation names the decision the run used, and changed nothing first
    assert preview["decision"]["chosen_mode"] == mode
    assert preview["decision"]["selection"]["policy"] == "auto"
    assert preview["tile_count"] == tiles
    assert report.status == "success", report.error
    assert report.mode == preview["decision"]["chosen_mode"]
    assert sum(1 for name in _artifacts(data) if name.endswith("structured/files.txt")) == tiles
