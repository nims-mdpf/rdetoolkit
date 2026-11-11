"""GA590 EP/BV: testing helpers for end-to-end flow tests with real RDE material.

| API | Partition / boundary | Expected | Test ID |
|-----|----------------------|----------|---------|
| ``run_flow`` | ``fixture_dir`` only | synthetic temporary tree (unchanged) | GA590-TEST-EP-1 |
| ``run_flow`` | ``data_root=`` | real invoice/metadata-def used, tree kept | GA590-TEST-EP-2 |
| ``run_flow`` | ``data_root=`` failing flow | job.failed kept for inspection | GA590-TEST-EP-3 |
| ``run_flow`` | relative ``data_root`` | resolved, caller cwd restored | GA590-TEST-EP-4 |
| ``run_flow`` | both / neither source | ValueError | GA590-TEST-BV-1 |
| ``run_flow`` | ``data_root`` missing / file | FileNotFoundError / NotADirectoryError | GA590-TEST-BV-2 |
| ``make_input_paths`` | default | ``invoice_org`` = ``invoice/invoice.json`` like the Runner | GA590-TEST-EP-5 |
| ``make_input_paths`` | explicit ``invoice_org`` | used verbatim | GA590-TEST-EP-5 |
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from rdetoolkit import flow
from rdetoolkit.testing import make_input_paths, run_flow
from rdetoolkit.types import InputPaths, InvoiceData, OutputContext

_INVOICE = {
    "datasetId": "real-dataset",
    "basic": {"dateSubmitted": "2026-11-10", "dataOwnerId": "1" * 56, "dataName": "real sample"},
    "custom": {"temperature": 25.0},
}


def _real_data_root(root: Path) -> Path:
    (root / "inputdata").mkdir(parents=True)
    (root / "inputdata" / "sample.txt").write_text("measured", encoding="utf-8")
    (root / "invoice").mkdir()
    (root / "invoice" / "invoice.json").write_text(json.dumps(_INVOICE), encoding="utf-8")
    (root / "tasksupport").mkdir()
    schema = {
        "$id": "https://rde.nims.go.jp/rde/dataset-templates/ga590/invoice.schema.json",
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["custom"],
        "properties": {
            "custom": {
                "type": "object",
                "label": {"ja": "固有情報", "en": "Custom"},
                "required": ["temperature"],
                "properties": {"temperature": {"type": "number", "label": {"ja": "温度", "en": "temperature"}}},
            },
        },
    }
    (root / "tasksupport" / "invoice.schema.json").write_text(json.dumps(schema), encoding="utf-8")
    metadef = {"temperature": {"schema": {"type": "number"}, "name": {"ja": "温度", "en": "temperature"}}}
    (root / "tasksupport" / "metadata-def.json").write_text(json.dumps(metadef), encoding="utf-8")
    return root


@flow(id="tests.ga590.real_material")
def _real_material(paths: InputPaths, invoice: InvoiceData, out: OutputContext) -> None:
    from rdetoolkit.nodes import build_meta, save_meta

    metadata = build_meta(invoice.get_custom_fields(), paths.tasksupport / "metadata-def.json")
    save_meta(metadata, out)
    (out.struct / "dataset.txt").write_text(str(invoice.raw["datasetId"]), encoding="utf-8")


@flow(id="tests.ga590.failing")
def _failing(paths: InputPaths) -> None:
    msg = "boom"
    raise ValueError(msg)


def test_fixture_dir_mode_is_unchanged__ga590_test_ep_1(tmp_path: Path) -> None:
    """GA590-TEST-EP-1: the fixture form still runs on a synthetic temporary tree."""
    # Given: a fixture directory with one input file
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    (fixture / "sample.txt").write_text("x", encoding="utf-8")
    seen: list[Path] = []

    @flow(id="tests.ga590.fixture")
    def pipeline(paths: InputPaths) -> None:
        seen.append(Path(paths.inputdata).resolve())

    # When: running through the fixture form
    report = run_flow(pipeline, fixture)
    # Then: it succeeds, and the temporary tree is gone afterwards
    assert report.status == "success"
    assert seen and not seen[0].exists()
    assert sorted(path.name for path in fixture.iterdir()) == ["sample.txt"]


def test_data_root_uses_real_material_and_keeps_tree__ga590_test_ep_2(tmp_path: Path) -> None:
    """GA590-TEST-EP-2: a full data root is used as-is and its outputs are kept."""
    # Given: a real invoice, schema and metadata definition
    root = _real_data_root(tmp_path / "data")
    # When: running the flow on that data root
    report = run_flow(_real_material, data_root=root)
    # Then: the real invoice and metadata-def were used, and the output tree remains
    assert report.status == "success", report.error
    assert (root / "structured" / "dataset.txt").read_text(encoding="utf-8") == "real-dataset"
    metadata = json.loads((root / "meta" / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["constant"] == {"temperature": {"value": 25.0}}
    assert json.loads((root / "invoice" / "invoice.json").read_text(encoding="utf-8"))["datasetId"] == "real-dataset"
    assert not (root / "job.failed").exists()


def test_data_root_failure_keeps_job_failed__ga590_test_ep_3(tmp_path: Path) -> None:
    """GA590-TEST-EP-3: a failing run leaves job.failed in the kept data root."""
    # Given: a real data root
    root = _real_data_root(tmp_path / "data")
    # When: the flow fails
    report = run_flow(_failing, data_root=root)
    # Then: the platform marker can be inspected after the call
    assert report.status == "failed"
    assert (root / "job.failed").read_text(encoding="utf-8").startswith("ErrorCode=")


def test_relative_data_root_restores_cwd__ga590_test_ep_4(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA590-TEST-EP-4: a relative data root is resolved against the caller's cwd."""
    # Given: a data root addressed relative to the working directory
    _real_data_root(tmp_path / "data")
    monkeypatch.chdir(tmp_path)
    # When: running with the relative spelling
    report = run_flow(_real_material, data_root=Path("data"))
    # Then: the run succeeds there and the caller's cwd is unchanged
    assert report.status == "success", report.error
    assert (tmp_path / "data" / "structured" / "dataset.txt").is_file()
    assert Path(os.getcwd()) == tmp_path


@pytest.mark.parametrize("both", [True, False])
def test_exactly_one_source_is_required__ga590_test_bv_1(tmp_path: Path, both: bool) -> None:
    """GA590-TEST-BV-1: fixture_dir and data_root are mutually exclusive and one is required."""
    # Given: either both sources or none
    root = _real_data_root(tmp_path / "data")
    # When / Then: the ambiguous call is rejected
    with pytest.raises(ValueError, match="fixture_dir|data_root"):
        if both:
            run_flow(_real_material, tmp_path / "fixture", data_root=root)
        else:
            run_flow(_real_material)


def test_data_root_must_be_an_existing_directory__ga590_test_bv_2(tmp_path: Path) -> None:
    """GA590-TEST-BV-2: a missing or non-directory data root fails before running."""
    # Given: a missing path and a regular file
    missing = tmp_path / "missing"
    regular = tmp_path / "file"
    regular.write_text("", encoding="utf-8")
    # When / Then: each is rejected with the matching error, creating nothing
    with pytest.raises(FileNotFoundError):
        run_flow(_real_material, data_root=missing)
    with pytest.raises(NotADirectoryError):
        run_flow(_real_material, data_root=regular)
    assert not missing.exists()


def test_make_input_paths_defaults_invoice_org__ga590_test_ep_5(tmp_path: Path) -> None:
    """GA590-TEST-EP-5: invoice_org defaults to the input invoice like non-backup Runner modes."""
    # Given / When: building input paths with and without an explicit source
    default = make_input_paths(tmp_path / "default")
    explicit = make_input_paths(tmp_path / "explicit", invoice_org=tmp_path / "temp" / "invoice_org.json")
    # Then: the default points at invoice/invoice.json and the explicit value is kept
    assert default.invoice_org == default.invoice / "invoice.json"
    assert explicit.invoice_org == tmp_path / "temp" / "invoice_org.json"
