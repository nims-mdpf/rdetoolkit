"""Tests for v2 @node decorator and NodeSpec (Phase 1.2).

EP Table:
| API                  | Partition             | Rationale              | Expected                  | Test ID     |
|----------------------|-----------------------|------------------------|---------------------------|-------------|
| NodeSpec()           | valid fields          | normal construction    | fields accessible         | TC-EP-021   |
| NodeSpec()           | missing required      | negative               | TypeError                 | TC-EP-022   |
| NodeSpec             | frozen                | immutability           | FrozenInstanceError       | TC-EP-023   |
| NodeSpec             | type info captured    | inspect.signature      | input/output schemas      | TC-EP-024   |
| @node                | direct call           | transparency           | same result as bare fn    | TC-EP-025   |
| @node                | __node_spec__ present | attribute attachment   | has NodeSpec              | TC-EP-026   |
| @node                | wraps metadata        | functools.wraps        | __name__, __doc__ kept    | TC-EP-027   |
| @node(tags=...)      | custom tags           | optional param         | tags stored in spec       | TC-EP-028   |
| @node(version=...)   | custom version        | optional param         | version stored            | TC-EP-029   |
| @node(idempotent=T)  | idempotent flag       | optional param         | flag stored               | TC-EP-030   |
| @node                | no args decorator     | bare @node usage       | works as @node            | TC-EP-031   |
| @node()              | empty parens          | @node() usage          | works as @node            | TC-EP-032   |

BV Table:
| API                  | Boundary              | Rationale              | Expected                  | Test ID     |
|----------------------|-----------------------|------------------------|---------------------------|-------------|
| NodeSpec             | empty tags list       | minimal                | tags is ()                | TC-BV-006   |
| @node                | no-arg function       | minimal function       | spec has empty inputs     | TC-BV-007   |
| @node                | many args function    | complex function       | all args captured         | TC-BV-008   |
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


class TestNodeSpec:
    """Tests for NodeSpec frozen dataclass."""

    def test_construction_with_valid_fields__tc_ep_021(self) -> None:
        """TC-EP-021: NodeSpec constructed with valid fields."""
        from rdetoolkit.core.node import NodeSpec

        # When: constructing NodeSpec
        spec = NodeSpec(
            id="read_csv",
            func_name="read_csv",
            input_schema={"paths": "InputPaths"},
            output_schema={"metadata": "Metadata", "data": "DataFrame"},
            tags=("io",),
            version="1.0.0",
            idempotent=False,
        )

        # Then: fields are accessible
        assert spec.id == "read_csv"
        assert spec.func_name == "read_csv"
        assert spec.input_schema == {"paths": "InputPaths"}
        assert spec.output_schema == {"metadata": "Metadata", "data": "DataFrame"}
        assert spec.tags == ("io",)
        assert spec.version == "1.0.0"
        assert spec.idempotent is False

    def test_construction_missing_required_raises__tc_ep_022(self) -> None:
        """TC-EP-022: NodeSpec without required fields raises TypeError."""
        from rdetoolkit.core.node import NodeSpec

        # When / Then: missing required fields
        with pytest.raises(TypeError):
            NodeSpec(id="test")  # type: ignore[call-arg]

    def test_frozen__tc_ep_023(self) -> None:
        """TC-EP-023: NodeSpec fields cannot be reassigned."""
        from rdetoolkit.core.node import NodeSpec

        # Given: a constructed NodeSpec
        spec = NodeSpec(
            id="test",
            func_name="test",
            input_schema={},
            output_schema={},
            tags=(),
            version="0.0.0",
            idempotent=False,
        )

        # When / Then: assignment raises
        with pytest.raises((AttributeError, TypeError)):
            spec.id = "other"  # type: ignore[misc]

    def test_empty_tags__tc_bv_006(self) -> None:
        """TC-BV-006: NodeSpec with empty tags tuple."""
        from rdetoolkit.core.node import NodeSpec

        # When: constructing with empty tags
        spec = NodeSpec(
            id="test",
            func_name="test",
            input_schema={},
            output_schema={},
            tags=(),
            version="0.0.0",
            idempotent=False,
        )

        # Then: tags is empty tuple
        assert spec.tags == ()


class TestNodeDecorator:
    """Tests for @node decorator."""

    def test_direct_call_transparency__tc_ep_025(self) -> None:
        """TC-EP-025: @node decorated function is directly callable with same result."""
        from rdetoolkit.core.node import node

        # Given: a decorated function
        @node
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        # When: calling directly
        result = add(2, 3)

        # Then: returns same result as bare function
        assert result == 5

    def test_node_spec_attached__tc_ep_026(self) -> None:
        """TC-EP-026: @node attaches __node_spec__ attribute."""
        from rdetoolkit.core.node import node, NodeSpec

        # Given: a decorated function
        @node
        def process(x: int) -> str:
            """Process x."""
            return str(x)

        # Then: __node_spec__ is a NodeSpec
        assert hasattr(process, "__node_spec__")
        assert isinstance(process.__node_spec__, NodeSpec)  # type: ignore[attr-defined]

    def test_wraps_metadata_preserved__tc_ep_027(self) -> None:
        """TC-EP-027: @node preserves __name__ and __doc__."""
        from rdetoolkit.core.node import node

        # Given: a decorated function with docstring
        @node
        def my_func(x: int) -> int:
            """My docstring."""
            return x

        # Then: metadata is preserved
        assert my_func.__name__ == "my_func"
        assert my_func.__doc__ == "My docstring."

    def test_type_info_captured__tc_ep_024(self) -> None:
        """TC-EP-024: @node captures input/output type info from signature."""
        from rdetoolkit.core.node import node

        # Given: a function with type annotations
        @node
        def transform(paths: Path, count: int) -> str:
            """Transform data."""
            return str(paths) * count

        # Then: input schema captures parameter types
        spec = transform.__node_spec__  # type: ignore[attr-defined]
        assert "paths" in spec.input_schema
        assert "count" in spec.input_schema

        # And: output schema captures return type
        assert spec.output_schema is not None

    def test_custom_tags__tc_ep_028(self) -> None:
        """TC-EP-028: @node with custom tags."""
        from rdetoolkit.core.node import node

        # Given: a decorated function with tags
        @node(tags=["io", "csv"])
        def read_csv(path: Path) -> str:
            return ""

        # Then: tags are stored
        spec = read_csv.__node_spec__  # type: ignore[attr-defined]
        assert "io" in spec.tags
        assert "csv" in spec.tags

    def test_custom_version__tc_ep_029(self) -> None:
        """TC-EP-029: @node with custom version."""
        from rdetoolkit.core.node import node

        # Given: a decorated function with version
        @node(version="2.1.0")
        def versioned_fn(x: int) -> int:
            return x

        # Then: version is stored
        spec = versioned_fn.__node_spec__  # type: ignore[attr-defined]
        assert spec.version == "2.1.0"

    def test_idempotent_flag__tc_ep_030(self) -> None:
        """TC-EP-030: @node with idempotent flag."""
        from rdetoolkit.core.node import node

        # Given: a decorated function with idempotent=True
        @node(idempotent=True)
        def safe_fn(x: int) -> int:
            return x

        # Then: idempotent flag is stored
        spec = safe_fn.__node_spec__  # type: ignore[attr-defined]
        assert spec.idempotent is True

    def test_bare_decorator__tc_ep_031(self) -> None:
        """TC-EP-031: @node without parentheses works."""
        from rdetoolkit.core.node import node

        # Given: bare @node usage
        @node
        def bare_fn(x: int) -> int:
            return x

        # Then: function works and has spec
        assert bare_fn(5) == 5
        assert hasattr(bare_fn, "__node_spec__")

    def test_empty_parens_decorator__tc_ep_032(self) -> None:
        """TC-EP-032: @node() with empty parentheses works."""
        from rdetoolkit.core.node import node

        # Given: @node() usage
        @node()
        def parens_fn(x: int) -> int:
            return x

        # Then: function works and has spec
        assert parens_fn(5) == 5
        assert hasattr(parens_fn, "__node_spec__")

    def test_no_arg_function__tc_bv_007(self) -> None:
        """TC-BV-007: @node on a no-argument function."""
        from rdetoolkit.core.node import node

        # Given: a function with no arguments
        @node
        def no_args() -> str:
            return "hello"

        # Then: spec has empty input schema
        spec = no_args.__node_spec__  # type: ignore[attr-defined]
        assert spec.input_schema == {}
        assert no_args() == "hello"

    def test_many_args_function__tc_bv_008(self) -> None:
        """TC-BV-008: @node on a function with many arguments."""
        from rdetoolkit.core.node import node

        # Given: a function with many arguments
        @node
        def many_args(a: int, b: str, c: float, d: list[int], e: dict[str, Any]) -> bool:
            return True

        # Then: all arguments captured in input schema
        spec = many_args.__node_spec__  # type: ignore[attr-defined]
        assert len(spec.input_schema) == 5
        assert "a" in spec.input_schema
        assert "b" in spec.input_schema
        assert "c" in spec.input_schema
        assert "d" in spec.input_schema
        assert "e" in spec.input_schema
