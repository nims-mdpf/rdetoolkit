"""Issue 598 EP/BV: installed build_meta stubs accept and constrain the new options.

| Partition | Expected | Test ID |
|---|---|---|
| Mapping or Path plus valid options | strict consumer passes | I598-TYPE-001 |
| invalid match, flag type or definition type | precise arg-type diagnostic | I598-TYPE-NEG-001 |
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


def _check(tmp_path: Path, source: str) -> subprocess.CompletedProcess[str]:
    consumer = tmp_path / "consumer.py"
    consumer.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "--ignore-missing-imports", "--no-incremental", str(consumer)],
        cwd=tmp_path, capture_output=True, text=True, check=False,
    )


def test_installed_options_are_typed__i598_type_001(tmp_path: Path) -> None:
    """I598-TYPE-001: public re-exports expose Mapping definitions and all options."""
    # Given: a strict consumer outside the repository's mypy configuration
    source = '''from collections.abc import Mapping
from pathlib import Path
from typing import Any
from rdetoolkit.nodes import build_meta
from rdetoolkit.types import Metadata
definition: Mapping[str, Any] = {"s": {"schema": {"type": "string"}}}
first: Metadata = build_meta({"s": ""}, definition, match="key", keep_empty_strings=True)
second: Metadata = build_meta({}, Path("metadata-def.json"), match="original_name")
'''
    # When: checking the installed public stubs
    result = _check(tmp_path, source)
    # Then: no Any return leakage or missing-option error is accepted
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("call", [
    'build_meta({}, Path("defs.json"), match="invalid")',
    'build_meta({}, Path("defs.json"), keep_empty_strings="yes")',
    'build_meta({}, 1)',
])
def test_invalid_options_are_rejected_by_typing__i598_type_neg_001(tmp_path: Path, call: str) -> None:
    """I598-TYPE-NEG-001: new options keep useful static constraints."""
    # Given: one invalid public argument in a strict consumer
    source = f"from pathlib import Path\nfrom rdetoolkit.nodes import build_meta\n{call}\n"
    # When: checking the installed signature
    result = _check(tmp_path, source)
    # Then: the invalid argument type is identified
    assert result.returncode == 1, result.stdout + result.stderr
    assert "[arg-type]" in result.stdout
