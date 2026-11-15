"""Executed examples of the v2 concept pages: node, flow and Runner (#454).

EP table
========

====================  ==========================  ====================================  =====================
Page                  Partition                   Expected                              Test ID
====================  ==========================  ====================================  =====================
node                  direct call / duplicate id  plain result; E2001 raised            TC-DOC-CON-EP-001
node                  CLI inspection commands     list / describe / lint exit 0         TC-DOC-CON-EP-002
node                  recording settings YAML     accepted by the real config loader    TC-DOC-CON-EP-003
flow                  injection / E2003 / direct  documented asserts hold               TC-DOC-CON-EP-004
flow                  ProcessingTemplate          template run succeeds                 TC-DOC-CON-EP-004
runner                continue vs fail_fast       partial(2) then failed(1, 3001)       TC-DOC-CON-EP-005
====================  ==========================  ====================================  =====================

BV table
========

====================  ==========================  ====================================  =====================
Item                  Boundary                    Expected                              Test ID
====================  ==========================  ====================================  =====================
documentation fences  every fenced block          marked; executed set is fixed         TC-DOC-CON-BV-001
prose outside fences  ``@`` + letter token         none (GitHub mention hazard)          TC-DOC-CON-BV-002
language twins        ja vs en fences             same names; identical executed code   TC-DOC-CON-BV-003
====================  ==========================  ====================================  =====================
"""

from __future__ import annotations

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

CONCEPTS = DOCS_DIR / "concepts"
PAGES = {
    "node": {"node-basic", "node-duplicate", "node-inspect", "node-config"},
    "flow": {"flow-injection", "flow-unresolvable", "flow-direct", "flow-template"},
    "runner": {"runner-error-policy"},
}
ALL_DOCS = [CONCEPTS / f"{page}{suffix}.md" for page in PAGES for suffix in ("", ".en")]
EACH_DOC = pytest.mark.parametrize("doc", ALL_DOCS, ids=[doc.name for doc in ALL_DOCS])


def _twins(page: str) -> pytest.MarkDecorator:
    docs = [CONCEPTS / f"{page}.md", CONCEPTS / f"{page}.en.md"]
    return pytest.mark.parametrize("doc", docs, ids=["ja", "en"])


@pytest.fixture
def registries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate the fixed node, flow and template ids both twins register."""
    scratch_registries(monkeypatch)


@_twins("node")
@pytest.mark.usefixtures("registries")
def test_node_examples_execute__tc_doc_con_ep_001(doc: Path) -> None:
    """TC-DOC-CON-EP-001: the direct-call and duplicate-id examples run as written."""
    examples = page_examples(doc)
    namespace: dict[str, object] = {"__name__": "docs_concepts_node"}
    # When: executing both examples in one module namespace
    exec(examples["node-basic"].code, namespace)  # noqa: S102
    exec(examples["node-duplicate"].code, namespace)  # noqa: S102
    # Then: their assertions held and the duplicate registration raised E2001
    assert namespace["scale"]([1.0]) == [2.0]
    assert namespace["code"] == 2001


@_twins("node")
def test_node_cli_inspection_succeeds__tc_doc_con_ep_002(
    doc: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-DOC-CON-EP-002: list, describe and lint accept the documented module."""
    # lint checks the whole process registry, so start from rdetoolkit's own entries
    scratch_registries(monkeypatch, builtin_only=True)
    # Given: concepts_nodes.py holding the documented scale node
    examples = page_examples(doc)
    (tmp_path / "concepts_nodes.py").write_text(examples["node-basic"].code, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    # When: invoking each documented command
    with isolated_modules("concepts_nodes"):
        results = [CliRunner().invoke(app, cli_args(line)) for line in command_lines(examples["node-inspect"])]
    # Then: every command succeeds and describe prints the documented fields
    assert [result.exit_code for result in results] == [0, 0, 0], [result.output for result in results]
    assert "docs.concepts.scale" in results[0].output
    assert "version: 1.0.0" in results[1].output
    assert "source_location: concepts_nodes:scale" in results[1].output


@_twins("node")
def test_recording_settings_load__tc_doc_con_ep_003(doc: Path, tmp_path: Path) -> None:
    """TC-DOC-CON-EP-003: the documented YAML is accepted by the Runner's loader."""
    from rdetoolkit.runner import load_run_config

    # Given: the documented settings saved as the project rdeconfig.yaml
    (tmp_path / "rdeconfig.yaml").write_text(page_examples(doc)["node-config"].code, encoding="utf-8")
    # When: loading the effective configuration
    config = load_run_config(tmp_path)
    # Then: the quoted on/off strings reach the strict model
    assert config.provenance.repr_head == "off"
    assert config.provenance.repr_head_len == 80
    assert config.execution.type_check == "warn"


@_twins("flow")
@pytest.mark.usefixtures("registries")
def test_flow_examples_execute__tc_doc_con_ep_004(
    doc: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-DOC-CON-EP-004: every flow-page example runs and its assertions hold."""
    monkeypatch.setenv("MPLCONFIGDIR", str(tmp_path / "mpl"))
    examples = page_examples(doc)
    for name in sorted(PAGES["flow"]):
        # Given: a fresh namespace exposing the page's ``workdir``
        workdir = tmp_path / name
        workdir.mkdir()
        namespace: dict[str, object] = {"__name__": f"docs_concepts_{name.replace('-', '_')}", "workdir": workdir}
        # When/Then: the example executes with its own assertions
        exec(examples[name].code, namespace)  # noqa: S102


@_twins("runner")
@pytest.mark.usefixtures("registries")
def test_runner_error_policy_example_executes__tc_doc_con_ep_005(
    doc: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-DOC-CON-EP-005: continue gives partial and fail_fast gives failed, as documented."""
    # Given: an initialised project with bad.txt and good.txt as inputs
    monkeypatch.chdir(tmp_path)
    assert CliRunner().invoke(app, ["init"]).exit_code == 0
    container = tmp_path / "container"
    (container / "data" / "inputdata" / "bad.txt").write_text("b\n", encoding="utf-8")
    (container / "data" / "inputdata" / "good.txt").write_text("a\n", encoding="utf-8")
    monkeypatch.chdir(container)
    namespace: dict[str, object] = {"__name__": "docs_concepts_runner"}
    # When: executing the documented example
    exec(page_examples(doc)["runner-error-policy"].code, namespace)  # noqa: S102
    # Then: its assertions held, and the failed run wrote job.failed with code 3001
    assert (container / "data" / "job.failed").read_text(encoding="utf-8").startswith("ErrorCode=3001")


@pytest.mark.parametrize("page", sorted(PAGES))
@pytest.mark.parametrize("suffix", ["", ".en"], ids=["ja", "en"])
def test_every_fence_is_marked_and_owned__tc_doc_con_bv_001(page: str, suffix: str) -> None:
    """TC-DOC-CON-BV-001: no unmarked fence exists and each page's executed set is fixed."""
    assert executed_names(CONCEPTS / f"{page}{suffix}.md") == PAGES[page]


@EACH_DOC
def test_prose_has_no_mention_tokens__tc_doc_con_bv_002(doc: Path) -> None:
    """TC-DOC-CON-BV-002: an ``@``-prefixed token may appear only inside a code fence."""
    assert mention_hazards(doc) == []


@pytest.mark.parametrize("page", sorted(PAGES))
def test_language_twins_carry_identical_examples__tc_doc_con_bv_003(page: str) -> None:
    """TC-DOC-CON-BV-003: the Japanese and English pages execute the same code."""
    ja, en = CONCEPTS / f"{page}.md", CONCEPTS / f"{page}.en.md"
    assert executed_twins(en) == executed_twins(ja)
    assert page_examples(en).keys() == page_examples(ja).keys()
