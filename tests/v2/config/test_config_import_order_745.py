"""``rdetoolkit.config`` names one module regardless of import order (#745).

EP table:

| API | Partition | Expected | Test ID |
|---|---|---|---|
| ``rdetoolkit.config`` | read before the subpackage is imported | the ``rdetoolkit.config`` package | TC-EP-745-001 |
| ``rdetoolkit.config`` | read after the subpackage is imported | the same package object | TC-EP-745-002 |
| ``from rdetoolkit import config`` | fresh interpreter | the ``rdetoolkit.config`` package | TC-EP-745-003 |
| ``rdetoolkit/__init__.pyi`` | ``config`` declaration | bound to the ``rdetoolkit.config`` package | TC-EP-745-004 |
| ``rdetoolkit.config.<name>`` | every name defined in ``models/config.pyi`` | same object, re-exported by the stub | TC-EP-745-005 |
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

import rdetoolkit

_PROBES = {
    "lazy_then_import": (
        "import importlib, rdetoolkit\n"
        "before = rdetoolkit.config\n"
        "importlib.import_module('rdetoolkit.config')\n"
        "after = rdetoolkit.config\n"
        "names = [before.__name__, after.__name__, before is after]\n"
    ),
    "import_then_lazy": (
        "import rdetoolkit.config as pkg\n"
        "import rdetoolkit\n"
        "names = [pkg.__name__, rdetoolkit.config.__name__, pkg is rdetoolkit.config]\n"
    ),
    "from_import": (
        "from rdetoolkit import config\n"
        "import rdetoolkit.config as pkg\n"
        "names = [config.__name__, pkg.__name__, config is pkg]\n"
    ),
}


def _probe(source: str) -> list[object]:
    completed = subprocess.run(
        [sys.executable, "-c", source + "import json; print(json.dumps(names))"],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(completed.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize(
    "order",
    [
        pytest.param("lazy_then_import", id="TC-EP-745-001"),
        pytest.param("import_then_lazy", id="TC-EP-745-002"),
        pytest.param("from_import", id="TC-EP-745-003"),
    ],
)
def test_config_resolves_to_package_in_every_import_order(order: str) -> None:
    """TC-EP-745-001..003: every import order yields the one config package."""
    # Given: a fresh interpreter that imports rdetoolkit.config in ``order``
    # When: the public name is read before and after the subpackage import
    first, second, same = _probe(_PROBES[order])
    # Then: both reads are the rdetoolkit.config package object
    assert (first, second, same) == ("rdetoolkit.config", "rdetoolkit.config", True)


def test_stub_declares_config_as_the_package() -> None:
    """TC-EP-745-004: the stub's ``config`` binding names the package."""
    # Given: the top-level stub shipped beside rdetoolkit/__init__.py
    stub = Path(rdetoolkit.__file__).with_name("__init__.pyi")
    tree = ast.parse(stub.read_text(encoding="utf-8"))
    # When: collecting every import that binds the name ``config``
    sources = [
        "rdetoolkit" if node.level == 1 and node.module is None else f"{'.' * node.level}{node.module or ''}"
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
        if (alias.asname or alias.name) == "config"
    ]
    # Then: exactly one binding, imported from the package root
    # (``from . import config`` or ``from rdetoolkit import config``)
    assert sources == ["rdetoolkit"]


def _stub_defined_names(stub: Path) -> set[str]:
    """Return the classes and aliases a stub defines itself (not imports)."""
    tree = ast.parse(stub.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return {name for name in names if not name.startswith("_")}


def _stub_reexported_names(stub: Path) -> set[str]:
    """Return the names a stub re-exports with the explicit ``X as X`` form."""
    tree = ast.parse(stub.read_text(encoding="utf-8"))
    return {
        alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
        if alias.asname == alias.name
    }


_PACKAGE_DIR = Path(rdetoolkit.__file__).parent
_FORMER_SURFACE = sorted(_stub_defined_names(_PACKAGE_DIR / "models" / "config.pyi"))


def test_former_surface_is_derived_from_the_models_stub() -> None:
    """TC-EP-745-005 guard: the derived surface is not empty and includes the alias."""
    # Given / When: the names defined in rdetoolkit/models/config.pyi
    # Then: the derivation found the models and the MultiDataTileOrder alias
    assert {"Config", "MultiDataTileOrder"} <= set(_FORMER_SURFACE)


@pytest.mark.parametrize("name", _FORMER_SURFACE)
def test_package_keeps_every_former_models_config_name(name: str) -> None:
    """TC-EP-745-005: ``rdetoolkit.config.<name>`` keeps working for every former name."""
    # Given: a public name defined in rdetoolkit.models.config
    import rdetoolkit.models.config as models_config

    # When / Then: the package exposes the identical object at runtime ...
    assert getattr(rdetoolkit.config, name) is getattr(models_config, name)
    # ... and its stub re-exports it, so type checkers see the same surface
    assert name in _stub_reexported_names(_PACKAGE_DIR / "config" / "__init__.pyi")
