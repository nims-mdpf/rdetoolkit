"""Issue #525: SmartTable runs keep the original invoice readable as ``invoice_org``.

SmartTable's tile 0 writes its row-merged invoice to ``data/invoice/invoice.json``,
which used to be the run's ``invoice_org`` too, so no tile could read the invoice
the run started from. SmartTable now backs it up to ``data/temp/invoice_org.json``
like ExcelInvoice does.

EP table:

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| ``workflows.run(flow=...)`` | SmartTable, three rows | every tile reads the original invoice from the backup | TC-525-EP-001 |
| ``workflows.run(custom_dataset_function=...)`` | SmartTable, three rows | ``resource_paths.invoice_org`` is the backup holding the original | TC-525-EP-002 |

BV table:

| API | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| ``workflows.run(flow=...)`` | the tile prepared after ``data/invoice/invoice.json`` is overwritten | still reads the original | TC-525-EP-001 |
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit import flow, workflows
from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath
from rdetoolkit.types import InputPaths, OutputContext
from tests.v2.contract.fixtures import _generate

_CONFIG = {"system": {"save_thumbnail_image": False}}


def _materialize(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    _generate.materialize_sut_case("smarttable", tmp_path)
    monkeypatch.chdir(tmp_path)
    original: dict[str, Any] = json.loads((tmp_path / "data" / "invoice" / "invoice.json").read_text(encoding="utf-8"))
    return original


def test_flow_tiles_read_the_original_invoice_from_the_backup__tc_525_ep_001(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-525-EP-001: ``paths.invoice_org`` is the untouched backup in every tile."""
    # Given: a three-row SmartTable run whose tile 0 overwrites data/invoice/invoice.json
    original = _materialize(tmp_path, monkeypatch)
    seen: list[tuple[Path, dict[str, Any]]] = []

    @flow
    def pipeline(paths: InputPaths, out: OutputContext) -> None:
        assert paths.invoice_org is not None
        seen.append((paths.invoice_org, json.loads(paths.invoice_org.read_text(encoding="utf-8"))))

    # When: the v2 flow entry runs every tile
    report = workflows.run(flow=pipeline, config=_CONFIG)

    # Then: each tile reads the original invoice from data/temp/invoice_org.json
    assert report.status == "success", report.error
    assert len(seen) == 3
    backup = tmp_path / "data" / "temp" / "invoice_org.json"
    assert all(source.resolve() == backup for source, _ in seen)
    assert all(content == original for _, content in seen)
    # And: tile 0's invoice really was overwritten, so the backup is what kept the original
    assert json.loads((tmp_path / "data" / "invoice" / "invoice.json").read_text(encoding="utf-8")) != original


def test_callback_receives_the_backup_as_invoice_org__tc_525_ep_002(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-525-EP-002: the v1 callback's ``invoice_org`` holds the original invoice."""
    # Given: the same SmartTable run driven through the v1 callback entry
    original = _materialize(tmp_path, monkeypatch)
    seen: list[tuple[Path, dict[str, Any]]] = []

    def callback(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath) -> None:
        _ = srcpaths
        seen.append((resource_paths.invoice_org, json.loads(resource_paths.invoice_org.read_text(encoding="utf-8"))))

    # When: the public callback entry runs
    result = workflows.run(custom_dataset_function=callback, config=_CONFIG)

    # Then: every invocation sees data/temp/invoice_org.json with the original content
    assert result
    assert len(seen) == 3
    assert all(Path(source) == Path("data/temp/invoice_org.json") for source, _ in seen)
    assert all(content == original for _, content in seen)
