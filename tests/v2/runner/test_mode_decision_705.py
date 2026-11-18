"""Versioned mode intent and decision contract for RM-01 through RM-03.

| API | Partition or boundary | Expected | Test ID |
|-----|-----------------------|----------|---------|
| normalizer | all canonical names and two legacy aliases | canonical mode, explicit intent | RM01-P |
| normalizer | None and omitted | implicit invoice | RM01-B0 |
| normalizer | typo, mixed case, extra name, empty string | catalog 1002 listing valid names | RM01-N |
| normalization/repro | default invoice explicitly supplied or omitted | distinct intent and digest survive reload | RM01-B1 |
| decision | one special file in auto | deterministic special choice with filename evidence | RM02-P |
| decision | conflicting explicit invoice or MultiDataTile | catalog 1005, configured name and filename | RM02-N1 |
| decision | SmartTable + ExcelInvoice | catalog 1007 | RM02-N2 |
| decision | two SmartTables or workbooks | catalog 1007 | RM02-N3 |
| decision | missing explicit special file | catalog 1008 | RM02-N4 |
| legacy decision | same conflict snapshot as v2 | historical chosen mode and W1001 | RM02-L |
| decision | empty input or multiple ordinary files | one Invoice mode, no payload evidence | RM03-B |
| decision | repeated read-only calls | equal immutable output, unchanged tree | RM03-P |
"""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from rdetoolkit.config.normalize import ConfigNormalizer
from rdetoolkit.domain.mode_selection import ModeKind, decide_mode
from rdetoolkit.errors import RdeConfigError
from rdetoolkit.runner.config_loader import compute_config_digest
from rdetoolkit.types import RdeConfig


@pytest.mark.parametrize("raw,expected", [(m.value, m) for m in ModeKind] + [("MultiDataTile", ModeKind.multidatatile), ("rdeformat", ModeKind.rdeformat), ("SmartTableInvoice", ModeKind.smarttable), ("ExcelInvoice", ModeKind.excelinvoice)])
def test_canonical_names__rm01_p(tmp_path: Path, raw: str, expected: ModeKind) -> None:
    # Given: a supported v2 name or explicit legacy alias.
    # When: normalizing at the public config boundary.
    config = ConfigNormalizer().normalize({"system": {"extended_mode": raw}}, root=tmp_path, origin="v2")
    # Then: the intent is normalized and stays explicit.
    assert config.system.extended_mode == expected.value
    assert "extended_mode" in config.system.model_fields_set


@pytest.mark.parametrize("raw", ["", "multidatatlie", "INVOICE", "Unknown", "MultiDataTile ", "excelInvoice", 5, False])
def test_invalid_names__rm01_n(tmp_path: Path, raw: object) -> None:
    # Given: a name outside the exact canonical and alias vocabulary.
    # When: normalizing a strict configuration.
    with pytest.raises(RdeConfigError) as caught:
        ConfigNormalizer().normalize({"system": {"extended_mode": raw}}, root=tmp_path, origin="v2")
    # Then: a catalogued config error lists the supported vocabulary.
    assert caught.value.code == 1002
    assert "invoice" in str(caught.value)
    assert "multidatatile" in str(caught.value)


@pytest.mark.parametrize("explicit", [False, True])
def test_normalizer_preserves_intent__rm01_b1(tmp_path: Path, explicit: bool) -> None:
    # Given: models whose effective invoice value agrees but intent differs.
    original = RdeConfig(system={"extended_mode": "invoice"}) if explicit else RdeConfig()
    # When: passing a preloaded model through normalization.
    normalized = ConfigNormalizer().normalize(original, root=tmp_path, origin="v2")
    # Then: configuration identity includes the meaningful explicitness.
    assert ("extended_mode" in normalized.system.model_fields_set) is explicit
    assert compute_config_digest(RdeConfig()) != compute_config_digest(RdeConfig(system={"extended_mode": "invoice"}))


def test_auto_evidence_is_immutable_and_read_only__rm03_p(tmp_path: Path) -> None:
    # Given: a single format indicator and no explicit mode.
    table = tmp_path / "smarttable_batch.csv"
    table.write_text("sensitive payload", encoding="utf-8")
    before = list(tmp_path.iterdir())
    # When: repeatedly selecting from the same snapshot.
    decision = decide_mode(RdeConfig(), tmp_path)
    # Then: only filenames are exposed and no outputs appear.
    assert decision == decide_mode(RdeConfig(), tmp_path)
    assert decision.chosen_mode is ModeKind.smarttable
    assert decision.configured_mode is None
    assert decision.evidence[0].filename == table.name
    assert "sensitive payload" not in str(decision.to_dict())
    assert list(tmp_path.iterdir()) == before
    with pytest.raises(FrozenInstanceError):
        decision.chosen_mode = ModeKind.invoice  # type: ignore[misc]


@pytest.mark.parametrize("mode", ["invoice", "multidatatile", "rdeformat", "excelinvoice"])
def test_explicit_conflicts__rm02_n1(tmp_path: Path, mode: str) -> None:
    # Given: explicit intent conflicting with a SmartTable indicator.
    (tmp_path / "smarttable_batch.csv").touch()
    # When: v2 resolves the snapshot.
    with pytest.raises(RdeConfigError) as caught:
        decide_mode(RdeConfig(system={"extended_mode": mode}), tmp_path)
    # Then: the setting and filename identify the fix without data values.
    assert caught.value.code == 1005
    assert mode in str(caught.value)
    assert "smarttable_batch.csv" in str(caught.value)


@pytest.mark.parametrize("names", [("smarttable_a.csv", "x_excel_invoice.xlsx"), ("smarttable_a.csv", "smarttable_b.tsv"), ("a_excel_invoice.xlsx", "b_excel_invoice.xlsx")])
def test_ambiguous_inputs__rm02_n2(tmp_path: Path, names: tuple[str, ...]) -> None:
    # Given: competing special input files.
    for name in names:
        (tmp_path / name).touch()
    # When: automatic v2 detection considers all candidates.
    with pytest.raises(RdeConfigError) as caught:
        decide_mode(RdeConfig(), tmp_path)
    # Then: ambiguity is a catalogued refusal before mutation.
    assert caught.value.code == 1007


@pytest.mark.parametrize("mode", ["smarttable", "excelinvoice", "rdeformat"])
def test_missing_required_indicator__rm02_n4(tmp_path: Path, mode: str) -> None:
    # Given: an explicitly requested format without required inputs.
    # When: planning the v2 run.
    with pytest.raises(RdeConfigError) as caught:
        decide_mode(RdeConfig(system={"extended_mode": mode}), tmp_path)
    # Then: the diagnostic is a catalogued input requirement.
    assert caught.value.code == 1008


def test_legacy_preserves_priority_for_same_conflict__rm02_l(tmp_path: Path) -> None:
    # Given: the same conflicting input used by strict-v2 cases.
    (tmp_path / "smarttable_batch.csv").touch()
    config = RdeConfig(system={"extended_mode": "MultiDataTile"})
    # When: selecting for the callback compatibility contract.
    decision = decide_mode(config, tmp_path, contract="v1")
    # Then: historical file precedence and its warning remain explicit.
    assert decision.chosen_mode is ModeKind.smarttable
    assert decision.warning_codes == (1001,)


@pytest.mark.parametrize("explicit", [False, True])
def test_repro_preserves_selection_intent__rm01_repro(tmp_path: Path, explicit: bool) -> None:
    # Given: auto and explicit invoice configurations with different selection contracts.
    from rdetoolkit.cli.repro_cmd import _config_yaml
    from rdetoolkit.runner.config_loader import load_run_config

    original = RdeConfig(system={"extended_mode": "invoice"}) if explicit else RdeConfig()
    digest = compute_config_digest(original)
    # When: serializing exactly the YAML used by repro export and loading the replay.
    (tmp_path / "rdeconfig.yaml").write_text(_config_yaml(original, digest), encoding="utf-8")
    replayed = load_run_config(tmp_path)
    inputs = tmp_path / "inputdata"
    inputs.mkdir()
    (inputs / "smarttable_batch.csv").touch()
    # Then: replay keeps the digest and either the explicit refusal or automatic choice.
    assert compute_config_digest(replayed) == digest
    assert ("extended_mode" in replayed.system.model_fields_set) is explicit
    if explicit:
        with pytest.raises(RdeConfigError) as caught:
            decide_mode(replayed, inputs)
        assert caught.value.code == 1005
    else:
        assert decide_mode(replayed, inputs).chosen_mode is ModeKind.smarttable


def test_same_snapshot_legacy_warning_and_strict_error__rm02_l_events(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Given: identical conflicting inputs and configuration for both contracts.
    from rdetoolkit.report.events import MemoryEventSink
    from rdetoolkit.runner.mode_resolver import resolve_mode

    (tmp_path / "smarttable_batch.csv").touch()
    config = RdeConfig(system={"extended_mode": "MultiDataTile"})
    sink = MemoryEventSink()
    sink.open("legacy")
    # When: selecting through each public resolver contract.
    legacy = resolve_mode(config, tmp_path, tmp_path / "unused", sink, "legacy", contract="v1")
    with pytest.raises(RdeConfigError) as caught:
        resolve_mode(config, tmp_path, tmp_path / "unused", sink, "strict")
    # Then: v1 returns its historical result with W1001; v2 returns a catalogued error.
    assert legacy is ModeKind.smarttable
    assert caught.value.code == 1005
    assert any(event.payload.get("code") == 1001 for event in sink.events)
    assert "ModeOverriddenByFileDetection" in capsys.readouterr().err


@pytest.mark.parametrize("entries,expected_code", [(["raw/data.csv", "raw/data.csv"], 1007), (["../raw.csv"], 1007), (["/raw.csv"], 1007)])
def test_ambiguous_archive_is_rejected_before_extraction__rm02_zip(tmp_path: Path, entries: list[str], expected_code: int) -> None:
    # Given: a format archive with ambiguous or unsafe member identities.
    from zipfile import ZipFile

    with ZipFile(tmp_path / "inputs.zip", "w") as archive:
        for name in entries:
            archive.writestr(name, "private")
    # When: selecting the RDEFormat contract without extracting anything.
    with pytest.raises(RdeConfigError) as caught:
        decide_mode(RdeConfig(system={"extended_mode": "rdeformat"}), tmp_path)
    # Then: the early catalogued diagnostic never includes payload content.
    assert caught.value.code == expected_code
    assert "private" not in str(caught.value)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["inputs.zip"]


@pytest.mark.parametrize("kind", ["broken", "multiple"])
def test_invalid_special_archives__rm02_zip_invalid(tmp_path: Path, kind: str) -> None:
    # Given: malformed or multiple special archive inputs.
    (tmp_path / "input.zip").write_text("broken", encoding="utf-8")
    if kind == "multiple":
        (tmp_path / "other.zip").touch()
    # When: deciding before any unpack operation.
    with pytest.raises(RdeConfigError) as caught:
        decide_mode(RdeConfig(system={"extended_mode": "rdeformat"}), tmp_path)
    # Then: malformed and ambiguous input have distinct stable errors.
    assert caught.value.code == (1008 if kind == "broken" else 1007)


@pytest.mark.parametrize("mode", list(ModeKind))
def test_all_five_legacy_and_strict_modes__rm03_matrix(tmp_path: Path, mode: ModeKind) -> None:
    # Given: unique valid indicators for each supported registration mode.
    from zipfile import ZipFile

    if mode is ModeKind.smarttable:
        (tmp_path / "smarttable_batch.tsv").touch()
    elif mode is ModeKind.excelinvoice:
        (tmp_path / "batch_excel_invoice.xlsx").touch()
    elif mode is ModeKind.rdeformat:
        with ZipFile(tmp_path / "inputs.zip", "w") as archive:
            archive.writestr("0001/raw/data.csv", "private")
    else:
        (tmp_path / "data.csv").touch()
    # When: requesting the canonical mode explicitly.
    decision = decide_mode(RdeConfig(system={"extended_mode": mode.value}), tmp_path)
    # Then: explicit selection remains stable and carries its reason.
    assert decision.chosen_mode is mode
    assert decision.configured_mode is mode
    assert decision.reason_codes == ("explicit_mode",)


@pytest.mark.property
def test_ordinary_file_counts_never_auto_select_multidatatile(tmp_path: Path) -> None:
    # Given: varying ordinary input counts with automatic mode intent.
    from hypothesis import given, settings, strategies as st

    @settings(max_examples=30)
    @given(st.integers(min_value=0, max_value=20))
    def check(count: int) -> None:
        for file in tmp_path.glob("*.csv"):
            file.unlink()
        for index in range(count):
            (tmp_path / f"{index:03d}.csv").touch()
        # When: selecting repeatedly from the same ordinary snapshot.
        first = decide_mode(RdeConfig(), tmp_path)
        # Then: selection stays Invoice and reproduces exactly.
        assert first == decide_mode(RdeConfig(), tmp_path)
        assert first.chosen_mode is ModeKind.invoice

    check()


@pytest.mark.parametrize("name", ["MultiDataTile", "multidatatile"])
def test_mode_alias_repro_retains_legacy_grouping__rm01_repro_legacy(tmp_path: Path, name: str) -> None:
    # Given: a callback config that selected one tile per raw file.
    from rdetoolkit.cli.repro_cmd import _config_yaml
    from rdetoolkit.compat.v1.callback import to_legacy_config
    from rdetoolkit.runner.config_loader import load_run_config
    from rdetoolkit.runner.iterator import iterate_tiles

    original = RdeConfig(system={"extended_mode": name})
    digest = compute_config_digest(original)
    (tmp_path / "rdeconfig.yaml").write_text(_config_yaml(original, digest), encoding="utf-8")
    inputs = tmp_path / "inputdata"
    inputs.mkdir()
    for filename in ["a.dat", "b.dat"]:
        (inputs / filename).touch()
    # When: replaying the serialized config through canonical normalization.
    replayed = load_run_config(tmp_path)
    decision = decide_mode(replayed, inputs, contract="v1")
    tiles = list(iterate_tiles(decision.chosen_mode, inputs, tmp_path / "temp", tmp_path, replayed))
    # Then: equal digest identifies equal callback selection and grouping behavior.
    assert compute_config_digest(replayed) == digest
    assert decision.chosen_mode is ModeKind.multidatatile
    assert len(tiles) == 2
    assert to_legacy_config(replayed).system.extended_mode == "MultiDataTile"


@pytest.mark.parametrize("settings", [{}, {"extended_mode": None}])
def test_omitted_and_null_modes_are_auto__rm01_b0(tmp_path: Path, settings: dict[str, object]) -> None:
    # Given: no mode intent, including the public null-clearing spelling.
    # When: normalizing the v2 source.
    config = ConfigNormalizer().normalize({"system": settings}, root=tmp_path, origin="v2")
    # Then: the effective default does not become an explicit request.
    assert config.system.extended_mode == "invoice"
    assert "extended_mode" not in config.system.model_fields_set


@pytest.mark.parametrize("explicit", [False, True])
def test_normalizer_keeps_mutated_default_sections__rm01_mutation(tmp_path: Path, explicit: bool) -> None:
    # Given: effective values changed through default-created nested models and mappings.
    original = RdeConfig()
    original.system.save_raw = True
    original.custom["label"] = "preserved"
    if explicit:
        original.system.extended_mode = "invoice"
    # When: normalizing the current model state rather than its constructor arguments.
    normalized = ConfigNormalizer().normalize(original, root=tmp_path, origin="v2")
    # Then: values and nested mode intent both survive.
    assert normalized.system.save_raw is True
    assert normalized.custom == {"label": "preserved"}
    assert ("extended_mode" in normalized.system.model_fields_set) is explicit


def test_invalid_preloaded_mode_never_runs_preparation__rm01_prepare(tmp_path: Path) -> None:
    # Given: a preloaded config and a preparation hook that would mutate user inputs.
    from rdetoolkit import flow
    from rdetoolkit.api.request import FlowTarget, RunRequest
    from rdetoolkit.runner.lifecycle import Runner
    from rdetoolkit.types import InputPaths

    def prepare(paths: InputPaths) -> None:
        (paths.inputdata / "prepared.csv").touch()

    @flow(prepare=prepare)
    def pipeline() -> None:
        raise AssertionError("invalid configuration must not run the flow")

    inputs = tmp_path / "data" / "inputdata"
    inputs.mkdir(parents=True)
    invalid = RdeConfig(system={"extended_mode": "UNKNOWN"})
    # When: running through the preloaded-model entry instead of a mapping.
    report = Runner(root=tmp_path).run(RunRequest(root=tmp_path, target=FlowTarget(function=pipeline), config_source=invalid))
    # Then: the catalogued name error precedes any preparation effects.
    assert report.status == "failed"
    assert report.error is not None and report.error["code"] == 1002
    assert not (inputs / "prepared.csv").exists()
