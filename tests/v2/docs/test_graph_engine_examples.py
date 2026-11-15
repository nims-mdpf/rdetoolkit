"""Executed examples of the Graph Engine guide (custom reader and custom renderer).

The two example scripts under ``docs/usage/structured_process/graph_engine_samples/``
are loaded with ``runpy.run_path`` and their ``main(output_dir)`` is called. They
must integrate a third-party ``TableReader`` and ``GraphRenderer`` through the public
``rdetoolkit.graph`` surface only: no private module, no monkeypatching, no edit of
rdetoolkit. The guide pages must include the scripts instead of retyping them.

EP table
========

| Example | Partition | Expected | Test ID |
|---|---|---|---|
| custom_reader.py | ``main(tmp)`` | the vendor reader is selected from the suffix; one PNG == manifest; metadata kept | TC-DOC-GE-EP-001 |
| custom_renderer.py | ``main(tmp)`` | three SVGs by ``svg-sketch`` == manifest; one polyline per series | TC-DOC-GE-EP-002 |
| both pages | ja / en | each script included through a snippet line inside a python fence | TC-DOC-GE-EP-003 |

BV table
========

| Example | Boundary | Expected | Test ID |
|---|---|---|---|
| custom_reader.py | ``main`` run twice into one directory | same file set; every artifact ``replaced_existing=True`` | TC-DOC-GE-BV-001 |

Negative cases
==============

| Example | Partition | Expected | Test ID |
|---|---|---|---|
| both | rdetoolkit imports | only ``rdetoolkit.graph`` names from ``__all__``; no private, ``compat``, ``naming`` or ``mpl_runtime`` reference | TC-DOC-GE-NEG-001 |
| both | ``rdetoolkit.graph`` modules after running | every module attribute is the same object as before (nothing patched) | TC-DOC-GE-NEG-002 |
| custom_reader.py | the same file without the caller registry | ``AmbiguousFormatError`` or ``InvalidCSVFormatError``: the format is not guessed | TC-DOC-GE-NEG-003 |
| custom_renderer.py | its registry asked for PNG | ``UnsupportedFormatError`` before any file exists | TC-DOC-GE-NEG-004 |
"""

from __future__ import annotations

import ast
import re
import runpy
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

import rdetoolkit.graph as graph_api
from rdetoolkit.graph import (
    DirectorySink,
    GraphSpec,
    InvalidCSVFormatError,
    OutputSpec,
    UnsupportedFormatError,
    render_graph,
)

DOCS_DIR = Path(__file__).parents[3] / "docs"
SAMPLES = DOCS_DIR / "usage" / "structured_process" / "graph_engine_samples"
READER = SAMPLES / "custom_reader.py"
RENDERER = SAMPLES / "custom_renderer.py"
PAGES = [DOCS_DIR / "usage" / "structured_process" / f"graph_engine.{lang}.md" for lang in ("ja", "en")]
FORBIDDEN = ("rdetoolkit.graph._", "compat", "naming", "mpl_runtime", "monkeypatch", "setattr")


def _run(script: Path) -> dict[str, Any]:
    return runpy.run_path(str(script), run_name="graph_engine_example")


def _files(root: Path) -> list[str]:
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())


def _graph_state() -> dict[str, dict[str, int]]:
    return {
        name: {attr: id(value) for attr, value in vars(module).items()}
        for name, module in sorted(sys.modules.items())
        if module is not None and (name == "rdetoolkit.graph" or name.startswith("rdetoolkit.graph."))
    }


def _rdetoolkit_imports(script: Path) -> list[tuple[str, tuple[str, ...]]]:
    imports: list[tuple[str, tuple[str, ...]]] = []
    for node in ast.walk(ast.parse(script.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("rdetoolkit"):
            imports.append((node.module or "", tuple(alias.name for alias in node.names)))
        elif isinstance(node, ast.Import):
            imports.extend((alias.name, ()) for alias in node.names if alias.name.startswith("rdetoolkit"))
    return imports


def test_custom_reader_example_runs__tc_doc_ge_ep_001(tmp_path: Path) -> None:
    """TC-DOC-GE-EP-001: the custom reader plots the vendor file through render_graph."""
    # Given: the example script
    namespace = _run(READER)
    # When: running its main into an empty directory
    result = namespace["main"](tmp_path)
    # Then: the vendor reader was selected from the suffix and every file is in the manifest
    assert result.detection.selected == "vendor.instrument"
    assert result.detection.forced is False
    assert _files(tmp_path) == ["graphs/instrument.png", "sample.instrument"]
    assert [a.path for a in result.artifacts] == [tmp_path / "graphs" / "instrument.png"]
    assert [(a.renderer, a.labels) for a in result.artifacts] == [("matplotlib", ("Signal",))]
    assert (tmp_path / "graphs" / "instrument.png").read_bytes().startswith(b"\x89PNG")
    table = namespace["InstrumentReader"]().read(tmp_path / "sample.instrument")
    assert dict(table.metadata) == {"title": "Sample run", "instrument": "vendor X-1"}
    assert list(table.frame.columns) == ["time (s)", "signal (mV)"]


def test_custom_renderer_example_runs__tc_doc_ge_ep_002(tmp_path: Path) -> None:
    """TC-DOC-GE-EP-002: the injected renderer draws every figure as SVG text."""
    # Given: the example script
    namespace = _run(RENDERER)
    # When: running its main
    result = namespace["main"](tmp_path)
    # Then: one overlay and two individual SVGs, all by the custom renderer and all listed
    expected = ["sketch.svg", "sketch_noise_(mv).svg", "sketch_signal_(mv).svg"]
    assert _files(tmp_path) == expected
    assert sorted(a.path.name for a in result.artifacts) == expected
    assert {(a.renderer, a.format) for a in result.artifacts} == {("svg-sketch", "svg")}
    overlay = (tmp_path / "sketch.svg").read_text(encoding="utf-8")
    assert overlay.startswith('<svg xmlns="http://www.w3.org/2000/svg"')
    assert overlay.count("<polyline") == 2
    assert "<title>Signal</title>" in overlay
    assert (tmp_path / "sketch_noise_(mv).svg").read_text(encoding="utf-8").count("<polyline") == 1


@pytest.mark.parametrize("page", PAGES, ids=["ja", "en"])
def test_pages_include_the_example_files__tc_doc_ge_ep_003(page: Path) -> None:
    """TC-DOC-GE-EP-003: the guide shows the scripts by inclusion, not by retyping."""
    # Given: one language page
    text = page.read_text(encoding="utf-8")
    # When: collecting the python fences
    fences = re.findall(r"```python[^\n]*\n(.*?)```", text, flags=re.DOTALL)
    # Then: each script is included by a snippet line, and no fence retypes a class of it
    for script in (READER, RENDERER):
        include = f'--8<-- "{script.relative_to(DOCS_DIR.parent).as_posix()}"'
        assert any(fence.strip() == include for fence in fences), include
    assert not any("class InstrumentReader" in fence or "class SvgSketchRenderer" in fence for fence in fences)


def test_reader_example_rerun_records_replacement__tc_doc_ge_bv_001(tmp_path: Path) -> None:
    """TC-DOC-GE-BV-001: running the example twice overwrites visibly, not silently."""
    # Given: one completed run of the reader example
    main = _run(READER)["main"]
    main(tmp_path)
    # When: running it again into the same directory
    second = main(tmp_path)
    # Then: the file set is unchanged and the replacement is recorded
    assert _files(tmp_path) == ["graphs/instrument.png", "sample.instrument"]
    assert [a.replaced_existing for a in second.artifacts] == [True]


@pytest.mark.parametrize("script", [READER, RENDERER], ids=["reader", "renderer"])
def test_examples_import_only_the_public_surface__tc_doc_ge_neg_001(script: Path) -> None:
    """TC-DOC-GE-NEG-001: the examples use nothing private from rdetoolkit."""
    # Given: the example source
    source = script.read_text(encoding="utf-8")
    # When: collecting its rdetoolkit imports
    imports = _rdetoolkit_imports(script)
    # Then: one import of public rdetoolkit.graph names, and no private reference
    assert [module for module, _names in imports] == ["rdetoolkit.graph"]
    assert set(imports[0][1]) <= set(graph_api.__all__)
    assert [token for token in FORBIDDEN if token in source] == []


@pytest.mark.parametrize("script", [READER, RENDERER], ids=["reader", "renderer"])
def test_examples_do_not_patch_rdetoolkit__tc_doc_ge_neg_002(script: Path, tmp_path: Path) -> None:
    """TC-DOC-GE-NEG-002: running an example leaves every rdetoolkit.graph module unchanged."""
    # Given: the graph modules as loaded by importing the example (lazy exports resolved)
    namespace = _run(script)
    before = _graph_state()
    # When: running the example
    namespace["main"](tmp_path)
    # Then: no attribute of an already-loaded graph module was rebound or removed
    after = _graph_state()
    changed = {
        (module, attr) for module, attrs in before.items() for attr, ident in attrs.items() if after[module].get(attr) != ident
    }
    assert changed == set()


def test_vendor_file_is_not_guessed_without_the_reader__tc_doc_ge_neg_003(tmp_path: Path) -> None:
    """TC-DOC-GE-NEG-003: without the caller registry, the vendor file is refused."""
    # Given: the sample file written by the example
    namespace = _run(READER)
    source = tmp_path / "sample.instrument"
    source.write_text(namespace["SAMPLE"], encoding="utf-8")
    # When: rendering it with the builtin readers only
    with pytest.raises(InvalidCSVFormatError):
        render_graph(source, output=OutputSpec(DirectorySink(tmp_path / "graphs")))
    # Then: nothing was written
    assert not (tmp_path / "graphs").exists()


def test_renderer_registry_refuses_undeclared_formats__tc_doc_ge_neg_004(tmp_path: Path) -> None:
    """TC-DOC-GE-NEG-004: a format the injected renderer does not declare fails before writing."""
    # Given: a registry holding only the example renderer
    namespace = _run(RENDERER)
    registry = graph_api.RendererRegistry([namespace["SvgSketchRenderer"]()])
    frame = pd.DataFrame({"x": [0, 1], "y": [1, 2]})
    # When: asking it for PNG
    with pytest.raises(UnsupportedFormatError):
        render_graph(frame, GraphSpec(), output=OutputSpec(DirectorySink(tmp_path / "out")), renderers=registry)
    # Then: nothing was written
    assert not (tmp_path / "out").exists()
