"""Mode identity EP/BV regressions for compatibility reproduction archives.

| ID | Partition or boundary | Expected |
|----|-----------------------|----------|
| LM-N1 | RDEFormat and rdeformat under the callback contract | distinct digests |
| LM-N2 | validated RDEFormat loaded from YAML | legacy invoice remains invoice |
| LM-N3 | RDEFormat callback export/import/reread | invoice and one tile survive |
| LM-B1 | canonical rdeformat callback export/import/reread | two format tiles survive |
| LM-P1 | all accepted aliases | normalization preserves both contracts' choices |
| LM-N4 | rejected mixed-case or unknown mode | catalogued 1002 without an archive |
"""

from pathlib import Path
from zipfile import ZipFile

import pytest
from typer.testing import CliRunner

from rdetoolkit.api.request import LegacyCallbackTarget, RunRequest
from rdetoolkit.cli.app import app
from rdetoolkit.config.normalize import ConfigNormalizer
from rdetoolkit.domain.mode_selection import ModeKind, decide_mode, normalize_mode_name
from rdetoolkit.errors import RdeConfigError
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.runner.config_loader import compute_config_digest, load_run_config
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import RdeConfig
from tests.v2.contract.fixtures import _generate


def _callback_run(root: Path, config: RdeConfig) -> RunReport:
    request = RunRequest(root=root, target=LegacyCallbackTarget(function=None), config_source=config)
    return Runner(root=root, inputdata_path=root / "data/inputdata", unpacked_dir_path=root / "data/temp").run(request)


def test_distinct_callback_mode_semantics_have_distinct_digests__lm_n1() -> None:
    # Given: spellings that the compatibility contract deliberately interprets differently.
    upper = RdeConfig(system={"extended_mode": "RDEFormat"})
    lower = RdeConfig(system={"extended_mode": "rdeformat"})
    # When: identifying these effective callback settings.
    upper_digest = compute_config_digest(upper)
    lower_digest = compute_config_digest(lower)
    # Then: a digest cannot conceal the invoice-versus-format difference.
    assert upper_digest != lower_digest


def test_yaml_reload_preserves_callback_mode_meaning__lm_n2(tmp_path: Path) -> None:
    # Given: an explicitly configured spelling whose callback meaning is Invoice.
    (tmp_path / "rdeconfig.yaml").write_text("system:\n  extended_mode: RDEFormat\n", encoding="utf-8")
    with ZipFile(tmp_path / "input.zip", "w") as archive:
        archive.writestr("0000/raw/a.txt", "a")
        archive.writestr("0001/raw/b.txt", "b")
    # When: reading the same setting through the shared configuration loader.
    reloaded = load_run_config(tmp_path)
    decision = decide_mode(reloaded, tmp_path, contract="v1")
    # Then: validation does not turn a legacy Invoice setting into RDEFormat.
    assert decision.chosen_mode is ModeKind.invoice
    assert reloaded.system.extended_mode == "RDEFormat"


@pytest.mark.parametrize("raw,expected_mode,expected_tiles", [("RDEFormat", "invoice", 1), ("rdeformat", "rdeformat", 2)])
def test_cli_repro_retains_callback_mode_and_tile_count__lm_n3_b1(tmp_path: Path, raw: str, expected_mode: str, expected_tiles: int) -> None:
    # Given: the same two-group archive, interpreted by the actual callback Runner.
    root = tmp_path / "original"
    _generate.materialize_case(_generate.oracle_case("v1/rdeformat/ok"), root)
    (root / "rdeconfig.yaml").write_text(f"system:\n  extended_mode: {raw}\n", encoding="utf-8")
    original = _callback_run(root, RdeConfig(system={"extended_mode": raw}))
    assert original.status == "success", original.error
    assert original.mode == expected_mode
    assert len(original.iterations) == expected_tiles
    report = root / "data/logs" / f"run_report_{original.run_id}.json"
    archive = tmp_path / "reproduction.zip"
    target = tmp_path / "imported"
    # When: exporting and importing through the public CLI, then rereading its YAML.
    exported = CliRunner().invoke(app, ["repro", "export", str(report), "--output", str(archive)])
    assert exported.exit_code == 0, exported.output
    imported = CliRunner().invoke(app, ["repro", "import", str(archive), str(target)])
    assert imported.exit_code == 0, imported.output
    reloaded = load_run_config(target)
    replay = _callback_run(target, reloaded)
    # Then: the real rerun retains both registration behavior and configuration identity.
    assert replay.status == "success", replay.error
    assert (replay.mode, len(replay.iterations)) == (original.mode, len(original.iterations))
    assert compute_config_digest(reloaded) == original.config_digest == replay.config_digest


@pytest.mark.parametrize("raw", ["Invoice", "MultiDataTile", "SmartTableInvoice", "ExcelInvoice", "RDEFormat"])
def test_alias_normalization_preserves_both_mode_contracts__lm_p1(tmp_path: Path, raw: str) -> None:
    # Given: a documented alias and its uniquely matching strict-mode input indicator.
    strict_mode = normalize_mode_name(raw)
    if strict_mode is ModeKind.smarttable:
        (tmp_path / "smarttable_case.csv").touch()
    elif strict_mode is ModeKind.excelinvoice:
        (tmp_path / "case_excel_invoice.xlsx").touch()
    elif strict_mode is ModeKind.rdeformat:
        with ZipFile(tmp_path / "input.zip", "w"):
            pass
    original = RdeConfig(system={"extended_mode": raw})
    # When: validating the setting before its execution target is known.
    normalized = ConfigNormalizer().normalize(original, root=tmp_path, origin="v2")
    # Then: both policy decisions and the digest retain the same meaning.
    assert decide_mode(normalized, tmp_path, contract="v1").chosen_mode == decide_mode(original, tmp_path, contract="v1").chosen_mode
    assert decide_mode(normalized, tmp_path, contract="v2").chosen_mode is strict_mode
    assert compute_config_digest(normalized) == compute_config_digest(original)


@pytest.mark.parametrize("raw", ["RDEFORMAT", "rdeFormat", "unknown", "", "RDEFormat "])
def test_invalid_spellings_still_fail_strict_normalization__lm_n4(tmp_path: Path, raw: str) -> None:
    # Given: a spelling outside the documented canonical and alias vocabulary.
    # When: validating it at the strict configuration boundary.
    with pytest.raises(RdeConfigError) as caught:
        ConfigNormalizer().normalize({"system": {"extended_mode": raw}}, root=tmp_path, origin="v2")
    # Then: preserving the one compatibility spelling does not accept invalid names.
    assert caught.value.code == 1002
    assert not list(tmp_path.iterdir())
