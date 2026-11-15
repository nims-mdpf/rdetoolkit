"""RDE-009 (#642): one type source per package for cli / graph / invoicefile.

``src/rdetoolkit/{cli,graph,invoicefile}.pyi`` sat next to the real packages.
mypy and pyright both resolve ``rdetoolkit.<pkg>`` to the package directory
first (``<pkg>/__init__.pyi``, then ``<pkg>/__init__.py``), so those root
stubs were dead and partly false (``cli.run(target: str)``,
``invoicefile.AttributeConfig``). After consolidation:

* ``rdetoolkit.cli`` -- ``cli/__init__.pyi`` (new) declares the Click command
  objects Typer builds, typed as their runtime class ``typer.core.TyperCommand``
  (recent typer releases vendor Click and do not install ``click``).
* ``rdetoolkit.graph`` -- ``graph/__init__.pyi`` (RDE-003 inventory).
* ``rdetoolkit.invoicefile`` -- the re-export-only ``invoicefile/__init__.py``
  backed by the per-module stubs; no ``__init__.pyi`` is added because it
  would be a second copy of the same re-exports.

The mypy checks run outside the repository against whatever ``rdetoolkit``
the interpreter imports; under tox that is the wheel tox built and installed.

EP table:
| TC | Partition | Input | Expected |
|----|-----------|-------|----------|
| TC-642-EP-1 | CLI typing | reveal ``app`` / every command / ``workflows`` | ``Typer`` / ``typer.core.TyperCommand`` / ``_LazyModuleProxy`` |
| TC-642-EP-2 | invoicefile typing | reveal representative v1 classes/functions | equal to the pre-consolidation inference |
| TC-642-EP-3 | graph typing | reveal ``csv2graph`` / ``PlotConfig`` | real signature, not ``Any`` |
| TC-642-EP-4 | CLI stub vs runtime | stub ``__all__`` / declared names vs runtime ``__all__`` | identical; every command is a ``typer.core.TyperCommand`` |
| TC-642-EP-5 | installed distribution | ``importlib.metadata`` file list (non-editable install) | ships ``py.typed`` + package stubs, no root stubs |
| TC-642-EP-6 | runtime imports | ``import rdetoolkit.{cli,graph,invoicefile}`` | same module objects / ``__all__`` as before |

Negative table:
| TC | Partition | Input | Expected |
|----|-----------|-------|----------|
| TC-642-NG-1 | duplicate root stub | ``src/rdetoolkit/<pkg>.pyi`` | absent for cli, graph, invoicefile |
| TC-642-NG-2 | stale CLI signature | ``run.no_such_attr`` / ``run`` passed as ``int`` | ``[attr-defined]`` / ``[arg-type]`` (not ``Any``) |
| TC-642-NG-3 | false invoicefile claim | ``rdetoolkit.invoicefile.AttributeConfig`` | ``[attr-defined]`` (runtime has no such name either) |
| TC-642-NG-4 | invoicefile wrong argument | ``InvoiceFile(1)`` | ``[arg-type]`` |
| TC-642-NG-5 | unknown CLI export | ``from rdetoolkit.cli import no_such`` | ``[attr-defined]`` |
"""

from __future__ import annotations

import ast
import importlib
import importlib.metadata
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import typer.core

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PKG = PROJECT_ROOT / "src" / "rdetoolkit"
TARGET_PACKAGES = ("cli", "graph", "invoicefile")
CLI_COMMANDS = ("artifact", "csv2graph", "gen_config", "init", "make_excelinvoice", "run", "version")


def _mypy(tmp_path: Path, source: str) -> subprocess.CompletedProcess[str]:
    consumer = tmp_path / "consumer.py"
    consumer.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "--ignore-missing-imports", "--no-incremental", str(consumer)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )


def _norm(type_text: str) -> str:
    """Drop the ``builtins.`` qualifier: newer mypy releases print ``str``, older ``builtins.str``."""
    return type_text.replace("builtins.", "")


def _revealed(stdout: str) -> dict[int, str]:
    """Map consumer line number -> revealed type string (``builtins.`` normalised away)."""
    return {
        int(m.group(1)): _norm(m.group(2))
        for m in re.finditer(r'^consumer\.py:(\d+): note: Revealed type is "(.*)"$', stdout, re.MULTILINE)
    }


def _is_editable_install() -> bool:
    dist = importlib.metadata.distribution("rdetoolkit")
    direct_url = dist.read_text("direct_url.json")
    if direct_url is None:
        return False
    return bool(json.loads(direct_url).get("dir_info", {}).get("editable", False))


@pytest.mark.parametrize("package", TARGET_PACKAGES)
def test_no_duplicate_root_stub__tc_642_ng_1(package: str) -> None:
    """TC-642-NG-1: no ``<pkg>.pyi`` competes with the ``<pkg>/`` package."""
    # Given: the package directory exists
    assert (SRC_PKG / package / "__init__.py").is_file()
    # When/Then: no module-level stub of the same name sits beside it
    assert not (SRC_PKG / f"{package}.pyi").exists()


@pytest.mark.slow
def test_cli_exports_are_typed_as_click_commands__tc_642_ep_1(tmp_path: Path) -> None:
    """TC-642-EP-1: CLI typing reflects the Typer app and Click command objects."""
    # Given: a consumer revealing every CLI export
    lines = ["import rdetoolkit.cli as cli", "reveal_type(cli.app)", "reveal_type(cli.workflows)"]
    lines += [f"reveal_type(cli.{name})" for name in CLI_COMMANDS]
    # When: checked with strict mypy
    result = _mypy(tmp_path, "\n".join(lines) + "\n")
    # Then: precise types, no Any and no plain-function signature
    assert result.returncode == 0, result.stdout + result.stderr
    revealed = _revealed(result.stdout)
    assert revealed[2] == "typer.main.Typer"
    assert revealed[3] == "rdetoolkit.cli._LazyModuleProxy"
    assert [revealed[n] for n in range(4, 4 + len(CLI_COMMANDS))] == ["typer.core.TyperCommand"] * len(CLI_COMMANDS)


INVOICEFILE_EXPECTED = {
    "InvoiceFile": "def (invoice_path: pathlib.Path, *, schema_path: pathlib.Path | None =) -> rdetoolkit.invoicefile._invoice.InvoiceFile",
    "InvoiceFile.read": "def (self: rdetoolkit.invoicefile._invoice.InvoiceFile, *, target_path: pathlib.Path | None =) -> builtins.dict[Any, Any]",
    "InvoiceFile.overwrite": (
        "def (self: rdetoolkit.invoicefile._invoice.InvoiceFile, dst_file_path: pathlib.Path | None =, *, "
        "src_obj: builtins.dict[builtins.str, Any] | pathlib.Path | builtins.str | None =, schema_path: pathlib.Path | None =)"
    ),
    "InvoiceFile.copy_original_invoice": "def (src_file_path: pathlib.Path, dst_file_path: pathlib.Path)",
    "ExcelInvoiceFile": "def (invoice_path: pathlib.Path) -> rdetoolkit.invoicefile._excelinvoice.ExcelInvoiceFile",
    "SmartTableFile": "def (smarttable_path: pathlib.Path) -> rdetoolkit.invoicefile._smarttable.SmartTableFile",
    "RuleBasedReplacer": "def (*, rule_file_path: builtins.str | pathlib.Path | None =) -> rdetoolkit.invoicefile._rule_replacer.RuleBasedReplacer",
    "MagicVariableResolver": (
        "def (*, rawfile_path: pathlib.Path, invoice_source: builtins.dict[builtins.str, Any], "
        "metadata_source: builtins.dict[builtins.str, Any] | None) -> rdetoolkit.invoicefile._magic_variable.MagicVariableResolver"
    ),
    "ExcelInvoiceTemplateGenerator": "def (fixed_header: rdetoolkit.models.invoice.FixedHeaders) -> rdetoolkit.invoicefile._template.ExcelInvoiceTemplateGenerator",
    "apply_magic_variable": (
        "def (invoice_path: builtins.str | pathlib.Path, rawfile_path: builtins.str | pathlib.Path, *, "
        "save_filepath: builtins.str | pathlib.Path | None =, dataset_paths: rdetoolkit.models.rde2types.RdeDatasetPaths | None =) "
        "-> builtins.dict[builtins.str, Any]"
    ),
    "backup_invoice_json_files": "def (excel_invoice_file: pathlib.Path | None, mode: builtins.str | None) -> pathlib.Path",
    "update_description_with_features": (
        "def (rde_resource: rdetoolkit.models.rde2types.RdeOutputResourcePath, dst_invoice_json: pathlib.Path, metadata_def_json: pathlib.Path)"
    ),
    "apply_default_filename_mapping_rule": (
        "def (replacement_rule: builtins.dict[builtins.str, Any], save_file_path: builtins.str | pathlib.Path) -> builtins.dict[builtins.str, Any]"
    ),
}


@pytest.mark.slow
def test_invoicefile_types_unchanged__tc_642_ep_2(tmp_path: Path) -> None:
    """TC-642-EP-2: v1 invoicefile consumers keep the same inferred types."""
    # Given: a consumer revealing representative v1 invoice classes/functions
    names = list(INVOICEFILE_EXPECTED)
    source = "import rdetoolkit.invoicefile as inv\n" + "".join(f"reveal_type(inv.{name})\n" for name in names)
    # When: checked with strict mypy
    result = _mypy(tmp_path, source)
    # Then: every revealed type equals the pre-consolidation inference
    assert result.returncode == 0, result.stdout + result.stderr
    revealed = _revealed(result.stdout)
    assert {name: revealed[index + 2] for index, name in enumerate(names)} == {name: _norm(text) for name, text in INVOICEFILE_EXPECTED.items()}


@pytest.mark.slow
def test_graph_types_come_from_package_stub__tc_642_ep_3(tmp_path: Path) -> None:
    """TC-642-EP-3: ``rdetoolkit.graph`` typing is the RDE-003 package stub."""
    # Given: a consumer revealing the main graph entry points
    source = "import rdetoolkit.graph as g\nreveal_type(g.csv2graph)\nreveal_type(g.PlotConfig)\nreveal_type(g.GraphPlottingError)\n"
    # When: checked with strict mypy
    result = _mypy(tmp_path, source)
    # Then: real callables/classes from the graph submodules
    assert result.returncode == 0, result.stdout + result.stderr
    revealed = _revealed(result.stdout)
    assert revealed[2].startswith("def (csv_path: str | pathlib.Path, ")
    assert revealed[2].endswith(")")
    assert "rdetoolkit.graph.models.PlotConfig" in revealed[3]
    assert revealed[4] == "def (*args: object) -> rdetoolkit.graph.exceptions.GraphPlottingError"


def test_cli_stub_matches_runtime_exports__tc_642_ep_4() -> None:
    """TC-642-EP-4: the CLI package stub declares exactly the runtime exports."""
    # Given: the parsed CLI package stub and the runtime package
    from rdetoolkit import cli  # noqa: PLC0415

    tree = ast.parse((SRC_PKG / "cli" / "__init__.pyi").read_text(encoding="utf-8"))
    declared = {stmt.target.id for stmt in tree.body if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)}
    stub_all = next(
        ast.literal_eval(stmt.value)
        for stmt in tree.body
        if isinstance(stmt, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in stmt.targets)
    )
    # When/Then: stub ``__all__`` == declared names == runtime ``__all__``
    assert stub_all == list(cli.__all__)
    assert declared == set(cli.__all__)
    # And: every declared command really is a Typer-built Click command at runtime
    for name in CLI_COMMANDS:
        assert isinstance(getattr(cli, name), typer.core.TyperCommand), name


def test_installed_distribution_ships_package_stubs__tc_642_ep_5() -> None:
    """TC-642-EP-5: a built distribution carries py.typed and the final stubs only."""
    # Given: a non-editable installation (tox installs the built wheel)
    if _is_editable_install():
        pytest.skip("editable install: no built file list to inspect (runs under tox)")
    files = {str(path).replace("\\", "/") for path in importlib.metadata.files("rdetoolkit") or []}
    # When/Then: the marker and the canonical package stubs are shipped
    for required in ("rdetoolkit/py.typed", "rdetoolkit/graph/__init__.pyi", "rdetoolkit/cli/__init__.pyi", "rdetoolkit/invoicefile/__init__.py"):
        assert required in files, required
    # And: none of the removed root stubs is shipped
    for package in TARGET_PACKAGES:
        assert f"rdetoolkit/{package}.pyi" not in files, package


def test_runtime_package_imports_unchanged__tc_642_ep_6() -> None:
    """TC-642-EP-6: removing stubs leaves runtime import behaviour as it was."""
    # Given/When: importing the three packages
    modules = {name: importlib.import_module(f"rdetoolkit.{name}") for name in TARGET_PACKAGES}
    # Then: each resolves to its package ``__init__.py`` and keeps its exports
    for name, module in modules.items():
        assert module.__file__ is not None
        assert Path(module.__file__).as_posix().endswith(f"rdetoolkit/{name}/__init__.py"), module.__file__
    assert modules["cli"].__all__ == ["app", "artifact", "csv2graph", "gen_config", "init", "make_excelinvoice", "run", "version", "workflows"]
    invoice = modules["invoicefile"]
    for name in ("InvoiceFile", "ExcelInvoiceFile", "SmartTableFile", "apply_magic_variable", "read_excelinvoice", "STATIC_DIR"):
        assert name in invoice.__all__
        assert getattr(invoice, name) is not None


@pytest.mark.slow
def test_negative_consumers_are_rejected__tc_642_ng_2_to_5(tmp_path: Path) -> None:
    """TC-642-NG-2..5: false or stale declarations are rejected by strict mypy."""
    # Given: one consumer with one violation per line
    source = "\n".join([
        "from pathlib import Path",
        "import rdetoolkit.cli as cli",
        "import rdetoolkit.invoicefile as inv",
        "def takes_int(value: int) -> None: ...",
        "cli.run.no_such_attr",  # line 5: NG-2 command is not Any
        "takes_int(cli.run)",  # line 6: NG-2 command is not a plain value
        "inv.AttributeConfig",  # line 7: NG-3 root stub claimed it, runtime lacks it
        "inv.InvoiceFile(1)",  # line 8: NG-4 wrong argument
        "from rdetoolkit.cli import no_such",  # line 9: NG-5 unknown export
    ]) + "\n"
    # When: checked with strict mypy
    result = _mypy(tmp_path, source)
    # Then: exactly the expected diagnostics, line by line
    assert result.returncode == 1, result.stdout + result.stderr
    errors = re.findall(r"^consumer\.py:(\d+): error: .*\[([a-z-]+)\]$", result.stdout, re.MULTILINE)
    assert sorted((int(line), code) for line, code in errors) == [
        (5, "attr-defined"),
        (6, "arg-type"),
        (7, "attr-defined"),
        (8, "arg-type"),
        (9, "attr-defined"),
    ], result.stdout
    assert '"TyperCommand" has no attribute "no_such_attr"' in result.stdout
    # And: the runtime agrees with the type checker on the false claim
    assert not hasattr(importlib.import_module("rdetoolkit.invoicefile"), "AttributeConfig")
