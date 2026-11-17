"""Read-only grouping and explanation contract for #732 and #735."""

from pathlib import Path

import pytest

from rdetoolkit.runner.input_snapshot import discover_input_snapshot
from rdetoolkit.runner.mode_resolver import ModeKind
from rdetoolkit.types import RdeConfig


def test_invoice_multiple_files_stay_one_group__preview_p1(tmp_path: Path) -> None:
    # Given: ordinary files do not request a split registration.
    (tmp_path / "b.txt").touch()
    (tmp_path / "a.txt").touch()
    # When: reading the input snapshot.
    snapshot = discover_input_snapshot(ModeKind.invoice, tmp_path, RdeConfig())
    # Then: the snapshot groups all files without creating outputs.
    assert len(snapshot.groups) == 1
    assert {ref.source.name for ref in snapshot.groups[0].files} == {"a.txt", "b.txt"}
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.txt", "b.txt"]


@pytest.mark.parametrize("count", [0, 1, 3])
def test_multidatatile_groups_names__preview_p2_b1(tmp_path: Path, count: int) -> None:
    # Given: files appear in reverse name order.
    for index in reversed(range(count)):
        (tmp_path / f"{index}.txt").touch()
    # When: reading a name-ordered MultiDataTile snapshot.
    snapshot = discover_input_snapshot(ModeKind.multidatatile, tmp_path, RdeConfig())
    # Then: each file belongs to one group, including the legacy empty tile.
    assert len(snapshot.groups) == max(count, 1)
    assert [ref.source.name for group in snapshot.groups for ref in group.files] == [f"{index}.txt" for index in range(count)]


def test_explain_is_read_only__explain_p1(tmp_path: Path) -> None:
    # Given: a valid input project.
    from tests.v2.contract.fixtures import _generate
    from rdetoolkit.runner.preview import preview_registration

    _generate.materialize_case(_generate.oracle_case("v1/invoice/ok"), tmp_path)
    before = {p.relative_to(tmp_path).as_posix(): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    # When: explanation inspects the project twice.
    first = preview_registration(tmp_path).to_dict()
    second = preview_registration(tmp_path).to_dict()
    # Then: the result is repeatable and no project file changes.
    assert first == second
    assert first["schema_version"] == "1"
    assert first["decision"]["chosen_mode"] == "invoice"
    assert before == {p.relative_to(tmp_path).as_posix(): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


@pytest.mark.parametrize("mode", list(ModeKind))
def test_snapshot_matches_materialized_legacy_groups__preview_p3_p4_p5(tmp_path: Path, mode: ModeKind) -> None:
    # Given: the frozen five-mode input family and matching config.
    from tests.v2.contract.fixtures import _generate
    from rdetoolkit.runner.input_snapshot import materialize_input_snapshot
    from rdetoolkit.runner.iterator import iterate_tiles

    _generate.materialize_case(_generate.oracle_case(f"v1/{mode.value}/ok"), tmp_path)
    data_root = tmp_path / "data"
    config = RdeConfig(system={"extended_mode": mode.value})
    before = {p.relative_to(tmp_path).as_posix(): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    # When: read-only discovery plans the groups used by strict execution.
    snapshot = discover_input_snapshot(mode, data_root / "inputdata", config)
    assert before == {p.relative_to(tmp_path).as_posix(): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    legacy_unpack = data_root / "legacy-temp"
    strict_unpack = data_root / "strict-temp"
    legacy = list(iterate_tiles(mode, data_root / "inputdata", legacy_unpack, data_root, config))
    strict = materialize_input_snapshot(snapshot, strict_unpack)

    # Then: group membership and order agree with the established checker corpus.
    def names(paths: tuple[Path, ...], unpacked: Path) -> list[str]:
        return [p.relative_to(unpacked).as_posix() if p.is_relative_to(unpacked) else p.name for p in paths]

    strict_names = [names(item[0], strict_unpack) for item in strict]
    legacy_names = [names(paths.rawfiles, legacy_unpack) for _, paths, _ in legacy]
    if mode is ModeKind.rdeformat:
        assert [sorted(group) for group in strict_names] == [sorted(group) for group in legacy_names]
    else:
        assert strict_names == legacy_names
    actual = list(iterate_tiles(mode, data_root / "inputdata", strict_unpack, data_root, config, snapshot=snapshot))
    assert [names(paths.rawfiles, strict_unpack) for _, paths, _ in actual] == strict_names


@pytest.mark.parametrize("members", [("../escape.txt",), ("/escape.txt",), ("a.txt", "a.txt"), ("a.txt", "A.txt"), ("folder", "folder/child.txt"), ("folder\\child.txt",)])
def test_unsafe_archive_rejected_without_extraction__preview_n1(tmp_path: Path, members: tuple[str, ...]) -> None:
    # Given: an archive whose names are unsafe or ambiguous.
    import zipfile
    from rdetoolkit.errors import RdeValidationError
    from rdetoolkit.runner.input_snapshot import archive_references

    archive = tmp_path / "input.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        for member in members:
            zipped.writestr(member, "private payload")
    # When: planning archive membership.
    with pytest.raises(RdeValidationError) as caught:
        archive_references([archive])
    # Then: one catalogued refusal occurs before any member is created.
    assert caught.value.code == 4006
    assert "private payload" not in str(caught.value)
    assert list(tmp_path.iterdir()) == [archive]


@pytest.mark.parametrize("references", ["missing.dat", "raw.txt"])
def test_missing_or_ambiguous_table_reference_is_redacted__preview_n2(tmp_path: Path, references: str) -> None:
    # Given: a row reference that resolves to zero or two archive members.
    import zipfile
    from rdetoolkit.errors import RdeValidationError

    (tmp_path / "smarttable_rows.csv").write_text(f"name,file\nbasic/dataName,inputdata1\nsecret name,{references}\n")
    with zipfile.ZipFile(tmp_path / "input.zip", "w") as zipped:
        zipped.writestr("a/raw.txt", "private")
        zipped.writestr("b/raw.txt", "private")
    # When: reading strict SmartTable groups.
    with pytest.raises(RdeValidationError) as caught:
        discover_input_snapshot(ModeKind.smarttable, tmp_path, RdeConfig())
    # Then: the row and column identify the correction without cell data.
    assert caught.value.code == 4006
    assert caught.value.detail["diagnostics"][0]["row"] == 3
    assert caught.value.detail["diagnostics"][0]["column"] == "inputdata1"
    assert "secret name" not in str(caught.value)
    assert "missing.dat" not in str(caught.value)


def test_filesystem_policy_is_explicit__preview_b2(tmp_path: Path) -> None:
    # Given: a caller deliberately requests filesystem iteration order.
    # When: grouping empty MultiDataTile input.
    snapshot = discover_input_snapshot(ModeKind.multidatatile, tmp_path, RdeConfig(multidata_tile={"order": "filesystem"}))
    # Then: the preview declares its nondeterministic ordering.
    assert snapshot.iteration_policy == "filesystem"
    assert not snapshot.deterministic_order


def test_header_only_table_preserves_original_tile__preview_b3(tmp_path: Path) -> None:
    # Given: an empty SmartTable whose original file must be registered.
    table = tmp_path / "smarttable_empty.csv"
    table.write_text("name\nbasic/dataName\n")
    # When: grouping the read-only snapshot.
    snapshot = discover_input_snapshot(ModeKind.smarttable, tmp_path, RdeConfig(smarttable={"save_table_file": True}))
    # Then: the original table is tile zero and does not invoke the flow.
    assert len(snapshot.groups) == 1
    assert snapshot.groups[0].original_table
    assert snapshot.groups[0].files[0].source == table


@pytest.mark.parametrize("case_id", ["v1/smarttable/ok__cp932_zip", "v1/smarttable/ok__save_table_file", "v1/smarttable/ok__header_only__save_table_file"])
def test_smarttable_variants_match_checker__preview_p3(tmp_path: Path, case_id: str) -> None:
    # Given: the non-UTF8 and original-table compatibility corpus.
    from tests.v2.contract.fixtures import _generate
    from rdetoolkit.runner.input_snapshot import materialize_input_snapshot
    from rdetoolkit.runner.iterator import iterate_tiles

    _generate.materialize_case(_generate.oracle_case(case_id), tmp_path)
    data_root = tmp_path / "data"
    config = RdeConfig(smarttable={"save_table_file": "save_table_file" in case_id})
    # When: planning without extraction, then comparing both materializations.
    snapshot = discover_input_snapshot(ModeKind.smarttable, data_root / "inputdata", config)
    old = list(iterate_tiles(ModeKind.smarttable, data_root / "inputdata", data_root / "old", data_root, config))
    new = materialize_input_snapshot(snapshot, data_root / "new")
    # Then: original files and decoded member names stay in the same tile groups.
    assert [[path.name for path in material[0]] for material in new] == [[path.name for path in paths.rawfiles] for _, paths, _ in old]


@pytest.mark.parametrize("mode", list(ModeKind))
def test_preview_grouping_matches_real_flow_calls__preview_p1(tmp_path: Path, mode: ModeKind) -> None:
    # Given: real five-mode inputs and a flow that records its public input paths.
    from rdetoolkit.runner.lifecycle import Runner
    from rdetoolkit.runner.preview import preview_registration
    from rdetoolkit.types import InputPaths
    from tests.v2.contract.fixtures import _generate

    _generate.materialize_case(_generate.oracle_case(f"v1/{mode.value}/ok"), tmp_path)
    (tmp_path / "rdeconfig.yaml").write_text(f"system:\n  extended_mode: {mode.value}\n")
    observed: list[list[str]] = []

    def record(paths: InputPaths) -> None:
        observed.append([path.name for path in paths.rawfiles])

    # When: explaining first and then running through the actual Runner.
    preview = preview_registration(tmp_path)
    data_root = tmp_path / "data"
    report = Runner(root=tmp_path, inputdata_path=data_root / "inputdata", unpacked_dir_path=data_root / "temp").run(record)
    # Then: the calls have exactly the predicted registration membership and order.
    assert report.status == "success", report.error
    expected = [[name.rsplit("/", 1)[-1].split("!/")[-1] for name in tile.input_names] for tile in preview.tiles if tile.invokes_flow]
    assert observed == expected


@pytest.mark.parametrize("mode", [ModeKind.smarttable, ModeKind.excelinvoice])
def test_unreadable_table_is_catalogued__preview_n3(tmp_path: Path, mode: ModeKind) -> None:
    # Given: a file indicator whose payload is not a supported table.
    from rdetoolkit.errors import RdeValidationError

    filename = "smarttable_bad.csv" if mode is ModeKind.smarttable else "bad_excel_invoice.xlsx"
    (tmp_path / filename).write_text("private invalid payload")
    # When: pure discovery tries to read row groups.
    with pytest.raises(RdeValidationError) as caught:
        discover_input_snapshot(mode, tmp_path, RdeConfig())
    # Then: only a safe layout diagnostic leaves the reader boundary.
    assert caught.value.code == 4006
    assert "private invalid payload" not in str(caught.value)


def test_custom_stage_order_is_shared_by_explain__explain_p1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: a registered mode owns a nondefault validated stage order.
    from rdetoolkit.modes import registry
    from rdetoolkit.runner.preview import preview_registration
    from tests.v2.contract.fixtures import _generate

    _generate.materialize_case(_generate.oracle_case("v1/invoice/ok"), tmp_path)

    class Handler:
        kind = ModeKind.invoice

        def create_tiles(self, context: object) -> object:
            raise AssertionError("preview cannot create executable tiles")

        def artifact_stage_order(self, plan: object) -> tuple[str, ...]:
            return ("magic", "thumbnail", "description")

    monkeypatch.setattr(registry, "_HANDLERS", {ModeKind.invoice: Handler()})
    # When: preview reads the same mode capability as actual planning.
    preview = preview_registration(tmp_path)
    # Then: it preserves the provider order and describes omitted stages.
    selected = [spec.name.value for spec in preview.stages if spec.reason != "omitted_by_mode"]
    assert selected == ["magic", "thumbnail", "description"]


@pytest.mark.parametrize("order", [("magic", "magic"), ("unknown",), ("description", "magic")])
def test_invalid_custom_stage_fails_explain__explain_n1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, order: tuple[str, ...]) -> None:
    # Given: a mode capability declares an invalid stage plan.
    from rdetoolkit.errors import RdeConfigError
    from rdetoolkit.modes import registry
    from rdetoolkit.runner.preview import preview_registration
    from tests.v2.contract.fixtures import _generate

    _generate.materialize_case(_generate.oracle_case("v1/invoice/ok"), tmp_path)

    class Handler:
        kind = ModeKind.invoice

        def create_tiles(self, context: object) -> object:
            raise AssertionError("invalid stage must fail before tile creation")

        def artifact_stage_order(self, plan: object) -> tuple[str, ...]:
            return order

    monkeypatch.setattr(registry, "_HANDLERS", {ModeKind.invoice: Handler()})
    # When: explaining the selected plan.
    with pytest.raises(RdeConfigError) as caught:
        preview_registration(tmp_path)
    # Then: provider validation uses the execution catalog error.
    assert caught.value.code == 1006


@pytest.mark.parametrize("variant,expected_error", [("no_archive", False), ("single_group", False), ("group_per_row", False), ("extra_group", True), ("stray_workbook", True)])
def test_excel_group_boundaries__preview_n3(tmp_path: Path, variant: str, expected_error: bool) -> None:
    # Given: workbook/archive count and membership boundary cases.
    from rdetoolkit.errors import RdeValidationError
    from tests.v2.contract.fixtures import _generate

    _generate.materialize_case(_generate.oracle_case(f"v1/excelinvoice/ok__{variant}"), tmp_path)
    # When: discovering the workbook's current input groups.
    if expected_error:
        with pytest.raises(RdeValidationError) as caught:
            discover_input_snapshot(ModeKind.excelinvoice, tmp_path / "data/inputdata", RdeConfig())
        # Then: invalid layouts stop before archive extraction.
        assert caught.value.code == 4006
    else:
        snapshot = discover_input_snapshot(ModeKind.excelinvoice, tmp_path / "data/inputdata", RdeConfig())
        # Then: row count controls the registration groups.
        assert len(snapshot.groups) == 2


@pytest.mark.parametrize("missing", [False, True])
def test_excel_flat_names_are_unique__preview_n3(tmp_path: Path, missing: bool) -> None:
    # Given: a file-mode workbook optionally names an unavailable file.
    from openpyxl import load_workbook
    from rdetoolkit.errors import RdeValidationError
    from tests.v2.contract.fixtures import _generate

    _generate.materialize_case(_generate.oracle_case("v1/excelinvoice/ok"), tmp_path)
    inputdata = tmp_path / "data/inputdata"
    table = inputdata / "contract_excel_invoice.xlsx"
    workbook = load_workbook(table)
    sheet = workbook["invoice_form"]
    sheet["A2"] = "data_file_names"
    if missing:
        sheet["A5"] = "private nonexistent reference"
    workbook.save(table)
    workbook.close()
    # When: grouping the file-mode rows.
    if missing:
        with pytest.raises(RdeValidationError) as caught:
            discover_input_snapshot(ModeKind.excelinvoice, inputdata, RdeConfig())
        # Then: the error exposes row identity but no cell value.
        assert caught.value.code == 4006
        assert "private nonexistent reference" not in str(caught.value)
    else:
        snapshot = discover_input_snapshot(ModeKind.excelinvoice, inputdata, RdeConfig())
        # Then: each row keeps its requested filename order.
        assert [[ref.member for ref in group.files] for group in snapshot.groups] == [["test_child1.txt"], ["test_child2.txt"]]


@pytest.mark.parametrize("mode", [ModeKind.smarttable, ModeKind.excelinvoice])
def test_snapshot_requires_one_table__preview_n3(tmp_path: Path, mode: ModeKind) -> None:
    # Given: direct planning receives a special mode without its table.
    from rdetoolkit.errors import RdeValidationError

    # When: enforcing the discovery boundary.
    with pytest.raises(RdeValidationError) as caught:
        discover_input_snapshot(mode, tmp_path, RdeConfig())
    # Then: the failure remains catalogued even outside mode detection.
    assert caught.value.code == 4006


def test_unreadable_archive_is_catalogued__preview_n1(tmp_path: Path) -> None:
    # Given: an archive filename whose bytes are not a ZIP file.
    from rdetoolkit.errors import RdeValidationError
    from rdetoolkit.runner.input_snapshot import archive_references

    archive = tmp_path / "input.zip"
    archive.write_text("private broken archive")
    # When: reading its member directory.
    with pytest.raises(RdeValidationError) as caught:
        archive_references([archive])
    # Then: payload bytes do not enter its catalogued diagnostic.
    assert caught.value.code == 4006
    assert "private broken archive" not in str(caught.value)


def test_system_archive_members_are_filtered__preview_b1(tmp_path: Path) -> None:
    # Given: a ZIP contains directory entries and platform metadata.
    import zipfile
    from rdetoolkit.runner.input_snapshot import archive_references

    archive = tmp_path / "input.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("folder/", "")
        zipped.writestr("folder/.DS_Store", "metadata")
        zipped.writestr("folder/raw.txt", "raw")
    # When: reading member references without extraction.
    refs = archive_references([archive])
    # Then: excluded members cannot create registration inputs.
    assert [ref.member for ref in refs] == ["folder/raw.txt"]


def test_tasksupport_source_is_reported__explain_p1(tmp_path: Path) -> None:
    # Given: the configuration comes from the legacy tasksupport discovery path.
    from rdetoolkit.runner.preview import preview_registration
    from tests.v2.contract.fixtures import _generate

    _generate.materialize_case(_generate.oracle_case("v1/invoice/ok"), tmp_path)
    (tmp_path / "data/tasksupport/rdeconfig.yaml").write_text("system:\n  save_raw: false\n")
    # When: explaining with normal Runner configuration discovery.
    preview = preview_registration(tmp_path)
    # Then: the winning config path is available without exposing its values.
    assert preview.config_source == "data/tasksupport/rdeconfig.yaml"


def test_empty_rdeformat_archive_has_legacy_empty_group__preview_b1(tmp_path: Path) -> None:
    # Given: an empty but valid RDEFormat ZIP.
    import zipfile

    with zipfile.ZipFile(tmp_path / "empty.zip", "w"):
        pass
    # When: grouping its member directory.
    snapshot = discover_input_snapshot(ModeKind.rdeformat, tmp_path, RdeConfig())
    # Then: the existing empty registration boundary is retained.
    assert len(snapshot.groups) == 1
    assert snapshot.groups[0].files == ()
