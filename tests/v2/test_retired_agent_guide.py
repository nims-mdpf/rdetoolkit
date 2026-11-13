"""#644: the package-embedded AI-agent guide is retired before v2 GA.

EP table:
| TC | Probe | Expected |
|----|-------|----------|
| TC-644-001 | ``rdetoolkit.get_agent_guide`` | ``AttributeError``; absent from ``__all__``, ``dir()`` and the stub |
| TC-644-002 | ``import rdetoolkit._agent`` in a fresh interpreter | ``ModuleNotFoundError`` |
| TC-644-003 | ``rdetoolkit agent-guide`` | not a registered CLI command |
| TC-644-004 | ``[tool.setuptools] package_data`` | no agent Markdown; ``py.typed`` and ``*.pyi`` kept |
| TC-644-005 | source tree under ``src/rdetoolkit`` | no ``_agent`` / ``.agents`` directory, no ``rdetoolkit._agent`` reference |

The wheel contents are pinned by ``tests/v2/test_wheel_layout.py``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import rdetoolkit

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

PROJECT_ROOT = Path(__file__).parent.parent.parent
PACKAGE_ROOT = PROJECT_ROOT / "src" / "rdetoolkit"


def test_get_agent_guide_is_not_public__tc_644_001() -> None:
    """TC-644-001: the retired API is neither resolvable nor advertised."""
    with pytest.raises(AttributeError):
        _ = rdetoolkit.get_agent_guide  # type: ignore[attr-defined]
    assert "get_agent_guide" not in rdetoolkit.__all__
    assert "get_agent_guide" not in dir(rdetoolkit)
    assert "get_agent_guide" not in (PACKAGE_ROOT / "__init__.pyi").read_text(encoding="utf-8")


def test_agent_module_is_not_importable__tc_644_002() -> None:
    """TC-644-002: the private implementation module is gone from the package."""
    probe = (
        "import importlib\n"
        "try:\n"
        "    importlib.import_module('rdetoolkit._agent')\n"
        "except ModuleNotFoundError:\n"
        "    print('absent')\n"
        "else:\n"
        "    print('present')\n"
    )
    result = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "absent"


def test_agent_guide_cli_command_is_not_registered__tc_644_003() -> None:
    """TC-644-003: the CLI no longer offers the retired command."""
    from typer.main import get_command

    from rdetoolkit.cli.app import app

    command = get_command(app)
    assert "agent-guide" not in getattr(command, "commands", {})


def test_package_data_ships_no_agent_markdown__tc_644_004() -> None:
    """TC-644-004: packaging no longer distributes agent Markdown, typing data stays."""
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as f:
        config = tomllib.load(f)
    package_data = config["tool"]["setuptools"]["package_data"]["rdetoolkit"]
    assert not [pattern for pattern in package_data if "agent" in pattern.lower() or pattern.endswith(".md")]
    assert "py.typed" in package_data
    assert "*.pyi" in package_data


def test_source_tree_has_no_agent_guide__tc_644_005() -> None:
    """TC-644-005: no agent-guide resources or imports remain in the package source."""
    assert not (PACKAGE_ROOT / "_agent").exists()
    assert not (PACKAGE_ROOT / ".agents").exists()
    offenders = [
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in sorted(PACKAGE_ROOT.rglob("*"))
        if path.suffix in {".py", ".pyi"} and "rdetoolkit._agent" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []
