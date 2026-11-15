"""``rdetoolkit.config`` names one module regardless of import order (#745).

EP table:

| API | Partition | Expected | Test ID |
|---|---|---|---|
| ``rdetoolkit.config`` | read before the subpackage is imported | the ``rdetoolkit.config`` package | TC-EP-745-001 |
| ``rdetoolkit.config`` | read after the subpackage is imported | the same package object | TC-EP-745-002 |
| ``from rdetoolkit import config`` | fresh interpreter | the ``rdetoolkit.config`` package | TC-EP-745-003 |
| ``rdetoolkit/__init__.pyi`` | ``config`` declaration | bound to the ``rdetoolkit.config`` package | TC-EP-745-004 |
| ``rdetoolkit.config.<model>`` | former ``models.config`` meaning | same class objects | TC-EP-745-005 |
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
        f"{'.' * node.level}{node.module or ''}"
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
        if (alias.asname or alias.name) == "config"
    ]
    # Then: exactly one binding, imported from the package root (``from . import config``)
    assert sources == ["."]


def test_package_keeps_the_former_models_config_classes() -> None:
    """TC-EP-745-005: code written against the old meaning keeps working."""
    # Given: the model names reachable through rdetoolkit.models.config
    import rdetoolkit.models.config as models_config

    names = ("Config", "SystemSettings", "MultiDataTileSettings", "SmartTableSettings", "TracebackSettings")
    # When / Then: rdetoolkit.config exposes the identical class objects
    for name in names:
        assert getattr(rdetoolkit.config, name) is getattr(models_config, name), name
