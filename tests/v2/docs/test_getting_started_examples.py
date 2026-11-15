"""Executed end-to-end walkthrough of the v2 Getting Started page (#454).

EP table
========

====================  ======================  ===================================  ====================
Step                  Partition               Expected                             Test ID
====================  ======================  ===================================  ====================
init + main.py run    documented project      ``success`` printed, outputs exist   TC-DOC-GS-EP-001
report / graph        recorded run report     summary and Call Sequence printed    TC-DOC-GS-EP-001
CLI run + nodes lint  same project via CLI    exit 0 for both commands             TC-DOC-GS-EP-002
====================  ======================  ===================================  ====================

BV table
========

====================  ======================  ===================================  ====================
Item                  Boundary                Expected                             Test ID
====================  ======================  ===================================  ====================
documentation fences  every fenced block      marked; executed set is fixed        TC-DOC-GS-BV-001
prose outside fences  ``@`` + letter token     none (GitHub mention hazard)         TC-DOC-GS-BV-002
language twins        ja vs en fences         same names; identical executed code  TC-DOC-GS-BV-003
====================  ======================  ===================================  ====================

The walkthrough is the pre-release end-to-end check of the documented
first-run experience: it runs the published commands against a freshly
initialised project, through a real ``python main.py`` subprocess.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rdetoolkit.cli.app import app
from tests.v2.docs.doc_examples import (
    DOCS_DIR,
    Example,
    cli_args,
    command_lines,
    executed_names,
    executed_twins,
    isolated_modules,
    mention_hazards,
    page_examples,
    scratch_registries,
)

DOC_JA = DOCS_DIR / "getting-started.md"
DOC_EN = DOCS_DIR / "getting-started.en.md"
DOCS = pytest.mark.parametrize("doc", [DOC_JA, DOC_EN], ids=["ja", "en"])
EXECUTED = {"gs-init", "gs-sample-csv", "gs-flow", "gs-main", "gs-run", "gs-inspect", "gs-cli"}


def _build_project(examples: dict[str, Example], root: Path) -> Path:
    """Follow steps 1-4 of the page inside ``root`` and return ``container/``."""
    result = CliRunner().invoke(app, cli_args(command_lines(examples["gs-init"])[0]))
    assert result.exit_code == 0, result.output
    container = root / "container"
    inputdata = container / "data" / "inputdata"
    assert inputdata.is_dir()
    (inputdata / "sample.csv").write_text(examples["gs-sample-csv"].code, encoding="utf-8")
    modules = container / "modules"
    assert modules.is_dir()
    (modules / "__init__.py").write_text("", encoding="utf-8")
    (modules / "flow.py").write_text(examples["gs-flow"].code, encoding="utf-8")
    (container / "main.py").write_text(examples["gs-main"].code, encoding="utf-8")
    return container


def _run_report(container: Path) -> Path:
    reports = sorted((container / "data" / "logs").glob("run_report_*.json"))
    assert len(reports) == 1, reports
    return reports[0]


@DOCS
def test_documented_walkthrough_runs_end_to_end__tc_doc_gs_ep_001(
    doc: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-DOC-GS-EP-001: init, main.py, report show and graph work as documented."""
    # Given: a project built exactly from the page's steps 1-4
    examples = page_examples(doc)
    monkeypatch.chdir(tmp_path)
    container = _build_project(examples, tmp_path)
    run_lines = command_lines(examples["gs-run"])
    assert run_lines == ["$ cd container", "$ python main.py"]
    # When: running the documented entry point as a real process
    env = {**os.environ, "MPLCONFIGDIR": str(tmp_path / "mpl")}
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "main.py"],
        cwd=container,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )
    # Then: the run succeeds and writes the outputs the page lists
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip().splitlines()[-1] == "success"
    data = container / "data"
    for relative in ("structured/sample.csv", "main_image/sample.png", "nonshared_raw/sample.csv"):
        assert (data / relative).is_file(), relative
    assert not (data / "job.failed").exists()
    assert (data / "structured" / "sample.csv").read_text(encoding="utf-8").splitlines()[1:] == [
        "0,0.25",
        "1,0.625",
        "2,1.0",
    ]
    # When: inspecting the recorded report with the documented commands
    report = _run_report(container).relative_to(container).as_posix()
    monkeypatch.chdir(container)
    outputs = []
    for line in command_lines(examples["gs-inspect"]):
        args = [report if arg == "data/logs/run_report_<run_id>.json" else arg for arg in cli_args(line)]
        result = CliRunner().invoke(app, args)
        assert result.exit_code == 0, result.output
        outputs.append(result.output)
    # Then: the summary and the Call Sequence describe the documented flow
    assert "status: success" in outputs[0]
    assert "Call Sequence" in outputs[1]
    assert "quickstart.normalize#2" in outputs[1]


@DOCS
def test_documented_cli_commands_succeed__tc_doc_gs_ep_002(
    doc: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-DOC-GS-EP-002: ``run --flow`` and ``nodes lint`` succeed on the documented project."""
    # Given: the documented project and isolated registries for its fixed ids
    examples = page_examples(doc)
    monkeypatch.chdir(tmp_path)
    container = _build_project(examples, tmp_path)
    monkeypatch.chdir(container)
    monkeypatch.setenv("MPLCONFIGDIR", str(tmp_path / "mpl"))
    scratch_registries(monkeypatch, builtin_only=True)
    # When: invoking each documented command through the public CLI
    with isolated_modules("modules"):
        results = [CliRunner().invoke(app, cli_args(line)) for line in command_lines(examples["gs-cli"])]
    # Then: the flow run succeeds and the annotated nodes pass the lint
    assert [result.exit_code for result in results] == [0, 0], [result.output for result in results]
    assert '"status": "success"' in results[0].output


@DOCS
def test_every_fence_is_marked_and_owned__tc_doc_gs_bv_001(doc: Path) -> None:
    """TC-DOC-GS-BV-001: no unmarked fence exists and the executed set is fixed."""
    # Given/When: the marked fences of the page
    # Then: exactly the walkthrough steps above are executed
    assert executed_names(doc) == EXECUTED


@DOCS
def test_prose_has_no_mention_tokens__tc_doc_gs_bv_002(doc: Path) -> None:
    """TC-DOC-GS-BV-002: an ``@``-prefixed token may appear only inside a code fence."""
    assert mention_hazards(doc) == []


def test_language_twins_carry_identical_examples__tc_doc_gs_bv_003() -> None:
    """TC-DOC-GS-BV-003: the Japanese and English pages execute the same code.

    Illustrations (trees, output) carry translated comments, so only their
    names must match.
    """
    assert executed_twins(DOC_EN) == executed_twins(DOC_JA)
    assert page_examples(DOC_EN).keys() == page_examples(DOC_JA).keys()
