"""Issue #783: a plain exception from a v1 dataset callback names the callback.

The v1 callback entry records no node call of its own, so the 3001 catalogue
wording ("Node execution failed for call unknown", "the call-log entry for the
failing call") pointed the template author at things that do not exist. The
code stays 3001; only the message names the callback instead.

| API | Partition | Input | Expected | Test ID |
|-----|-----------|-------|----------|---------|
| ``workflows.run`` (invoice) | EP invalid | callback raises ``zipfile.BadZipFile`` | 3001, message names the callback and keeps ``str(exc)`` | TC-783-001 |
| ``workflows.run`` (MultiDataTile) | EP invalid | callback raises ``ValueError`` | same wording on the MultiDataTile entry | TC-783-002 |
| ``workflows.run`` (invoice) | EP valid | callback raises ``StructuredError`` | its own code and message (v1 passthrough) | TC-783-003 |
| ``workflows.run`` (invoice) | EP invalid | a node called by the callback fails | 3001 naming the failed call id (unchanged) | TC-783-004 |
"""

from __future__ import annotations

import json
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit import node, workflows
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.models.config import Config, MultiDataTileSettings, SystemSettings

_MODULE = __name__
_REMEDIATION = (
    "Remediation: Inspect the chained original exception (__cause__); raise StructuredError "
    "(or ProcessingError) in the callback to choose the code and message."
)


def _seed(data_root: Path) -> None:
    """Create a valid one-tile invoice-mode input tree."""
    for dirname in ("inputdata", "invoice", "tasksupport"):
        (data_root / dirname).mkdir(parents=True, exist_ok=True)
    (data_root / "inputdata" / "sample.txt").write_text("input", encoding="utf-8")
    invoice = {
        "datasetId": "issue-783",
        "basic": {"dateSubmitted": "2026-11-21", "dataOwnerId": "0" * 56, "dataName": "issue-783"},
    }
    (data_root / "invoice" / "invoice.json").write_text(json.dumps(invoice), encoding="utf-8")
    (data_root / "tasksupport" / "invoice.schema.json").write_text('{"properties": {}}', encoding="utf-8")
    (data_root / "tasksupport" / "metadata-def.json").write_text('{"constant": {}, "variable": []}', encoding="utf-8")


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Return a project root holding a valid one-tile input tree, as the cwd."""
    _seed(tmp_path / "data")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _run_v1(callback: Callable[..., Any], config: Config | None = None) -> int:
    try:
        workflows.run(custom_dataset_function=callback, config=config)
    except SystemExit as error:
        return int(error.code or 0)
    return 0


def _job_failed(root: Path) -> str:
    return (root / "data" / "job.failed").read_text(encoding="utf-8")


def _broken_zip(srcpaths: Any, resource_paths: Any) -> None:
    del srcpaths, resource_paths
    msg = "File is not a zip file"
    raise zipfile.BadZipFile(msg)


def _value_error(srcpaths: Any, resource_paths: Any) -> None:
    del srcpaths, resource_paths
    msg = "bad tile"
    raise ValueError(msg)


def _structured(srcpaths: Any, resource_paths: Any) -> None:
    del srcpaths, resource_paths
    msg = "template says no"
    raise StructuredError(msg, ecode=42)


@node(id="tests.v2.runner.issue783.failing_node")
def _failing_node(value: int) -> int:
    msg = f"node rejected {value}"
    raise RuntimeError(msg)


def _calls_failing_node(srcpaths: Any, resource_paths: Any) -> None:
    del srcpaths, resource_paths
    _failing_node(1)


def test_plain_exception_names_the_callback__tc_783_001(project: Path) -> None:
    """TC-783-001: invoice mode, plain exception -> 3001 naming the callback."""
    # Given: an unchanged v1 template whose callback hits a broken upload
    # When: the v1 entry runs it
    code = _run_v1(_broken_zip)

    # Then: code 3001, the callback named, the original text kept, no node wording
    assert code == 1
    assert _job_failed(project) == (
        "ErrorCode=3001\n"
        f"ErrorMessage=Dataset callback {_MODULE}._broken_zip failed (BadZipFile): "
        f"File is not a zip file {_REMEDIATION}\n"
    )
    assert "call unknown" not in _job_failed(project)


def test_multidatatile_plain_exception_names_the_callback__tc_783_002(project: Path) -> None:
    """TC-783-002: MultiDataTile mode uses the same callback wording."""
    # Given: a MultiDataTile run whose callback fails on its tile
    config = Config(
        system=SystemSettings(extended_mode="MultiDataTile"),
        multidata_tile=MultiDataTileSettings(ignore_errors=False),
    )

    # When: the v1 entry runs it
    code = _run_v1(_value_error, config)

    # Then: the job.failed message names the callback
    assert code == 1
    assert _job_failed(project) == (
        "ErrorCode=3001\n"
        f"ErrorMessage=Dataset callback {_MODULE}._value_error failed (ValueError): bad tile {_REMEDIATION}\n"
    )


def test_structured_error_passes_through__tc_783_003(project: Path) -> None:
    """TC-783-003: a StructuredError keeps its own code and message."""
    # Given / When: the callback raises StructuredError(ecode=42)
    code = _run_v1(_structured)

    # Then: the v1 passthrough is unchanged
    assert code == 1
    assert _job_failed(project) == "ErrorCode=42\nErrorMessage=template says no\n"


def test_failed_node_inside_callback_names_the_call__tc_783_004(project: Path) -> None:
    """TC-783-004: a node failing inside the callback still names its call id."""
    # Given / When: the callback calls a node that raises
    code = _run_v1(_calls_failing_node)

    # Then: the node wording with a real call id, not the callback wording
    assert code == 1
    text = _job_failed(project)
    assert text.startswith("ErrorCode=3001\nErrorMessage=Node execution failed for call ")
    assert "call unknown" not in text
    assert "node rejected 1" in text
    assert "Dataset callback" not in text
