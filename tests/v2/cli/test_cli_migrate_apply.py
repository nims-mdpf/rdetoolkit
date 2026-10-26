"""Session F3 acceptance tests for ``rdetoolkit migrate apply``.

EP table
========

=======================  ========================  ====================================  ====================
Input / option           Partition                 Expected                              Test ID
=======================  ========================  ====================================  ====================
five-case corpus         ``--no-dry-run``          >=4/5 executable via ``run_flow``     TC-MIG-APPLY-EP-001
legacy directory         default dry-run           preview only; no filesystem mutation  TC-MIG-APPLY-EP-002
dynamic dispatch case    unconvertible construct   TODO emitted; exit 0                  TC-MIG-APPLY-EP-003
missing input path       Click path validation     exit 2                                TC-MIG-APPLY-EP-004
output inside input      unsafe destination        exit 3 with remediation               TC-MIG-APPLY-EP-005
existing output          overwrite attempt         exit 3 with remediation               TC-MIG-APPLY-EP-006
directory without Python application usage error   exit 3 with remediation               TC-MIG-APPLY-EP-007
PEP 263 CP932 source    declared non-UTF-8 input    conversion succeeds as UTF-8 output  TC-MIG-APPLY-EP-008
broken encoded source  sibling valid source        diagnose and continue, exit 0         TC-MIG-APPLY-EP-009
top-level run(...)     no ``__main__`` guard       call removed; module imports          TC-MIG-APPLY-EP-010
guarded run(...)       ``__main__`` guard          guard removed; module imports         TC-MIG-APPLY-EP-011
top-level other call   no callback keyword         statement kept                        TC-MIG-APPLY-EP-012
=======================  ========================  ====================================  ====================

BV table
========

=======================  ========================  ====================================  ====================
Input / option           Boundary                  Expected                              Test ID
=======================  ========================  ====================================  ====================
one Python source        ``--no-dry-run``          one external converted file           TC-MIG-APPLY-BV-001
five corpus cases        4/5 threshold             successful count >=4                  TC-MIG-APPLY-BV-002
=======================  ========================  ====================================  ====================
"""

from __future__ import annotations

import hashlib
import importlib.util
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any, cast

from typer.testing import CliRunner

from rdetoolkit.cli.app import app
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.testing import run_flow

CORPUS = Path(__file__).parent / "fixtures" / "migrate_corpus"


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        digest.update(str(path.relative_to(root)).encode())
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _load_pipeline(path: Path, module_name: str) -> Callable[..., Any]:
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return cast(Callable[..., Any], getattr(cast(ModuleType, module), "pipeline"))


def test_apply_converts_at_least_four_of_five_corpus_cases__tc_mig_apply_ep_001_bv_002(
    tmp_path: Path,
) -> None:
    """TC-MIG-APPLY-EP-001/BV-002: the fixed representative corpus clears ADR-021's 80% bar."""
    # Given: the five binding representative v1 templates and one real input fixture
    source = tmp_path / "source"
    shutil.copytree(CORPUS, source)
    output = tmp_path / "migrated"
    fixture_dir = tmp_path / "fixture"
    fixture_dir.mkdir()
    (fixture_dir / "sample.txt").write_text("sample", encoding="utf-8")

    # When: apply writes converted files to a separate tree
    result = CliRunner().invoke(
        app,
        ["migrate", "apply", str(source), "--out", str(output), "--no-dry-run"],
    )

    # Then: at least four converted pipelines import and execute through the public level-3 helper
    assert result.exit_code == 0, result.output
    reports: list[RunReport] = []
    for index, main_path in enumerate(sorted(output.glob("case*/main.py")), start=1):
        try:
            pipeline = _load_pipeline(main_path, f"migrated_case_{index}")
            reports.append(run_flow(pipeline, fixture_dir))
        except Exception:  # noqa: BLE001
            continue
    assert sum(report.status == "success" for report in reports) >= 4


def test_apply_defaults_to_dry_run_without_mutation__tc_mig_apply_ep_002(tmp_path: Path) -> None:
    """TC-MIG-APPLY-EP-002: the default command previews and writes nowhere."""
    # Given: a copied source tree and its content digest
    source = tmp_path / "source"
    shutil.copytree(CORPUS, source)
    before = _tree_digest(source)
    default_output = source.with_name("source_migrated")

    # When: apply is invoked without the explicit write flag
    result = CliRunner().invoke(app, ["migrate", "apply", str(source)])

    # Then: conversion succeeds as a preview and neither tree is mutated/created
    assert result.exit_code == 0, result.output
    assert "dry-run" in result.output.lower()
    assert _tree_digest(source) == before
    assert not default_output.exists()


def test_apply_marks_dynamic_dispatch_with_todo__tc_mig_apply_ep_003(tmp_path: Path) -> None:
    """TC-MIG-APPLY-EP-003: unresolved dynamic behavior is visible but not a command failure."""
    # Given: the required dynamic-dispatch corpus case
    source = CORPUS / "case05_dynamic" / "main.py"
    output = tmp_path / "migrated"

    # When: apply writes its best-effort conversion
    result = CliRunner().invoke(
        app,
        ["migrate", "apply", str(source), "--out", str(output), "--no-dry-run"],
    )

    # Then: the command exits zero and the output embeds an actionable TODO
    assert result.exit_code == 0, result.output
    converted = (output / "main.py").read_text(encoding="utf-8")
    assert "TODO(rdetoolkit-migrate)" in converted
    assert "dynamic dispatch" in converted


def test_apply_missing_input_uses_click_exit_2__tc_mig_apply_ep_004(tmp_path: Path) -> None:
    """TC-MIG-APPLY-EP-004: Click owns validation of a nonexistent input path."""
    # Given: a path that does not exist
    missing = tmp_path / "missing"
    # When: apply receives it
    result = CliRunner().invoke(app, ["migrate", "apply", str(missing)])
    # Then: Click's path validation exit code is preserved
    assert result.exit_code == 2


def test_apply_rejects_output_inside_input__tc_mig_apply_ep_005(tmp_path: Path) -> None:
    """TC-MIG-APPLY-EP-005: apply never writes into its input tree."""
    # Given: an input directory and an unsafe nested destination
    source = tmp_path / "source"
    shutil.copytree(CORPUS, source)
    # When: explicit writing targets a child of the input
    result = CliRunner().invoke(
        app,
        ["migrate", "apply", str(source), "--out", str(source / "migrated"), "--no-dry-run"],
    )
    # Then: an application usage error embeds remediation
    assert result.exit_code == 3
    assert "Remediation:" in result.output


def test_apply_rejects_existing_output__tc_mig_apply_ep_006(tmp_path: Path) -> None:
    """TC-MIG-APPLY-EP-006: existing destinations are not overwritten."""
    # Given: a source file and an already existing external output directory
    source = CORPUS / "case01_init" / "main.py"
    output = tmp_path / "existing"
    output.mkdir()
    # When: apply would overwrite that destination
    result = CliRunner().invoke(
        app,
        ["migrate", "apply", str(source), "--out", str(output), "--no-dry-run"],
    )
    # Then: it fails as a remediable usage error
    assert result.exit_code == 3
    assert "Remediation:" in result.output


def test_apply_rejects_directory_without_python__tc_mig_apply_ep_007(tmp_path: Path) -> None:
    """TC-MIG-APPLY-EP-007: an existing but non-convertible input is a usage error."""
    # Given: an input directory with no Python source
    source = tmp_path / "empty"
    source.mkdir()
    (source / "README.txt").write_text("nothing to migrate", encoding="utf-8")
    # When: apply scans it
    result = CliRunner().invoke(app, ["migrate", "apply", str(source)])
    # Then: it explains how to supply a convertible target
    assert result.exit_code == 3
    assert "Remediation:" in result.output


def test_apply_single_file_writes_one_external_file__tc_mig_apply_bv_001(tmp_path: Path) -> None:
    """TC-MIG-APPLY-BV-001: the smallest write conversion creates exactly one file."""
    # Given: one legacy Python file and a non-existing external directory
    source = CORPUS / "case01_init" / "main.py"
    output = tmp_path / "single"
    before = source.read_bytes()
    # When: apply is explicitly allowed to write
    result = CliRunner().invoke(
        app,
        ["migrate", "apply", str(source), "--out", str(output), "--no-dry-run"],
    )
    # Then: one converted file is written and the input remains byte-identical
    assert result.exit_code == 0, result.output
    assert [path.name for path in output.iterdir()] == ["main.py"]
    assert source.read_bytes() == before


def test_apply_reads_pep263_cp932_source__tc_mig_apply_ep_008(tmp_path: Path) -> None:
    """TC-MIG-APPLY-EP-008: declared source encodings are honored on input."""
    # Given: a CP932 v1 source with an encoding cookie and Japanese comment
    source = tmp_path / "legacy_cp932.py"
    text = (
        "# -*- coding: cp932 -*-\n"
        "# 日本語のコメント\n"
        "from rdetoolkit import workflows\n\n"
        "def dataset(src, resource_paths):\n"
        "    return None\n\n"
        "workflows.run(custom_dataset_function=dataset)\n"
    )
    source.write_bytes(text.encode("cp932"))
    output = tmp_path / "converted"

    # When: apply reads using the declared PEP 263 encoding
    result = CliRunner().invoke(
        app,
        ["migrate", "apply", str(source), "--out", str(output), "--no-dry-run"],
    )

    # Then: conversion succeeds and the output contract remains UTF-8
    assert result.exit_code == 0, result.output
    converted = (output / source.name).read_text(encoding="utf-8")
    assert "@flow" in converted
    assert "def pipeline" in converted


def test_apply_reports_broken_encoding_and_continues__tc_mig_apply_ep_009(tmp_path: Path) -> None:
    """TC-MIG-APPLY-EP-009: one undecodable file cannot abort a directory apply."""
    # Given: one malformed declared-UTF-8 source beside one valid v1 source
    source = tmp_path / "sources"
    source.mkdir()
    broken = source / "broken.py"
    broken.write_bytes(b"# coding: utf-8\n# \xff\n")
    valid = source / "valid.py"
    valid.write_text(
        "from rdetoolkit import workflows\n"
        "def dataset(src, resource_paths):\n    return None\n"
        "workflows.run(custom_dataset_function=dataset)\n",
        encoding="utf-8",
    )
    output = tmp_path / "converted"

    # When: apply processes the directory
    result = CliRunner().invoke(
        app,
        ["migrate", "apply", str(source), "--out", str(output), "--no-dry-run"],
    )

    # Then: it diagnoses the file, continues, and preserves the current success exit convention
    assert result.exit_code == 0, result.output
    assert "broken.py" in result.output
    assert "Remediation:" in result.output
    assert "@flow" in (output / "valid.py").read_text(encoding="utf-8")
    assert "TODO(rdetoolkit-migrate)" in (output / "broken.py").read_text(encoding="utf-8")


_TOP_LEVEL_SOURCE = (
    "from rdetoolkit import workflows\n\n"
    "MARKERS = []\n\n"
    "def process(srcpaths, resource_paths):\n"
    "    return None\n\n"
    "MARKERS.append('kept')\n"
    "workflows.run(custom_dataset_function=process)\n"
)


def _apply_single(tmp_path: Path, text: str) -> str:
    source = tmp_path / "legacy_main.py"
    source.write_text(text, encoding="utf-8")
    output = tmp_path / "converted"
    result = CliRunner().invoke(
        app,
        ["migrate", "apply", str(source), "--out", str(output), "--no-dry-run"],
    )
    assert result.exit_code == 0, result.output
    return str(output / source.name)


def test_apply_removes_top_level_callback_run__tc_mig_apply_ep_010(tmp_path: Path) -> None:
    """TC-MIG-APPLY-EP-010: an unguarded top-level run(custom_dataset_function=...) is removed."""
    # Given: a v1 script calling workflows.run at module level, with no __main__ guard
    # When: apply converts it
    converted_path = Path(_apply_single(tmp_path, _TOP_LEVEL_SOURCE))

    # Then: the old call is gone, so the renamed callback is never referenced
    converted = converted_path.read_text(encoding="utf-8")
    assert "custom_dataset_function" not in converted
    assert "def pipeline" in converted

    # Then: importing the migrated module succeeds and exposes the pipeline flow
    pipeline = _load_pipeline(converted_path, "migrated_top_level_ep_010")
    assert callable(pipeline)


def test_apply_removes_guarded_callback_run__tc_mig_apply_ep_011(tmp_path: Path) -> None:
    """TC-MIG-APPLY-EP-011: the __main__-guarded run(custom_dataset_function=...) is still removed."""
    # Given: a v1 script whose workflows.run call sits under the __main__ guard
    text = (
        "from rdetoolkit import workflows\n\n"
        "def process(srcpaths, resource_paths):\n"
        "    return None\n\n"
        "if __name__ == '__main__':\n"
        "    workflows.run(custom_dataset_function=process)\n"
    )

    # When: apply converts it
    converted_path = Path(_apply_single(tmp_path, text))

    # Then: the guard and its call are gone and the module imports
    converted = converted_path.read_text(encoding="utf-8")
    assert "custom_dataset_function" not in converted
    assert "__main__" not in converted
    assert callable(_load_pipeline(converted_path, "migrated_guarded_ep_011"))


def test_apply_keeps_other_top_level_calls__tc_mig_apply_ep_012(tmp_path: Path) -> None:
    """TC-MIG-APPLY-EP-012: a top-level call without the callback keyword survives."""
    # Given: a v1 script with an unrelated module-level call beside the run call
    # When: apply converts it
    converted_path = Path(_apply_single(tmp_path, _TOP_LEVEL_SOURCE))

    # Then: only the callback run call was removed
    converted = converted_path.read_text(encoding="utf-8")
    assert "MARKERS.append('kept')" in converted


def test_apply_keeps_a_wrapper_function_syntactically_valid__tc_mig_apply_ep_013(tmp_path: Path) -> None:
    """TC-MIG-APPLY-EP-013: removing the run call from ``def main():`` leaves a ``pass`` body.

    PR #556 review R2: the emptied wrapper was rendered as a bare ``def main():``
    header, an IndentationError on import.
    """
    # Given: a v1 script whose workflows.run call is the only statement of a wrapper function
    text = (
        "from rdetoolkit import workflows\n\n"
        "def process(srcpaths, resource_paths):\n"
        "    return None\n\n"
        "def main():\n"
        "    workflows.run(custom_dataset_function=process)\n\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )

    # When: apply converts it
    converted_path = Path(_apply_single(tmp_path, text))

    # Then: the call is gone, the wrapper keeps a body, and the module imports
    converted = converted_path.read_text(encoding="utf-8")
    assert "custom_dataset_function" not in converted
    assert "def main():\n    pass\n" in converted
    compile(converted, str(converted_path), "exec")
    assert callable(_load_pipeline(converted_path, "migrated_wrapper_ep_013"))
