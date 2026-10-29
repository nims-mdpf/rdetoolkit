"""Tests for rdetoolkit v2 builtin structured-save nodes (Session F1.3,
TC-F1-STRUCT-*).

Written before implementation (TDD Red phase). Target: make all tests pass
in codex-worker Green phase. Authority: local/develop/v2/tasks/session_f1.md
Conflict #2 (argument order), Conflict #3 (OutputKind guidance -- both nodes
target ``"struct"``), Conflict #4 (save_csv's 1-row-header contract, the
concrete RULING reproduced below).

Pinned API shapes (binding contract for this file):

    save_csv(df: pd.DataFrame, out: OutputContext, filename: str) -> Path
    save_json(content: Any, out: OutputContext, filename: str) -> Path

Conflict #4's 1-row-header contract (verbatim ruling): ``save_csv`` must
produce a CSV whose header occupies exactly one line -- i.e. it must reject
(raise, with a message naming the reason) a DataFrame whose ``df.columns``
is a ``pandas.MultiIndex`` (``df.columns.nlevels > 1``), which
``df.to_csv()`` would otherwise silently serialize as multiple header rows.
A flat single-level ``Index`` always satisfies the contract via plain
``df.to_csv(dest, index=False)``.

Delegation guard (Design v2.1 R3): both nodes must call
``OutputContext.write_bytes``/``path_for`` internally -- ``OutputContext``
itself gains no new ``save_*`` methods. Checked here via
``inspect.getsource`` (also checked by the orchestrator's grep verification
guard #8 at the file level; this test pins it as an executable assertion).
"""
from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from rdetoolkit.types import OutputContext


def _delegates_to_output_context_write_api(func: Any) -> bool:
    source = inspect.getsource(func)
    return "write_bytes" in source or "path_for" in source


class TestSaveCsv:
    """TC-F1-STRUCT-CSV-*."""

    def test_flat_columns_writes_file_under_struct_with_single_header_line(self, output_context: OutputContext) -> None:
        """EP: a flat-columns DataFrame writes a file under out.struct with exactly one header line."""
        from rdetoolkit.nodes.structured import save_csv

        df = pd.DataFrame({"col_a": [1, 2], "col_b": [3, 4]})

        result_path = save_csv(df, output_context, "result.csv")

        assert result_path.exists()
        assert result_path.parent == output_context.struct
        lines = result_path.read_text(encoding="utf-8").splitlines()
        # Header occupies exactly one line: 1 header line + 2 data lines.
        assert lines[0] == "col_a,col_b"
        assert len(lines) == 3

    def test_flat_columns_content_round_trips_via_read_csv(self, output_context: OutputContext) -> None:
        """EP: the written CSV content round-trips through pandas.read_csv."""
        from rdetoolkit.nodes.structured import save_csv

        df = pd.DataFrame({"col_a": [1, 2], "col_b": [3, 4]})

        result_path = save_csv(df, output_context, "roundtrip.csv")
        read_back = pd.read_csv(result_path)

        assert list(read_back.columns) == ["col_a", "col_b"]
        assert read_back.equals(df.reset_index(drop=True))

    def test_multiindex_columns_raises_naming_the_header_problem(self, output_context: OutputContext) -> None:
        """BV (Conflict #4): a MultiIndex-columns DataFrame raises with a
        message identifying the multi-row-header problem, and writes no file."""
        from rdetoolkit.nodes.structured import save_csv

        df = pd.DataFrame(
            {("group1", "col_a"): [1, 2], ("group1", "col_b"): [3, 4]},
        )
        assert df.columns.nlevels > 1  # sanity check on the fixture itself

        with pytest.raises(ValueError, match=r"(?i)header"):
            save_csv(df, output_context, "should_not_exist.csv")

        assert not (output_context.struct / "should_not_exist.csv").exists()

    def test_filename_with_path_separator_raises(self, output_context: OutputContext) -> None:
        """BV: a filename containing directory components is rejected (Known Trap 11 -- OutputContext._require_simple_filename)."""
        from rdetoolkit.nodes.structured import save_csv

        df = pd.DataFrame({"col_a": [1]})

        with pytest.raises(ValueError):
            save_csv(df, output_context, "sub/dir/result.csv")

    def test_delegates_to_output_context_write_api(self) -> None:
        """Delegation guard: save_csv's source calls write_bytes or path_for, never a raw open()/Path.write_text bypassing OutputContext."""
        from rdetoolkit.nodes.structured import save_csv

        assert _delegates_to_output_context_write_api(save_csv)

    def test_registered_as_builtin_node(self) -> None:
        """Registration: save_csv appears in the registry after import."""
        import rdetoolkit.nodes  # noqa: F401
        from rdetoolkit.core import registry

        ids = {spec.id for spec in registry.list_nodes()}
        assert any(node_id.endswith("save_csv") for node_id in ids), ids


class TestSaveJson:
    """TC-F1-STRUCT-JSON-*."""

    def test_dict_content_round_trips(self, output_context: OutputContext) -> None:
        """EP: a dict is written as valid, round-trippable JSON under out.struct (or documented OutputKind)."""
        import json

        from rdetoolkit.nodes.structured import save_json

        content = {"key1": "value1", "key2": 2, "nested": {"a": [1, 2, 3]}}

        result_path = save_json(content, output_context, "result.json")

        assert result_path.exists()
        assert json.loads(result_path.read_text(encoding="utf-8")) == content

    def test_list_content_round_trips(self, output_context: OutputContext) -> None:
        """EP: a list is written as valid, round-trippable JSON."""
        import json

        from rdetoolkit.nodes.structured import save_json

        content = [1, "two", {"three": 3}]

        result_path = save_json(content, output_context, "list_result.json")

        assert json.loads(result_path.read_text(encoding="utf-8")) == content

    def test_non_json_serializable_content_raises(self, output_context: OutputContext) -> None:
        """BV: content that is not JSON-serializable raises, and writes no file."""
        from rdetoolkit.nodes.structured import save_json

        content = {"bad": {1, 2, 3}}  # a set() is not JSON-serializable

        with pytest.raises((TypeError, ValueError)):
            save_json(content, output_context, "should_not_exist.json")

        assert not (output_context.struct / "should_not_exist.json").exists()

    def test_delegates_to_output_context_write_api(self) -> None:
        """Delegation guard: save_json's source calls write_bytes or path_for."""
        from rdetoolkit.nodes.structured import save_json

        assert _delegates_to_output_context_write_api(save_json)

    def test_registered_as_builtin_node(self) -> None:
        """Registration: save_json appears in the registry after import."""
        import rdetoolkit.nodes  # noqa: F401
        from rdetoolkit.core import registry

        ids = {spec.id for spec in registry.list_nodes()}
        assert any(node_id.endswith("save_json") for node_id in ids), ids
