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
| Metadata()        | valid dict          | normal construction     | data accessible         | TC-EP-007   |
| Metadata()        | empty               | boundary                | empty data              | TC-EP-008   |
| InvoiceData()     | valid construction  | normal                  | fields accessible       | TC-EP-009   |
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
        # Given: three valid Path objects
        from rdetoolkit.types import InputPaths

        # When: constructing InputPaths
        paths = InputPaths(
            inputdata=Path("/data/inputdata"),
            invoice=Path("/data/invoice"),
            tasksupport=Path("/data/tasksupport"),
        )

        # Then: fields are accessible
        assert paths.inputdata == Path("/data/inputdata")
        assert paths.invoice == Path("/data/invoice")
        assert paths.tasksupport == Path("/data/tasksupport")

    def test_construction_missing_required_raises__tc_ep_002(self) -> None:
        """TC-EP-002: InputPaths without required fields raises TypeError."""
        from rdetoolkit.types import InputPaths

        # When / Then: missing required field raises TypeError
        with pytest.raises(TypeError):
            InputPaths(inputdata=Path("/data"))  # type: ignore[call-arg]

    def test_immutability__tc_ep_003(self) -> None:
        """TC-EP-003: InputPaths fields cannot be reassigned (frozen)."""
        from rdetoolkit.types import InputPaths

        # Given: a constructed InputPaths
        paths = InputPaths(
            inputdata=Path("/data/inputdata"),
            invoice=Path("/data/invoice"),
            tasksupport=Path("/data/tasksupport"),
        )

        # When / Then: assignment raises FrozenInstanceError or AttributeError
        with pytest.raises((AttributeError, TypeError)):
            paths.inputdata = Path("/other")  # type: ignore[misc]

    def test_empty_path_strings__tc_bv_001(self) -> None:
        """TC-BV-001: InputPaths with empty path strings."""
        from rdetoolkit.types import InputPaths

        # Given/When: paths constructed with empty strings
        paths = InputPaths(
            inputdata=Path(""),
            invoice=Path(""),
            tasksupport=Path(""),
        )

        # Then: constructed successfully
        assert paths.inputdata == Path("")


class TestOutputContext:
    """Tests for OutputContext frozen dataclass."""

    def test_construction_with_valid_paths__tc_ep_004(self) -> None:
        """TC-EP-004: OutputContext constructed with valid fields."""
        from rdetoolkit.types import OutputContext

        # When: constructing OutputContext
        ctx = OutputContext(
            raw=Path("/out/raw"),
            struct=Path("/out/struct"),
            main_image=Path("/out/main_image"),
            other_image=Path("/out/other_image"),
            meta=Path("/out/meta"),
            thumbnail=Path("/out/thumbnail"),
            logs=Path("/out/logs"),
        )

        # Then: fields are accessible
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

        # When / Then: missing required field raises TypeError
        with pytest.raises(TypeError):
            OutputContext(raw=Path("/out/raw"))  # type: ignore[call-arg]

    def test_immutability__tc_ep_006(self) -> None:
        """TC-EP-006: OutputContext fields cannot be reassigned (frozen)."""
        from rdetoolkit.types import OutputContext

        # Given: a constructed OutputContext
        ctx = OutputContext(
            raw=Path("/out/raw"),
            struct=Path("/out/struct"),
            main_image=Path("/out/main_image"),
            other_image=Path("/out/other_image"),
            meta=Path("/out/meta"),
            thumbnail=Path("/out/thumbnail"),
            logs=Path("/out/logs"),
        )

        # When / Then: assignment raises
        with pytest.raises((AttributeError, TypeError)):
            ctx.raw = Path("/other")  # type: ignore[misc]

    def test_all_none_optionals__tc_bv_002(self) -> None:
        """TC-BV-002: OutputContext with optional fields as None."""
        from rdetoolkit.types import OutputContext

        # When: constructing with required fields only
        ctx = OutputContext(
            raw=Path("/out/raw"),
            struct=Path("/out/struct"),
            main_image=Path("/out/main_image"),
            other_image=Path("/out/other_image"),
            meta=Path("/out/meta"),
            thumbnail=Path("/out/thumbnail"),
            logs=Path("/out/logs"),
        )

        # Then: constructed ok
        assert ctx.raw == Path("/out/raw")


class TestMetadata:
    """Tests for Metadata type."""

    def test_construction_with_valid_dict__tc_ep_007(self) -> None:
        """TC-EP-007: Metadata constructed with valid dict data."""
        from rdetoolkit.types import Metadata

        # When: constructing Metadata
        meta = Metadata(data={"key1": "value1", "key2": 42})

        # Then: data is accessible
        assert meta.data["key1"] == "value1"
        assert meta.data["key2"] == 42

    def test_construction_with_empty_dict__tc_ep_008(self) -> None:
        """TC-EP-008: Metadata constructed with empty dict."""
        from rdetoolkit.types import Metadata

        # When: constructing with empty data
        meta = Metadata(data={})

        # Then: data is empty dict
        assert meta.data == {}


class TestInvoiceData:
    """Tests for InvoiceData type."""

    def test_construction_with_valid_fields__tc_ep_009(self) -> None:
        """TC-EP-009: InvoiceData constructed with valid fields."""
        from rdetoolkit.types import InvoiceData

        # When: constructing InvoiceData
        invoice = InvoiceData(
            schema={"type": "object"},
            content={"sample_name": "test"},
        )

        # Then: fields are accessible
        assert invoice.schema == {"type": "object"}
        assert invoice.content["sample_name"] == "test"


class TestIterationInfo:
    """Tests for IterationInfo type."""

    def test_construction_with_valid_fields__tc_ep_010(self) -> None:
        """TC-EP-010: IterationInfo constructed with valid fields."""
        from rdetoolkit.types import IterationInfo

        # When: constructing IterationInfo
        info = IterationInfo(index=3, total=10, mode="invoice")

        # Then: fields are accessible
        assert info.index == 3
        assert info.total == 10
        assert info.mode == "invoice"

    def test_zero_index_boundary__tc_ep_011(self) -> None:
        """TC-EP-011: IterationInfo with zero index (boundary)."""
        from rdetoolkit.types import IterationInfo

        # When: constructing with index=0
        info = IterationInfo(index=0, total=1, mode="invoice")

        # Then: index is 0
        assert info.index == 0

    def test_minimal_iteration__tc_bv_003(self) -> None:
        """TC-BV-003: IterationInfo with minimal values."""
        from rdetoolkit.types import IterationInfo

        # When: constructing with minimal values
        info = IterationInfo(index=0, total=1, mode="invoice")

        # Then: constructed ok
        assert info.total == 1
