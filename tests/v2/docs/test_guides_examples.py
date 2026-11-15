"""Executed examples of the v2 testing and plugin development guides (#454).

EP table
========

====================  ==========================  ====================================  =====================
Page                  Partition                   Expected                              Test ID
====================  ==========================  ====================================  =====================
testing guide         documented project tests    ``python -m pytest tests`` passes     TC-DOC-GUI-EP-001
testing guide         documented lint command     exit 0 on the documented module       TC-DOC-GUI-EP-002
plugin guide          entry point + provider      nodes/templates/formats discovered    TC-DOC-GUI-EP-003
plugin guide          template use from plugin    describe and init succeed             TC-DOC-GUI-EP-004
====================  ==========================  ====================================  =====================

BV table
========

====================  ==========================  ====================================  =====================
Item                  Boundary                    Expected                              Test ID
====================  ==========================  ====================================  =====================
documentation fences  every fenced block          marked; executed set is fixed         TC-DOC-GUI-BV-001
prose outside fences  ``@`` + letter token         none (GitHub mention hazard)          TC-DOC-GUI-BV-002
language twins        ja vs en fences             same names; identical executed code   TC-DOC-GUI-BV-003
====================  ==========================  ====================================  =====================

The plugin tests stand in for ``pip install`` by pointing
``importlib.metadata.entry_points`` at the documented entry point, which is
exactly what discovery reads from an installed distribution.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from importlib.metadata import EntryPoint
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rdetoolkit.cli.app import app
from tests.v2.docs.doc_examples import (
    DOCS_DIR,
    cli_args,
    command_lines,
    executed_names,
    executed_twins,
    isolated_modules,
    mention_hazards,
    page_examples,
    scratch_registries,
)

GUIDES = DOCS_DIR / "guides"
PAGES = {
    "testing": {"testing-source", "testing-tests", "testing-run", "testing-lint"},
    "plugins": {"plugin-provider", "plugin-entry-point", "plugin-discovery", "plugin-usage"},
}
ALL_DOCS = [GUIDES / f"{page}{suffix}.md" for page in PAGES for suffix in ("", ".en")]
EACH_DOC = pytest.mark.parametrize("doc", ALL_DOCS, ids=[doc.name for doc in ALL_DOCS])
PLUGIN_MODULE = "rdetoolkit_example_plugin"


def _twins(page: str) -> pytest.MarkDecorator:
    docs = [GUIDES / f"{page}.md", GUIDES / f"{page}.en.md"]
    return pytest.mark.parametrize("doc", docs, ids=["ja", "en"])


def _write_project(doc: Path, root: Path) -> None:
    examples = page_examples(doc)
    (root / "modules").mkdir()
    (root / "modules" / "__init__.py").write_text("", encoding="utf-8")
    (root / "modules" / "processing.py").write_text(examples["testing-source"].code, encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_processing.py").write_text(examples["testing-tests"].code, encoding="utf-8")


@_twins("testing")
def test_documented_project_tests_pass__tc_doc_gui_ep_001(doc: Path, tmp_path: Path) -> None:
    """TC-DOC-GUI-EP-001: the documented test module passes under the documented command."""
    # Given: modules/processing.py and tests/test_processing.py from the page
    _write_project(doc, tmp_path)
    (line,) = command_lines(page_examples(doc)["testing-run"])
    assert line == "$ python -m pytest tests"
    # When: running pytest as documented, in its own process
    env = {**os.environ, "MPLCONFIGDIR": str(tmp_path / "mpl")}
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider", "--basetemp", str(tmp_path / "pt")],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )
    # Then: all five documented tests (levels 1-3, fixtures from the plugin) pass
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "5 passed" in completed.stdout


@_twins("testing")
def test_documented_lint_succeeds__tc_doc_gui_ep_002(
    doc: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-DOC-GUI-EP-002: ``nodes lint`` reports no violation for the documented module."""
    _write_project(doc, tmp_path)
    monkeypatch.chdir(tmp_path)
    scratch_registries(monkeypatch, builtin_only=True)
    with isolated_modules("modules"):
        (line,) = command_lines(page_examples(doc)["testing-lint"])
        result = CliRunner().invoke(app, cli_args(line))
    assert result.exit_code == 0, result.output
    assert "0 violations" in result.output


@pytest.fixture
def installed_plugin(request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Make the documented provider module discoverable through its documented entry point."""
    from rdetoolkit.plugin import discovery

    doc: Path = request.getfixturevalue("doc")
    examples = page_examples(doc)
    (tmp_path / f"{PLUGIN_MODULE}.py").write_text(examples["plugin-provider"].code, encoding="utf-8")
    entry_points = tomllib.loads(examples["plugin-entry-point"].code)["project"]["entry-points"]["rdetoolkit.plugins"]
    entries = tuple(EntryPoint(name=name, value=value, group="rdetoolkit.plugins") for name, value in entry_points.items())
    assert [entry.value for entry in entries] == [PLUGIN_MODULE]
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(discovery.metadata, "entry_points", lambda *, group: entries)
    monkeypatch.setattr(discovery, "_discovered", {})
    scratch_registries(monkeypatch)
    return tmp_path


@_twins("plugins")
def test_documented_plugin_is_discovered__tc_doc_gui_ep_003(doc: Path, installed_plugin: Path) -> None:
    """TC-DOC-GUI-EP-003: the three discovery commands show what the provider declares."""
    # When: running the documented discovery commands
    with isolated_modules(PLUGIN_MODULE):
        results = [CliRunner().invoke(app, cli_args(line)) for line in command_lines(page_examples(doc)["plugin-discovery"])]
    # Then: the node, the skeleton and the format handler are listed
    assert [result.exit_code for result in results] == [0, 0, 0], [result.output for result in results]
    assert results[0].output.split() == ["example_plugin.count_lines"]
    assert f"{PLUGIN_MODULE}.LineCountTemplate" in results[1].output.split()
    assert results[2].output.strip() == f"Example text log (.log) -> {PLUGIN_MODULE}:LineCountTemplate [example]"


@_twins("plugins")
def test_documented_plugin_template_is_usable__tc_doc_gui_ep_004(doc: Path, installed_plugin: Path) -> None:
    """TC-DOC-GUI-EP-004: describe and init work on the plugin's template, as documented."""
    # When: running the documented user-side commands
    with isolated_modules(PLUGIN_MODULE, "processing"):
        results = [CliRunner().invoke(app, cli_args(line)) for line in command_lines(page_examples(doc)["plugin-usage"])]
    # Then: the slot is described and the three documented files are generated
    assert [result.exit_code for result in results] == [0, 0], [result.output for result in results]
    assert "'name': 'read'" in results[0].output
    for generated in ("processing.py", "tests/test_processing.py", "main.py"):
        assert (installed_plugin / generated).is_file(), generated


@pytest.mark.parametrize("page", sorted(PAGES))
@pytest.mark.parametrize("suffix", ["", ".en"], ids=["ja", "en"])
def test_every_fence_is_marked_and_owned__tc_doc_gui_bv_001(page: str, suffix: str) -> None:
    """TC-DOC-GUI-BV-001: no unmarked fence exists and each page's executed set is fixed."""
    assert executed_names(GUIDES / f"{page}{suffix}.md") == PAGES[page]


@EACH_DOC
def test_prose_has_no_mention_tokens__tc_doc_gui_bv_002(doc: Path) -> None:
    """TC-DOC-GUI-BV-002: an ``@``-prefixed token may appear only inside a code fence."""
    assert mention_hazards(doc) == []


@pytest.mark.parametrize("page", sorted(PAGES))
def test_language_twins_carry_identical_examples__tc_doc_gui_bv_003(page: str) -> None:
    """TC-DOC-GUI-BV-003: the Japanese and English pages execute the same code."""
    ja, en = GUIDES / f"{page}.md", GUIDES / f"{page}.en.md"
    assert executed_twins(en) == executed_twins(ja)
    assert page_examples(en).keys() == page_examples(ja).keys()
