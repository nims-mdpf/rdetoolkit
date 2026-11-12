"""RDE-003 (#639): one canonical ``rdetoolkit.graph`` export inventory.

Every lazy package attribute is classified into exactly one tier:

* ``supported`` -- GA public API: in runtime ``__all__``, ``__dir__`` and the
  package stub.
* ``compatibility`` -- names the shipped package stub already promised; they
  stay in ``__all__`` and the stub so strict-typed consumers do not break, but
  new code should import them from their defining submodule.
* ``private`` -- implementation helpers that were only reachable through the
  lazy map. They are absent from ``__all__``, ``__dir__`` and the stub; the
  runtime attribute still resolves so existing imports keep working.

The authoritative inventory is the table in ``docs/rdetoolkit/csv2graph.md``;
the tests below tie that table, the runtime maps and the stub together.

EP table:
| TC | Partition | Input | Expected |
|----|-----------|-------|----------|
| TC-639-EP-1 | supported names at runtime | every supported name | resolves to the defining submodule's object |
| TC-639-EP-2 | compatibility names at runtime | every compatibility name | resolves to the defining submodule's object |
| TC-639-EP-3 | runtime ``__all__`` | ``rdetoolkit.graph.__all__`` | supported + compatibility, no duplicates |
| TC-639-EP-4 | stub drift | AST of ``graph/__init__.pyi`` | re-exports == stub ``__all__`` == runtime ``__all__``, same source modules |
| TC-639-EP-5 | documented inventory | docs table | equals the runtime classification |
| TC-639-EP-6 | strict mypy consumer | import every ``__all__`` name + typed calls | clean |
| TC-639-EP-7 | ``csv2graph`` compatibility | package root vs ``graph.api`` vs CLI binding | same object, parameter list unchanged |
| TC-639-EP-8 | ``graph/api/csv2graph.pyi`` drift | stub ``def`` vs ``inspect.signature`` | one declaration per entry point, same names/kinds/defaults |
| TC-639-EP-9 | documented ``csv2graph`` calls | ``html_output_dir=`` keyword and positional order | strict mypy clean |

BV table:
| TC | Boundary | Input | Expected |
|----|----------|-------|----------|
| TC-639-BV-1 | private name, runtime | ``rdetoolkit.graph.RenderResult`` etc. | still resolves (runtime import behaviour unchanged) |

Negative table:
| TC | Partition | Input | Expected |
|----|-----------|-------|----------|
| TC-639-NG-1 | private name in ``__all__`` | private names | absent |
| TC-639-NG-2 | private name in ``dir()`` | ``dir()`` before and after access | absent |
| TC-639-NG-3 | private name in stub | stub AST | absent |
| TC-639-NG-4 | unknown attribute | ``rdetoolkit.graph.no_such_name`` | ``AttributeError`` naming the module |
| TC-639-NG-5 | strict mypy, private import | ``from rdetoolkit.graph import <private>`` | ``[attr-defined]`` for every private name |
| TC-639-NG-6 | star import | ``from rdetoolkit.graph import *`` | binds no private name |
| TC-639-NG-7 | strict mypy, wrong argument | ``csv2graph(1)`` / ``PlotMode`` misuse | ``[arg-type]`` |
| TC-639-NG-8 | tier overlap | the three tier maps | pairwise disjoint, union == lazy map |
"""

from __future__ import annotations

import ast
import importlib
import inspect
import re
import subprocess
import sys
from pathlib import Path

import pytest

import rdetoolkit.graph as graph_pkg

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STUB_PATH = PROJECT_ROOT / "src" / "rdetoolkit" / "graph" / "__init__.pyi"
DOC_PATH = PROJECT_ROOT / "docs" / "rdetoolkit" / "csv2graph.md"

SUPPORTED = (
    "csv2graph",
    "plot_from_dataframe",
    "GraphPlottingError",
    "ColumnNotFoundError",
    "InvalidMetadataError",
    "InvalidCSVFormatError",
    "DirectionError",
    "DualAxisError",
    "PlotConfigError",
    "RendererError",
    "PlotMode",
    "CSVFormat",
    "Direction",
    "AxisConfig",
    "LegendConfig",
    "DirectionConfig",
    "OutputConfig",
    "PlotConfig",
    "CSVMetadata",
    "ParsedData",
)
COMPATIBILITY = (
    "titleize",
    "sanitize_filename",
    "to_snake_case",
    "parse_header",
    "ColumnNormalizer",
    "validate_column_specs",
    "PlotConfigBuilder",
    "apply_matplotlib_config",
    "DEFAULT_FIG_SIZE",
    "DEFAULT_PLOT_PARAMS",
)
PRIVATE = (
    "normalize_direction_filter",
    "build_direction_config",
    "RenderResult",
    "MatplotlibArtifact",
    "NormalizedColumns",
    "RenderCollections",
    "resolve_column_index",
    "determine_titles",
    "determine_formats",
    "normalize_axis_limits",
    "collect_render_results",
    "build_matplotlib_artifacts",
)
TIER_OF = {
    **dict.fromkeys(SUPPORTED, "supported"),
    **dict.fromkeys(COMPATIBILITY, "compatibility"),
    **dict.fromkeys(PRIVATE, "private"),
}


def _stub_reexports() -> tuple[dict[str, tuple[str, str]], list[str]]:
    """Return ``{name: (module, attr)}`` for ``X as X`` re-exports and the stub ``__all__``."""
    tree = ast.parse(STUB_PATH.read_text(encoding="utf-8"))
    reexports: dict[str, tuple[str, str]] = {}
    stub_all: list[str] = []
    for stmt in tree.body:
        if isinstance(stmt, ast.ImportFrom) and stmt.module is not None:
            for alias in stmt.names:
                # Only the explicit ``name as name`` form is a re-export in a stub.
                if alias.asname == alias.name:
                    reexports[alias.name] = (stmt.module, alias.name)
        elif isinstance(stmt, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in stmt.targets):
            stub_all = list(ast.literal_eval(stmt.value))
    return reexports, stub_all


def _doc_inventory() -> dict[str, tuple[str, str]]:
    """Parse the ``| `name` | tier | `module` |`` rows between the inventory markers."""
    text = DOC_PATH.read_text(encoding="utf-8")
    match = re.search(r"<!-- graph-export-inventory:start -->(.*?)<!-- graph-export-inventory:end -->", text, re.DOTALL)
    assert match is not None, "inventory markers missing from the graph API page"
    rows: dict[str, tuple[str, str]] = {}
    for line in match.group(1).splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and cells[0].startswith("`"):
            rows[cells[0].strip("`")] = (cells[1], cells[2].strip("`"))
    return rows


def _mypy(tmp_path: Path, source: str) -> subprocess.CompletedProcess[str]:
    consumer = tmp_path / "consumer.py"
    consumer.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "--ignore-missing-imports", "--no-incremental", str(consumer)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )


def _canonical(name: str) -> object:
    module_name, attr = graph_pkg._LAZY_ATTRS[name]
    return getattr(importlib.import_module(module_name), attr)


@pytest.mark.parametrize("name", SUPPORTED)
def test_supported_names_resolve_to_defining_object__tc_639_ep_1(name: str) -> None:
    """TC-639-EP-1: every supported export is importable at runtime."""
    # Given: a supported name in the inventory
    # When: it is read from the package root
    value = getattr(graph_pkg, name)
    # Then: it is the object the defining submodule exports
    assert value is _canonical(name)


@pytest.mark.parametrize("name", COMPATIBILITY)
def test_compatibility_names_resolve_to_defining_object__tc_639_ep_2(name: str) -> None:
    """TC-639-EP-2: compatibility-only exports keep working at runtime."""
    # Given/When: a compatibility name read from the package root
    value = getattr(graph_pkg, name)
    # Then: it is the object the defining submodule exports
    assert value is _canonical(name)


def test_runtime_all_is_supported_plus_compatibility__tc_639_ep_3() -> None:
    """TC-639-EP-3: ``__all__`` lists exactly the approved names, once each."""
    # Given/When: the runtime export list
    exported = list(graph_pkg.__all__)
    # Then: it is the approved set without duplicates, supported names first
    assert len(exported) == len(set(exported))
    assert exported == [*SUPPORTED, *COMPATIBILITY]
    assert list(graph_pkg._PUBLIC_ATTRS) == list(SUPPORTED)
    assert list(graph_pkg._COMPAT_ATTRS) == list(COMPATIBILITY)
    assert list(graph_pkg._PRIVATE_ATTRS) == list(PRIVATE)


def test_stub_matches_runtime_exports__tc_639_ep_4() -> None:
    """TC-639-EP-4: drift check between the package stub and the runtime maps."""
    # Given: the parsed package stub
    reexports, stub_all = _stub_reexports()
    # When/Then: re-exports, stub ``__all__`` and runtime ``__all__`` agree
    assert sorted(reexports) == sorted(stub_all) == sorted(graph_pkg.__all__)
    assert stub_all == list(graph_pkg.__all__)
    # And: each stub re-export names the module the lazy map imports from
    for name, source in reexports.items():
        assert source == graph_pkg._LAZY_ATTRS[name], name


def test_documented_inventory_matches_runtime__tc_639_ep_5() -> None:
    """TC-639-EP-5: the docs table is the single authoritative inventory."""
    # Given: the documented inventory table
    documented = _doc_inventory()
    # When/Then: it covers every lazy attribute with the same tier and module
    assert sorted(documented) == sorted(graph_pkg._LAZY_ATTRS)
    for name, (tier, module) in documented.items():
        assert tier == TIER_OF[name], name
        assert module == graph_pkg._LAZY_ATTRS[name][0], name


@pytest.mark.slow
def test_strict_consumer_imports_every_export__tc_639_ep_6(tmp_path: Path) -> None:
    """TC-639-EP-6: every approved export is importable by strict mypy."""
    # Given: a consumer importing all ``__all__`` names and using the main API
    names = ", ".join(graph_pkg.__all__)
    source = f"""from pathlib import Path
from rdetoolkit.graph import {names}

def render(out: Path) -> None:
    csv2graph(out / "data.csv", output_dir=out, mode="overlay", csv_format="standard")
    config = PlotConfig(mode=PlotMode.OVERLAY)
    _: PlotConfig = config
    try:
        csv2graph("x.csv")
    except GraphPlottingError as exc:
        _e: Exception = exc
    error: GraphPlottingError = ColumnNotFoundError("x")
    axis: AxisConfig = AxisConfig(label="x")
    direction: Direction = Direction.CHARGE
    size: tuple[float, float] = DEFAULT_FIG_SIZE
    label: str = titleize("x")
"""
    # When: checked with strict mypy against the installed package
    result = _mypy(tmp_path, source)
    # Then: no diagnostics
    assert result.returncode == 0, result.stdout + result.stderr


CSV2GRAPH_PARAMETERS = [
    "csv_path", "output_dir", "main_image_dir", "html_output_dir", "csv_format", "logy", "logx", "html", "mode",
    "x_col", "y_cols", "direction_cols", "direction_filter", "direction_colors", "title", "legend_info",
    "legend_loc", "xlim", "ylim", "grid", "invert_x", "invert_y", "no_individual", "max_legend_items",
    "legend_policy", "legend_outside_threshold", "legend_bottom_threshold", "legend_ncol",
    "x_tick_format", "y_tick_format",
]


def test_csv2graph_entry_point_is_unchanged__tc_639_ep_7() -> None:
    """TC-639-EP-7: the documented ``csv2graph`` entry point stays the same object."""
    # Given: the three ways v1 code reaches csv2graph
    from rdetoolkit.cmd import csv2graph as cmd_module  # noqa: PLC0415
    from rdetoolkit.graph import csv2graph  # noqa: PLC0415
    from rdetoolkit.graph.api import csv2graph as api_csv2graph  # noqa: PLC0415

    # When/Then: they are the same function with the same parameter list
    assert csv2graph is api_csv2graph is cmd_module.api_csv2graph
    assert list(inspect.signature(csv2graph).parameters) == CSV2GRAPH_PARAMETERS


API_STUB_PATH = PROJECT_ROOT / "src" / "rdetoolkit" / "graph" / "api" / "csv2graph.pyi"


def _stub_parameters(func: ast.FunctionDef) -> list[tuple[str, str, bool]]:
    """Return ``(name, kind, has_default)`` for every parameter of a stub ``def``."""
    args = func.args
    positional = args.posonlyargs + args.args
    first_default = len(positional) - len(args.defaults)
    params = [(a.arg, "POSITIONAL_OR_KEYWORD", i >= first_default) for i, a in enumerate(positional)]
    params += [(a.arg, "KEYWORD_ONLY", d is not None) for a, d in zip(args.kwonlyargs, args.kw_defaults, strict=True)]
    return params


@pytest.mark.parametrize("name", ["csv2graph", "plot_from_dataframe"])
def test_api_stub_declares_runtime_signature_once__tc_639_ep_8(name: str) -> None:
    """TC-639-EP-8: ``graph/api/csv2graph.pyi`` declares each entry point once, matching runtime."""
    # Given: the runtime function and every stub ``def`` of the same name
    runtime = getattr(importlib.import_module("rdetoolkit.graph.api.csv2graph"), name)
    tree = ast.parse(API_STUB_PATH.read_text(encoding="utf-8"))
    defs = [stmt for stmt in tree.body if isinstance(stmt, ast.FunctionDef) and stmt.name == name]
    # When: comparing parameter name, kind and default presence
    expected = [
        (p.name, p.kind.name, p.default is not inspect.Parameter.empty)
        for p in inspect.signature(runtime).parameters.values()
    ]
    # Then: exactly one declaration (a duplicate makes mypy and pyright disagree) and it matches
    assert len(defs) == 1, f"{name} declared {len(defs)} times in {API_STUB_PATH.name}"
    assert _stub_parameters(defs[0]) == expected


@pytest.mark.slow
def test_strict_consumer_documented_csv2graph_calls__tc_639_ep_9(tmp_path: Path) -> None:
    """TC-639-EP-9: documented ``csv2graph`` keyword and positional calls type check."""
    # Given: calls using html_output_dir by keyword and the runtime positional order
    source = """from pathlib import Path
from rdetoolkit.graph import csv2graph
from rdetoolkit.graph.api import csv2graph as api_csv2graph

csv2graph("data.csv", output_dir="out", html=True, html_output_dir=Path("html"))
csv2graph("data.csv", "out", None, "html", "transpose", True, False, True, "individual")
api_csv2graph(Path("data.csv"), html_output_dir=None, csv_format="noheader", x_tick_format="sci")
"""
    # When: checked with strict mypy
    result = _mypy(tmp_path, source)
    # Then: no diagnostics
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("name", PRIVATE)
def test_private_names_still_resolve_at_runtime__tc_639_bv_1(name: str) -> None:
    """TC-639-BV-1: demoting a helper does not break existing runtime imports."""
    # Given/When: a private helper read from the package root
    value = getattr(graph_pkg, name)
    # Then: it is still the defining submodule's object
    assert value is _canonical(name)


@pytest.mark.parametrize("name", PRIVATE)
def test_private_names_not_in_all__tc_639_ng_1(name: str) -> None:
    """TC-639-NG-1: private helpers are not promised through ``__all__``."""
    # Given/When/Then: the name is absent from the export list
    assert name not in graph_pkg.__all__


def test_private_names_not_in_dir__tc_639_ng_2() -> None:
    """TC-639-NG-2: ``dir()`` does not advertise private helpers, even once cached."""
    # Given: every private helper has been accessed (and cached) once
    for name in PRIVATE:
        getattr(graph_pkg, name)
    # When: the module namespace is listed
    listed = set(dir(graph_pkg))
    # Then: no private helper appears, every approved name does
    assert listed.isdisjoint(PRIVATE)
    assert set(graph_pkg.__all__) <= listed


def test_private_names_not_in_stub__tc_639_ng_3() -> None:
    """TC-639-NG-3: the stub never declares a private helper."""
    # Given: the parsed stub
    reexports, stub_all = _stub_reexports()
    stub_text = STUB_PATH.read_text(encoding="utf-8")
    # When/Then: no private name is declared or mentioned
    for name in PRIVATE:
        assert name not in reexports
        assert name not in stub_all
        assert re.search(rf"\b{name}\b", stub_text) is None, name


def test_unknown_attribute_raises_attribute_error__tc_639_ng_4() -> None:
    """TC-639-NG-4: unknown names fail like a normal module attribute."""
    # Given/When/Then: an unknown attribute raises AttributeError naming the module
    with pytest.raises(AttributeError, match=r"module 'rdetoolkit\.graph' has no attribute 'no_such_name'"):
        _ = graph_pkg.no_such_name


@pytest.mark.slow
def test_strict_consumer_cannot_import_private_helpers__tc_639_ng_5(tmp_path: Path) -> None:
    """TC-639-NG-5: strict mypy rejects every private helper import from the root."""
    # Given: a consumer importing each private helper from the package root
    source = "".join(f"from rdetoolkit.graph import {name}\n" for name in PRIVATE)
    # When: checked with strict mypy
    result = _mypy(tmp_path, source)
    # Then: one attr-defined error per private helper
    assert result.returncode == 1, result.stdout + result.stderr
    for name in PRIVATE:
        assert f'Module "rdetoolkit.graph" has no attribute "{name}"' in result.stdout, name
    assert result.stdout.count("[attr-defined]") == len(PRIVATE)


def test_star_import_binds_no_private_helper__tc_639_ng_6() -> None:
    """TC-639-NG-6: ``import *`` follows ``__all__`` and omits private helpers."""
    # Given: an empty namespace
    namespace: dict[str, object] = {}
    # When: star-importing the package
    exec("from rdetoolkit.graph import *", namespace)  # noqa: S102
    # Then: approved names are bound, private ones are not
    assert set(graph_pkg.__all__) <= set(namespace)
    assert set(namespace).isdisjoint(PRIVATE)


@pytest.mark.slow
@pytest.mark.parametrize(
    "source",
    [
        "from rdetoolkit.graph import csv2graph\ncsv2graph(1)\n",
        'from rdetoolkit.graph import csv2graph\ncsv2graph("x.csv", mode="bad")\n',
        'from rdetoolkit.graph import titleize\ntitleize(1)\n',
    ],
)
def test_strict_consumer_wrong_arguments_rejected__tc_639_ng_7(tmp_path: Path, source: str) -> None:
    """TC-639-NG-7: the package stub keeps real signatures (not ``Any``)."""
    # Given/When: a consumer passing an invalid argument
    result = _mypy(tmp_path, source)
    # Then: mypy reports an argument-type error
    assert result.returncode == 1, result.stdout + result.stderr
    assert "[arg-type]" in result.stdout


def test_tiers_are_disjoint_and_cover_lazy_map__tc_639_ng_8() -> None:
    """TC-639-NG-8: no name is classified twice and none is left unclassified."""
    # Given: the three runtime tier maps
    public, compat, private = (set(graph_pkg._PUBLIC_ATTRS), set(graph_pkg._COMPAT_ATTRS), set(graph_pkg._PRIVATE_ATTRS))
    # When/Then: pairwise disjoint and their union is the lazy map
    assert public.isdisjoint(compat)
    assert public.isdisjoint(private)
    assert compat.isdisjoint(private)
    assert public | compat | private == set(graph_pkg._LAZY_ATTRS)
