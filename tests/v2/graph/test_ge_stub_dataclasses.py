"""Fix round 1 / A-2: graph model stubs declare dataclasses as they are defined.

``graph/api/csv2graph.pyi`` re-exports ``MatplotlibArtifact``, ``NormalizedColumns``,
``RenderCollections`` and ``RenderResult`` from ``graph/models.pyi`` (where the
runtime defines them) instead of declaring a second copy (develop 05277ac3 intent).
The declaring stub must then carry the runtime ``frozen`` flag, otherwise a strict
consumer is told a frozen artifact is mutable.

EP table:
| TC | Partition | Input | Expected |
|----|-----------|-------|----------|
| TC-FIX1-A2-EP-001 | dataclass declared in models.pyi | every ``@dataclass`` class | stub ``frozen`` == runtime ``frozen`` |
| TC-FIX1-A2-EP-002 | csv2graph.pyi re-exports | ``X as X`` names | same object as the runtime module attribute |

Negative table:
| TC | Partition | Input | Expected |
|----|-----------|-------|----------|
| TC-FIX1-A2-NEG-001 | duplicate class declaration | ``class`` statements in csv2graph.pyi | none (the classes are declared where defined) |
| TC-FIX1-A2-NEG-002 | strict consumer mutates a frozen artifact | ``MatplotlibArtifact(...).filename = "x"`` | mypy reports ``[misc]`` |
"""

from __future__ import annotations

import ast
import dataclasses
import importlib
import subprocess
import sys
from pathlib import Path

import pytest

GRAPH_SRC = Path(__file__).resolve().parents[3] / "src" / "rdetoolkit" / "graph"
MODELS_STUB = GRAPH_SRC / "models.pyi"
API_STUB = GRAPH_SRC / "api" / "csv2graph.pyi"


def _stub_dataclass_frozen(stub: Path) -> dict[str, bool]:
    """Return ``{class name: frozen flag}`` for every ``@dataclass`` class in *stub*."""
    result: dict[str, bool] = {}
    for stmt in ast.parse(stub.read_text(encoding="utf-8")).body:
        if not isinstance(stmt, ast.ClassDef):
            continue
        for deco in stmt.decorator_list:
            if isinstance(deco, ast.Name) and deco.id == "dataclass":
                result[stmt.name] = False
            elif isinstance(deco, ast.Call) and isinstance(deco.func, ast.Name) and deco.func.id == "dataclass":
                frozen = next((kw.value for kw in deco.keywords if kw.arg == "frozen"), None)
                result[stmt.name] = isinstance(frozen, ast.Constant) and frozen.value is True
    return result


def test_models_stub_frozen_flags_match_runtime__tc_fix1_a2_ep_001() -> None:
    """TC-FIX1-A2-EP-001: every stub dataclass has the runtime frozen flag."""
    # Given: the runtime models module and its stub
    models = importlib.import_module("rdetoolkit.graph.models")
    declared = _stub_dataclass_frozen(MODELS_STUB)
    assert declared, "no dataclass found in models.pyi"
    # When: comparing each declaration with the runtime dataclass parameters
    mismatched = {
        name: (frozen, getattr(models, name).__dataclass_params__.frozen)
        for name, frozen in declared.items()
        if frozen != getattr(models, name).__dataclass_params__.frozen
    }
    # Then: no drift
    assert mismatched == {}


def test_api_stub_reexports_are_the_runtime_objects__tc_fix1_a2_ep_002() -> None:
    """TC-FIX1-A2-EP-002: csv2graph.pyi re-exports name the runtime objects."""
    # Given: the stub re-exports of graph/api/csv2graph.pyi
    api = importlib.import_module("rdetoolkit.graph.api.csv2graph")
    tree = ast.parse(API_STUB.read_text(encoding="utf-8"))
    reexports = [
        (stmt.module, alias.name)
        for stmt in tree.body
        if isinstance(stmt, ast.ImportFrom) and stmt.module is not None
        for alias in stmt.names
        if alias.asname == alias.name
    ]
    assert reexports
    # When/Then: each one is the same object at runtime
    for module_name, name in reexports:
        assert getattr(api, name) is getattr(importlib.import_module(module_name), name), name


def test_api_stub_declares_no_class__tc_fix1_a2_neg_001() -> None:
    """TC-FIX1-A2-NEG-001: no dataclass is declared a second time in csv2graph.pyi."""
    # Given: the csv2graph stub
    tree = ast.parse(API_STUB.read_text(encoding="utf-8"))
    # When: listing class statements
    classes = [stmt.name for stmt in tree.body if isinstance(stmt, ast.ClassDef)]
    # Then: none; the runtime module defines no class either
    api = importlib.import_module("rdetoolkit.graph.api.csv2graph")
    assert classes == []
    assert not [
        name for name, value in vars(api).items()
        if dataclasses.is_dataclass(value) and getattr(value, "__module__", "") == api.__name__
    ]


@pytest.mark.slow
def test_strict_consumer_cannot_mutate_frozen_artifact__tc_fix1_a2_neg_002(tmp_path: Path) -> None:
    """TC-FIX1-A2-NEG-002: the stub promises the runtime immutability."""
    # Given: a consumer assigning to a frozen dataclass field
    consumer = tmp_path / "consumer.py"
    consumer.write_text(
        "from rdetoolkit.graph.api.csv2graph import MatplotlibArtifact\n"
        "a = MatplotlibArtifact(filename='a.png', figure=None)\n"
        "a.filename = 'b.png'\n",
        encoding="utf-8",
    )
    # When: checked with strict mypy
    result = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "--ignore-missing-imports", "--no-incremental", str(consumer)],
        cwd=tmp_path, capture_output=True, text=True, check=False,
    )
    # Then: the assignment is rejected
    assert result.returncode == 1, result.stdout + result.stderr
    assert "[misc]" in result.stdout, result.stdout
