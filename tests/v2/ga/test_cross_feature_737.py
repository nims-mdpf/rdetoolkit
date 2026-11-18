r"""QA-02 (#737): cross-feature and negative-case release gate for modes, magic and graph.

Each test drives the unified ``Runner`` end to end on a committed contract input
and compares against values that do not come from the code under test: the
frozen v1 observations (``tests/v2/contract/fixtures/expected/v1``, locked by
``parity_oracle_lock.json``), literals derived by hand from the inputs below, or
the error catalog numbers. ``test_parity_oracles_737.py`` maps every test to its
row in the v1-unchanged / v2-intentional contract tables.

Failing runs are inspected for what they leave behind: ``job.failed``, the
diagnostics sidecar, tile directories, untouched source invoices and the absence
of temporary publication files.

EP table:

| Feature | Partition | Entry | Expected | Test ID |
| --- | --- | --- | --- | --- |
| magic | ``${metadata:constant}`` + ``${invoice:basic}``, zero raw files | flow | expanded literal ``run-S-01-2026-07-15`` | QA02-MAGIC-NORAW-FLOW |
| magic | same template, zero raw files, ``magic_variable: true`` | callback | template kept verbatim (v1 rawfiles gate) | QA02-MAGIC-NORAW-CB |
| magic | ``${filename}``, zero raw files | flow | 4010, invoice untouched, job.failed + sidecar | QA02-MAGIC-NORAW-FILENAME |
| magic | source key present on tile 0 only, ``fail_fast`` | flow | tile 0 published, tile 1 invoice untouched, 4010 | QA02-MAGIC-PARTIAL-FAILFAST |
| magic | same, ``continue`` | flow | ``partial``, same artifacts, no job.failed | QA02-MAGIC-PARTIAL-CONTINUE |
| magic | malformed expressions (extra segment, ``filename:typo``, ``${}``, unclosed) | flow | 4009, invoice untouched | QA02-MAGIC-MALFORMED-* |
| modes | SmartTable table + ExcelInvoice workbook | flow | 1007 before any tile directory | QA02-MODE-MIXED-FLOW |
| modes | same mixed input | callback | v1 precedence: frozen v1 SmartTable artifacts | QA02-MODE-MIXED-CB |
| modes | ``multidatatile`` / ``MultiDataTile`` | flow | frozen v1 MultiDataTile tile count, not invoice | QA02-MODE-ALIAS-* |
| modes | unknown spellings | flow | 1002 listing valid names, no tile output | QA02-MODE-INVALID-* |
| graph | case-colliding labels ``Voltage`` / ``voltage`` on two tiles | flow, callback | two distinct figures per tile, same names on every tile | QA02-GRAPH-DUPLABEL-* |
| graph | ``mode="Overlay"`` | flow | 3001 naming the invalid mode, no figure anywhere | QA02-GRAPH-INVALID-MODE |
| runner | a second run while another owns the root | flow, callback | 3008 ``RunRootBusy``, root byte-identical; holder = frozen v1 | QA02-CONC-{FLOW,CB}-* |
| runner | two runs released together (5 attempts per mode) | flow | each succeeds or gets 3008, never another failure; frozen v1 artifacts | QA02-CONC-RACE-* |

BV table:

| Feature | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| magic | 0 raw files (filename needs exactly 1) | 4010 ``filename_not_unique`` | QA02-MAGIC-NORAW-FILENAME |
| magic | failure on the last of 2 tiles | the earlier tile stays published | QA02-MAGIC-PARTIAL-* |
| modes | 2 special files (1 is the maximum) | 1007 | QA02-MODE-MIXED-FLOW |
| graph | 2 series sharing one stem | suffixes ``_s000`` / ``_s001`` | QA02-GRAPH-DUPLABEL-* |
| runner | 2 simultaneous runs (barrier) | at most one refused, at least one succeeds | QA02-CONC-RACE-* |
"""

from __future__ import annotations

import hashlib
import json
import shutil
import threading
import warnings
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.api.request import FlowTarget, LegacyCallbackTarget, RunRequest
from rdetoolkit.core.flow import flow
from rdetoolkit.core.node import node
from rdetoolkit.graph.api.csv2graph import csv2graph
from rdetoolkit.graph.exceptions import GraphUserWarning
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import IterationInfo, OutputContext
from tests.v2.contract.fixtures import _generate
from tests.v2.contract.frozen import frozen_observed
from tests.v2.contract.observe import observe_v2_run, parity_pair, parity_view
from tests.v2.ga import _harness as ga

#: The seed invoice of every committed contract input (``_generate._SEED_INVOICE``).
SEED_DATE = "2026-07-15"
SAMPLE = "S-01"
NORAW_TEMPLATE = "run-${metadata:constant:sample}-${invoice:basic:dateSubmitted}"
PARTIAL_TEMPLATE = "${filename}-${metadata:constant:sample}"
#: Input files of the committed MultiDataTile contract input, in tile order.
MDT_INPUTS = ("tile_00.txt", "tile_日本語.txt")
#: Case-colliding labels: v1 wrote both series to ``iv_voltage.png`` (IC-3).
DUPLICATE_LABEL_CSV = "x,Voltage,voltage\n0,1,3\n1,2,2\n2,3,1\n"
VALID_MODE_NAMES = "invoice, excelinvoice, multidatatile, smarttable, rdeformat"


# ------------------------------------------------------------------ user code


@node(id="tests.v2.ga.qa02.write_sample_metadata")
def write_sample_metadata(out: OutputContext, index: int) -> None:
    """Publish ``constant.sample`` on tile 0 only; later tiles get an empty constant."""
    out.meta.mkdir(parents=True, exist_ok=True)
    constant = {"sample": {"value": SAMPLE}} if index == 0 else {}
    (out.meta / "metadata.json").write_text(json.dumps({"constant": constant, "variable": []}), encoding="utf-8")


@flow(id="tests.v2.ga.qa02.metadata_flow")
def metadata_flow(out: OutputContext, iteration: IterationInfo) -> None:
    """Write the tile's metadata; interpolation then reads it."""
    write_sample_metadata(out, iteration.index)


def metadata_callback(srcpaths: object, resource_paths: Any) -> None:
    """The v1 callback counterpart of :func:`metadata_flow` (single tile)."""
    meta = Path(resource_paths.meta)
    meta.mkdir(parents=True, exist_ok=True)
    (meta / "metadata.json").write_text(json.dumps({"constant": {"sample": {"value": SAMPLE}}, "variable": []}), encoding="utf-8")


def _plot(struct: Path, other_image: Path, main_image: Path, *, mode: str) -> None:
    csv_path = struct / "iv.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.write_text(DUPLICATE_LABEL_CSV, encoding="utf-8")
    csv2graph(csv_path, output_dir=other_image, main_image_dir=main_image, mode=mode)  # type: ignore[arg-type]


@node(id="tests.v2.ga.qa02.plot_duplicate_labels")
def plot_duplicate_labels(out: OutputContext) -> None:
    """Plot the case-colliding labels with a valid mode."""
    _plot(out.struct, out.other_image, out.main_image, mode="overlay")


@node(id="tests.v2.ga.qa02.plot_invalid_mode")
def plot_invalid_mode(out: OutputContext) -> None:
    """Plot with a wrongly cased mode that v1 drew as individual figures."""
    _plot(out.struct, out.other_image, out.main_image, mode="Overlay")


@flow(id="tests.v2.ga.qa02.duplicate_label_flow")
def duplicate_label_flow(out: OutputContext) -> None:
    """Flow entry of the duplicate-label plot."""
    plot_duplicate_labels(out)


@flow(id="tests.v2.ga.qa02.invalid_plot_mode_flow")
def invalid_plot_mode_flow(out: OutputContext) -> None:
    """Flow entry of the invalid-mode plot."""
    plot_invalid_mode(out)


def duplicate_label_callback(srcpaths: object, resource_paths: Any) -> None:
    """The v1 callback counterpart of :func:`duplicate_label_flow`."""
    _plot(Path(resource_paths.struct), Path(resource_paths.other_image), Path(resource_paths.main_image), mode="overlay")


# ------------------------------------------------------------------ helpers


def _run(root: Path, target: FlowTarget | LegacyCallbackTarget, config: Any, *, run_id: str | None = None) -> RunReport:
    runner = Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "temp",
        **({"run_id_factory": lambda: run_id} if run_id is not None else {}),
    )
    return runner.run(RunRequest(root=root, target=target, config_source=config))


def _set_data_name(root: Path, template: str) -> None:
    path = root / "data" / "invoice" / "invoice.json"
    invoice = json.loads(path.read_text(encoding="utf-8"))
    invoice["basic"]["dataName"] = template
    path.write_text(json.dumps(invoice, ensure_ascii=False), encoding="utf-8")


def _data_name(path: Path) -> str:
    name: str = json.loads(path.read_text(encoding="utf-8"))["basic"]["dataName"]
    return name


def _files(root: Path) -> set[str]:
    data = root / "data"
    return {path.relative_to(data).as_posix() for path in data.rglob("*") if path.is_file()}


def _digests(directory: Path) -> dict[str, str]:
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(directory.iterdir())}


def _job_failed(root: Path) -> str | None:
    path = root / "data" / "job.failed"
    return path.read_text(encoding="utf-8") if path.exists() else None


def _sidecar(root: Path, report: RunReport) -> Path:
    return root / "data" / "logs" / f"diagnostics_{report.run_id}.json"


def _publication_leftovers(root: Path) -> list[str]:
    """Temporary invoice candidates the atomic publisher must never leave behind."""
    return sorted(path.name for path in (root / "data").rglob(".invoice-*"))


def _magic_config(mode: str, *, policy: str = "fail_fast", magic_variable: bool | None = None) -> dict[str, Any]:
    system: dict[str, Any] = {"extended_mode": {"multidatatile": "multidatatile"}.get(mode), "save_raw": True, "save_thumbnail_image": False}
    if magic_variable is not None:
        system["magic_variable"] = magic_variable
    return {"system": system, "execution": {"on_iteration_error": policy}}


def _noraw_invoice_root(tmp_path: Path, template: str) -> Path:
    root = tmp_path / "noraw"
    _generate.materialize_sut_case("invoice", root)
    for path in (root / "data" / "inputdata").iterdir():
        path.unlink()
    _set_data_name(root, template)
    return root


# ------------------------------------------------------------------ magic (#704)


def test_invoice_and_metadata_magic_expand_without_rawfiles__qa02_magic_noraw_flow(tmp_path: Path) -> None:
    """QA02-MAGIC-NORAW-FLOW: invoice and metadata expressions need no raw file (#722)."""
    # Given: an Invoice-mode input with no raw file and an invoice/metadata template
    root = _noraw_invoice_root(tmp_path, NORAW_TEMPLATE)

    # When: a flow publishes the metadata constant the template reads
    report = _run(root, FlowTarget(function=metadata_flow), _magic_config("invoice"))

    # Then: the template is expanded from the two sources, not left literal
    assert (report.status, report.error) == ("success", None)
    assert _data_name(root / "data" / "invoice" / "invoice.json") == f"run-{SAMPLE}-{SEED_DATE}"

    # And: no raw artifact was invented for the empty input
    assert not any(path.startswith(("raw/", "nonshared_raw/")) for path in _files(root))
    assert _job_failed(root) is None
    assert _publication_leftovers(root) == []


def test_callback_keeps_the_v1_rawfiles_gate__qa02_magic_noraw_cb(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """QA02-MAGIC-NORAW-CB: the v1 callback entry still skips magic without a raw file."""
    # Given: the same zero-raw input, with v1's explicit magic_variable switch
    root = _noraw_invoice_root(tmp_path, NORAW_TEMPLATE)
    monkeypatch.chdir(root)

    # When: a v1 callback publishes the same metadata constant
    report = _run(root, LegacyCallbackTarget(function=metadata_callback), _magic_config("invoice", magic_variable=True))

    # Then: v1 1.7.1 applied magic variables only to rawfiles[0]; the template stays verbatim
    assert (report.status, report.error) == ("success", None)
    assert _data_name(root / "data" / "invoice" / "invoice.json") == NORAW_TEMPLATE
    assert _job_failed(root) is None


def test_filename_without_rawfile_fails_and_keeps_the_invoice__qa02_magic_noraw_filename(tmp_path: Path) -> None:
    """QA02-MAGIC-NORAW-FILENAME: ``${filename}`` with zero raw files is a 4010 source error."""
    # Given: a zero-raw input whose template asks for the raw file name
    template = "x-${filename}"
    root = _noraw_invoice_root(tmp_path, template)

    # When: the flow runs
    report = _run(root, FlowTarget(function=metadata_flow), _magic_config("invoice"))

    # Then: the run fails with the catalogued unavailable-source code
    assert report.status == "failed"
    assert report.error is not None
    assert report.error["code"] == 4010
    assert "filename_not_unique" in report.error["message"]
    assert [iteration["status"] for iteration in report.iterations] == ["failed"]

    # And: the failure leaves job.failed and a sidecar, and the invoice untouched
    job_failed = _job_failed(root)
    assert job_failed is not None
    assert job_failed.startswith("ErrorCode=4010\n")
    assert _sidecar(root, report).exists()
    assert _data_name(root / "data" / "invoice" / "invoice.json") == template
    assert _publication_leftovers(root) == []


@pytest.mark.parametrize(
    ("policy", "status"),
    [
        pytest.param("fail_fast", "failed", id="QA02-MAGIC-PARTIAL-FAILFAST"),
        pytest.param("continue", "partial", id="QA02-MAGIC-PARTIAL-CONTINUE"),
    ],
)
def test_magic_failure_after_partial_publication(policy: str, status: str, tmp_path: Path) -> None:
    """QA02-MAGIC-PARTIAL-*: a late magic failure keeps earlier tiles and never half-writes its own."""
    # Given: two MultiDataTile tiles; only tile 0 publishes the referenced metadata key
    root = tmp_path / "partial"
    _generate.materialize_sut_case("multidatatile", root)
    _set_data_name(root, PARTIAL_TEMPLATE)

    # When: the flow runs under the given error policy
    report = _run(root, FlowTarget(function=metadata_flow), _magic_config("multidatatile", policy=policy))

    # Then: tile 0 completes and tile 1 fails on the missing source key
    assert report.status == status
    assert [iteration["status"] for iteration in report.iterations] == ["completed", "failed"]
    failure = report.iterations[1]["error"]
    assert failure["code"] == 4010
    assert "missing_key" in failure["message"]

    # And: tile 0's invoice was published with both sources resolved
    data = root / "data"
    assert _data_name(data / "invoice" / "invoice.json") == f"{MDT_INPUTS[0]}-{SAMPLE}"

    # And: tile 1 keeps its seeded template, while its raw copy and metadata stay as leftovers
    assert _data_name(data / "divided" / "0001" / "invoice" / "invoice.json") == PARTIAL_TEMPLATE
    assert (data / "divided" / "0001" / "raw" / MDT_INPUTS[1]).is_file()
    assert (data / "divided" / "0001" / "meta" / "metadata.json").is_file()
    assert _publication_leftovers(root) == []

    # And: job.failed is the fail_fast contract only; a partial run records no fatal error
    job_failed = _job_failed(root)
    if policy == "fail_fast":
        assert report.error is not None
        assert report.error["code"] == 4010
        assert job_failed is not None
        assert job_failed.startswith("ErrorCode=4010\n")
    else:
        assert report.error is None
        assert job_failed is None


@pytest.mark.parametrize(
    "template",
    [
        pytest.param("x-${invoice:basic:dataName:extra}", id="QA02-MAGIC-MALFORMED-EXTRA-SEGMENT"),
        pytest.param("x-${filename:typo}", id="QA02-MAGIC-MALFORMED-FILENAME-ARITY"),
        pytest.param("x-${}", id="QA02-MAGIC-MALFORMED-EMPTY"),
        pytest.param("x-${filename", id="QA02-MAGIC-MALFORMED-UNCLOSED"),
        pytest.param("x-${unknown:basic:dataName}", id="QA02-MAGIC-MALFORMED-UNKNOWN-SOURCE"),
    ],
)
def test_malformed_expression_fails_before_invoice_persistence(template: str, tmp_path: Path) -> None:
    """QA02-MAGIC-MALFORMED-*: the strict parser rejects what the old regex accepted (#723)."""
    # Given: the one-raw-file Invoice input with a malformed template
    root = tmp_path / "malformed"
    _generate.materialize_sut_case("invoice", root)
    _set_data_name(root, template)

    # When: the flow runs
    report = _run(root, FlowTarget(function=metadata_flow), _magic_config("invoice"))

    # Then: the syntax error code, and the template is never replaced
    assert report.status == "failed"
    assert report.error is not None
    assert report.error["code"] == 4009
    assert _data_name(root / "data" / "invoice" / "invoice.json") == template
    job_failed = _job_failed(root)
    assert job_failed is not None
    assert job_failed.startswith("ErrorCode=4009\n")
    assert _publication_leftovers(root) == []


# ------------------------------------------------------------------ modes (#705)


def _mixed_root(tmp_path: Path) -> Path:
    """The committed SmartTable input plus the committed ExcelInvoice workbook."""
    root = tmp_path / "mixed"
    _generate.materialize_sut_case("smarttable", root)
    workbook_source = tmp_path / "workbook"
    _generate.materialize_sut_case("excelinvoice", workbook_source)
    for path in (workbook_source / "data" / "inputdata").glob("*_excel_invoice.xlsx"):
        shutil.copy2(path, root / "data" / "inputdata" / path.name)
    shutil.rmtree(workbook_source)
    return root


def _extra_workbooks(root: Path) -> set[str]:
    """Output-tree paths (``data/...``) of the ExcelInvoice workbooks added to the input."""
    return {f"data/inputdata/{path.name}" for path in (root / "data" / "inputdata").glob("*_excel_invoice.xlsx")}


def test_mixed_special_inputs_fail_before_mutation__qa02_mode_mixed_flow(tmp_path: Path) -> None:
    """QA02-MODE-MIXED-FLOW: SmartTable + ExcelInvoice is ambiguous for a flow (#730)."""
    # Given: one SmartTable table and one ExcelInvoice workbook side by side
    root = _mixed_root(tmp_path)
    inputs_before = _digests(root / "data" / "inputdata")
    files_before = _files(root)

    # When: a flow runs with automatic mode selection
    report = _run(root, FlowTarget(function=ga.USER_CODE["inflight"]["flow"]), {"system": {"save_thumbnail_image": False}})

    # Then: the ambiguity is a catalogued configuration error, raised before any tile
    assert report.status == "failed"
    assert report.error is not None
    assert report.error["code"] == 1007
    assert "smarttable_full.xlsx" in report.error["message"]
    assert "contract_excel_invoice.xlsx" in report.error["message"]
    assert report.iterations == []

    # And: only the failure record and run-scoped logs were added; inputs are untouched
    added = _files(root) - files_before
    assert {path for path in added if not path.startswith("logs/")} == {"job.failed"}
    assert _sidecar(root, report).relative_to(root / "data").as_posix() in added
    assert not (root / "data" / "divided").exists()
    assert not (root / "data" / "temp").exists() or not any((root / "data" / "temp").iterdir())
    assert _digests(root / "data" / "inputdata") == inputs_before
    job_failed = _job_failed(root)
    assert job_failed is not None
    assert job_failed.startswith("ErrorCode=1007\n")


def test_mixed_special_inputs_keep_v1_smarttable_precedence__qa02_mode_mixed_cb(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """QA02-MODE-MIXED-CB: the v1 callback entry keeps SmartTable-before-ExcelInvoice precedence."""
    # Given: the mixed input, and the frozen v1 observation of the SmartTable input alone
    root = _mixed_root(tmp_path)
    extra = _extra_workbooks(root)
    expected = ga.frozen_ok("smarttable")
    monkeypatch.chdir(root)

    # When: the frozen corpus's own v1 callback runs through the callback entry
    report = _run(root, LegacyCallbackTarget(function=ga.USER_CODE["ok"]["callback"]), ga.v1_config("smarttable"))

    # Then: v1 picked SmartTable, so the run is exactly the frozen SmartTable run
    assert (report.status, report.mode, report.error) == ("success", "smarttable", None)
    assert len(report.iterations) == expected["callback_count"]
    actual, expected_view = parity_pair(root, expected)
    actual["output_tree"]["files"] = [path for path in actual["output_tree"]["files"] if path not in extra]
    assert actual == expected_view
    assert _job_failed(root) is None


@pytest.mark.parametrize(
    "spelling",
    [
        pytest.param("multidatatile", id="QA02-MODE-ALIAS-CANONICAL"),
        pytest.param("MultiDataTile", id="QA02-MODE-ALIAS-LEGACY"),
    ],
)
def test_multidatatile_spellings_select_multidatatile(spelling: str, tmp_path: Path) -> None:
    """QA02-MODE-ALIAS-*: neither spelling falls back to Invoice (#729)."""
    # Given: the committed MultiDataTile input and v1's tile count for it
    root = tmp_path / "alias"
    _generate.materialize_sut_case("multidatatile", root)
    tiles = ga.tile_count("multidatatile")

    # When: a flow runs with the spelling
    report = _run(root, FlowTarget(function=ga.USER_CODE["inflight"]["flow"]), {"system": {"extended_mode": spelling, "save_thumbnail_image": False}})

    # Then: one tile per input file, as frozen v1 MultiDataTile ran it (Invoice would be 1)
    assert (report.status, report.mode) == ("success", "multidatatile")
    assert tiles == len(MDT_INPUTS)
    assert [iteration["index"] for iteration in report.iterations] == list(range(tiles))
    assert (root / "data" / "divided" / "0001" / "nonshared_raw" / MDT_INPUTS[1]).is_file()

    # And: the published invoices are v1's
    assert observe_v2_run(root)["invoices"] == parity_view(frozen_observed("v1/multidatatile/ok"))["invoices"]


@pytest.mark.parametrize(
    "spelling",
    [
        pytest.param("multi_data_tile", id="QA02-MODE-INVALID-SNAKE"),
        pytest.param("Multidatatile", id="QA02-MODE-INVALID-CASE"),
        pytest.param("excel_invoice", id="QA02-MODE-INVALID-TYPO"),
    ],
)
def test_unknown_mode_names_fail_before_any_tile(spelling: str, tmp_path: Path) -> None:
    """QA02-MODE-INVALID-*: an unknown spelling lists the valid names and creates no tile (#729)."""
    # Given: the committed MultiDataTile input
    root = tmp_path / "invalid"
    _generate.materialize_sut_case("multidatatile", root)
    files_before = _files(root)

    # When: a flow runs with the unknown spelling
    report = _run(root, FlowTarget(function=ga.USER_CODE["inflight"]["flow"]), {"system": {"extended_mode": spelling}})

    # Then: configuration error 1002 naming every canonical mode
    assert report.status == "failed"
    assert report.error is not None
    assert report.error["code"] == 1002
    assert VALID_MODE_NAMES in report.error["message"]
    assert report.iterations == []

    # And: nothing but the failure record and logs was written
    added = _files(root) - files_before
    assert {path for path in added if not path.startswith("logs/")} == {"job.failed"}


# ------------------------------------------------------------------ graph (#703)


@pytest.mark.parametrize(
    "target",
    [
        pytest.param(FlowTarget(function=duplicate_label_flow), id="QA02-GRAPH-DUPLABEL-FLOW"),
        pytest.param(LegacyCallbackTarget(function=duplicate_label_callback), id="QA02-GRAPH-DUPLABEL-CB"),
    ],
)
def test_duplicate_labels_give_distinct_figures_on_every_tile(
    target: FlowTarget | LegacyCallbackTarget, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """QA02-GRAPH-DUPLABEL-*: colliding labels never overwrite each other, on any tile (#708)."""
    # Given: two MultiDataTile tiles whose user code plots ``Voltage`` and ``voltage``
    root = tmp_path / "graph"
    _generate.materialize_sut_case("multidatatile", root)
    monkeypatch.chdir(root)

    # When: the run plots on each tile, with thumbnails on
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        report = _run(root, target, {"system": {"extended_mode": "MultiDataTile", "save_thumbnail_image": True}})

    # Then: the run succeeds and warns once per tile about the collision
    assert (report.status, report.error) == ("success", None)
    collisions = [item for item in caught if issubclass(item.category, GraphUserWarning)]
    assert len(collisions) == len(MDT_INPUTS)

    # And: each tile has one figure per series under a stable suffixed name, contents distinct
    data = root / "data"
    names_per_tile = []
    for tile in (data, data / "divided" / "0001"):
        figures = _digests(tile / "other_image")
        assert sorted(figures) == ["iv_voltage_s000.png", "iv_voltage_s001.png"]
        assert len(set(figures.values())) == len(figures)
        names_per_tile.append(sorted(figures))
        assert sorted(path.name for path in (tile / "main_image").iterdir()) == ["iv.png"]
        assert sorted(path.name for path in (tile / "thumbnail").iterdir()) == ["iv.png"]

    # And: the naming plan is the same on every tile
    assert names_per_tile[0] == names_per_tile[1]


def test_invalid_plot_mode_fails_before_any_figure__qa02_graph_invalid_mode(tmp_path: Path) -> None:
    """QA02-GRAPH-INVALID-MODE: ``mode="Overlay"`` is rejected instead of plotting individually (#707)."""
    # Given: two MultiDataTile tiles whose node plots with a wrongly cased mode
    root = tmp_path / "graph"
    _generate.materialize_sut_case("multidatatile", root)

    # When: the run continues past the first failure
    report = _run(root, FlowTarget(function=invalid_plot_mode_flow), {"system": {"extended_mode": "MultiDataTile"}, "execution": {"on_iteration_error": "continue"}})

    # Then: every tile fails as a node execution failure naming the invalid mode
    assert report.status == "failed"
    for iteration in report.iterations:
        assert iteration["status"] == "failed"
        assert iteration["error"]["code"] == 3001
        assert "Invalid mode: 'Overlay'" in iteration["error"]["message"]

    # And: no figure was written anywhere (v1 drew individual figures)
    assert sorted(path for path in _files(root) if path.endswith((".png", ".html"))) == []
    job_failed = _job_failed(root)
    assert job_failed is not None
    assert job_failed.startswith("ErrorCode=3001\n")


# ------------------------------------------------------------------ concurrency

_holder_entered = threading.Event()
_holder_release = threading.Event()


@node(id="tests.v2.ga.qa02.hold_root")
def hold_root(index: int) -> int:
    """On tile 0, signal that the run owns its root and wait for the test."""
    if index == 0:
        _holder_entered.set()
        assert _holder_release.wait(timeout=120), "the test never released the holding run"
    return index


@flow(id="tests.v2.ga.qa02.holding_flow")
def holding_flow(iteration: IterationInfo) -> None:
    """Own the root until the test releases tile 0."""
    hold_root(iteration.index)


@pytest.mark.parametrize(("entry", "mode"), [
    pytest.param(entry, mode, id=f"QA02-CONC-{ga.ENTRY_IDS[entry]}-{ga.MODE_IDS[mode]}")
    for entry in ga.ENTRIES
    for mode in ga.MODES
])
def test_a_second_run_on_a_busy_root_is_refused(entry: str, mode: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """QA02-CONC-*: while one run owns a root, a second one is refused and writes nothing (3008)."""
    # Given: a flow run that owns the root and is paused inside tile 0
    root = tmp_path / mode
    _generate.materialize_sut_case(mode, root)
    # The oracle callbacks write their call markers to the CWD.
    monkeypatch.chdir(root)
    _holder_entered.clear()
    _holder_release.clear()
    outcome: dict[str, RunReport] = {}
    holder = threading.Thread(
        target=lambda: outcome.setdefault("report", _run(root, FlowTarget(function=holding_flow), ga.v1_config(mode), run_id="qa02holder")),
    )
    holder.start()
    try:
        assert _holder_entered.wait(timeout=120), "the holding run never reached its flow"
        before = {path: (root / "data" / path).read_bytes() for path in _files(root)}

        # When: a second run starts on the same root through the given entry
        intruder = _run(root, ga.target_for(entry, ga.USER_CODE["ok"][entry]), ga.v1_config(mode), run_id="qa02intruder")

        # Then: it is refused with RunRootBusy before doing anything
        assert (intruder.status, intruder.iterations) == ("failed", [])
        assert intruder.error is not None
        assert (intruder.error["code"], intruder.error["name"]) == (3008, "RunRootBusy")

        # And: the root is byte-for-byte what the holder had written so far
        assert {path: (root / "data" / path).read_bytes() for path in _files(root)} == before
    finally:
        _holder_release.set()
        holder.join(timeout=300)

    # And: the holder finishes exactly as the frozen v1 run did
    report = outcome["report"]
    assert (report.status, report.error) == ("success", None)
    assert [iteration["status"] for iteration in report.iterations] == ["completed"] * ga.tile_count(mode)
    actual, expected = parity_pair(root, ga.frozen_ok(mode))
    assert actual == expected
    assert _job_failed(root) is None
    assert not (root / "data" / "logs" / "run_report_qa02intruder.json").exists()
    assert not (root / "data" / "logs" / "events_qa02intruder.jsonl").exists()


@pytest.mark.parametrize("mode", [pytest.param(mode, id=f"QA02-CONC-RACE-{ga.MODE_IDS[mode]}") for mode in ga.MODES])
def test_simultaneous_runs_never_corrupt_each_other(mode: str, tmp_path: Path) -> None:
    """QA02-CONC-RACE-*: two runs released together end in success or 3008, nothing else."""
    for attempt in range(5):
        # Given: one root and two runs released at the same instant
        root = tmp_path / f"{mode}-{attempt}"
        _generate.materialize_sut_case(mode, root)
        barrier = threading.Barrier(2)
        reports: dict[str, RunReport] = {}

        def work(run_id: str, root: Path = root, barrier: threading.Barrier = barrier, reports: dict[str, RunReport] = reports) -> None:
            barrier.wait()
            reports[run_id] = _run(root, FlowTarget(function=ga.USER_CODE["inflight"]["flow"]), ga.v1_config(mode), run_id=run_id)

        # When: both run
        threads = [threading.Thread(target=work, args=(run_id,)) for run_id in ("qa02a", "qa02b")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=300)

        # Then: each run either succeeded or was refused; at least one succeeded
        outcomes = sorted((report.status, (report.error or {}).get("code")) for report in reports.values())
        assert outcomes in ([("failed", 3008), ("success", None)], [("success", None), ("success", None)]), outcomes

        # And: the root holds exactly the frozen v1 artifacts
        actual, expected = parity_pair(root, ga.frozen_ok(mode))
        assert actual == expected
        assert _job_failed(root) is None
