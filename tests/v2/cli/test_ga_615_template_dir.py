"""GA615: ``init`` generates ``template/``; the v1 ``templates/`` layout is migrated.

EP table
========

=========================  ===============================  ==========================================  ==============
Command                    Partition                        Expected                                    Test ID
=========================  ===============================  ==========================================  ==============
init                       empty directory                  template/tasksupport created, no templates  GA615-EP-1
init                       v1 templates/tasksupport exists  warns, points to migrate apply, no template GA615-EP-2
init                       unrelated templates/ (no         template/ created, no warning               GA615-EP-3
                           tasksupport inside)
validate all               template/ layout                 no deprecation warning, exit 0              GA615-EP-4
validate all               v1 templates/ layout             schemas read, warning, exit 0 / strict 1    GA615-EP-5
validate all               both layouts                     template/ wins, no warning                  GA615-EP-6
migrate check              v1 templates/ layout             reports the old directory                   GA615-EP-7
migrate apply (dry-run)    v1 templates/ layout             previews the rename, writes nothing         GA615-EP-8
migrate apply (write)      v1 templates/ layout             output has template/, input unchanged       GA615-EP-9
migrate apply              template/ layout                 no rename reported                          GA615-EP-10
=========================  ===============================  ==========================================  ==============

BV / negative table
===================

=========================  ===============================  ==========================================  ==============
Command                    Boundary                         Expected                                    Test ID
=========================  ===============================  ==========================================  ==============
migrate apply              templates/ and template/ exist   exit 3 with remediation, nothing written    GA615-NEG-1
migrate check / apply      file argument (not a project)    no layout finding or rename                 GA615-BV-1
migrate apply              v1 templates/ only, no .py files  rename previewed / written, exit 0          GA615-BV-2
validate all               empty v1 templates/tasksupport/  deprecation reported, strict exit 1         GA615-BV-3
=========================  ===============================  ==========================================  ==============
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rdetoolkit.cli.app import app

LEGACY_MAIN = (
    "from rdetoolkit import workflows\n"
    "def dataset(srcpaths, resource_paths):\n"
    "    pass\n"
    "workflows.run(custom_dataset_function=dataset)\n"
)


def _init_project(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(root)
    result = CliRunner().invoke(app, ["init"])
    assert result.exit_code == 0, result.output


def _make_v1_project(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Build a project with the v1 layout: init output with templates/ instead of template/."""
    _init_project(root, monkeypatch)
    (root / "template").rename(root / "templates")
    (root / "container" / "main.py").write_text(LEGACY_MAIN, encoding="utf-8")


def _snapshot(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def test_init_creates_template_dir__ga615_ep_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA615-EP-1: a fresh init writes template/tasksupport and no templates/."""
    # Given/When: init in an empty directory
    _init_project(tmp_path, monkeypatch)
    # Then: the schemas are mirrored into template/tasksupport only
    assert (tmp_path / "template" / "tasksupport" / "invoice.schema.json").is_file()
    assert (tmp_path / "template" / "tasksupport" / "metadata-def.json").is_file()
    assert not (tmp_path / "templates").exists()


def test_init_warns_on_v1_layout__ga615_ep_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA615-EP-2: init in a v1 project warns and does not create a second copy."""
    # Given: a project with the v1 templates/tasksupport directory
    legacy = tmp_path / "templates" / "tasksupport"
    legacy.mkdir(parents=True)
    (legacy / "invoice.schema.json").write_text('{"kept": true}', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    # When: running init there
    result = CliRunner().invoke(app, ["init"])
    # Then: init succeeds, says how to migrate, and leaves the v1 files alone
    assert result.exit_code == 0, result.output
    assert "Warning:" in result.output
    assert "rdetoolkit migrate apply" in result.output
    assert not (tmp_path / "template").exists()
    assert (legacy / "invoice.schema.json").read_text(encoding="utf-8") == '{"kept": true}'
    assert not (legacy / "metadata-def.json").exists()
    assert (tmp_path / "container" / "data" / "tasksupport" / "metadata-def.json").is_file()


def test_init_warns_on_v1_layout_with_tasksupport_template__ga615_ep_2b(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA615-EP-2: a --tasksupport source is copied to container/ only in a v1 project."""
    # Given: a v1 project and a separate tasksupport template directory
    (tmp_path / "templates" / "tasksupport").mkdir(parents=True)
    source = tmp_path / "tpl" / "tasksupport"
    source.mkdir(parents=True)
    (source / "custom.schema.json").write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    # When: running init with --tasksupport
    result = CliRunner().invoke(app, ["init", "--tasksupport", str(source)])
    # Then: the template reaches container/ but no template/ directory is made
    assert result.exit_code == 0, result.output
    assert "rdetoolkit migrate apply" in result.output
    assert (tmp_path / "container" / "data" / "tasksupport" / "custom.schema.json").is_file()
    assert not (tmp_path / "template").exists()
    assert not (tmp_path / "templates" / "tasksupport" / "custom.schema.json").exists()


def test_init_ignores_unrelated_templates_dir__ga615_ep_3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA615-EP-3: a templates/ directory without tasksupport/ is not the v1 layout."""
    # Given: a templates/ directory used for something else
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "page.html.j2").write_text("<p></p>", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    # When: running init
    result = CliRunner().invoke(app, ["init"])
    # Then: template/ is created as usual and no warning is printed
    assert result.exit_code == 0, result.output
    assert "Warning:" not in result.output
    assert (tmp_path / "template" / "tasksupport" / "invoice.schema.json").is_file()


def _validate_json(root: Path, *extra: str) -> tuple[int, list[dict[str, object]]]:
    result = CliRunner().invoke(app, ["validate", "all", str(root), "--format", "json", *extra])
    return result.exit_code, json.loads(result.output) if result.output.strip().startswith("[") else []


def _deprecations(results: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        warning
        for result in results
        for warning in result["warnings"]  # type: ignore[attr-defined]
        if warning["type"] == "deprecated_layout"  # type: ignore[index]
    ]


def test_validate_all_new_layout__ga615_ep_4(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA615-EP-4: the generated layout validates without a deprecation warning."""
    # Given: a freshly initialized project
    _init_project(tmp_path, monkeypatch)
    # When: validating it strictly
    exit_code, results = _validate_json(tmp_path, "--strict")
    # Then: template/ schemas are validated and nothing is deprecated
    assert exit_code == 0
    targets = {str(result["target"]) for result in results}
    assert str(tmp_path / "template" / "tasksupport" / "invoice.schema.json") in targets
    assert _deprecations(results) == []


def test_validate_all_falls_back_to_v1_layout__ga615_ep_5(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA615-EP-5: templates/ is read with a warning; only --strict fails on it."""
    # Given: a v1 project
    _make_v1_project(tmp_path, monkeypatch)
    # When: validating with and without --strict
    exit_code, results = _validate_json(tmp_path)
    strict_code, _ = _validate_json(tmp_path, "--strict")
    # Then: the old schemas are validated, the warning is reported, strict fails
    assert exit_code == 0
    assert strict_code == 1
    targets = {str(result["target"]) for result in results}
    assert str(tmp_path / "templates" / "tasksupport" / "invoice.schema.json") in targets
    assert str(tmp_path / "templates" / "tasksupport" / "metadata-def.json") in targets
    deprecations = _deprecations(results)
    assert len(deprecations) == 1
    assert "rdetoolkit migrate apply" in str(deprecations[0]["message"])


def test_validate_all_text_output_shows_v1_warning__ga615_ep_5b(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA615-EP-5: the default text format shows the deprecation too."""
    # Given: a v1 project
    _make_v1_project(tmp_path, monkeypatch)
    # When: validating with the default format
    result = CliRunner().invoke(app, ["validate", "all", str(tmp_path)])
    # Then: the warning is printed and the exit code is unchanged
    assert result.exit_code == 0, result.output
    assert "deprecated_layout" in result.output


def test_validate_all_prefers_new_layout__ga615_ep_6(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA615-EP-6: when both directories exist, template/ is used without a warning."""
    # Given: an initialized project that also has a broken v1 templates/ copy
    _init_project(tmp_path, monkeypatch)
    legacy = tmp_path / "templates" / "tasksupport"
    legacy.mkdir(parents=True)
    (legacy / "invoice.schema.json").write_text("not json", encoding="utf-8")
    # When: validating strictly
    exit_code, results = _validate_json(tmp_path, "--strict")
    # Then: only template/ is read
    assert exit_code == 0
    assert all("templates" not in Path(str(result["target"])).parts for result in results)
    assert _deprecations(results) == []


def test_migrate_check_reports_v1_layout__ga615_ep_7(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA615-EP-7: migrate check lists templates/ as a finding."""
    # Given: a v1 project
    _make_v1_project(tmp_path, monkeypatch)
    # When: checking the project root
    result = CliRunner().invoke(app, ["migrate", "check", "."])
    # Then: the directory finding is reported along with the source findings
    assert result.exit_code == 0, result.output
    assert "templates: legacy templates/ directory" in result.output
    assert "custom_dataset_function keyword" in result.output


def test_migrate_apply_previews_rename__ga615_ep_8(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA615-EP-8: the dry-run lists the directory move next to the conversions."""
    # Given: a v1 project
    project = tmp_path / "project"
    _make_v1_project(project, monkeypatch)
    before = _snapshot(project)
    # When: previewing the migration
    result = CliRunner().invoke(app, ["migrate", "apply", str(project)])
    # Then: the rename and the conversion are both previewed and nothing is written
    assert result.exit_code == 0, result.output
    destination = tmp_path / "project_migrated"
    assert f"--- {project / 'templates'} -> {destination / 'template'} (dry-run, directory rename) ---" in result.output
    assert "def pipeline" in result.output
    assert not destination.exists()
    assert _snapshot(project) == before


def test_migrate_apply_writes_template_dir__ga615_ep_9(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA615-EP-9: the written output has template/; the input keeps templates/."""
    # Given: a v1 project
    project = tmp_path / "project"
    _make_v1_project(project, monkeypatch)
    before = _snapshot(project)
    destination = tmp_path / "out"
    # When: writing the migration to --out
    result = CliRunner().invoke(app, ["migrate", "apply", str(project), "--output", str(destination), "--no-dry-run"])
    # Then: the schemas move to template/ in the output only
    assert result.exit_code == 0, result.output
    assert "Renamed templates/ to template/" in result.output
    assert not (destination / "templates").exists()
    for name in ("invoice.schema.json", "metadata-def.json"):
        assert (destination / "template" / "tasksupport" / name).read_bytes() == before[f"templates/tasksupport/{name}"]
    assert "def pipeline" in (destination / "container" / "main.py").read_text(encoding="utf-8")
    assert _snapshot(project) == before


def test_migrate_apply_new_layout_has_no_rename__ga615_ep_10(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA615-EP-10: a project already on template/ is copied as is."""
    # Given: a project with the new layout and a v1 callback
    project = tmp_path / "project"
    _init_project(project, monkeypatch)
    (project / "container" / "main.py").write_text(LEGACY_MAIN, encoding="utf-8")
    # When: previewing and writing the migration
    preview = CliRunner().invoke(app, ["migrate", "apply", str(project)])
    written = CliRunner().invoke(app, ["migrate", "apply", str(project), "--no-dry-run"])
    # Then: no rename is reported and template/ is carried over
    assert preview.exit_code == 0, preview.output
    assert written.exit_code == 0, written.output
    assert "directory rename" not in preview.output
    assert "Renamed" not in written.output
    assert (tmp_path / "project_migrated" / "template" / "tasksupport" / "invoice.schema.json").is_file()


@pytest.mark.parametrize("write", [False, True])
def test_migrate_apply_rejects_both_layouts__ga615_neg_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, write: bool) -> None:
    """GA615-NEG-1: templates/ and template/ together are a usage error, never merged."""
    # Given: a v1 project that also has template/
    project = tmp_path / "project"
    _make_v1_project(project, monkeypatch)
    (project / "template").mkdir()
    before = _snapshot(project)
    # When: migrating it
    result = CliRunner().invoke(app, ["migrate", "apply", str(project), *(["--no-dry-run"] if write else [])])
    # Then: exit 3 with a remediation and no output directory
    assert result.exit_code == 3
    assert "Both templates/ and template/ exist" in result.output
    assert "Remediation:" in result.output
    assert not (tmp_path / "project_migrated").exists()
    assert _snapshot(project) == before


def test_migrate_file_argument_has_no_layout_handling__ga615_bv_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA615-BV-1: a single-file argument never reports or renames a directory."""
    # Given: a v1 project, migrated by naming main.py directly
    project = tmp_path / "project"
    _make_v1_project(project, monkeypatch)
    main = project / "container" / "main.py"
    # When: checking and applying on the file
    check = CliRunner().invoke(app, ["migrate", "check", str(main)])
    preview = CliRunner().invoke(app, ["migrate", "apply", str(main)])
    # Then: only source findings appear
    assert check.exit_code == 0, check.output
    assert preview.exit_code == 0, preview.output
    assert "legacy templates/" not in check.output
    assert "directory rename" not in preview.output


@pytest.mark.parametrize("write", [False, True])
def test_migrate_apply_renames_without_python_files__ga615_bv_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, write: bool) -> None:
    """GA615-BV-2: a project with only the v1 template directory is still migrated."""
    # Given: a directory holding templates/tasksupport/metadata-def.json and no Python file
    project = tmp_path / "project"
    legacy = project / "templates" / "tasksupport"
    legacy.mkdir(parents=True)
    (legacy / "metadata-def.json").write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    before = _snapshot(project)
    destination = tmp_path / "project_migrated"
    # When: previewing or writing the migration
    result = CliRunner().invoke(app, ["migrate", "apply", str(project), *(["--no-dry-run"] if write else [])])
    # Then: the rename is handled instead of rejecting the input
    assert result.exit_code == 0, result.output
    assert "No Python files found" not in result.output
    if write:
        assert "Renamed templates/ to template/" in result.output
        assert (destination / "template" / "tasksupport" / "metadata-def.json").read_text(encoding="utf-8") == "{}"
        assert not (destination / "templates").exists()
    else:
        assert f"--- {project / 'templates'} -> {destination / 'template'} (dry-run, directory rename) ---" in result.output
        assert not destination.exists()
    assert _snapshot(project) == before


def test_validate_all_empty_v1_layout_warns__ga615_bv_3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GA615-BV-3: an empty templates/tasksupport/ still reports the deprecation."""
    # Given: a directory whose only RDE content is an empty v1 template directory
    (tmp_path / "templates" / "tasksupport").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    # When: validating with and without --strict
    exit_code, results = _validate_json(tmp_path)
    strict_code, _ = _validate_json(tmp_path, "--strict")
    # Then: the warning is reported and only --strict fails on it
    assert exit_code == 0
    assert strict_code == 1
    assert len(_deprecations(results)) == 1
