"""Post-invoke artifact stage for Session I6-1 (rulings #4 and #8b).

The v1 pipelines publish tile artifacts *after* the dataset callback returns:
raw/nonshared copies, thumbnails, the structured invoice copy, magic-variable
substitution and the feature description update, each behind its own config
gate (``processing/factories.py``). v2 only performed the raw and thumbnail
steps, and ``InvoiceService.apply_config`` had no caller at all.

Every test below runs the real Runner against a real fixture and observes real
files: no mock objects, no patched collaborators. The two ordering probes are
subclasses of the injectable artifact services that record filesystem state and
then delegate to the real implementation, so the observed behavior is the
production behavior.

EP table (config gates):
| TC | Flag | Value | Expected |
|----|------|-------|----------|
| TC-I6-1-EP-010 | ``save_raw`` | True | tile input appears in ``raw/`` |
| TC-I6-1-EP-011 | ``save_nonshared_raw`` | True | tile input appears in ``nonshared_raw/`` |
| TC-I6-1-EP-012 | ``save_thumbnail_image`` | True | main image copied to ``thumbnail/`` |
| TC-I6-1-EP-013 | ``save_invoice_to_structured`` | True | ``structured/invoice.json`` copied from ``invoice_org`` |
| TC-I6-1-EP-014 | ``magic_variable`` | True | ``${filename}`` replaced in the tile invoice |
| TC-I6-1-EP-015 | ``feature_description`` | True | ``_feature`` metadata appended to the description |
| TC-I6-1-EP-016 | ordering | all on | raw -> thumbnail -> invoice stage (v1 order) |
| TC-I6-1-EP-017 | failed tile | invoice usererr flow | raw digests equal the frozen v1 usererr snapshot |
| TC-I6-1-EP-018 | failed tile | multidatatile usererr flow | tile-0 raw digests equal the frozen snapshot |
| TC-I6-1-EP-019 | magic source | ``${metadata:constant:X}`` | resolved from the tile's metadata.json |
| TC-I6-1-EP-020 | magic source | ``${invoice:basic:X}`` | resolved from invoice_org, not the tile invoice |

BV / negative table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-I6-1-EV-020 | gate off | ``save_raw=False`` | ``raw/`` stays empty |
| TC-I6-1-EV-021 | gate off | ``save_nonshared_raw=False`` | ``nonshared_raw/`` stays empty |
| TC-I6-1-EV-022 | gate off | ``save_thumbnail_image=False`` | ``thumbnail/`` stays empty |
| TC-I6-1-EV-023 | gate off | ``save_invoice_to_structured=False`` | no ``structured/invoice.json`` |
| TC-I6-1-EV-024 | gate off | ``magic_variable=False`` | ``${filename}`` survives verbatim |
| TC-I6-1-EV-025 | gate off | ``feature_description=False`` | description unchanged |
| TC-I6-1-EV-026 | wrong source | structured copy | copies ``invoice_org``, not the tile invoice |
| TC-I6-1-EV-027 | I/O failure | blocked ``raw/`` copy | 3005 ArtifactPublicationFailed, never 3001 |
| TC-I6-1-EV-028 | I/O failure | blocked structured copy | 3006 InvoiceArtifactFailed, call log and stacktrace survive |
| TC-I6-1-EV-029 | invoice stage | ``StructuredError`` from magic | v1 ecode passthrough, not 3005/3006 |
| TC-I6-1-EV-030 | mode seam | handler selecting only ``description`` | structured and magic do not run |
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.core.flow import flow
from rdetoolkit.core.node import node
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.domain.artifacts import ImageArtifactService, RawArtifactService
from rdetoolkit.errors import ERROR_CATALOG
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.runner.executor import TileExecutor
from rdetoolkit.runner.invoker import InvokerRegistry
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import InputPaths, OutputContext
from tests.v2.contract.fixtures import _generate
from tests.v2.contract.observe import observe_v2_run

_ARTIFACT_PUBLICATION_FAILED = 3005
_INVOICE_ARTIFACT_FAILED = 3006
_NODE_EXECUTION_FAILED = 3001

_FEATURE_METADATA_DEF = {
    "temperature": {
        "name": {"ja": "温度", "en": "Temperature"},
        "schema": {"type": "number"},
        "unit": "C",
        "_feature": True,
    },
}


@node
def _write_tile_metadata(out: OutputContext) -> None:
    """Write the metadata.json the description updater consumes."""
    out.write_bytes(
        "meta",
        "metadata.json",
        json.dumps({"constant": {"temperature": {"value": 20.5}}, "variable": []}).encode("utf-8"),
    )


@node
def _write_main_image(out: OutputContext) -> None:
    """Write a main image so the thumbnail step has something to copy."""
    out.write_bytes("main_image", "plot.png", b"\x89PNG\r\n\x1a\n")


@flow
def _artifact_flow(out: OutputContext) -> None:
    """Produce the tile artifacts the post-invoke stage depends on."""
    _write_tile_metadata(out)
    _write_main_image(out)


#: Values a flow writes into its own tile invoice, so the tile invoice and the
#: run-level ``invoice_org`` disagree by the time the invoice stage runs.
_FLOW_WRITTEN_NAME = "written-by-the-flow"
_FIXTURE_OWNER_ID = "0" * 56
_FLOW_WRITTEN_OWNER_ID = "1" * 56


def _rewrite_tile_invoice(out: OutputContext, **fields: str) -> None:
    """Edit the tile invoice in place, as a user flow is free to do."""
    invoice_path = out.invoice / "invoice.json"
    invoice = json.loads(invoice_path.read_text(encoding="utf-8"))
    invoice["basic"].update(fields)
    invoice_path.write_text(json.dumps(invoice), encoding="utf-8")


@flow
def _tile_invoice_rewriting_flow(out: OutputContext) -> None:
    """Complete after giving the tile invoice a distinct data name."""
    _write_tile_metadata(out)
    _rewrite_tile_invoice(out, dataName=_FLOW_WRITTEN_NAME)


@flow
def _owner_id_rewriting_flow(out: OutputContext) -> None:
    """Complete after making the tile invoice disagree with the backup."""
    _write_tile_metadata(out)
    _rewrite_tile_invoice(
        out,
        dataName="${invoice:basic:dataOwnerId}",
        dataOwnerId=_FLOW_WRITTEN_OWNER_ID,
    )


def _config(**system: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "extended_mode": "invoice",
        "save_raw": False,
        "save_nonshared_raw": False,
        "save_thumbnail_image": False,
        "save_invoice_to_structured": False,
        "magic_variable": False,
        "feature_description": False,
    }
    base.update(system)
    return {"system": base}


def _prepare_root(tmp_path: Path, *, data_name: str = "seed") -> Path:
    """Materialize the invoice fixture with a feature-capable metadata-def."""
    root = tmp_path / "invoice"
    _generate.materialize_sut_case("invoice", root)
    data = root / "data"
    (data / "tasksupport" / "metadata-def.json").write_text(
        json.dumps(_FEATURE_METADATA_DEF),
        encoding="utf-8",
    )
    invoice_path = data / "invoice" / "invoice.json"
    invoice = json.loads(invoice_path.read_text(encoding="utf-8"))
    invoice["basic"]["dataName"] = data_name
    invoice["basic"]["description"] = ""
    invoice_path.write_text(json.dumps(invoice), encoding="utf-8")
    return root


def _prepare_multidatatile_root(tmp_path: Path, *, data_name: str) -> Path:
    """Materialize the MultiDataTile fixture, whose invoice_org is a real backup."""
    root = tmp_path / "multidatatile"
    _generate.materialize_sut_case("multidatatile", root)
    data = root / "data"
    (data / "tasksupport" / "metadata-def.json").write_text(
        json.dumps(_FEATURE_METADATA_DEF),
        encoding="utf-8",
    )
    invoice_path = data / "invoice" / "invoice.json"
    invoice = json.loads(invoice_path.read_text(encoding="utf-8"))
    invoice["basic"]["dataName"] = data_name
    invoice["basic"]["description"] = ""
    invoice_path.write_text(json.dumps(invoice), encoding="utf-8")
    return root


def _run_multidatatile(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    overrides: dict[str, Any],
    target: Any = None,
) -> RunReport:
    """Run a flow over the MultiDataTile fixture."""
    monkeypatch.chdir(root)
    runner = Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "temp",
    )
    return runner.run(target or _artifact_flow, **overrides)


def _run(root: Path, monkeypatch: pytest.MonkeyPatch, overrides: dict[str, Any], **kwargs: Any) -> RunReport:
    monkeypatch.chdir(root)
    runner = Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "temp",
        **kwargs,
    )
    return runner.run(_artifact_flow, **overrides)


def _tile_invoice(root: Path) -> dict[str, Any]:
    return json.loads((root / "data" / "invoice" / "invoice.json").read_text(encoding="utf-8"))


def _names(directory: Path) -> list[str]:
    return sorted(path.name for path in directory.iterdir())


def test_raw_copy_gate_publishes_the_tile_input__tc_i6_1_ep_010(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-I6-1-EP-010: save_raw publishes the tile input to raw/."""
    # Given: an invoice fixture with only save_raw enabled
    root = _prepare_root(tmp_path)

    # When: running the flow
    report = _run(root, monkeypatch, _config(save_raw=True))

    # Then: raw/ holds the input while nonshared_raw/ stays empty
    assert report.status == "success"
    assert _names(root / "data" / "raw") == ["invoice_input.txt"]
    assert _names(root / "data" / "nonshared_raw") == []


def test_nonshared_raw_gate_publishes_the_tile_input__tc_i6_1_ep_011(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-I6-1-EP-011: save_nonshared_raw publishes the tile input to nonshared_raw/."""
    # Given: an invoice fixture with only save_nonshared_raw enabled
    root = _prepare_root(tmp_path)

    # When: running the flow
    report = _run(root, monkeypatch, _config(save_nonshared_raw=True))

    # Then: nonshared_raw/ holds the input while raw/ stays empty
    assert report.status == "success"
    assert _names(root / "data" / "nonshared_raw") == ["invoice_input.txt"]
    assert _names(root / "data" / "raw") == []


def test_thumbnail_gate_copies_the_main_image__tc_i6_1_ep_012(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-I6-1-EP-012: save_thumbnail_image copies main_image/ into thumbnail/."""
    # Given: an invoice fixture whose flow writes a main image
    root = _prepare_root(tmp_path)

    # When: running with the thumbnail gate enabled
    report = _run(root, monkeypatch, _config(save_thumbnail_image=True))

    # Then: the image reached the thumbnail directory
    assert report.status == "success"
    assert _names(root / "data" / "thumbnail") == ["plot.png"]


def test_structured_gate_copies_the_invoice_org__tc_i6_1_ep_013(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-I6-1-EP-013: save_invoice_to_structured stores invoice.json under structured/."""
    # Given: an invoice fixture with the structured gate enabled
    root = _prepare_root(tmp_path)
    original = json.loads((root / "data" / "invoice" / "invoice.json").read_text(encoding="utf-8"))

    # When: running the flow
    report = _run(root, monkeypatch, _config(save_invoice_to_structured=True))

    # Then: the structured copy exists and matches the v1 source invoice
    assert report.status == "success"
    structured = root / "data" / "structured" / "invoice.json"
    assert json.loads(structured.read_text(encoding="utf-8")) == original


def test_magic_variable_gate_rewrites_the_tile_invoice__tc_i6_1_ep_014(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-I6-1-EP-014: magic_variable replaces ${filename} with the raw file name."""
    # Given: an invoice whose dataName is the magic variable
    root = _prepare_root(tmp_path, data_name="${filename}")

    # When: running with the magic-variable gate enabled
    report = _run(root, monkeypatch, _config(magic_variable=True))

    # Then: the tile invoice carries the input file name
    assert report.status == "success"
    assert _tile_invoice(root)["basic"]["dataName"] == "invoice_input.txt"


def test_description_gate_appends_feature_metadata__tc_i6_1_ep_015(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-I6-1-EP-015: feature_description transfers _feature metadata to the description."""
    # Given: a metadata definition marking temperature as a feature
    root = _prepare_root(tmp_path)

    # When: running with the description gate enabled
    report = _run(root, monkeypatch, _config(feature_description=True))

    # Then: the description quotes the feature value and unit
    assert report.status == "success"
    assert "20.5" in _tile_invoice(root)["basic"]["description"]


def test_post_invoke_runs_in_the_v1_order__tc_i6_1_ep_016(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-I6-1-EP-016: raw copy precedes thumbnails, which precede the invoice stage."""
    # Given: recording subclasses that still perform the real publication work
    root = _prepare_root(tmp_path)
    observed: list[tuple[str, bool, bool]] = []
    structured_invoice = root / "data" / "structured" / "invoice.json"
    raw_dir = root / "data" / "raw"

    class _RecordingRaw(RawArtifactService):
        def copy(self, source_files: tuple[Path, ...], **kwargs: Any) -> None:
            observed.append(("raw", any(raw_dir.iterdir()), structured_invoice.exists()))
            super().copy(source_files, **kwargs)

    class _RecordingImages(ImageArtifactService):
        def generate(self, **kwargs: Any) -> None:
            observed.append(("thumbnail", any(raw_dir.iterdir()), structured_invoice.exists()))
            super().generate(**kwargs)

    executor = TileExecutor(
        event_sink=_SilentSink(),
        flow_invoker=InvokerRegistry(),
        raw_artifact_service=_RecordingRaw(),
        image_artifact_service=_RecordingImages(),
    )

    # When: running the whole post-invoke stage with every gate enabled
    report = _run(
        root,
        monkeypatch,
        _config(
            save_raw=True,
            save_nonshared_raw=True,
            save_thumbnail_image=True,
            save_invoice_to_structured=True,
            magic_variable=True,
            feature_description=True,
        ),
        executor=executor,
    )

    # Then: raw ran first with nothing published, thumbnails ran with raw done,
    # and the invoice stage ran only after both
    assert report.status == "success"
    assert [step for step, _, _ in observed] == ["raw", "thumbnail"]
    assert observed[0] == ("raw", False, False)
    assert observed[1] == ("thumbnail", True, False)
    assert structured_invoice.exists()


def test_raw_gate_off_publishes_nothing__tc_i6_1_ev_020(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-I6-1-EV-020/021: both raw gates off leave both directories empty."""
    # Given: an invoice fixture with every gate disabled
    root = _prepare_root(tmp_path)

    # When: running the flow
    report = _run(root, monkeypatch, _config())

    # Then: neither raw directory received a copy
    assert report.status == "success"
    assert _names(root / "data" / "raw") == []
    assert _names(root / "data" / "nonshared_raw") == []


def test_thumbnail_gate_off_publishes_nothing__tc_i6_1_ev_022(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-I6-1-EV-022: save_thumbnail_image off leaves thumbnail/ empty."""
    # Given: a flow that wrote a main image but the gate is off
    root = _prepare_root(tmp_path)

    # When: running the flow
    report = _run(root, monkeypatch, _config(save_thumbnail_image=False))

    # Then: no thumbnail was produced
    assert report.status == "success"
    assert _names(root / "data" / "thumbnail") == []
    assert _names(root / "data" / "main_image") == ["plot.png"]


def test_structured_gate_off_writes_no_copy__tc_i6_1_ev_023(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-I6-1-EV-023: save_invoice_to_structured off writes no structured invoice."""
    # Given: an invoice fixture with the structured gate off
    root = _prepare_root(tmp_path)

    # When: running the flow
    report = _run(root, monkeypatch, _config(save_invoice_to_structured=False))

    # Then: structured/ has no invoice copy
    assert report.status == "success"
    assert not (root / "data" / "structured" / "invoice.json").exists()


def test_magic_gate_off_keeps_the_placeholder__tc_i6_1_ev_024(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-I6-1-EV-024: magic_variable off leaves ${filename} untouched."""
    # Given: an invoice whose dataName is the magic variable
    root = _prepare_root(tmp_path, data_name="${filename}")

    # When: running with the gate off
    report = _run(root, monkeypatch, _config(magic_variable=False))

    # Then: the placeholder survives verbatim
    assert report.status == "success"
    assert _tile_invoice(root)["basic"]["dataName"] == "${filename}"


def test_description_gate_off_keeps_the_description__tc_i6_1_ev_025(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-I6-1-EV-025: feature_description off leaves the description empty."""
    # Given: feature metadata available but the gate disabled
    root = _prepare_root(tmp_path)

    # When: running the flow
    report = _run(root, monkeypatch, _config(feature_description=False))

    # Then: the description was never touched
    assert report.status == "success"
    assert _tile_invoice(root)["basic"]["description"] == ""


def test_structured_copy_uses_invoice_org_not_the_tile_invoice__tc_i6_1_ev_026(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-I6-1-EV-026: the structured copy comes from invoice_org, as v1 does.

    ``prepare_tile`` writes the tile invoice as a byte copy of ``invoice_org``,
    so the two files are identical when the flow starts: a wrong copy source
    would be invisible unless the tile invoice changes first. The flow here
    edits its own tile invoice — something a user flow is free to do — which
    makes the source discriminating at the structured step.
    """
    # Given: a MultiDataTile fixture and a flow that rewrites its tile invoice
    root = _prepare_multidatatile_root(tmp_path, data_name="seed")

    # When: running with the structured gate enabled
    report = _run_multidatatile(
        root,
        monkeypatch,
        _config(save_invoice_to_structured=True, extended_mode="MultiDataTile"),
        target=_tile_invoice_rewriting_flow,
    )

    # Then: the two invoices really differ and structured holds the backup
    assert report.status == "success", report.error
    invoice_org = json.loads((root / "data" / "temp" / "invoice_org.json").read_text(encoding="utf-8"))
    tile_invoice = _tile_invoice(root)
    structured = json.loads((root / "data" / "structured" / "invoice.json").read_text(encoding="utf-8"))
    assert tile_invoice["basic"]["dataName"] == _FLOW_WRITTEN_NAME
    assert invoice_org["basic"]["dataName"] == "seed"
    assert structured == invoice_org
    assert structured != tile_invoice


def test_failed_tile_keeps_the_v1_raw_copies__tc_i6_1_ep_017(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-I6-1-EP-017: a user error still leaves the raw copies v1 makes.

    v1 runs FileCopier before DatasetRunner in every pipeline, so the frozen
    ``usererr`` observation records raw digests even though the callback
    raised. The expectation here is that frozen fixture, not a hand-written
    list.
    """
    # Given: the invoice fixture and its frozen v1 user-error observation
    root = tmp_path / "invoice"
    _generate.materialize_sut_case("invoice", root)
    expected = json.loads(
        (_generate.EXPECTED_ROOT / "invoice" / "usererr.json").read_text(encoding="utf-8"),
    )["observed"]["raw_sha256"]
    assert expected, "the frozen usererr snapshot must record raw digests"
    monkeypatch.chdir(root)
    runner = Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "temp",
    )

    # When: running a flow that fails the way the frozen v1 callback failed
    report = runner.run(_usererr_flow, **_config(save_raw=True, save_nonshared_raw=True))

    # Then: the run failed and the raw digests match the frozen observation
    assert report.status == "failed"
    assert observe_v2_run(root)["raw_sha256"] == expected


def test_failed_multidatatile_tile_keeps_the_v1_raw_copies__tc_i6_1_ep_018(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-I6-1-EP-018: the same holds for tile 0 of a multi-tile mode.

    v1 stops at tile 0 on a user error while the v2 flow entry continues
    (contracts.md §I6-0 recorded divergence), so only the tile-0 subset of the
    frozen digests is comparable.
    """
    # Given: the multidatatile fixture and its frozen tile-0 digests
    root = tmp_path / "multidatatile"
    _generate.materialize_sut_case("multidatatile", root)
    expected = json.loads(
        (_generate.EXPECTED_ROOT / "multidatatile" / "usererr.json").read_text(encoding="utf-8"),
    )["observed"]["raw_sha256"]
    assert expected, "the frozen usererr snapshot must record raw digests"
    monkeypatch.chdir(root)
    runner = Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "temp",
    )

    # When: running the failing flow over every tile
    report = runner.run(
        _usererr_flow,
        **_config(save_raw=True, save_nonshared_raw=True, extended_mode="MultiDataTile"),
    )

    # Then: tile 0's digests match v1 exactly
    assert report.status == "failed"
    actual = observe_v2_run(root)["raw_sha256"]
    tile_zero = {path: digest for path, digest in actual.items() if "divided" not in path}
    assert tile_zero == expected


def test_magic_variable_resolves_metadata_and_invoice_sources__tc_i6_1_ep_019(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-I6-1-EP-019: ${metadata:...} resolves from the tile's metadata.json.

    v1's VariableApplier passes ``dataset_paths``, which is the only way
    ``apply_magic_variable`` can read ``meta/metadata.json``.
    """
    # Given: an invoice whose dataName references a metadata constant
    root = _prepare_root(tmp_path, data_name="${metadata:constant:temperature}")

    # When: running with the magic gate enabled
    report = _run(root, monkeypatch, _config(magic_variable=True))

    # Then: the metadata value replaced the expression
    assert report.status == "success", report.error
    assert _tile_invoice(root)["basic"]["dataName"] == "20.5"


def test_magic_variable_resolves_from_the_invoice_backup__tc_i6_1_ep_020(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-I6-1-EP-020: ``${invoice:...}`` resolves from invoice_org, not the tile invoice.

    ``apply_magic_variable`` falls back to the invoice being edited when it is
    given no ``dataset_paths``, so the two files must disagree on the
    referenced field for this to discriminate. The flow rewrites the tile
    invoice's owner id, leaving the backup as the only source that still holds
    the fixture value.
    """
    # Given: a tile invoice whose owner id differs from the run-level backup
    root = _prepare_multidatatile_root(tmp_path, data_name="seed")

    # When: running with the magic gate enabled
    report = _run_multidatatile(
        root,
        monkeypatch,
        _config(magic_variable=True, extended_mode="MultiDataTile"),
        target=_owner_id_rewriting_flow,
    )

    # Then: the backup's owner id replaced the expression, not the tile's
    assert report.status == "success", report.error
    invoice_org = json.loads((root / "data" / "temp" / "invoice_org.json").read_text(encoding="utf-8"))
    assert invoice_org["basic"]["dataOwnerId"] == _FIXTURE_OWNER_ID
    assert _FLOW_WRITTEN_OWNER_ID != _FIXTURE_OWNER_ID
    assert _tile_invoice(root)["basic"]["dataName"] == _FIXTURE_OWNER_ID


class _SilentSink:
    """Minimal event sink used where events are not under test."""

    def open(self, run_id: str) -> None:
        """Ignore the run-open boundary."""

    def emit(self, event: Any) -> None:
        """Ignore emitted events."""

    def close(self) -> None:
        """Ignore the run-close boundary."""


def _block_copy_destination(destination: Path) -> None:
    """Make ``shutil.copy2`` fail on ``destination`` with a real I/O error.

    ``copy2`` joins the source basename once when the destination is a
    directory, so nesting a second directory of the same name makes the final
    open fail with ``IsADirectoryError``. A read-only parent directory is not
    used because ``root`` can write into a mode ``0o500`` directory, which
    would make the test pass vacuously in a root container.
    """
    (destination / destination.name).mkdir(parents=True, exist_ok=True)


def _break_structured_destination(root: Path) -> None:
    """Block the structured invoice copy with a real filesystem error."""
    _block_copy_destination(root / "data" / "structured" / "invoice.json")


def _break_raw_destination(root: Path) -> None:
    """Block the raw copy of the fixture input with a real filesystem error."""
    _block_copy_destination(root / "data" / "raw" / "invoice_input.txt")


@flow
def _usererr_flow(paths: InputPaths) -> None:
    """Fail the tile the way the frozen v1 callback oracle fails."""
    assert paths.inputdata.is_dir()
    raise StructuredError("contract flow failed", ecode=999)


@flow
def _magic_failure_flow(out: OutputContext) -> None:
    """Complete normally; the invoice stage then fails on a magic variable."""
    _write_tile_metadata(out)


def test_raw_publication_failure_is_a_framework_error__tc_i6_1_ev_027(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-I6-1-EV-027: a raw copy I/O failure is 3005, never 3001."""
    # Given: a raw destination that cannot receive the tile input
    root = _prepare_root(tmp_path)
    _break_raw_destination(root)
    monkeypatch.chdir(root)
    runner = Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "temp",
    )

    # When: running with the raw gate enabled
    report = runner.run(_artifact_flow, **_config(save_raw=True))

    # Then: the failure is attributed to the framework's publication stage
    assert report.status == "failed"
    assert report.error is not None
    assert report.error["code"] == _ARTIFACT_PUBLICATION_FAILED
    assert report.error["code"] != _NODE_EXECUTION_FAILED
    assert report.error["name"] == ERROR_CATALOG[_ARTIFACT_PUBLICATION_FAILED].name
    job_failed = (root / "data" / "job.failed").read_text(encoding="utf-8")
    assert job_failed.splitlines()[0] == f"ErrorCode={_ARTIFACT_PUBLICATION_FAILED}"


def test_invoice_stage_failure_keeps_execution_evidence__tc_i6_1_ev_028(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-I6-1-EV-028: an invoice-stage failure is 3006 and keeps the call log."""
    # Given: a structured destination that cannot receive the copy
    root = _prepare_root(tmp_path)
    _break_structured_destination(root)
    monkeypatch.chdir(root)
    runner = Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "temp",
    )

    # When: running with the structured gate enabled
    report = runner.run(_artifact_flow, **_config(save_invoice_to_structured=True))

    # Then: the invoice stage owns the failure and the evidence survives
    assert [iteration["status"] for iteration in report.iterations] == ["failed"]
    iteration = report.iterations[0]
    assert iteration["node_calls"]
    assert iteration["stacktrace"]
    assert iteration["error"]["code"] == _INVOICE_ARTIFACT_FAILED
    assert iteration["error"]["code"] != _ARTIFACT_PUBLICATION_FAILED
    assert iteration["error"]["name"] == ERROR_CATALOG[_INVOICE_ARTIFACT_FAILED].name


def test_invoice_stage_structured_error_passes_through__tc_i6_1_ev_029(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-I6-1-EV-029: a StructuredError from the invoice stage keeps its ecode.

    v1 surfaced these verbatim through ``catch_exception_with_message``, so the
    I6-0 passthrough applies instead of a framework code.
    """
    # Given: a magic variable that cannot resolve, which v1 reports as ecode 1
    root = _prepare_root(tmp_path, data_name="${metadata:constant:missing_key}")
    monkeypatch.chdir(root)
    runner = Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "temp",
    )

    # When: running with the magic gate enabled
    report = runner.run(_magic_failure_flow, **_config(magic_variable=True))

    # Then: the user-facing StructuredError code is published, not 3005/3006
    assert report.status == "failed"
    assert report.error is not None
    assert report.error["code"] not in {_ARTIFACT_PUBLICATION_FAILED, _INVOICE_ARTIFACT_FAILED}
    job_failed = (root / "data" / "job.failed").read_text(encoding="utf-8")
    assert job_failed.splitlines()[0] == f"ErrorCode={report.error['code']}"


def test_mode_selected_steps_skip_the_omitted_ones__tc_i6_1_ev_030(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-I6-1-EV-030: a handler-selected sequence omits structured and magic.

    Updated in Session I-REVIEW-A (ruling #5): the seam is an ordered
    ``artifact_stage_order`` instead of a ``frozenset``, because review R3
    proved the order is observable when a stage fails.
    """
    # Given: a handler that declares only the description step
    from rdetoolkit.modes.install import install_default_handlers
    from rdetoolkit.modes.registry import clear, register
    from rdetoolkit.runner.mode_resolver import ModeKind
    from rdetoolkit.runner.planner import create_common_tiles

    class _DescriptionOnlyHandler:
        kind = ModeKind.invoice

        def create_tiles(self, context: Any) -> Any:
            return create_common_tiles(self.kind, context)

        def artifact_stage_order(self, plan: Any) -> tuple[str, ...]:
            _ = plan
            return ("description",)

    root = _prepare_root(tmp_path, data_name="${filename}")
    monkeypatch.chdir(root)
    runner = Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "temp",
    )
    register(ModeKind.invoice, _DescriptionOnlyHandler())

    # When: running with every invoice gate enabled
    try:
        report = runner.run(
            _artifact_flow,
            **_config(save_invoice_to_structured=True, magic_variable=True, feature_description=True),
        )
    finally:
        # install_default_handlers keeps an already-registered handler, so the
        # registry has to be cleared before the built-ins can come back.
        clear()
        install_default_handlers()

    # Then: only the selected step produced its effect
    assert report.status == "success", report.error
    assert not (root / "data" / "structured" / "invoice.json").exists()
    assert _tile_invoice(root)["basic"]["dataName"] == "${filename}"
    assert "20.5" in _tile_invoice(root)["basic"]["description"]
