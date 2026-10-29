"""Design §13 level-3 acceptance tests for ``testing.run_flow``.

EP/BV table
===========

==================  ==========================  ==============================  ====================
Input               Partition / boundary        Expected                        Test ID
==================  ==========================  ==============================  ====================
flow function       one top-level input file    one successful Runner iteration TC-RUN-FLOW-EP-001
template subclass   one top-level input file    same Runner integration path     TC-RUN-FLOW-EP-002
flow function       nested fixture file         fixture tree copied recursively  TC-RUN-FLOW-BV-001
flow function       raises an exception         failed report with E3001         TC-RUN-FLOW-EP-003
==================  ==========================  ==============================  ====================
"""

from __future__ import annotations

from pathlib import Path
from typing import final

from rdetoolkit import flow
from rdetoolkit.templates import ProcessingTemplate, slot
from rdetoolkit.testing import run_flow
from rdetoolkit.types import InputPaths, OutputContext

_FUNCTION_CALLS: list[tuple[str, ...]] = []
_TEMPLATE_CALLS: list[str] = []


@flow(id="tests.run_flow.level3_function")
def _level3_function(paths: InputPaths, out: OutputContext) -> None:
    names = tuple(path.name for path in paths.inputdata.rglob("*.txt"))
    _FUNCTION_CALLS.append(names)
    out.write_bytes("struct", "seen.txt", "\n".join(names).encode())


@flow(id="tests.run_flow.level3_failure")
def _level3_failure(paths: InputPaths) -> None:
    del paths
    msg = "fixture failure"
    raise RuntimeError(msg)


class _Level3Skeleton(ProcessingTemplate):
    @slot
    def read(self, paths: InputPaths) -> str: ...

    @final
    def __flow__(self, paths: InputPaths, out: OutputContext) -> None:
        out.write_bytes("struct", "template.txt", self.read(paths).encode())


class _Level3Concrete(_Level3Skeleton):
    def read(self, paths: InputPaths) -> str:
        name = paths.rawfiles[0].name
        _TEMPLATE_CALLS.append(name)
        return name


def test_run_flow_executes_function_through_runner__tc_run_flow_ep_001(tmp_path: Path) -> None:
    """TC-RUN-FLOW-EP-001: a flow receives copied fixtures and reserved values."""
    # Given: one realistic input fixture and a clean call observation
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    (fixture_dir / "sample.txt").write_text("sample", encoding="utf-8")
    _FUNCTION_CALLS.clear()

    # When: the public level-3 helper runs the eager flow
    report = run_flow(_level3_function, fixture_dir)

    # Then: the actual Runner performs one completed iteration
    assert report.status == "success"
    assert len(report.iterations) == 1
    assert _FUNCTION_CALLS == [("sample.txt",)]


def test_run_flow_accepts_template_subclass__tc_run_flow_ep_002(tmp_path: Path) -> None:
    """TC-RUN-FLOW-EP-002: a concrete template uses the same Runner path."""
    # Given: one fixture and a valid concrete ProcessingTemplate subclass
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    (fixture_dir / "template.txt").write_text("template", encoding="utf-8")
    _TEMPLATE_CALLS.clear()

    # When: the class itself is passed to run_flow
    report = run_flow(_Level3Concrete, fixture_dir)

    # Then: the template is instantiated and its slot executes once
    assert report.status == "success"
    assert len(report.iterations) == 1
    assert _TEMPLATE_CALLS == ["template.txt"]


def test_run_flow_preserves_nested_fixture_tree__tc_run_flow_bv_001(tmp_path: Path) -> None:
    """TC-RUN-FLOW-BV-001: nested fixture data is available to the flow."""
    # Given: the smallest nested fixture tree
    fixture_dir = tmp_path / "fixtures"
    nested = fixture_dir / "instrument"
    nested.mkdir(parents=True)
    (nested / "nested.txt").write_text("nested", encoding="utf-8")
    _FUNCTION_CALLS.clear()

    # When: run_flow constructs its temporary RDE input tree
    report = run_flow(_level3_function, fixture_dir)

    # Then: recursive content is preserved and processed as one tile
    assert report.status == "success"
    assert len(report.iterations) == 1
    assert _FUNCTION_CALLS == [("nested.txt",)]


def test_run_flow_reports_flow_failure__tc_run_flow_ep_003(tmp_path: Path) -> None:
    """TC-RUN-FLOW-EP-003: user exceptions follow the catalogued Runner contract."""
    # Given: a flow that raises and one input tile
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    (fixture_dir / "broken.txt").write_text("broken", encoding="utf-8")

    # When: run_flow executes the failing flow
    report = run_flow(_level3_failure, fixture_dir)

    # Then: failure is represented in the RunReport with the catalogued code
    assert report.status == "failed"
    assert report.error is not None
    assert report.error["code"] == 3001
    assert "Remediation:" in str(report.error["message"])
