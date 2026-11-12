"""Issue #637 (RDE-001): the top-level ``rdetoolkit`` API is one synchronized inventory.

The supported top-level surface is declared four times — the runtime lazy tables
(``_LAZY_ATTRS`` / ``_LAZY_MODULES``), ``__all__``, ``__dir__`` and the shipped
``__init__.pyi`` stub. These tests keep the four in lock-step so star imports, IDE
completion and static type checking agree, and pin the import-safety baseline
(a bare ``import rdetoolkit`` loads no submodule and no heavy dependency).

EP/BV table:

| ID | Input / partition | Class | Expected |
|----|-------------------|-------|----------|
| TC-API637-001 | runtime ``__all__`` vs lazy tables | positive | equal sets, no duplicates |
| TC-API637-002 | ``node`` / ``flow`` / ``as_node`` | positive | in ``__all__`` and in the stub |
| TC-API637-003 | every ``__all__`` name, ``from rdetoolkit import X`` | positive (param) | import succeeds, not ``None`` |
| TC-API637-004 | stub ``__all__`` literal vs runtime ``__all__`` | positive | identical list |
| TC-API637-005 | stub-bound names vs runtime ``__all__`` | positive | identical set |
| TC-API637-006 | stub re-export source vs runtime object (fresh interpreter) | positive | same object |
| TC-API637-007 | stub ``def`` vs runtime callable | positive | same parameter list |
| TC-API637-008 | ``from rdetoolkit import *`` | positive | binds every ``__all__`` name incl. decorators |
| TC-API637-009 | ``dir(rdetoolkit)`` | positive | superset of ``__all__`` |
| TC-API637-010 | strict mypy client snippet | positive | exit 0 |
| TC-API637-011 | unknown attribute | negative | ``AttributeError`` |
| TC-API637-012 | unknown ``from`` import | negative | ``ImportError`` |
| TC-API637-013 | private / helper names | negative | not in ``__all__``, not star-imported |
| TC-API637-014 | ``__all__`` underscore entries | negative (BV) | only ``__version__`` |
| TC-API637-015 | bare ``import rdetoolkit`` | negative | no submodule, no heavy dependency in ``sys.modules`` |
| TC-API637-016 | mypy: unknown top-level attribute | negative | ``[attr-defined]`` |
| TC-API637-017 | mypy: wrong type from a top-level export | negative | ``[assignment]`` (types are not ``Any``) |
| TC-API637-018 | mypy: unknown ``from`` import | negative | ``[attr-defined]`` |
| TC-API637-019 | docs top-level table vs ``__all__`` | positive | supported names == ``__all__`` minus legacy |
| TC-API637-020 | docs table never promises ``get_agent_guide`` | negative | absent (slated for removal, #644) |
"""

from __future__ import annotations

import ast
import inspect
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

import rdetoolkit

_PACKAGE_DIR = Path(rdetoolkit.__file__).parent
_STUB_PATH = _PACKAGE_DIR / "__init__.pyi"
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DOCS = (_REPO_ROOT / "docs" / "api" / "index.en.md", _REPO_ROOT / "docs" / "api" / "index.ja.md")

# Kept exported only for the v1 oracle (tests/test_package_exports.py); RDE-005 (#644)
# removes it, so the docs must not list it as part of the supported surface.
_LEGACY_EXPORTS = frozenset({"get_agent_guide"})

# Heavy or optional third-party dependencies that must stay out of a bare import.
_HEAVY_MODULES = (
    "pandas",
    "polars",
    "numpy",
    "matplotlib",
    "PIL",
    "openpyxl",
    "plotly",
    "minio",
    "pydantic",
    "typer",
    "yaml",
    "jsonschema",
)


def _stub_tree() -> ast.Module:
    return ast.parse(_STUB_PATH.read_text(encoding="utf-8"))


def _stub_all() -> list[str]:
    for stmt in _stub_tree().body:
        target: ast.expr | None = None
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
            target, value = stmt.targets[0], stmt.value
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            target, value = stmt.target, stmt.value
        if isinstance(target, ast.Name) and target.id == "__all__":
            return list(ast.literal_eval(value))
    msg = "__init__.pyi does not declare a literal __all__"
    raise AssertionError(msg)


def _stub_bindings() -> dict[str, ast.stmt]:
    """Map every top-level name the stub binds to the statement binding it."""
    bound: dict[str, ast.stmt] = {}
    for stmt in _stub_tree().body:
        if isinstance(stmt, ast.ImportFrom):
            for alias in stmt.names:
                bound[alias.asname or alias.name] = stmt
        elif isinstance(stmt, (ast.FunctionDef, ast.ClassDef)):
            bound[stmt.name] = stmt
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            bound[stmt.target.id] = stmt
        elif isinstance(stmt, ast.Assign):
            bound.update({t.id: stmt for t in stmt.targets if isinstance(t, ast.Name)})
    bound.pop("__all__", None)
    return bound


def _stub_reexports() -> list[tuple[str, str, str]]:
    """``(exported_name, source_module, source_attr)`` for every stub re-export."""
    rows: list[tuple[str, str, str]] = []
    for stmt in _stub_tree().body:
        if isinstance(stmt, ast.ImportFrom):
            module = stmt.module or ""
            if stmt.level:
                module = "rdetoolkit" + (f".{module}" if module else "")
            rows.extend((alias.asname or alias.name, module, alias.name) for alias in stmt.names)
    return sorted(rows)


def _run_python(source: str) -> Any:
    result = subprocess.run(
        [sys.executable, "-c", source], capture_output=True, text=True, check=False, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def _mypy(tmp_path: Path, source: str) -> subprocess.CompletedProcess[str]:
    consumer = tmp_path / "consumer.py"
    consumer.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "--no-incremental", "--show-error-codes", str(consumer)],
        cwd=tmp_path, capture_output=True, text=True, check=False, timeout=300,
    )


def _docs_table_names(doc: Path) -> list[str]:
    text = doc.read_text(encoding="utf-8")
    block = re.search(r"<!-- top-level-api:start -->(.*?)<!-- top-level-api:end -->", text, re.S)
    assert block is not None, f"{doc} has no top-level API table"
    return re.findall(r"^\|\s*`([A-Za-z_][A-Za-z0-9_]*)`\s*\|", block.group(1), re.M)


# --- runtime inventory ---------------------------------------------------------


def test_all_equals_lazy_tables__tc_api637_001() -> None:
    """TC-API637-001: ``__all__`` is exactly the lazy tables plus ``__version__``."""
    # Given: the runtime declarations
    lazy = set(rdetoolkit._LAZY_ATTRS) | set(rdetoolkit._LAZY_MODULES)
    # When: comparing them with __all__
    exported = list(rdetoolkit.__all__)
    # Then: one inventory, no duplicates, no overlap between the two tables
    assert len(exported) == len(set(exported))
    assert set(exported) == lazy | {"__version__"}
    assert set(rdetoolkit._LAZY_ATTRS).isdisjoint(rdetoolkit._LAZY_MODULES)


@pytest.mark.parametrize("name", ["node", "flow", "as_node"])
def test_v2_decorators_are_canonical_exports__tc_api637_002(name: str) -> None:
    """TC-API637-002: the v2 decorators are in ``__all__`` and in the stub."""
    # Given/When: the runtime and stub inventories
    # Then: the decorator is declared in both
    assert name in rdetoolkit.__all__
    assert name in _stub_all()
    assert name in _stub_bindings()


@pytest.mark.parametrize("name", sorted(rdetoolkit.__all__))
def test_every_exported_name_imports__tc_api637_003(name: str) -> None:
    """TC-API637-003: no ``__all__`` entry lacks a working runtime import."""
    # Given: a declared public name
    namespace: dict[str, Any] = {}
    # When: importing it the way users do
    exec(f"from rdetoolkit import {name}", namespace)  # noqa: S102
    # Then: it resolves to a real object
    assert namespace[name] is not None


def test_stub_all_matches_runtime_all__tc_api637_004() -> None:
    """TC-API637-004: the stub's ``__all__`` literal is the runtime list."""
    # Given/When: both lists
    # Then: they are identical (order included, so diffs stay reviewable)
    assert _stub_all() == list(rdetoolkit.__all__)


def test_stub_binds_exactly_the_public_names__tc_api637_005() -> None:
    """TC-API637-005: the stub declares every public name and nothing else."""
    # Given: names bound at stub top level
    bound = set(_stub_bindings())
    # When/Then: they equal the runtime public inventory
    assert sorted(bound - set(rdetoolkit.__all__)) == []
    assert sorted(set(rdetoolkit.__all__) - bound) == []


def test_stub_reexports_point_at_runtime_objects__tc_api637_006() -> None:
    """TC-API637-006: each stub re-export names the object the runtime returns.

    Checked in a fresh interpreter: ``rdetoolkit.config`` is a lazy alias of
    ``rdetoolkit.models.config`` that a later ``import rdetoolkit.config`` (the v1
    config-parsing package) rebinds, so only first resolution is a stable contract.
    """
    # Given: the stub claims each ``name`` is ``module.attr``
    rows = _stub_reexports()
    assert rows
    # When: resolving every name through the lazy package attribute first
    result = _run_python(
        f"""
import importlib, json
import rdetoolkit
rows = {rows!r}
actual = {{name: getattr(rdetoolkit, name) for name, _, _ in rows}}
bad = []
for name, module, attr in rows:
    source = importlib.import_module(module)
    expected = getattr(source, attr, None)
    if expected is None:
        expected = importlib.import_module(module + "." + attr)
    if actual[name] is not expected:
        bad.append(name)
print(json.dumps(bad))
""",
    )
    # Then: both resolve to the same object, so the stub type is accurate
    assert result == []


def test_stub_functions_match_runtime_signature__tc_api637_007() -> None:
    """TC-API637-007: functions defined inline in the stub keep the runtime parameters."""
    # Given: inline stub definitions
    defs = [s for s in _stub_bindings().values() if isinstance(s, ast.FunctionDef)]
    assert defs
    for stub_def in defs:
        # When: reading the runtime signature
        runtime = inspect.signature(getattr(rdetoolkit, stub_def.name))
        stub_params = [a.arg for a in stub_def.args.args]
        # Then: parameter names and defaults agree
        assert stub_params == list(runtime.parameters), stub_def.name
        assert len(stub_def.args.defaults) == sum(
            p.default is not inspect.Parameter.empty for p in runtime.parameters.values()
        )


def test_star_import_exports_decorators__tc_api637_008() -> None:
    """TC-API637-008: ``from rdetoolkit import *`` binds the whole public API."""
    # Given/When: a fresh interpreter doing a star import
    result = _run_python(
        """
import json
ns = {}
exec("from rdetoolkit import *", ns)
import rdetoolkit
print(json.dumps({
    "missing": sorted(set(rdetoolkit.__all__) - set(ns)),
    "decorators": [callable(ns.get(n)) for n in ("node", "flow", "as_node")],
    "leaked": sorted(n for n in ("import_module", "sys", "Any", "annotations") if n in ns),
}))
""",
    )
    # Then: every name arrives, the decorators are callable, helpers stay out
    assert result == {"missing": [], "decorators": [True, True, True], "leaked": []}


def test_dir_lists_every_public_name__tc_api637_009() -> None:
    """TC-API637-009: ``dir()`` exposes the public API even before lazy loading."""
    # Given/When: dir() of the package
    listed = set(dir(rdetoolkit))
    # Then: all public names are discoverable
    assert sorted(set(rdetoolkit.__all__) - listed) == []


# --- negative runtime cases ----------------------------------------------------


@pytest.mark.parametrize("name", ["not_a_symbol", "modeproc", "Node", "get_guide"])
def test_unknown_attribute_raises__tc_api637_011(name: str) -> None:
    """TC-API637-011: undeclared names are not reachable as attributes."""
    # Given/When/Then: attribute access fails with AttributeError
    with pytest.raises(AttributeError, match=name):
        getattr(rdetoolkit, name)


def test_unknown_from_import_raises__tc_api637_012() -> None:
    """TC-API637-012: ``from rdetoolkit import <unknown>`` fails with ``ImportError``."""
    # Given/When/Then
    with pytest.raises(ImportError):
        exec("from rdetoolkit import not_a_symbol", {})  # noqa: S102


@pytest.mark.parametrize("name", ["import_module", "sys", "Any", "_LAZY_ATTRS", "_LAZY_MODULES"])
def test_helpers_are_not_public__tc_api637_013(name: str) -> None:
    """TC-API637-013: implementation helpers never join the public inventory."""
    # Given/When/Then: absent from __all__ and from the stub
    assert name not in rdetoolkit.__all__
    assert name not in _stub_bindings()


def test_only_version_dunder_is_exported__tc_api637_014() -> None:
    """TC-API637-014 (BV): ``__version__`` is the only underscore-prefixed export."""
    # Given/When/Then
    assert [n for n in rdetoolkit.__all__ if n.startswith("_")] == ["__version__"]


def test_bare_import_is_lazy__tc_api637_015() -> None:
    """TC-API637-015: bare ``import rdetoolkit`` loads no submodule or heavy dependency."""
    # Given/When: a fresh interpreter importing only the package
    result = _run_python(
        f"""
import json, sys
import rdetoolkit
print(json.dumps({{
    "submodules": sorted(m for m in sys.modules if m.startswith("rdetoolkit.")),
    "heavy": sorted(m for m in {list(_HEAVY_MODULES)!r} if m in sys.modules),
}}))
""",
    )
    # Then: the current baseline (nothing beyond the package itself) holds
    assert result == {"submodules": [], "heavy": []}


# --- static typing (strict mypy client) ------------------------------------------

_POSITIVE_CLIENT = '''from pathlib import Path
from types import ModuleType

import rdetoolkit
from rdetoolkit import (
    DirectoryOps,
    Failure,
    ManagedDirectory,
    Result,
    Success,
    as_node,
    detect_encoding,
    flow,
    node,
    resize_image_aspect_ratio,
    try_result,
)
from rdetoolkit.types import InputPaths


@node
def double(x: int) -> int:
    return x * 2


@node(tags=["io"], version="1.0.0")
def tagged(x: int) -> int:
    return x


@flow
def pipeline(paths: InputPaths) -> None:
    doubled: int = double(1)
    del doubled, paths


@try_result
def parse(text: str) -> int:
    return int(text)


def check(r: Result[int, Exception]) -> bool:
    return r.is_success()


def use(directory: DirectoryOps, managed: ManagedDirectory) -> None:
    encoding: str = detect_encoding("x.txt")
    resize_image_aspect_ratio("in.png", "out.png", 10, 10)
    del encoding, directory, managed


version: str = rdetoolkit.__version__
names: list[str] = rdetoolkit.__all__
ok: Success[int] = Success(1)
bad: Failure[ValueError] = Failure(ValueError("x"))
parsed: Result[int, Exception] = parse("1")
guide: str = rdetoolkit.get_agent_guide(detailed=False)
adapter = as_node(object(), method="run")
modules: list[ModuleType] = [
    rdetoolkit.errors, rdetoolkit.exceptions, rdetoolkit.img2thumb, rdetoolkit.invoicefile,
    rdetoolkit.rde2util, rdetoolkit.rdelogger, rdetoolkit.workflows, rdetoolkit.storage,
    rdetoolkit.traceback, rdetoolkit.config, rdetoolkit.invoice, rdetoolkit.invoice_schema,
    rdetoolkit.metadata, rdetoolkit.rde2types, rdetoolkit.models,
]
from rdetoolkit import *  # noqa: E402, F403
star_flow = flow
star_node = node
'''


def test_strict_mypy_client_accepts_public_api__tc_api637_010(tmp_path: Path) -> None:
    """TC-API637-010: a strict mypy client sees every public export with a type."""
    # Given: a consumer using representative top-level types, decorators and modules
    # When: type checking it with --strict
    result = _mypy(tmp_path, _POSITIVE_CLIENT)
    # Then: mypy accepts it
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    ("source", "diagnostic"),
    [
        ("import rdetoolkit\nrdetoolkit.not_a_symbol\n", "[attr-defined]"),
        ('from rdetoolkit import detect_encoding\nn: int = detect_encoding("x")\n', "[assignment]"),
        ("from rdetoolkit import modeproc\n", "[attr-defined]"),
    ],
    ids=["tc_api637_016", "tc_api637_017", "tc_api637_018"],
)
def test_strict_mypy_client_rejects_misuse__tc_api637_016_017_018(
    tmp_path: Path, source: str, diagnostic: str,
) -> None:
    """TC-API637-016..018: the stub is precise, not a blanket ``Any``."""
    # Given: a consumer misusing the top-level API
    # When: type checking it with --strict
    result = _mypy(tmp_path, source)
    # Then: mypy reports the specific violation
    assert result.returncode == 1, result.stdout + result.stderr
    assert diagnostic in result.stdout


# --- documentation inventory -----------------------------------------------------


@pytest.mark.parametrize("doc", _DOCS, ids=lambda p: p.name)
def test_docs_table_lists_supported_api__tc_api637_019(doc: Path) -> None:
    """TC-API637-019: the documented top-level table is the supported inventory."""
    # Given: the documented table
    names = _docs_table_names(doc)
    # When/Then: it lists every supported name exactly once
    assert len(names) == len(set(names))
    assert set(names) == set(rdetoolkit.__all__) - _LEGACY_EXPORTS - {"__version__"}


@pytest.mark.parametrize("doc", _DOCS, ids=lambda p: p.name)
def test_docs_table_does_not_promise_legacy__tc_api637_020(doc: Path) -> None:
    """TC-API637-020: ``get_agent_guide`` is not documented as supported (#644)."""
    # Given/When: the documented table
    names = _docs_table_names(doc)
    # Then: legacy exports are excluded
    assert sorted(_LEGACY_EXPORTS & set(names)) == []
