"""Tests for v2 type definitions (Phase 1.1).

EP Table:
| API               | Partition           | Rationale               | Expected                | Test ID     |
|-------------------|---------------------|-------------------------|-------------------------|-------------|
| InputPaths()      | valid 3 paths       | normal construction     | fields accessible       | TC-EP-001   |
| InputPaths()      | missing required    | negative                | TypeError               | TC-EP-002   |
| InputPaths.field=  | assign after init   | immutability check      | FrozenInstanceError     | TC-EP-003   |
| OutputContext()   | valid paths         | normal construction     | fields accessible       | TC-EP-004   |
| OutputContext()   | missing required    | negative                | TypeError               | TC-EP-005   |
| OutputContext     | immutability        | frozen check            | FrozenInstanceError     | TC-EP-006   |
| OutputContext     | save_csv            | method API              | file written            | TC-EP-040   |
| OutputContext     | save_meta           | method API              | JSON written            | TC-EP-041   |
| OutputContext     | save_file           | method API              | bytes written           | TC-EP-042   |
| OutputContext     | save_thumbnail      | method API              | file copied             | TC-EP-043   |
| OutputContext     | save_main_image     | method API              | file copied             | TC-EP-044   |
| OutputContext     | save_raw            | method API              | file copied             | TC-EP-045   |
| Metadata()        | custom/basic        | design spec fields      | fields accessible       | TC-EP-007   |
| Metadata()        | empty               | boundary                | empty custom            | TC-EP-008   |
| Metadata.set/get  | method API          | design spec             | set/get work            | TC-EP-046   |
| InvoiceData()     | valid construction  | normal                  | fields accessible       | TC-EP-009   |
| InvoiceData       | get_field           | method API              | returns field           | TC-EP-047   |
| InvoiceData       | get_custom_fields   | method API              | filters _-prefixed      | TC-EP-048   |
| IterationInfo()   | valid construction  | normal                  | fields accessible       | TC-EP-010   |
| IterationInfo()   | zero index          | boundary                | index=0                 | TC-EP-011   |

BV Table:
| API               | Boundary            | Rationale               | Expected                | Test ID     |
|-------------------|---------------------|-------------------------|-------------------------|-------------|
| InputPaths()      | empty path strings  | minimal valid           | constructed ok          | TC-BV-001   |
| OutputContext     | all None optionals  | minimal valid           | constructed ok          | TC-BV-002   |
| IterationInfo     | index=0, total=1    | minimal iteration       | constructed ok          | TC-BV-003   |
"""

from __future__ import annotations

from pathlib import Path

import pytest


class TestInputPaths:
    """Tests for InputPaths frozen dataclass."""

    def test_construction_with_valid_paths__tc_ep_001(self) -> None:
        """TC-EP-001: InputPaths constructed with valid Path objects."""
        from rdetoolkit.types import InputPaths

        paths = InputPaths(
            inputdata=Path("/data/inputdata"),
            invoice=Path("/data/invoice"),
            tasksupport=Path("/data/tasksupport"),
        )

        assert paths.inputdata == Path("/data/inputdata")
        assert paths.invoice == Path("/data/invoice")
        assert paths.tasksupport == Path("/data/tasksupport")

    def test_construction_missing_required_raises__tc_ep_002(self) -> None:
        """TC-EP-002: InputPaths without required fields raises TypeError."""
        from rdetoolkit.types import InputPaths

        with pytest.raises(TypeError):
            InputPaths(inputdata=Path("/data"))  # type: ignore[call-arg]

    def test_immutability__tc_ep_003(self) -> None:
        """TC-EP-003: InputPaths fields cannot be reassigned (frozen)."""
        from rdetoolkit.types import InputPaths

        paths = InputPaths(
            inputdata=Path("/data/inputdata"),
            invoice=Path("/data/invoice"),
            tasksupport=Path("/data/tasksupport"),
        )

        with pytest.raises((AttributeError, TypeError)):
            paths.inputdata = Path("/other")  # type: ignore[misc]

    def test_empty_path_strings__tc_bv_001(self) -> None:
        """TC-BV-001: InputPaths with empty path strings."""
        from rdetoolkit.types import InputPaths

        paths = InputPaths(
            inputdata=Path(""),
            invoice=Path(""),
            tasksupport=Path(""),
        )

        assert paths.inputdata == Path("")


class TestOutputContext:
    """Tests for OutputContext frozen dataclass and method API."""

    def _make_ctx(self, tmp_path: Path) -> "OutputContext":
        from rdetoolkit.types import OutputContext

        return OutputContext(
            raw=tmp_path / "raw",
            struct=tmp_path / "struct",
            main_image=tmp_path / "main_image",
            other_image=tmp_path / "other_image",
            meta=tmp_path / "meta",
            thumbnail=tmp_path / "thumbnail",
            logs=tmp_path / "logs",
        )

    def test_construction_with_valid_paths__tc_ep_004(self) -> None:
        """TC-EP-004: OutputContext constructed with valid fields."""
        from rdetoolkit.types import OutputContext

        ctx = OutputContext(
            raw=Path("/out/raw"),
            struct=Path("/out/struct"),
            main_image=Path("/out/main_image"),
            other_image=Path("/out/other_image"),
            meta=Path("/out/meta"),
            thumbnail=Path("/out/thumbnail"),
            logs=Path("/out/logs"),
        )

        assert ctx.raw == Path("/out/raw")
        assert ctx.struct == Path("/out/struct")
        assert ctx.main_image == Path("/out/main_image")
        assert ctx.other_image == Path("/out/other_image")
        assert ctx.meta == Path("/out/meta")
        assert ctx.thumbnail == Path("/out/thumbnail")
        assert ctx.logs == Path("/out/logs")

    def test_construction_missing_required_raises__tc_ep_005(self) -> None:
        """TC-EP-005: OutputContext without required fields raises TypeError."""
        from rdetoolkit.types import OutputContext

        with pytest.raises(TypeError):
            OutputContext(raw=Path("/out/raw"))  # type: ignore[call-arg]

    def test_immutability__tc_ep_006(self) -> None:
        """TC-EP-006: OutputContext fields cannot be reassigned (frozen)."""
        from rdetoolkit.types import OutputContext

        ctx = OutputContext(
            raw=Path("/out/raw"),
            struct=Path("/out/struct"),
            main_image=Path("/out/main_image"),
            other_image=Path("/out/other_image"),
            meta=Path("/out/meta"),
            thumbnail=Path("/out/thumbnail"),
            logs=Path("/out/logs"),
        )

        with pytest.raises((AttributeError, TypeError)):
            ctx.raw = Path("/other")  # type: ignore[misc]

    def test_all_none_optionals__tc_bv_002(self) -> None:
        """TC-BV-002: OutputContext with required fields only."""
        from rdetoolkit.types import OutputContext

        ctx = OutputContext(
            raw=Path("/out/raw"),
            struct=Path("/out/struct"),
            main_image=Path("/out/main_image"),
            other_image=Path("/out/other_image"),
            meta=Path("/out/meta"),
            thumbnail=Path("/out/thumbnail"),
            logs=Path("/out/logs"),
        )

        assert ctx.raw == Path("/out/raw")

    def test_save_file__tc_ep_042(self, tmp_path: Path) -> None:
        """TC-EP-042: save_file writes bytes to struct dir."""
        ctx = self._make_ctx(tmp_path)
        result = ctx.save_file(b"hello", "test.bin")
        assert result.exists()
        assert result.read_bytes() == b"hello"
        assert result.parent == tmp_path / "struct"

    def test_save_thumbnail__tc_ep_043(self, tmp_path: Path) -> None:
        """TC-EP-043: save_thumbnail copies file to thumbnail dir."""
        ctx = self._make_ctx(tmp_path)
        src = tmp_path / "source.png"
        src.write_bytes(b"PNG")
        result = ctx.save_thumbnail(src)
        assert result.exists()
        assert result.read_bytes() == b"PNG"
        assert result.parent == tmp_path / "thumbnail"

    def test_save_main_image__tc_ep_044(self, tmp_path: Path) -> None:
        """TC-EP-044: save_main_image copies file to main_image dir."""
        ctx = self._make_ctx(tmp_path)
        src = tmp_path / "image.png"
        src.write_bytes(b"IMG")
        result = ctx.save_main_image(src)
        assert result.exists()
        assert result.parent == tmp_path / "main_image"

    def test_save_raw__tc_ep_045(self, tmp_path: Path) -> None:
        """TC-EP-045: save_raw copies file to raw dir."""
        ctx = self._make_ctx(tmp_path)
        src = tmp_path / "data.raw"
        src.write_bytes(b"RAW")
        result = ctx.save_raw(src)
        assert result.exists()
        assert result.parent == tmp_path / "raw"

    def test_save_meta__tc_ep_041(self, tmp_path: Path) -> None:
        """TC-EP-041: save_meta writes metadata JSON."""
        from rdetoolkit.types import Metadata

        ctx = self._make_ctx(tmp_path)
        meta = Metadata(custom={"key": "value"})
        ctx.save_meta(meta)
        dest = tmp_path / "meta" / "metadata.json"
        assert dest.exists()
        import json

        data = json.loads(dest.read_text())
        assert data["key"] == "value"

    def test_has_method_api(self) -> None:
        """OutputContext exposes method-based API (not just path bundle)."""
        from rdetoolkit.types import OutputContext

        methods = ["save_csv", "save_meta", "save_graph", "save_file",
                    "save_thumbnail", "save_main_image", "save_raw"]
        for m in methods:
            assert hasattr(OutputContext, m), f"Missing method: {m}"


class TestMetadata:
    """Tests for Metadata type."""

    def test_construction_with_custom_dict__tc_ep_007(self) -> None:
        """TC-EP-007: Metadata constructed with custom and basic fields."""
        from rdetoolkit.types import Metadata

        meta = Metadata(custom={"key1": "value1", "key2": 42})

        assert meta.custom["key1"] == "value1"
        assert meta.custom["key2"] == 42

    def test_construction_with_empty_dict__tc_ep_008(self) -> None:
        """TC-EP-008: Metadata constructed with default empty custom."""
        from rdetoolkit.types import Metadata

        meta = Metadata()
        assert meta.custom == {}
        assert meta.basic is None

    def test_set_and_get__tc_ep_046(self) -> None:
        """TC-EP-046: Metadata set/get methods work correctly."""
        from rdetoolkit.types import Metadata

        meta = Metadata()
        meta.set("temperature", 300.0)
        assert meta.get("temperature") == 300.0
        assert meta.get("missing", "default") == "default"
        assert meta.custom["temperature"] == 300.0

    def test_metadata_is_mutable(self) -> None:
        """Metadata is not frozen — set() can modify custom dict."""
        from rdetoolkit.types import Metadata

        meta = Metadata()
        meta.set("a", 1)
        meta.set("b", 2)
        assert len(meta.custom) == 2


class TestInvoiceData:
    """Tests for InvoiceData type."""

    def test_construction_with_valid_fields__tc_ep_009(self) -> None:
        """TC-EP-009: InvoiceData constructed with valid fields."""
        from rdetoolkit.types import InvoiceData

        invoice = InvoiceData(
            raw={"sample_name": "test", "_system": "internal"},
            mode="invoice",
            schema={"type": "object"},
        )

        assert invoice.raw["sample_name"] == "test"
        assert invoice.mode == "invoice"
        assert invoice.schema == {"type": "object"}

    def test_get_field__tc_ep_047(self) -> None:
        """TC-EP-047: get_field returns top-level field from raw data."""
        from rdetoolkit.types import InvoiceData

        invoice = InvoiceData(raw={"name": "test", "value": 42})
        assert invoice.get_field("name") == "test"
        assert invoice.get_field("missing", "default") == "default"

    def test_get_custom_fields__tc_ep_048(self) -> None:
        """TC-EP-048: get_custom_fields filters out _-prefixed keys."""
        from rdetoolkit.types import InvoiceData

        invoice = InvoiceData(
            raw={"sample_name": "test", "_system": "internal", "value": 42},
        )
        custom = invoice.get_custom_fields()
        assert "sample_name" in custom
        assert "value" in custom
        assert "_system" not in custom


class TestIterationInfo:
    """Tests for IterationInfo type."""

    def test_construction_with_valid_fields__tc_ep_010(self) -> None:
        """TC-EP-010: IterationInfo constructed with valid fields."""
        from rdetoolkit.types import IterationInfo

        info = IterationInfo(index=3, total=10, mode="invoice")

        assert info.index == 3
        assert info.total == 10
        assert info.mode == "invoice"

    def test_zero_index_boundary__tc_ep_011(self) -> None:
        """TC-EP-011: IterationInfo with zero index (boundary)."""
        from rdetoolkit.types import IterationInfo

        info = IterationInfo(index=0, total=1, mode="invoice")
        assert info.index == 0

    def test_minimal_iteration__tc_bv_003(self) -> None:
        """TC-BV-003: IterationInfo with minimal values."""
        from rdetoolkit.types import IterationInfo

        info = IterationInfo(index=0, total=1, mode="invoice")
        assert info.total == 1
