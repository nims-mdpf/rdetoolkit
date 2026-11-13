"""``repro export`` archives the effective config (Session RC1-INT-CLI, review item F09).

Export archived only ``data_root.parent/rdeconfig.yaml``. The Runner also
reads root ``pyproject.toml [tool.rdetoolkit]``, a flat data root's own
``rdeconfig.yaml``, ``tasksupport`` files and overrides, so those runs
replayed with a different config (``configured`` became ``DEFAULT``) while
export/import/rerun all reported success. Export now rebuilds the effective
config with the Runner's own loader, checks it against the report's
``config_digest`` with the Runner's own digest function, and writes it as the
archive-root ``rdeconfig.yaml``; a run whose overrides cannot be recovered
from files exits 3 unless ``export --config`` supplies the same override YAML.

EP table:
    TC-RC1-F09-EP-001 | no config file                     | round trip keeps output + config_digest
    TC-RC1-F09-EP-002 | root rdeconfig.yaml                | round trip keeps output + config_digest
    TC-RC1-F09-EP-003 | root pyproject.toml [tool.rdetoolkit] | round trip keeps output + config_digest
    TC-RC1-F09-EP-004 | flat data-root rdeconfig.yaml      | round trip keeps output + config_digest
    TC-RC1-F09-EP-005 | data/tasksupport/rdeconfig.yaml    | round trip keeps output + config_digest
    TC-RC1-F09-EP-006 | ``run --config`` + ``export --config`` | round trip keeps output + config_digest
    TC-RC1-F09-EP-007 | v1 callback run (v1 entry config)  | export -> import -> rerun (v1 entry and --flow) keeps config_digest
    TC-RC1-F09-EP-008 | custom keys not in alphabetical order (nested too) | round trip keeps output + config_digest
    TC-D1-EP-007      | rdeconfig.yaml keys reordered after the run | export still matches the run's config_digest

Negative table:
    TC-RC1-F09-NEG-001 | ``run --config`` override, export without --config | exit 3 naming --config; no archive
    TC-RC1-F09-NEG-002 | export --config with a different override          | exit 3; no archive
    TC-RC1-F09-NEG-003 | export --config YAML that is not a mapping         | exit 3
    TC-RC1-F09-NEG-004 | export --config path that does not exist           | exit 3
    TC-RC1-F09-NEG-005 | report digest no file config reproduces            | exit 3; no archive
    TC-RC1-F09-NEG-006 | config file broken after the run                   | exit 3 (no traceback); no archive
    TC-RC1-F09-NEG-007 | no YAML form of the effective config replays       | exit 3 naming the digest; no archive

BV table:
    TC-RC1-F09-BV-001 | all-default effective config | archived rdeconfig.yaml is an empty mapping (no default marked explicit)
    TC-RC1-F09-BV-002 | one non-default key          | archived rdeconfig.yaml holds exactly that key
    TC-RC1-F09-BV-003 | non-default-only form does not replay | the full dump is archived instead
"""

from __future__ import annotations

import json
import os
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from rdetoolkit.cli import repro_cmd
from rdetoolkit.cli.app import app
from rdetoolkit.runner.config_loader import compute_config_digest, load_config

FLOW = "tests.v2.cli.fixtures.repro_config_flows:config_pipeline"
LEGACY = "tests.v2.cli.fixtures.repro_config_flows::legacy_callback"


def _seed(data_root: Path) -> None:
    """Create a valid one-tile invoice-mode input tree."""
    for dirname in ("inputdata", "invoice", "tasksupport", "temp"):
        (data_root / dirname).mkdir(parents=True, exist_ok=True)
    (data_root / "inputdata" / "sample.txt").write_text("input", encoding="utf-8")
    invoice = {
        "datasetId": "rc1-f09-dataset",
        "basic": {"dateSubmitted": "2026-07-12", "dataOwnerId": "0" * 56, "dataName": "rc1"},
    }
    (data_root / "invoice" / "invoice.json").write_text(json.dumps(invoice), encoding="utf-8")
    (data_root / "tasksupport" / "invoice.schema.json").write_text('{"properties": {}}', encoding="utf-8")
    (data_root / "tasksupport" / "metadata-def.json").write_text('{"constant": {}, "variable": []}', encoding="utf-8")


@contextmanager
def _cwd(path: Path) -> Iterator[None]:
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def _project(base: Path, case: str) -> tuple[Path, Path]:
    """Build one configuration case; return (project root, data root)."""
    root = base / case
    data_root = root if case == "flat_yaml" else root / "data"
    _seed(data_root)
    if case in {"root_yaml", "flat_yaml"}:
        (root / "rdeconfig.yaml").write_text("custom:\n  label: configured\n", encoding="utf-8")
    elif case == "root_toml":
        (root / "pyproject.toml").write_text('[tool.rdetoolkit.custom]\nlabel = "configured"\n', encoding="utf-8")
    elif case == "tasksupport_yaml":
        (data_root / "tasksupport" / "rdeconfig.yaml").write_text("system:\n  save_raw: false\n", encoding="utf-8")
    elif case == "unsorted_keys":
        # Keys deliberately not in alphabetical order (sorted: a, label, nested, z),
        # one level down too: config_digest must not depend on key order.
        (root / "rdeconfig.yaml").write_text(
            "custom:\n  z: 1\n  label: configured\n  a: 2\n  nested:\n    y: 1\n    b: 2\n",
            encoding="utf-8",
        )
    return root, data_root


def _run(root: Path, *extra: str) -> dict[str, Any]:
    with _cwd(root):
        result = CliRunner().invoke(app, ["run", FLOW, *extra])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def _report_path(data_root: Path, report: dict[str, Any]) -> Path:
    return data_root / "logs" / f"run_report_{report['run_id']}.json"


def _export(report_path: Path, archive: Path, *extra: str) -> Any:
    return CliRunner().invoke(app, ["repro", "export", str(report_path), "--output", str(archive), *extra])


def _round_trip(tmp_path: Path, report_path: Path, *export_extra: str) -> tuple[dict[str, Any], Path, dict[str, Any]]:
    archive = tmp_path / "archive.zip"
    exported = _export(report_path, archive, *export_extra)
    assert exported.exit_code == 0, exported.output
    target = tmp_path / "imported"
    imported = CliRunner().invoke(app, ["repro", "import", str(archive), str(target)])
    assert imported.exit_code == 0, imported.output
    (target / "data" / "temp").mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as opened:
        manifest = json.loads(opened.read("repro_manifest.json"))
    return _run(target), target, manifest


@pytest.mark.parametrize(
    "case",
    [
        pytest.param("default", id="tc_rc1_f09_ep_001_default"),
        pytest.param("root_yaml", id="tc_rc1_f09_ep_002_root_yaml"),
        pytest.param("root_toml", id="tc_rc1_f09_ep_003_root_toml"),
        pytest.param("flat_yaml", id="tc_rc1_f09_ep_004_flat_yaml"),
        pytest.param("tasksupport_yaml", id="tc_rc1_f09_ep_005_tasksupport_yaml"),
        pytest.param("unsorted_keys", id="tc_rc1_f09_ep_008_unsorted_keys"),
    ],
)
def test_round_trip_keeps_effective_config__tc_rc1_f09_ep_001_005(tmp_path: Path, case: str) -> None:
    """TC-RC1-F09-EP-001..005: every file-based config source survives export -> import -> run."""
    # Given: a completed run whose config came from one supported file source
    root, data_root = _project(tmp_path, case)
    original = _run(root)
    original_label = (data_root / "structured" / "label.txt").read_text(encoding="utf-8")
    # When: the run is exported, imported into a fresh tree and run again there
    replay, target, manifest = _round_trip(tmp_path, _report_path(data_root, original))
    # Then: the config-dependent output and the config digest are both reproduced
    assert (target / "data" / "structured" / "label.txt").read_text(encoding="utf-8") == original_label
    assert replay["config_digest"] == original["config_digest"]
    assert manifest == {"schema_version": "1", "config_included": True, "config_digest": original["config_digest"]}


def test_reordered_config_file_still_exports__tc_d1_ep_007(tmp_path: Path) -> None:
    """TC-D1-EP-007: reordering keys in the config file does not make a run unexportable."""
    # Given: a completed run, after which the same keys are rewritten in another order
    root, data_root = _project(tmp_path, "unsorted_keys")
    original = _run(root)
    (root / "rdeconfig.yaml").write_text(
        "custom:\n  nested:\n    b: 2\n    y: 1\n  a: 2\n  label: configured\n  z: 1\n",
        encoding="utf-8",
    )
    archive = tmp_path / "archive.zip"
    # When: the run is exported
    result = _export(_report_path(data_root, original), archive)
    # Then: the reordered file still reproduces the run's digest
    assert result.exit_code == 0, result.output
    with zipfile.ZipFile(archive) as opened:
        assert json.loads(opened.read("repro_manifest.json"))["config_digest"] == original["config_digest"]


def test_run_config_override_round_trips_with_export_config__tc_rc1_f09_ep_006(tmp_path: Path) -> None:
    """TC-RC1-F09-EP-006: ``export --config`` recovers a ``run --config`` override."""
    # Given: a run that took its label from a run --config override file
    root, data_root = _project(tmp_path, "default")
    override = tmp_path / "override.yaml"
    override.write_text("custom:\n  label: overridden\n", encoding="utf-8")
    original = _run(root, "--config", str(override))
    # When: export receives the same override YAML, then the archive is replayed without it
    replay, target, manifest = _round_trip(tmp_path, _report_path(data_root, original), "--config", str(override))
    # Then: the override was baked into the archived config
    assert (target / "data" / "structured" / "label.txt").read_text(encoding="utf-8") == "overridden"
    assert replay["config_digest"] == original["config_digest"]
    assert manifest["config_digest"] == original["config_digest"]


def test_v1_callback_run_exports_its_entry_config__tc_rc1_f09_ep_007(tmp_path: Path) -> None:
    """TC-RC1-F09-EP-007: a v1 callback run (v1 loader config) round-trips with an equal rerun digest."""
    # Given: a v1 callback run through the CLI target form with no config file;
    # its v1-normalized config differs from what v2 discovery alone would yield
    root, data_root = _project(tmp_path, "default")
    with _cwd(root):
        result = CliRunner().invoke(app, ["run", LEGACY])
    assert result.exit_code == 0, result.output
    report_path = next(iter(sorted((data_root / "logs").glob("run_report_*.json"))))
    original_digest = json.loads(report_path.read_text(encoding="utf-8"))["config_digest"]
    assert compute_config_digest(load_config(root, data_root=data_root)) != original_digest
    # When: the run is exported, imported, and rerun there through both entries
    archive = tmp_path / "legacy.zip"
    exported = _export(report_path, archive)
    assert exported.exit_code == 0, exported.output
    target = tmp_path / "legacy_imported"
    imported = CliRunner().invoke(app, ["repro", "import", str(archive), str(target)])
    assert imported.exit_code == 0, imported.output
    (target / "data" / "temp").mkdir(parents=True, exist_ok=True)
    archived_reports = set((target / "data" / "logs").glob("run_report_*.json"))
    with _cwd(target):
        legacy_rerun = CliRunner().invoke(app, ["run", LEGACY])
    assert legacy_rerun.exit_code == 0, legacy_rerun.output
    (legacy_report,) = set((target / "data" / "logs").glob("run_report_*.json")) - archived_reports
    flow_rerun = _run(target)
    # Then: the manifest and both reruns carry the original run's config digest
    with zipfile.ZipFile(archive) as opened:
        assert json.loads(opened.read("repro_manifest.json"))["config_digest"] == original_digest
    assert json.loads(legacy_report.read_text(encoding="utf-8"))["config_digest"] == original_digest
    assert flow_rerun["config_digest"] == original_digest


def test_override_without_export_config_is_usage_error__tc_rc1_f09_neg_001(tmp_path: Path) -> None:
    """TC-RC1-F09-NEG-001: an unrecoverable override stops export and names --config."""
    # Given: a run whose label came from a run --config override
    root, data_root = _project(tmp_path, "default")
    override = tmp_path / "override.yaml"
    override.write_text("custom:\n  label: overridden\n", encoding="utf-8")
    original = _run(root, "--config", str(override))
    archive = tmp_path / "archive.zip"
    # When: export runs without the override
    result = _export(_report_path(data_root, original), archive)
    # Then: it is a usage error pointing at export --config, and no archive is left behind
    assert result.exit_code == 3, result.output
    assert "--config" in result.output
    assert "override" in result.output
    assert not archive.exists()


def test_export_config_that_does_not_match_is_usage_error__tc_rc1_f09_neg_002(tmp_path: Path) -> None:
    """TC-RC1-F09-NEG-002: a different override YAML does not reproduce the digest."""
    # Given: a run with one override, and a different override handed to export
    root, data_root = _project(tmp_path, "default")
    override = tmp_path / "override.yaml"
    override.write_text("custom:\n  label: overridden\n", encoding="utf-8")
    wrong = tmp_path / "wrong.yaml"
    wrong.write_text("custom:\n  label: something-else\n", encoding="utf-8")
    original = _run(root, "--config", str(override))
    archive = tmp_path / "archive.zip"
    # When: export is given the wrong override
    result = _export(_report_path(data_root, original), archive, "--config", str(wrong))
    # Then: export refuses rather than archiving a config the run did not use
    assert result.exit_code == 3, result.output
    assert not archive.exists()


def test_export_config_not_a_mapping_is_usage_error__tc_rc1_f09_neg_003(tmp_path: Path) -> None:
    """TC-RC1-F09-NEG-003: export --config is validated like run --config."""
    # Given: a plain run and an override file whose top level is a list
    root, data_root = _project(tmp_path, "default")
    original = _run(root)
    bad = tmp_path / "bad.yaml"
    bad.write_text("- not\n- a mapping\n", encoding="utf-8")
    # When: export receives it
    result = _export(_report_path(data_root, original), tmp_path / "archive.zip", "--config", str(bad))
    # Then: the run --config validation message and exit code apply
    assert result.exit_code == 3, result.output
    assert "top-level YAML mapping" in result.output


def test_export_config_missing_file_is_usage_error__tc_rc1_f09_neg_004(tmp_path: Path) -> None:
    """TC-RC1-F09-NEG-004: a missing export --config file is a usage error."""
    # Given: a plain run and a non-existent override path
    root, data_root = _project(tmp_path, "default")
    original = _run(root)
    # When: export receives the missing path
    result = _export(_report_path(data_root, original), tmp_path / "archive.zip", "--config", str(tmp_path / "missing.yaml"))
    # Then: it exits 3 naming the option
    assert result.exit_code == 3, result.output
    assert "--config" in result.output


def test_unreproducible_digest_is_usage_error__tc_rc1_f09_neg_005(tmp_path: Path) -> None:
    """TC-RC1-F09-NEG-005: a report digest that no discoverable config yields is refused."""
    # Given: a real run whose report digest is then replaced by an unrelated value
    root, data_root = _project(tmp_path, "root_yaml")
    original = _run(root)
    report_path = _report_path(data_root, original)
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    payload["config_digest"] = "sha256:" + "0" * 64
    report_path.write_text(json.dumps(payload), encoding="utf-8")
    archive = tmp_path / "archive.zip"
    # When: export runs
    result = _export(report_path, archive)
    # Then: it stops with a usage error and writes nothing
    assert result.exit_code == 3, result.output
    assert not archive.exists()


def test_broken_config_source_is_usage_error__tc_rc1_f09_neg_006(tmp_path: Path) -> None:
    """TC-RC1-F09-NEG-006: a config file that no longer loads is a usage error, not a crash."""
    # Given: a run whose root rdeconfig.yaml was replaced by invalid YAML afterwards
    root, data_root = _project(tmp_path, "root_yaml")
    original = _run(root)
    (root / "rdeconfig.yaml").write_text("custom: [unclosed\n", encoding="utf-8")
    archive = tmp_path / "archive.zip"
    # When: export runs
    result = _export(_report_path(data_root, original), archive)
    # Then: the digest cannot be reproduced, which is reported as exit 3
    assert result.exit_code == 3, result.output
    assert not archive.exists()


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        pytest.param("default", {}, id="tc_rc1_f09_bv_001_all_defaults"),
        pytest.param("root_yaml", {"custom": {"label": "configured"}}, id="tc_rc1_f09_bv_002_one_key"),
    ],
)
def test_archived_config_holds_only_non_default_values__tc_rc1_f09_bv_001_002(
    tmp_path: Path,
    case: str,
    expected: dict[str, Any],
) -> None:
    """TC-RC1-F09-BV-001/002: defaults are not written, so they are not marked as explicitly set."""
    # Given: a completed run
    root, data_root = _project(tmp_path, case)
    original = _run(root)
    archive = tmp_path / "archive.zip"
    # When: it is exported
    result = _export(_report_path(data_root, original), archive)
    # Then: the archive-root config holds exactly the non-default values
    assert result.exit_code == 0, result.output
    with zipfile.ZipFile(archive) as opened:
        assert yaml.safe_load(opened.read("rdeconfig.yaml")) == expected


def test_full_dump_is_archived_when_minimal_form_does_not_replay__tc_rc1_f09_bv_003(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-RC1-F09-BV-003: the digest is the contract, so the full dump backs up the minimal form."""
    # Given: a completed all-default run, and a replay check that rejects the minimal (empty) form
    root, data_root = _project(tmp_path, "default")
    original = _run(root)
    real_replays_to = repro_cmd._replays_to
    monkeypatch.setattr(repro_cmd, "_replays_to", lambda text, digest: text != "{}\n" and real_replays_to(text, digest))
    archive = tmp_path / "archive.zip"
    # When: it is exported
    result = _export(_report_path(data_root, original), archive)
    # Then: the archived config is the complete dump, which still reloads to the run's digest
    assert result.exit_code == 0, result.output
    with zipfile.ZipFile(archive) as opened:
        archived = yaml.safe_load(opened.read("rdeconfig.yaml"))
    assert archived["system"]["save_raw"] is not None
    replay_root = tmp_path / "replay"
    replay_root.mkdir()
    (replay_root / "rdeconfig.yaml").write_text(yaml.safe_dump(archived), encoding="utf-8")
    assert compute_config_digest(load_config(replay_root, data_root=replay_root / "data")) == original["config_digest"]


def test_unreplayable_effective_config_is_usage_error__tc_rc1_f09_neg_007(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-RC1-F09-NEG-007: export refuses to archive a config that would not reproduce the digest."""
    # Given: a completed run, and a replay check that no YAML form passes
    root, data_root = _project(tmp_path, "root_yaml")
    original = _run(root)
    monkeypatch.setattr(repro_cmd, "_replays_to", lambda text, digest: False)
    archive = tmp_path / "archive.zip"
    # When: it is exported
    result = _export(_report_path(data_root, original), archive)
    # Then: it is a usage error naming the digest, and no archive is written
    assert result.exit_code == 3, result.output
    assert original["config_digest"] in result.output
    assert not archive.exists()
