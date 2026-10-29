"""Tests for rdetoolkit v2 builtin metadata nodes (Session F1.4,
TC-F1-META-*).

Written before implementation (TDD Red phase). Target: make all tests pass
in codex-worker Green phase. Authority: local/develop/v2/tasks/session_f1.md
Conflict #2 (argument order: ``save_meta(metadata: Metadata, out:
OutputContext) -> Path`` is the pinned literal example), Conflict #9
(invalid-input exception choice: v1's ``StructuredError`` OR a plain
``ValueError`` -- Codex's choice, this file accepts either).

Pinned API shapes (binding contract for this file):

    parse_invoice_meta(invoice: InvoiceData, metadef_path: Path) -> Metadata
    save_meta(metadata: Metadata, out: OutputContext) -> Path

Porting source: ``rdetoolkit.rde2util.Meta`` (``__init__``/``assign_vals``).
This test file's ``metadata-def.json`` fixture and its EP/BV invoice payloads
were independently verified directly against ``rde2util.Meta`` before being
pinned here as node-level oracles (see the tdd-enforcer session transcript):

    - EP: ``Meta(metadef_path).assign_vals({"sample.key1": "value1",
      "sample.key2": 42})`` succeeds and assigns both keys.
    - BV: adding ``"sample.derived"`` (an action-derived key in the fixture
      metadata-def) directly to the input dict makes
      ``Meta.assign_vals`` raise ``StructuredError("ERROR: this meta value
      should set by action")`` -- a real v1 contract violation, not an
      invented one.

``parse_invoice_meta`` is expected to raise on the same underlying condition
when it encounters ``sample.derived`` directly in ``invoice.raw`` (Conflict
#9: propagating v1's ``StructuredError`` or raising a documented
``ValueError`` are both acceptable; this file's BV test accepts either).
"""
from __future__ import annotations

import inspect
import json

import pytest

from rdetoolkit.exceptions import StructuredError
from rdetoolkit.testing.builders import make_invoice
from rdetoolkit.types import Metadata, OutputContext
from tests.v2.nodes.conftest import FIXTURES_DIR


class TestParseInvoiceMeta:
    """TC-F1-META-PARSE-*."""

    def test_valid_invoice_produces_metadata_with_assigned_custom_fields(self) -> None:
        """EP: a valid invoice + metadata-def.json fixture pair produces a
        Metadata instance whose custom fields include the assigned values
        (mirrors Meta.assign_vals)."""
        from rdetoolkit.nodes.meta import parse_invoice_meta

        invoice = make_invoice({"sample.key1": "value1", "sample.key2": 42})

        result = parse_invoice_meta(invoice, FIXTURES_DIR / "metadata-def.json")

        assert isinstance(result, Metadata)
        assert result.custom.get("sample.key1") == "value1"
        assert str(result.custom.get("sample.key2")) == "42"

    def test_invoice_value_violating_metadef_action_contract_raises(self) -> None:
        """BV (Conflict #9): an invoice directly assigning a value to an
        action-derived metadata-def key violates the v1 contract and raises
        (StructuredError, propagated from rde2util.Meta, or a documented
        plain ValueError -- Codex's choice)."""
        from rdetoolkit.nodes.meta import parse_invoice_meta

        invoice = make_invoice({"sample.key1": "value1", "sample.derived": "not-allowed"})

        with pytest.raises((StructuredError, ValueError)):
            parse_invoice_meta(invoice, FIXTURES_DIR / "metadata-def.json")

    def test_nonexistent_metadef_path_raises(self) -> None:
        """BV: a nonexistent metadata-def.json path raises."""
        from rdetoolkit.nodes.meta import parse_invoice_meta

        invoice = make_invoice({"sample.key1": "value1"})

        with pytest.raises(OSError):
            parse_invoice_meta(invoice, FIXTURES_DIR / "definitely_missing_metadata_def.json")

    def test_registered_as_builtin_node(self) -> None:
        """Registration: parse_invoice_meta appears in the registry after import."""
        import rdetoolkit.nodes  # noqa: F401
        from rdetoolkit.core import registry

        ids = {spec.id for spec in registry.list_nodes()}
        assert any(node_id.endswith("parse_invoice_meta") for node_id in ids), ids


class TestSaveMeta:
    """TC-F1-META-SAVE-*."""

    def test_writes_json_file_under_out_meta(self, output_context: OutputContext) -> None:
        """EP: a Metadata instance is written as a JSON file under out.meta."""
        from rdetoolkit.nodes.meta import save_meta

        metadata = Metadata(custom={"sample.key1": "value1"})

        result_path = save_meta(metadata, output_context)

        assert result_path.exists()
        assert result_path.parent == output_context.meta
        assert result_path.suffix == ".json"
        decoded = json.loads(result_path.read_text(encoding="utf-8"))
        # K4-F6 F6-1: the RDE metadata.json contract (constant/variable,
        # MetaValue = {value, unit?}) replaces the former custom/basic shape.
        assert decoded == {"constant": {"sample.key1": {"value": "value1"}}, "variable": []}

    def test_written_file_passes_metadata_validate__tc_k4f6_meta_001(self, output_context: OutputContext) -> None:
        """TC-K4F6-META-001: the written file satisfies the Runner's metadata.json validator."""
        from rdetoolkit.domain.validation import metadata_validate
        from rdetoolkit.nodes.meta import save_meta

        # Given: metadata with one numeric custom field
        metadata = Metadata(custom={"temperature": 300})

        # When: saving it
        result_path = save_meta(metadata, output_context)

        # Then: the file validates and carries the value under constant
        metadata_validate(result_path)
        decoded = json.loads(result_path.read_text(encoding="utf-8"))
        assert decoded["constant"]["temperature"]["value"] == 300
        assert decoded["variable"] == []

    def test_basic_is_not_written__tc_k4f6_meta_002(self, output_context: OutputContext) -> None:
        """TC-K4F6-META-002: invoice basic info has no metadata.json slot and is not written."""
        from rdetoolkit.nodes.meta import save_meta

        # Given: metadata carrying basic info and no custom fields
        metadata = Metadata(custom={}, basic={"dataName": "x"})

        # When: saving it
        result_path = save_meta(metadata, output_context)

        # Then: only the empty constant/variable contract is written
        decoded = json.loads(result_path.read_text(encoding="utf-8"))
        assert decoded == {"constant": {}, "variable": []}

    def test_delegates_to_output_context_write_api(self) -> None:
        """Delegation guard: save_meta's source calls write_bytes or path_for."""
        from rdetoolkit.nodes.meta import save_meta

        source = inspect.getsource(save_meta)
        assert "write_bytes" in source or "path_for" in source

    def test_registered_as_builtin_node(self) -> None:
        """Registration: save_meta appears in the registry after import."""
        import rdetoolkit.nodes  # noqa: F401
        from rdetoolkit.core import registry

        ids = {spec.id for spec in registry.list_nodes()}
        assert any(node_id.endswith("save_meta") for node_id in ids), ids


class TestParseInvoiceMetaThenSaveMetaRoundTrip:
    """Integration: TC-F1-META-ROUNDTRIP-001."""

    def test_parse_then_save_round_trip_is_readable_back(self, output_context: OutputContext) -> None:
        """parse_invoice_meta -> save_meta round-trip produces a file whose
        decoded JSON still contains the originally-assigned values."""
        from rdetoolkit.nodes.meta import parse_invoice_meta, save_meta

        invoice = make_invoice({"sample.key1": "value1", "sample.key2": 42})
        metadata = parse_invoice_meta(invoice, FIXTURES_DIR / "metadata-def.json")

        result_path = save_meta(metadata, output_context)
        decoded = json.loads(result_path.read_text(encoding="utf-8"))

        assert decoded["constant"]["sample.key1"] == {"value": "value1"}
        assert decoded["constant"]["sample.key2"] == {"value": 42}
        assert decoded["variable"] == []
