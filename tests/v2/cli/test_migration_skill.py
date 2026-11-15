"""Migration Skill comparator and conversion-safety checks (#672).

The documented commands themselves are executed from the Skill text in
tests/v2/docs/test_agent_skills.py (AS-04, AS-07).

EP/BV table (written before implementation)
| ID | Partition / boundary | Expected |
| MIG-002 | preview before opt-in | source unchanged, destination absent (AS-07) |
| MIG-003 | dynamic dispatcher | exit 0 alone is not success; TODO marker remains |
| MIG-004 | reused or nested destination | apply refuses with exit 3; no overwrite |
| MIG-006 | existing exercise work directory | refuse without touching its files |
| MIG-007 | dynamic callback as the worked example | exercise refuses to claim success |
| PAR-001 | equivalent JSON, different whitespace | invoice/metadata values equal |
| PAR-002 | unit changed | comparison fails |
| PAR-003 | variable rows reordered | comparison fails |
| PAR-004 | missing metadata, structured output or image | comparison fails |
| PAR-005 | binary bytes changed | comparison fails |
| PAR-006 | empty tile directory added | comparison fails |
| PAR-007 | job.failed added or changed | comparison fails |
| PAR-008 | empty, absent or symlinked data root | refuse to claim parity |
| PAR-009 | Runner log contents differ | allowed; the logs directory itself is compared |
| PAR-010 | boolean or float replacing an integer | comparison fails (scalar type kept) |
| PAR-011 | malformed/non-finite JSON or symlinked descendant | refuse invalid evidence |
| PAR-012 | user files named like Runner JSON or logs | compared byte for byte |
| PAR-013 | tile numbering 0001 / 9999 / 10000 | tile JSON and log rules apply |
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SKILL = ROOT / ".agents/skills/rdetoolkit-v1-migration"


def _comparator():
    spec = importlib.util.spec_from_file_location("migration_comparator", SKILL / "scripts/compare_artifacts.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tree(root: Path) -> None:
    for name in ("invoice", "meta", "structured", "main_image", "logs"):
        (root / name).mkdir(parents=True)
    (root / "invoice/invoice.json").write_text('{"basic": {"dataName": "sample"}}')
    (root / "meta/metadata.json").write_text(json.dumps({
        "constant": {"temperature": {"value": 25, "unit": "degC"}},
        "variable": [{"time": {"value": 1, "unit": "s"}}, {"time": {"value": 2, "unit": "s"}}],
    }))
    (root / "structured/table.csv").write_bytes(b"time,value\n1,2\n")
    (root / "main_image/image.png").write_bytes(b"image-bytes")


def test_comparison_accepts_json_whitespace_and_log_contents(tmp_path: Path) -> None:
    # Given: two output trees with equivalent invoice values and distinct logs
    baseline, candidate = tmp_path / "baseline", tmp_path / "candidate"
    _tree(baseline)
    shutil.copytree(baseline, candidate)
    (candidate / "invoice/invoice.json").write_text('{"basic":{"dataName":"sample"}}')
    (candidate / "logs/run-report.json").write_text("{}")
    # When: comparing the complete output contract
    differences = _comparator().compare(baseline, candidate)
    # Then: formatting and documented log contents do not create a false difference
    assert differences == []


@pytest.mark.parametrize("mutation", ["unit", "rows", "metadata", "structured", "image", "bytes", "directory", "job", "boolean", "float"])
def test_comparison_rejects_artifact_regressions(tmp_path: Path, mutation: str) -> None:
    # Given: matching representative artifacts with units and repeated rows
    baseline, candidate = tmp_path / "baseline", tmp_path / "candidate"
    _tree(baseline)
    shutil.copytree(baseline, candidate)
    # When: one externally observable artifact regresses
    meta = candidate / "meta/metadata.json"
    if mutation in {"unit", "rows", "boolean", "float"}:
        payload = json.loads(meta.read_text())
        if mutation == "unit":
            payload["constant"]["temperature"]["unit"] = "K"
        elif mutation in {"boolean", "float"}:
            payload["variable"][0]["time"]["value"] = True if mutation == "boolean" else 1.0
        else:
            payload["variable"].reverse()
        meta.write_text(json.dumps(payload))
    elif mutation in {"metadata", "structured", "image"}:
        candidate.joinpath({"metadata": "meta/metadata.json", "structured": "structured/table.csv", "image": "main_image/image.png"}[mutation]).unlink()
    elif mutation == "bytes":
        (candidate / "main_image/image.png").write_bytes(b"broken")
    elif mutation == "directory":
        (candidate / "divided/0001/meta").mkdir(parents=True)
    else:
        (candidate / "job.failed").write_text("ErrorCode=999\nmessage changed")
    # Then: the regression cannot be reported as parity
    assert _comparator().compare(baseline, candidate)


@pytest.mark.parametrize("kind", ["empty", "absent", "symlink"])
def test_comparison_refuses_invalid_baselines(tmp_path: Path, kind: str) -> None:
    # Given: an unusable baseline and a valid candidate tree
    baseline, candidate = tmp_path / "baseline", tmp_path / "candidate"
    _tree(candidate)
    if kind == "empty":
        baseline.mkdir()
    elif kind == "symlink":
        baseline.symlink_to(candidate, target_is_directory=True)
    # When / Then: missing evidence raises instead of passing two empty snapshots
    with pytest.raises(ValueError):
        _comparator().compare(baseline, candidate)


def test_structured_logs_are_artifacts(tmp_path: Path) -> None:
    # Given: a user artifact directory named logs below structured outputs
    baseline, candidate = tmp_path / "baseline", tmp_path / "candidate"
    _tree(baseline)
    (baseline / "structured/logs").mkdir()
    (baseline / "structured/logs/instrument.txt").write_text("measurement")
    shutil.copytree(baseline, candidate)
    # When: its content changes
    (candidate / "structured/logs/instrument.txt").write_text("corrupted")
    # Then: a log-like user name does not broaden Runner log exclusions
    assert _comparator().compare(baseline, candidate) == ["structured/logs/instrument.txt"]


@pytest.mark.parametrize("relative", ["raw/invoice.json", "inputdata/metadata.json", "structured/metadata.json"])
def test_json_named_user_files_keep_byte_contract(tmp_path: Path, relative: str) -> None:
    # Given: an instrument file whose name resembles a Runner JSON artifact.
    baseline, candidate = tmp_path / "baseline", tmp_path / "candidate"
    _tree(baseline)
    path = baseline / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"value": 1}\n')
    shutil.copytree(baseline, candidate)
    # When: its original bytes change without changing the parsed JSON value.
    (candidate / relative).write_text('{"value":1}')
    # Then: artifact-name coincidences do not weaken raw/structured byte parity.
    assert _comparator().compare(baseline, candidate) == [relative]


@pytest.mark.parametrize("relative", ["divided/0001/invoice/invoice.json", "divided/10000/meta/metadata.json"])
def test_tile_json_artifacts_allow_only_formatting_changes(tmp_path: Path, relative: str) -> None:
    # Given: the actual invoice or metadata artifact of a later tile.
    baseline, candidate = tmp_path / "baseline", tmp_path / "candidate"
    _tree(baseline)
    path = baseline / relative
    path.parent.mkdir(parents=True)
    path.write_text('{"value": 1}\n')
    shutil.copytree(baseline, candidate)
    # When: serialization whitespace changes within a recognized artifact path.
    (candidate / relative).write_text('{"value":1}')
    # Then: the documented semantic comparison also applies to divided tiles.
    assert _comparator().compare(baseline, candidate) == []


@pytest.mark.parametrize("entry", ["dynamic", "nested", "existing"])
def test_ambiguous_or_unsafe_source_never_implies_acceptance(tmp_path: Path, entry: str) -> None:
    from typer.testing import CliRunner
    from rdetoolkit.cli.app import app
    # Given: a dynamic dispatch or forbidden write destination
    source = tmp_path / "source"
    source.mkdir()
    legacy = ROOT / "tests/v2/cli/fixtures/migrate_corpus/case05_dynamic/main.py"
    shutil.copy2(legacy, source / "main.py")
    destination = source / "child" if entry == "nested" else tmp_path / "candidate"
    if entry == "existing":
        destination.mkdir()
    before = (source / "main.py").read_bytes()
    # When: executing the documented explicit apply with that problematic input
    result = CliRunner().invoke(app, ["migrate", "apply", str(source), "-o", str(destination), "--no-dry-run"])
    # Then: either refuse writing, or retain a blocking manual-review marker despite zero exit
    if entry == "dynamic":
        assert result.exit_code == 0
        assert "TODO(rdetoolkit-migrate)" in (destination / "main.py").read_text()
    else:
        assert result.exit_code == 3
        assert "Remediation:" in result.output
    assert (source / "main.py").read_bytes() == before


def test_comparator_command_reports_missing_evidence(tmp_path: Path) -> None:
    # Given: a baseline data root without its invoice evidence
    baseline, candidate = tmp_path / "baseline", tmp_path / "candidate"
    _tree(baseline)
    shutil.copytree(baseline, candidate)
    (baseline / "invoice/invoice.json").unlink()
    # When: running the comparator command
    result = subprocess.run([sys.executable, str(SKILL / "scripts/compare_artifacts.py"), str(baseline), str(candidate)], capture_output=True, text=True, check=False)
    # Then: exit 2 and a machine-readable refusal, distinct from a difference (exit 1)
    assert result.returncode == 2, result.stderr
    assert json.loads(result.stdout)["parity"] is False


@pytest.mark.parametrize("tile", ["0001", "9999", "10000"])
def test_tile_logs_only_exclude_contents(tmp_path: Path, tile: str) -> None:
    # Given: identical trees at the Runner's minimum-width tile numbering boundary
    baseline, candidate = tmp_path / "baseline", tmp_path / "candidate"
    _tree(baseline)
    (baseline / "divided" / tile / "logs").mkdir(parents=True)
    shutil.copytree(baseline, candidate)
    # When: the v2 run writes its extra report in that tile's log directory
    (candidate / "divided" / tile / "logs/report.json").write_text("{}")
    # Then: report content is excluded but removing the directory remains a difference
    assert _comparator().compare(baseline, candidate) == []
    shutil.rmtree(candidate / "divided" / tile / "logs")
    assert _comparator().compare(baseline, candidate) == [f"divided/{tile}/logs"]


@pytest.mark.parametrize("invalid", ["malformed", "nonfinite", "symlink"])
def test_comparison_rejects_unreadable_contract_evidence(tmp_path: Path, invalid: str) -> None:
    # Given: preserved output containing corrupt JSON or an external reference
    baseline, candidate = tmp_path / "baseline", tmp_path / "candidate"
    _tree(baseline)
    shutil.copytree(baseline, candidate)
    if invalid == "symlink":
        (baseline / "main_image/reference.png").symlink_to(candidate / "main_image/image.png")
    else:
        (baseline / "meta/metadata.json").write_text("{" if invalid == "malformed" else '{"value": NaN}')
    # When / Then: invalid evidence must never become a successful comparison
    with pytest.raises(ValueError):
        _comparator().compare(baseline, candidate)


def test_example_refuses_existing_work_directory(tmp_path: Path) -> None:
    # Given: an existing work directory containing a user's file
    work = tmp_path / "existing"
    work.mkdir()
    marker = work / "source.py"
    marker.write_text("preserve me")
    # When: the documented exercise is invoked with a reused destination
    result = subprocess.run([sys.executable, str(SKILL / "scripts/exercise_migration.py"), "--work-dir", str(work)], cwd=ROOT, capture_output=True, text=True)
    # Then: it fails without overwriting or adding any source files
    assert result.returncode != 0
    assert marker.read_text() == "preserve me"
    assert sorted(path.name for path in work.iterdir()) == ["source.py"]


def _exercise_module(monkeypatch):
    monkeypatch.syspath_prepend(str(SKILL / "scripts"))
    spec = importlib.util.spec_from_file_location("migration_exercise_tests", SKILL / "scripts/exercise_migration.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_exercise_rejects_ambiguous_example(tmp_path: Path, monkeypatch) -> None:
    # Given: the corpus's dynamic callback replaces the supposedly simple example
    module = _exercise_module(monkeypatch)
    skill = tmp_path / "skill"
    (skill / "examples").mkdir(parents=True)
    shutil.copy2(ROOT / "tests/v2/cli/fixtures/migrate_corpus/case05_dynamic/main.py", skill / "examples/legacy_callback.py")
    monkeypatch.setattr(module, "SKILL", skill)
    # When / Then: a zero-exit best-effort apply still cannot claim migration success
    with pytest.raises(AssertionError, match="manual migration"):
        module.exercise(tmp_path / "work")
    assert not (tmp_path / "work/summary.json").exists()