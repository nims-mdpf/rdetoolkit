"""QA-01 (#736): public API and type-stub contracts for graph, modes and magic.

#639 (``test_rde003_graph_public_api.py``) owns the ``rdetoolkit.graph`` package
inventory. This module covers the GA APIs added after it -- GraphSpec, the magic
resolver/policy and ModeDecision -- and the stub drift check for the packages
that hold them.

EP table:
| TC | Partition | Input | Expected |
|----|-----------|-------|----------|
| TC-736-EP-1 | approved names at runtime | every ``INVENTORY`` name | importable from its module |
| TC-736-EP-2 | approved names in stubs | public names declared by each ``.pyi`` | equal to ``INVENTORY`` |
| TC-736-EP-3 | runtime ``__all__`` | modules that define one | approved names only, equal to the stub ``__all__`` |
| TC-736-EP-4 | stub drift | ``mypy.stubtest`` over ``STUBTEST_PACKAGES`` | clean with the checked-in allowlist |
| TC-736-EP-5 | strict consumer | GraphSpec + magic resolver/policy + ModeDecision + preview | ``mypy --strict`` clean |
| TC-736-EP-6 | the same consumer executed | real input project | runs, values as typed |

Negative table:
| TC | Partition | Input | Expected |
|----|-----------|-------|----------|
| TC-736-NG-1 | runtime function missing from its stub | throwaway package | stubtest reports "not present in stub" |
| TC-736-NG-2 | stub function removed at runtime | throwaway package | stubtest reports "not present at runtime" |
| TC-736-NG-3 | stub signature out of date | throwaway package | stubtest reports the differing parameter |
| TC-736-NG-4 | ``X.py``/``X.pyi`` beside package ``X/`` | source tree, and a throwaway tree | none in src; the throwaway shadow is found |
| TC-736-NG-5..9 | invalid consumer calls | wrong Literal, frozen field, wrong container type | precise mypy error code |
"""

from __future__ import annotations

import ast
import importlib
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC = PROJECT_ROOT / "src"
ALLOWLIST = Path(__file__).resolve().parent / "stubtest_allowlist.txt"

# Packages checked recursively by stubtest: every module holding a GA API of
# the graph, magic or mode epics, plus their siblings so a new module cannot
# land beside them without a matching stub.
STUBTEST_PACKAGES = ("rdetoolkit.graph", "rdetoolkit.domain", "rdetoolkit.runner", "rdetoolkit.modes")

# Approved public names of the GA modules. A new public function or class in
# one of these modules must be added here on purpose; anything else is an
# internal helper and needs a leading underscore.
INVENTORY: dict[str, frozenset[str]] = {
    "rdetoolkit.graph.spec": frozenset({
        "AxisLimits", "AxisSpec", "ColumnRef", "GraphSpec", "INVALID_SPEC", "LegendSpec", "Origin", "OutputSpec",
        "SPEC_VERSION", "SeriesSpec", "StyleSpec", "direction_key",
    }),
    "rdetoolkit.graph.plan": frozenset({
        "FigurePlan", "GraphDiagnostic", "OVERLAY_FIGURE_ID", "PlotData", "PlotPlan", "SeriesPlan", "UNIT_MISMATCH",
        "UNIT_UNKNOWN", "build_plot_plan", "column_position",
    }),
    "rdetoolkit.graph.result": frozenset({"Artifact", "ArtifactRole", "GraphResult", "MANIFEST_SCHEMA_VERSION"}),
    "rdetoolkit.graph.engine": frozenset({"render_graph"}),
    "rdetoolkit.graph.outputs": frozenset({"ArtifactSink", "DirectorySink", "OutputContextSink"}),
    "rdetoolkit.graph.readers": frozenset({
        "ColumnProvenance", "DetectionDecision", "FormatCandidate", "READER_ENTRY_POINT_GROUP", "ReaderRegistry",
        "TableData", "TableReader", "builtin_readers", "detect_table_format", "discover_readers", "read_table",
        "resolve_reader",
    }),
    "rdetoolkit.domain.magic": frozenset({
        "MAX_NAME_LENGTH", "MAX_OUTPUT_LENGTH", "MagicOptions", "ResolutionContext", "ResolutionDiagnostic",
        "ResolutionPreview", "preview_invoice", "resolve_invoice",
    }),
    "rdetoolkit.domain.magic_policy": frozenset({"options_from_config"}),
    "rdetoolkit.domain.mode_selection": frozenset({"ModeDecision", "ModeEvidence", "ModeKind", "decide_mode", "normalize_mode_name"}),
    "rdetoolkit.runner.mode_resolver": frozenset({"ModeDecision", "ModeKind", "resolve_mode", "resolve_mode_decision"}),
    "rdetoolkit.runner.preview": frozenset({"MagicPreview", "MagicTilePreview", "PlannedTile", "RegistrationPreview", "preview_registration"}),
    "rdetoolkit.modes.stages": frozenset({
        "ArtifactStage", "DEFAULT_ARTIFACT_STAGE_ORDER", "StageSpec", "artifact_stage_order", "describe_artifact_stages",
        "mode_stage_order", "plan_artifact_stages",
    }),
}


def _stub_path(module: str) -> Path:
    relative = Path(*module.split("."))
    package = SRC / relative / "__init__.pyi"
    return package if package.is_file() else (SRC / relative).with_suffix(".pyi")


def _stub_tree(module: str) -> ast.Module:
    return ast.parse(_stub_path(module).read_text(encoding="utf-8"))


def _stub_public_names(module: str) -> set[str]:
    """Return the public names a stub declares, re-exports (``X as X``) included."""
    names: set[str] = set()
    for stmt in _stub_tree(module).body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(stmt.name)
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            names.add(stmt.target.id)
        elif isinstance(stmt, ast.Assign):
            names.update(target.id for target in stmt.targets if isinstance(target, ast.Name))
        elif isinstance(stmt, ast.ImportFrom):
            names.update(alias.name for alias in stmt.names if alias.asname == alias.name)
    return {name for name in names if not name.startswith("_")}


def _stub_all(module: str) -> list[str] | None:
    for stmt in _stub_tree(module).body:
        if isinstance(stmt, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in stmt.targets):
            return list(ast.literal_eval(stmt.value))
    return None


def _stubtest(cwd: Path, *modules: str, allowlist: Path | None = None, pythonpath: Path | None = None) -> subprocess.CompletedProcess[str]:
    config = cwd / "stubtest.ini"
    config.write_text("[mypy]\nignore_missing_imports = True\n", encoding="utf-8")
    cmd = [sys.executable, "-m", "mypy.stubtest", "--concise", "--mypy-config-file", str(config)]
    if allowlist is not None:
        cmd += ["--allowlist", str(allowlist)]
    env = None
    if pythonpath is not None:
        env = {**os.environ, "PYTHONPATH": str(pythonpath), "MYPYPATH": str(pythonpath)}
    # stubtest writes .mypy_cache into its working directory, so run it in tmp.
    return subprocess.run([*cmd, *modules], cwd=cwd, capture_output=True, text=True, check=False, env=env)  # noqa: S603


def _mypy(tmp_path: Path, source: str) -> subprocess.CompletedProcess[str]:
    consumer = tmp_path / "consumer.py"
    consumer.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "--ignore-missing-imports", "--no-incremental", str(consumer)],
        cwd=tmp_path, capture_output=True, text=True, check=False,
    )


@pytest.mark.parametrize("module", sorted(INVENTORY))
def test_approved_names_import_at_runtime__tc_736_ep_1(module: str) -> None:
    """TC-736-EP-1: every approved name resolves on the runtime module."""
    # Given: the runtime module
    runtime = importlib.import_module(module)
    # When: looking up each approved name
    missing = sorted(name for name in INVENTORY[module] if not hasattr(runtime, name))
    # Then: none is missing
    assert missing == []


@pytest.mark.parametrize("module", sorted(INVENTORY))
def test_stub_public_names_match_inventory__tc_736_ep_2(module: str) -> None:
    """TC-736-EP-2: a stub promises exactly the approved names, no internal helper."""
    # Given/When: the public names the module stub declares
    declared = _stub_public_names(module)
    # Then: they are the approved inventory
    assert sorted(declared - INVENTORY[module]) == [], "unapproved public name in stub (add it to INVENTORY or prefix _)"
    assert sorted(INVENTORY[module] - declared) == [], "approved name missing from stub"


@pytest.mark.parametrize("module", sorted(m for m in INVENTORY if hasattr(importlib.import_module(m), "__all__")))
def test_runtime_all_matches_stub_all__tc_736_ep_3(module: str) -> None:
    """TC-736-EP-3: ``__all__`` lists approved names only, identically at runtime and in the stub."""
    # Given: the runtime and stub ``__all__``
    runtime_all = importlib.import_module(module).__all__
    # When/Then: both list approved names once each
    assert sorted(set(runtime_all) - INVENTORY[module]) == []
    assert len(set(runtime_all)) == len(runtime_all)
    assert sorted(_stub_all(module) or []) == sorted(runtime_all)


def test_stubtest_is_clean_for_ga_packages__tc_736_ep_4(tmp_path: Path) -> None:
    """TC-736-EP-4: CI drift check -- stubs match the runtime of every GA package."""
    # Given: the GA packages and the reviewed allowlist (unused entries also fail)
    # When: stubtest compares every module's stub with its runtime
    result = _stubtest(tmp_path, *STUBTEST_PACKAGES, allowlist=ALLOWLIST)
    # Then: no missing, stale or inconsistent declaration remains
    assert result.returncode == 0, result.stdout + result.stderr


def _throwaway_package(root: Path, runtime: str, stub: str) -> Path:
    package = root / "qa01pkg"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "__init__.pyi").write_text("", encoding="utf-8")
    (package / "py.typed").write_text("", encoding="utf-8")
    (package / "api.py").write_text(textwrap.dedent(runtime), encoding="utf-8")
    (package / "api.pyi").write_text(textwrap.dedent(stub), encoding="utf-8")
    return root


@pytest.mark.parametrize(("runtime", "stub", "expected"), [
    ("def old() -> None: ...\ndef new_api() -> None: ...\n", "def old() -> None: ...\n", "qa01pkg.api.new_api is not present in stub"),
    ("def old() -> None: ...\n", "def old() -> None: ...\ndef removed() -> None: ...\n", "qa01pkg.api.removed is not present at runtime"),
    ("def old(path: str, *, mode: str = 'a') -> None: ...\n", "def old(path: str) -> None: ...\n", 'qa01pkg.api.old is inconsistent, stub does not have parameter "mode"'),
], ids=["tc_736_ng_1_missing_stub", "tc_736_ng_2_stale_stub", "tc_736_ng_3_stale_signature"])
def test_stubtest_detects_drift__tc_736_ng_1_2_3(tmp_path: Path, runtime: str, stub: str, expected: str) -> None:
    """TC-736-NG-1..3: the drift check fails on a missing, stale or out-of-date stub."""
    # Given: a throwaway typed package whose stub disagrees with its runtime
    work = tmp_path / "work"
    work.mkdir()
    root = _throwaway_package(tmp_path, runtime, stub)
    # When: the same stubtest invocation runs on it
    result = _stubtest(work, "qa01pkg", pythonpath=root)
    # Then: the disagreement is reported and the check fails
    assert result.returncode == 1, result.stdout + result.stderr
    assert expected in result.stdout


def _shadowed_modules(root: Path) -> list[str]:
    """Return ``X.py``/``X.pyi`` files that sit beside a package directory ``X/``."""
    return sorted(
        sibling.relative_to(root).as_posix()
        for directory in root.rglob("*")
        if directory.is_dir() and directory.name != "__pycache__"
        for sibling in (directory.with_suffix(".py"), directory.with_suffix(".pyi"))
        if sibling.is_file()
    )


def test_no_module_or_stub_is_shadowed_by_a_package__tc_736_ng_4(tmp_path: Path) -> None:
    """TC-736-NG-4: a package always wins, so a same-named ``.py``/``.pyi`` would drift unseen."""
    # Given: a throwaway tree with the shadowing layout removed from rdetoolkit.graph
    (tmp_path / "pkg" / "parsers").mkdir(parents=True)
    (tmp_path / "pkg" / "parsers.py").touch()
    (tmp_path / "pkg" / "parsers.pyi").touch()
    # When/Then: the detector finds it there, and nothing in the source tree
    assert _shadowed_modules(tmp_path) == ["pkg/parsers.py", "pkg/parsers.pyi"]
    assert _shadowed_modules(SRC) == []


CONSUMER = '''import sys
from pathlib import Path

import pandas as pd

from rdetoolkit.domain.magic import MagicOptions, ResolutionContext, ResolutionDiagnostic, ResolutionPreview, preview_invoice, resolve_invoice
from rdetoolkit.domain.magic_policy import options_from_config
from rdetoolkit.domain.mode_selection import ModeDecision, ModeEvidence, ModeKind, decide_mode
from rdetoolkit.graph import GraphSpec, PlotPlan, SeriesSpec, build_plot_plan
from rdetoolkit.runner.preview import RegistrationPreview, preview_registration
from rdetoolkit.types import RdeConfig


def main(root: Path) -> list[str]:
    config = RdeConfig()
    options: MagicOptions = options_from_config(config)
    context = ResolutionContext.from_sources(
        original_invoice={"custom": {"batch": "B-1"}},
        current_invoice={"basic": {"dataName": "${invoice:custom:batch}"}},
    )
    resolved = resolve_invoice(context, options=MagicOptions(policy="enabled", missing="error"))
    preview: ResolutionPreview = preview_invoice(context, options=options, deferred_scopes=frozenset({"metadata"}))
    first: ResolutionDiagnostic = preview.diagnostics[0]
    decision: ModeDecision = decide_mode(config, root / "data" / "inputdata", contract="v2")
    chosen: ModeKind = decision.chosen_mode
    evidence: tuple[ModeEvidence, ...] = decision.evidence
    registration: RegistrationPreview = preview_registration(root)
    frame = pd.DataFrame({"x": [0, 1], "y": [1.0, 2.0]})
    plan: PlotPlan = build_plot_plan(frame, GraphSpec(x="x", series=(SeriesSpec(y="y"),)), base_name="g")
    return [
        str(resolved["basic"]["dataName"]),
        first.status,
        chosen.value,
        str(len(evidence)),
        registration.decision.chosen_mode.value,
        str(len(plan.series)),
        str(decision.to_dict()["schema_version"]),
    ]


if __name__ == "__main__":
    print(" ".join(main(Path(sys.argv[1]))))
'''


def test_strict_consumer_of_ga_apis__tc_736_ep_5(tmp_path: Path) -> None:
    """TC-736-EP-5: GraphSpec, magic resolver/policy and ModeDecision type-check strictly."""
    # Given: a standalone consumer outside the repository configuration
    # When: strict mypy checks it against the installed package
    result = _mypy(tmp_path, CONSUMER)
    # Then: every import, keyword option and field is typed
    assert result.returncode == 0, result.stdout + result.stderr


def test_strict_consumer_runs__tc_736_ep_6(tmp_path: Path) -> None:
    """TC-736-EP-6: the typed example is also a working example."""
    # Given: a real invoice-mode input project
    from tests.v2.contract.fixtures import _generate

    root = tmp_path / "project"
    _generate.materialize_case(_generate.oracle_case("v1/invoice/ok"), root)
    consumer = tmp_path / "consumer.py"
    consumer.write_text(CONSUMER, encoding="utf-8")
    # When: the consumer runs
    result = subprocess.run([sys.executable, str(consumer), str(root)], cwd=tmp_path, capture_output=True, text=True, check=False)  # noqa: S603
    # Then: the runtime values have the documented shape
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["B-1", "resolved", "invoice", "0", "invoice", "1", "1"]


@pytest.mark.parametrize(("source", "diagnostic"), [
    ('from rdetoolkit.domain.magic import MagicOptions\nMagicOptions(policy="sometimes")\n', "[arg-type]"),
    (
        textwrap.dedent("""\
            from rdetoolkit.domain.mode_selection import ModeDecision, ModeKind
            def invalid(decision: ModeDecision) -> None:
                decision.chosen_mode = ModeKind.invoice
        """),
        "[misc]",
    ),
    (
        textwrap.dedent("""\
            from pathlib import Path
            from rdetoolkit.domain.mode_selection import decide_mode
            from rdetoolkit.types import RdeConfig
            decide_mode(RdeConfig(), Path("."), contract="v3")
        """),
        "[arg-type]",
    ),
    (
        textwrap.dedent("""\
            from rdetoolkit.domain.magic import ResolutionContext, preview_invoice
            def invalid(context: ResolutionContext) -> None:
                preview_invoice(context, deferred_scopes={"metadata"})
        """),
        "[arg-type]",
    ),
    ('from rdetoolkit.graph import GraphSpec, SeriesSpec\nGraphSpec(x="x", series=[SeriesSpec(y="y")])\n', "[arg-type]"),
], ids=["tc_736_ng_5_magic_policy", "tc_736_ng_6_frozen_decision", "tc_736_ng_7_contract", "tc_736_ng_8_deferred_scopes", "tc_736_ng_9_series_tuple"])
def test_invalid_ga_usage_is_rejected__tc_736_ng_5_to_9(tmp_path: Path, source: str, diagnostic: str) -> None:
    """TC-736-NG-5..9: the stubs keep the runtime constraints, not ``Any``."""
    # Given: a consumer misusing one GA API
    # When: strict mypy checks it
    result = _mypy(tmp_path, source)
    # Then: the precise violation is reported
    assert result.returncode == 1, result.stdout + result.stderr
    assert diagnostic in result.stdout
