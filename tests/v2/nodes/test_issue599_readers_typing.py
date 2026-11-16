"""Issue 599 (readers): the installed stubs type the new reader options precisely.

pandas ships no type information, so ``pd.DataFrame`` is ``Any`` to a plain
consumer and any return type would pass. The consumer below therefore gets a
nominal ``pandas.DataFrame`` stub on ``MYPYPATH``: a leaked ``Any`` or a dict
can then no longer pass as a DataFrame under ``assert_type``.

| Partition | Expected | Test ID |
|---|---|---|
| str / DataFrame / dict results for every documented call shape | strict consumer passes | I599R-TYPE-001 |
| wrong result type, positional option, bad option type, bad sheet selection | precise diagnostic | I599R-TYPE-NEG-001 |
| io.pyi and io.py declare the same signatures, overloads included | identical | I599R-TYPE-002 |
| io.pyi checked on its own under --strict | clean | I599R-TYPE-003 |
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

import rdetoolkit.nodes.io as io_module

_PANDAS_STUB = "from typing import Any\n\nclass DataFrame: ...\n\ndef __getattr__(name: str) -> Any: ...\n"

_HEADER = """from pathlib import Path
from typing import assert_type
import pandas as pd
from rdetoolkit.nodes import read_csv_with_header, read_excel, read_text
p = Path("x")
"""


def _check(tmp_path: Path, body: str) -> subprocess.CompletedProcess[str]:
    stubs = tmp_path / "stubs" / "pandas"
    stubs.mkdir(parents=True)
    (stubs / "__init__.pyi").write_text(_PANDAS_STUB, encoding="utf-8")
    consumer = tmp_path / "consumer.py"
    consumer.write_text(_HEADER + body, encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "--no-incremental", str(consumer)],
        cwd=tmp_path, capture_output=True, text=True, check=False,
        env={**os.environ, "MYPYPATH": str(tmp_path / "stubs")},
    )


def test_call_shapes_are_inferred__i599r_type_001(tmp_path: Path) -> None:
    """I599R-TYPE-001: single sheets infer DataFrame, None and lists infer dicts."""
    # Given: a strict consumer covering every documented call shape
    body = '''assert_type(read_text(p), str)
assert_type(read_text(p, encoding="utf-8"), str)
assert_type(read_text(p, encoding=None), str)
assert_type(read_csv_with_header(p), pd.DataFrame)
assert_type(read_csv_with_header(p, encoding="cp932", skiprows=2, header=None, dtype=str, keep_default_na=False, sep=";"), pd.DataFrame)
assert_type(read_csv_with_header(p, header="infer", names=["a"]), pd.DataFrame)
assert_type(read_csv_with_header(p, skiprows=[0, 2], header=[0, 1]), pd.DataFrame)
assert_type(read_csv_with_header(p, skiprows=lambda row: row % 2 == 0), pd.DataFrame)
assert_type(read_excel(p), pd.DataFrame)
assert_type(read_excel(p, sheet_name="s"), pd.DataFrame)
assert_type(read_excel(p, sheet_name=1, header=None, nrows=3, dtype=str), pd.DataFrame)
assert_type(read_excel(p, sheet_name=None), dict[str, pd.DataFrame])
assert_type(read_excel(p, sheet_name=["a", "b"]), dict[str, pd.DataFrame])
assert_type(read_excel(p, sheet_name=[0, 1]), dict[int, pd.DataFrame])
assert_type(read_excel(p, sheet_name=["a", 0]), dict[str | int, pd.DataFrame])
mixed: list[str | int] = ["a", 0]
assert_type(read_excel(p, sheet_name=mixed), dict[str | int, pd.DataFrame])
def pick(name: str | int) -> pd.DataFrame:
    return read_excel(p, sheet_name=name)
'''
    # When: checking it against the installed stubs
    result = _check(tmp_path, body)
    # Then: every inference is exact
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("line, code", [
    ("frame: pd.DataFrame = read_excel(p, sheet_name=None)", "[assignment]"),
    ("frame2: pd.DataFrame = read_excel(p, sheet_name=['a'])", "[assignment]"),
    ("sheets: dict[str, pd.DataFrame] = read_excel(p)", "[assignment]"),
    ("assert_type(read_excel(p, sheet_name=None), pd.DataFrame)", "[assert-type]"),
    ("read_text(p, 'utf-8')", "[call-arg]"),
    ("read_text(p, encoding=1)", "[arg-type]"),
    ("read_csv_with_header(p, 'cp932')", "[call-arg]"),
    ("read_csv_with_header(p, header='first')", "[arg-type]"),
    ("read_csv_with_header(p, skiprows='2')", "[arg-type]"),
    ("read_csv_with_header(p, encoding=b'utf-8')", "[arg-type]"),
    ("read_excel(p, sheet_name=('a',))", "[call-overload]"),
    ("read_excel(p, sheet_name=1.5)", "[call-overload]"),
])
def test_invalid_uses_are_rejected__i599r_type_neg_001(tmp_path: Path, line: str, code: str) -> None:
    """I599R-TYPE-NEG-001: wrong results and option types are reported, not hidden."""
    # Given: one invalid use in a strict consumer
    # When: checking it
    result = _check(tmp_path, line + "\n")
    # Then: mypy reports the specific error code
    assert result.returncode == 1, result.stdout + result.stderr
    assert code in result.stdout, result.stdout


def _signatures(path: Path, names: set[str]) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = []
    overloaded = set()
    for item in tree.body:
        if isinstance(item, ast.FunctionDef) and item.name in names:
            overload = any(ast.unparse(d) == "overload" for d in item.decorator_list)
            if overload:
                overloaded.add(item.name)
            elif item.name in overloaded:
                continue  # the runtime implementation behind the overloads has no stub counterpart
            args = ast.unparse(item.args)
            found.append(f"{'@overload ' if overload else ''}{item.name}({args}) -> {ast.unparse(item.returns) if item.returns else ''}")
    return found


def test_stub_matches_runtime__i599r_type_002() -> None:
    """I599R-TYPE-002: io.pyi mirrors the runtime signatures, overloads included."""
    # Given: the runtime module and its stub
    runtime = Path(io_module.__file__)
    stub = runtime.with_suffix(".pyi")
    names = {"read_text", "read_csv_with_header", "read_excel"}
    # When: comparing their declarations
    # Then: both declare the same signatures in the same order
    assert _signatures(stub, names) == _signatures(runtime, names)
    assert sum(sig.startswith("@overload read_excel") for sig in _signatures(runtime, names)) >= 2


def test_stub_is_strict_clean__i599r_type_003(tmp_path: Path) -> None:
    """I599R-TYPE-003: the stub itself has no strict-mode error."""
    # Given: a standalone copy of the repository's io.pyi; checked in place,
    # mypy would also report the rdetoolkit parent package stubs
    stub = Path(__file__).resolve().parents[3] / "src" / "rdetoolkit" / "nodes" / "io.pyi"
    copy = tmp_path / "io_stub.pyi"
    copy.write_text(stub.read_text(encoding="utf-8"), encoding="utf-8")
    # When: checking it under --strict
    result = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "--no-incremental", "--ignore-missing-imports", str(copy)],
        cwd=tmp_path, capture_output=True, text=True, check=False,
    )
    # Then: mypy accepts it
    assert result.returncode == 0, result.stdout + result.stderr
