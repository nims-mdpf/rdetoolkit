"""Contracts for Phase H3 common domain services.

Equivalence partitions (EP):

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| ``RawArtifactService.copy`` | raw/nonshared enabled | copies both destinations | TC-H3-EP-001 |
| ``RawArtifactService.copy`` | SmartTable source disabled | original table is excluded | TC-H3-EP-002 |
| ``RawArtifactService.copy`` | copy failure | raises catalogued execution error | TC-H3-EP-003 |
| ``ImageArtifactService.generate`` | enabled | delegates thumbnail generation | TC-H3-EP-004 |
| ``ImageArtifactService.generate`` | converter failure | suppresses the exception | TC-H3-EP-005 |
| ``OutputLayoutResolver.resolve`` | divided tile | resolves divided/0001 | TC-H3-EP-006 |
| ``OutputLayoutResolver.resolve`` | negative index | raises catalogued internal error | TC-H3-EP-007 |
| ``InputValidator.validate`` | complete input | returns normalized paths | TC-H3-EP-008 |
| ``InputValidator.validate`` | missing required child | raises catalogued validation error | TC-H3-EP-009 |
| ``IterationFactory.files`` | unordered siblings | returns sorted paths | TC-H3-EP-010 |
| ``IterationFactory.files`` | missing directory | raises catalogued validation error | TC-H3-EP-011 |
| ``InvoiceService.backup`` | backup mode | copies to explicit temp path | TC-H3-EP-012 |
| ``InvoiceService.apply_step`` | three invoice flags | consumes all three flags, structured copy taken from ``invoice_org`` | TC-H3-EP-013 |
| ``InvoiceService.apply_step`` | omitted stage | a stage left out of the sequence does not run | TC-H3-EV-017 |
| ``InvoiceService.apply_step`` | feature updater fails | suppresses the exception | TC-H3-EP-014 |
| ``InvoiceService.apply_step`` | structured source absent | raises ``FileNotFoundError`` like v1 | TC-H3-EV-015 |
| ``InvoiceService.apply_step`` | source already is the destination | copy is skipped, file untouched | TC-H3-EV-016 |

Boundary values (BV):

| API | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| ``OutputLayoutResolver.resolve`` | indexes 0 and 1 | root then first divided tile | TC-H3-BV-001 |
| ``IterationFactory.files`` | empty directory | empty tuple | TC-H3-BV-002 |
| ``InvoiceService.backup`` | source absent | returns source path without creating backup | TC-H3-BV-003 |

Negative/abnormal rows (8) outnumber positive rows (6). Every ``RdeConfig`` v1
compatibility key is observed by a service: raw, nonshared raw, thumbnail,
magic variable, structured invoice, feature description, and SmartTable table.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rdetoolkit.domain.artifacts import ImageArtifactService, RawArtifactService
from rdetoolkit.domain.input_validation import InputValidator
from rdetoolkit.domain.invoice_service import InvoiceService
from rdetoolkit.domain.iteration import IterationFactory
from rdetoolkit.domain.output_layout import OutputLayoutResolver
from rdetoolkit.errors import RdeExecutionError, RdeInternalError, RdeValidationError
from rdetoolkit.models.rde2types import RdeDatasetPaths
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.types import RdeConfig


def test_raw_artifacts_consume_copy_and_smarttable_flags__tc_h3_ep_001_002(tmp_path: Path) -> None:
    """TC-H3-EP-001/002: raw copies honor all three artifact flags."""
    # Given: ordinary data, a generated row, and the original SmartTable file
    inputdata = tmp_path / "inputdata"
    inputdata.mkdir()
    ordinary = inputdata / "sample.dat"
    generated = inputdata / "fsmarttable_row.csv"
    table = inputdata / "smarttable_source.csv"
    for path in (ordinary, generated, table):
        path.write_text(path.name, encoding="utf-8")
    config = RdeConfig(
        system={"save_raw": True, "save_nonshared_raw": True},
        smarttable={"save_table_file": False},
    )

    # When: copying SmartTable inputs with original-table persistence disabled
    RawArtifactService().copy(
        (table, generated, ordinary),
        raw_dir=tmp_path / "raw",
        nonshared_raw_dir=tmp_path / "nonshared_raw",
        config=config,
        smarttable=True,
    )

    # Then: only ordinary input is copied to both configured destinations
    assert sorted(path.name for path in (tmp_path / "raw").iterdir()) == ["sample.dat"]
    assert sorted(path.name for path in (tmp_path / "nonshared_raw").iterdir()) == ["sample.dat"]


def test_raw_artifact_copy_wraps_copy_failure__tc_h3_ep_003(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-H3-EP-003: invalid source paths retain v1 FileCopier failure behavior."""
    # Given: copying is enabled and the filesystem copy fails
    source = tmp_path / "source.dat"
    source.write_text("raw", encoding="utf-8")
    monkeypatch.setattr("rdetoolkit.domain.artifacts.shutil.copy2", lambda *args: (_ for _ in ()).throw(OSError("disk")))
    config = RdeConfig(system={"save_raw": True, "save_nonshared_raw": False})

    # When/Then: the service maps the copy failure to the v2 execution catalog
    with pytest.raises(RdeExecutionError, match="Failed to copy") as exc_info:
        RawArtifactService().copy(
            (source,),
            raw_dir=tmp_path / "raw",
            nonshared_raw_dir=tmp_path / "nonshared_raw",
            config=config,
        )
    assert exc_info.value.code == 3001


def test_image_artifact_consumes_thumbnail_flag__tc_h3_ep_004(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-H3-EP-004: enabled thumbnail generation delegates with explicit paths."""
    # Given: enabled thumbnail generation and a recording converter
    calls: list[tuple[Path, Path]] = []
    monkeypatch.setattr(
        "rdetoolkit.domain.artifacts.img2thumb.copy_images_to_thumbnail",
        lambda thumbnail, main: calls.append((thumbnail, main)),
    )

    # When: the service generates image artifacts
    ImageArtifactService().generate(
        main_image_dir=tmp_path / "main_image",
        thumbnail_dir=tmp_path / "thumbnail",
        config=RdeConfig(system={"save_thumbnail_image": True}),
    )

    # Then: the configured explicit paths are delegated once
    assert calls == [(tmp_path / "thumbnail", tmp_path / "main_image")]


def test_image_artifact_suppresses_converter_failure__tc_h3_ep_005(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-H3-EP-005: thumbnail failures remain intentionally noncritical."""
    # Given: the v1 image converter raises
    def fail(*args: object) -> None:
        raise OSError("bad image")

    monkeypatch.setattr("rdetoolkit.domain.artifacts.img2thumb.copy_images_to_thumbnail", fail)

    # When/Then: enabled generation preserves v1 exception suppression
    ImageArtifactService().generate(
        main_image_dir=tmp_path / "main_image",
        thumbnail_dir=tmp_path / "thumbnail",
        config=RdeConfig(system={"save_thumbnail_image": True}),
    )


def test_output_layout_root_and_divided_boundaries__tc_h3_ep_006_bv_001(tmp_path: Path) -> None:
    """TC-H3-EP-006/BV-001: layout resolution preserves the v1 tile boundary."""
    # Given: a path-only resolver and output root
    resolver = OutputLayoutResolver()

    # When: resolving the two sides of the divided boundary
    first = resolver.resolve(tmp_path, 0)
    second = resolver.resolve(tmp_path, 1)

    # Then: tile zero is flat and tile one uses the first divided directory
    assert first.invoice == tmp_path / "invoice"
    assert second.invoice == tmp_path / "divided" / "0001" / "invoice"
    assert not first.invoice.exists()


def test_output_layout_rejects_negative_index__tc_h3_ep_007(tmp_path: Path) -> None:
    """TC-H3-EP-007: negative tile indexes are outside the output contract."""
    # Given: a path-only resolver
    # When/Then: resolving an invalid negative tile fails before filesystem work
    with pytest.raises(RdeInternalError, match="non-negative") as exc_info:
        OutputLayoutResolver().resolve(tmp_path, -1)
    assert exc_info.value.code == 5001


def test_input_validator_accepts_complete_tree__tc_h3_ep_008(tmp_path: Path) -> None:
    """TC-H3-EP-008: complete input structure yields explicit input paths."""
    # Given: the three required input directories
    for name in ("inputdata", "invoice", "tasksupport"):
        (tmp_path / name).mkdir()

    # When: validating the root
    paths = InputValidator().validate(tmp_path)

    # Then: the returned paths are rooted at the validated directory
    assert paths.inputdata == tmp_path / "inputdata"
    assert paths.invoice == tmp_path / "invoice"
    assert paths.tasksupport == tmp_path / "tasksupport"


@pytest.mark.parametrize("missing", ["inputdata", "invoice", "tasksupport"])
def test_input_validator_rejects_missing_child__tc_h3_ep_009(tmp_path: Path, missing: str) -> None:
    """TC-H3-EP-009: every missing required directory is rejected."""
    # Given: an input root missing exactly one required child
    for name in ("inputdata", "invoice", "tasksupport"):
        if name != missing:
            (tmp_path / name).mkdir()

    # When/Then: validation names the missing child
    with pytest.raises(RdeValidationError, match=missing) as exc_info:
        InputValidator().validate(tmp_path)
    assert exc_info.value.code == 4003


def test_iteration_factory_always_sorts_siblings__tc_h3_ep_010_bv_002(tmp_path: Path) -> None:
    """TC-H3-EP-010/BV-002: enumeration is deterministic, including empty input."""
    # Given: siblings created in reverse lexical order and an empty directory
    populated = tmp_path / "populated"
    empty = tmp_path / "empty"
    populated.mkdir()
    empty.mkdir()
    for name in ("z.dat", "a.dat", "m.dat"):
        (populated / name).write_text(name, encoding="utf-8")

    # When: enumerating both directories
    factory = IterationFactory()
    ordered = factory.files(populated)

    # Then: the populated result is sorted and the empty boundary stays empty
    assert [path.name for path in ordered] == ["a.dat", "m.dat", "z.dat"]
    assert factory.files(empty) == ()


def test_iteration_factory_rejects_missing_directory__tc_h3_ep_011(tmp_path: Path) -> None:
    """TC-H3-EP-011: enumeration rejects an absent input directory."""
    # Given: a path that does not exist
    # When/Then: enumeration raises instead of silently producing zero tiles
    with pytest.raises(RdeValidationError, match="does not exist") as exc_info:
        IterationFactory().files(tmp_path / "missing")
    assert exc_info.value.code == 4003


def test_invoice_service_backup_is_path_based__tc_h3_ep_012_bv_003(tmp_path: Path) -> None:
    """TC-H3-EP-012/BV-003: backup selection uses explicit paths only."""
    # Given: a nested source invoice and an absent flat source
    data_root = tmp_path / "data"
    source = data_root / "invoice" / "invoice.json"
    source.parent.mkdir(parents=True)
    source.write_text('{"datasetId": "source"}', encoding="utf-8")
    service = InvoiceService()

    # When: backing up a v1 backup mode
    backup = service.backup(ModeKind.rdeformat, data_root=data_root, inputdata_path=data_root / "inputdata")

    # Then: the source is copied to the explicit data-root temp directory
    assert backup == data_root / "temp" / "invoice_org.json"
    assert json.loads(backup.read_text(encoding="utf-8")) == {"datasetId": "source"}
    assert service.backup(
        ModeKind.rdeformat,
        data_root=tmp_path / "absent",
        inputdata_path=tmp_path / "absent" / "inputdata",
    ) == tmp_path / "absent" / "invoice" / "invoice.json"


def _dataset_paths(tmp_path: Path, *, invoice_org: Path, rawfiles: tuple[Path, ...] = ()) -> RdeDatasetPaths:
    """Build the v1 tile bundle ``apply_step`` consumes."""
    from rdetoolkit.domain.invoice_service import build_tile_dataset_paths
    from rdetoolkit.runner.paths import resolve_tile_paths
    from rdetoolkit.types import InputPaths, OutputContext

    tile = resolve_tile_paths(tmp_path, 0)
    paths = InputPaths(
        inputdata=tmp_path / "inputdata",
        invoice=tmp_path / "invoice",
        tasksupport=tmp_path / "tasksupport",
        raw=rawfiles[0] if len(rawfiles) == 1 else None,
        rawfiles=rawfiles,
    )
    return build_tile_dataset_paths(
        paths=paths,
        out=OutputContext.from_resource_paths(tile),
        invoice_org=invoice_org,
    )


def test_invoice_service_consumes_three_invoice_flags__tc_h3_ep_013_014(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-H3-EP-013/014: invoice postprocessing consumes its three config flags.

    Updated in Session I6-1: the structured copy source is the run-level
    ``invoice_org`` (v1 ``StructuredInvoiceSaver``) and the magic-variable step
    receives the whole v1 dataset bundle, because ``apply_magic_variable``
    resolves ``${invoice:...}`` / ``${metadata:...}`` only when it is given.
    """
    # Given: a tile invoice, a distinct source invoice, one raw input, and a failing updater
    invoice = tmp_path / "invoice" / "invoice.json"
    invoice_org = tmp_path / "temp" / "invoice_org.json"
    rawfile = tmp_path / "inputdata" / "sample.dat"
    invoice.parent.mkdir()
    invoice_org.parent.mkdir()
    rawfile.parent.mkdir()
    invoice.write_text('{"basic": {"dataName": "${filename}"}}', encoding="utf-8")
    invoice_org.write_text('{"basic": {"dataName": "original"}}', encoding="utf-8")
    rawfile.write_text("raw", encoding="utf-8")
    magic_calls: list[tuple[Path, Path, object]] = []
    monkeypatch.setattr(
        "rdetoolkit.domain.invoice_service.apply_magic_variable",
        lambda invoice_path, raw_path, **kwargs: magic_calls.append(
            (Path(invoice_path), Path(raw_path), kwargs.get("dataset_paths")),
        )
        or {},
    )
    dataset_paths = _dataset_paths(tmp_path, invoice_org=invoice_org, rawfiles=(rawfile,))

    # When: running the v1 invoice pipeline's stages in order (ruling #5)
    service = InvoiceService()
    config = RdeConfig(
        system={
            "magic_variable": True,
            "save_invoice_to_structured": True,
            "feature_description": True,
        },
    )
    for step in ("structured", "magic", "description"):
        service.apply_step(
            step,
            config=config,
            dataset_paths=dataset_paths,
            feature_updater=lambda: (_ for _ in ()).throw(OSError("optional metadata")),
        )

    # Then: mandatory actions run, magic receives the bundle, feature failure is suppressed
    assert magic_calls == [(invoice, rawfile, dataset_paths)]
    structured = tmp_path / "structured" / "invoice.json"
    assert structured.read_text(encoding="utf-8") == invoice_org.read_text(encoding="utf-8")
    assert structured.read_text(encoding="utf-8") != invoice.read_text(encoding="utf-8")


def test_invoice_service_rejects_a_missing_structured_source__tc_h3_ev_015(tmp_path: Path) -> None:
    """TC-H3-EV-015: an absent invoice_org fails the structured copy, as v1 does."""
    # Given: the structured gate enabled but no source invoice on disk
    (tmp_path / "invoice").mkdir()
    (tmp_path / "invoice" / "invoice.json").write_text('{"basic": {}}', encoding="utf-8")

    # When/Then: the v1 FileNotFoundError contract is preserved
    with pytest.raises(FileNotFoundError):
        InvoiceService().apply_step(
            "structured",
            config=RdeConfig(system={"save_invoice_to_structured": True}),
            dataset_paths=_dataset_paths(tmp_path, invoice_org=tmp_path / "temp" / "invoice_org.json"),
        )


def test_invoice_service_skips_a_self_targeted_structured_copy__tc_h3_ev_016(tmp_path: Path) -> None:
    """TC-H3-EV-016: an invoice_org already inside structured/ is not copied onto itself."""
    # Given: a source invoice that is already the structured destination
    structured_dir = tmp_path / "structured"
    structured_dir.mkdir()
    invoice_org = structured_dir / "invoice.json"
    invoice_org.write_text('{"datasetId": "already-there"}', encoding="utf-8")

    # When: applying the structured gate
    InvoiceService().apply_step(
        "structured",
        config=RdeConfig(system={"save_invoice_to_structured": True}),
        dataset_paths=_dataset_paths(tmp_path, invoice_org=invoice_org),
    )

    # Then: the file survives untouched instead of raising SameFileError
    assert json.loads(invoice_org.read_text(encoding="utf-8")) == {"datasetId": "already-there"}


def test_invoice_service_runs_only_the_selected_steps__tc_h3_ev_017(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-H3-EV-017 (UPDATED, ruling #5): an omitted stage is simply not run.

    The step selection used to be a ``frozenset`` argument to ``apply_config``.
    A set cannot express order, and review R3 proved the order is observable,
    so the caller now drives an ordered sequence of ``apply_step`` calls: a mode
    omits a stage by leaving it out of its sequence.
    """
    # Given: every gate enabled but only the description step selected
    invoice_org = tmp_path / "temp" / "invoice_org.json"
    rawfile = tmp_path / "inputdata" / "sample.dat"
    invoice_org.parent.mkdir()
    rawfile.parent.mkdir()
    invoice_org.write_text('{"basic": {"dataName": "original"}}', encoding="utf-8")
    rawfile.write_text("raw", encoding="utf-8")
    magic_calls: list[Path] = []
    monkeypatch.setattr(
        "rdetoolkit.domain.invoice_service.apply_magic_variable",
        lambda invoice_path, raw_path, **kwargs: magic_calls.append(Path(invoice_path)) or {},
    )
    description_calls: list[int] = []

    # When: running only the RDEFormat-shaped sequence
    service = InvoiceService()
    config = RdeConfig(
        system={
            "magic_variable": True,
            "save_invoice_to_structured": True,
            "feature_description": True,
        },
    )
    dataset_paths = _dataset_paths(tmp_path, invoice_org=invoice_org, rawfiles=(rawfile,))
    for step in ("description",):
        service.apply_step(
            step,
            config=config,
            dataset_paths=dataset_paths,
            feature_updater=lambda: description_calls.append(1),
        )

    # Then: only the selected step ran
    assert magic_calls == []
    assert not (tmp_path / "structured" / "invoice.json").exists()
    assert description_calls == [1]
