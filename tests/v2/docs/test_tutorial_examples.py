"""Executed examples for the v2 progressive-disclosure tutorial.

EP table
========

====================  ======================  ==============================  ====================
Level                 Partition               Expected                        Test ID
====================  ======================  ==============================  ====================
level 1               processing template CLI skeleton and sample test exist TC-DOC-TUT-EP-001
level 2               plain ``@flow``         direct eager call succeeds      TC-DOC-TUT-EP-002
level 3               ``testing.run_flow``    successful RunReport returned   TC-DOC-TUT-EP-003
====================  ======================  ==============================  ====================

BV table
========

====================  ======================  ==============================  ====================
Level                 Boundary                Expected                        Test ID
====================  ======================  ==============================  ====================
documentation fences  every fenced example   marker and execution coverage  TC-DOC-TUT-BV-001
====================  ======================  ==============================  ====================
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from typer.testing import CliRunner

from rdetoolkit.cli.app import app

DOC = Path(__file__).parents[3] / "docs" / "tutorial_v2.md"
EXAMPLE_RE = re.compile(r"<!-- test: (?P<name>[\w-]+) -->\n```(?P<language>\w+)\n(?P<code>.*?)```", re.DOTALL)


def _examples() -> dict[str, tuple[str, str]]:
    text = DOC.read_text(encoding="utf-8")
    examples = {
        match.group("name"): (match.group("language"), match.group("code"))
        for match in EXAMPLE_RE.finditer(text)
    }
    assert text.count("```") == 2 * len(examples), "Every fenced example must have a test marker"
    return examples


def test_level_1_init_command_executes__tc_doc_tut_ep_001(tmp_path: Path, monkeypatch) -> None:
    """TC-DOC-TUT-EP-001: the documented template initialization command generates both artifacts."""
    # Given: the documented level-1 command and an isolated project directory
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    (tmp_path / "instrument_template.py").write_text(
        _examples()["level-1-template-package"][1],
        encoding="utf-8",
    )
    command = _examples()["level-1-init"][1].strip().removeprefix("$ ").split()
    # When: invoking the command through the public CLI
    result = CliRunner().invoke(app, command[3:])
    # Then: a TODO skeleton and its executable sample test are generated
    assert result.exit_code == 0, result.output
    sources = list(tmp_path.rglob("*.py"))
    assert any("TODO" in source.read_text(encoding="utf-8") for source in sources)
    assert any(source.name.startswith("test_") for source in sources)


def test_level_2_flow_executes_eagerly__tc_doc_tut_ep_002() -> None:
    """TC-DOC-TUT-EP-002: the documented flow behaves as a plain Python function."""
    # Given: the complete documented level-2 example
    namespace: dict[str, object] = {}
    # When: executing the example directly
    exec(_examples()["level-2-flow"][1], namespace)  # noqa: S102
    # Then: its branch, loop, default argument, literal, and f-string assertions passed
    assert namespace["result"] == ["sample-2", "sample-4"]


def test_level_3_run_flow_executes__tc_doc_tut_ep_003(tmp_path: Path) -> None:
    """TC-DOC-TUT-EP-003: the documented level-3 helper returns a successful RunReport."""
    # Given: the documented example and a temporary fixture directory
    namespace: dict[str, object] = {"fixture_dir": tmp_path / "fixture"}
    # When: executing it against the real testing helper
    exec(_examples()["level-3-run-flow"][1], namespace)  # noqa: S102
    # Then: the example's assertion ran against a successful report
    assert getattr(namespace["report"], "status") == "success"


def test_every_tutorial_fence_is_executed__tc_doc_tut_bv_001() -> None:
    """TC-DOC-TUT-BV-001: no unmarked tutorial code fence can bypass execution."""
    # Given: all fenced examples in the tutorial
    examples = _examples()
    # When: comparing their stable marker names with this module's executed set
    executed = {"level-1-template-package", "level-1-init", "level-2-flow", "level-3-run-flow"}
    # Then: every example is explicitly owned by an execution test
    assert set(examples) == executed
