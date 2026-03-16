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
| NodeSpec.fn          | fn field              | design spec            | is original function      | TC-EP-033   |
| NodeSpec.input_schema| type objects          | design spec            | values are type, not str  | TC-EP-034   |
| NodeSpec.source_loc  | module:qualname       | design spec            | correct format            | TC-EP-035   |
| NodeSpec.name        | name field            | design spec            | equals function name      | TC-EP-036   |
| NodeSpec.output_schema| dict[str, type]      | design spec            | port→type mapping         | TC-EP-037   |

BV Table:
| API                  | Boundary              | Rationale              | Expected                  | Test ID     |
|----------------------|-----------------------|------------------------|---------------------------|-------------|
| NodeSpec             | empty tags list       | minimal                | tags is ()                | TC-BV-006   |
| @node                | no-arg function       | minimal function       | spec has empty inputs     | TC-BV-007   |
| @node                | many args function    | complex function       | all args captured         | TC-BV-008   |
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest


def _dummy_fn() -> None:
    pass


class TestNodeSpec:
    """Tests for NodeSpec frozen dataclass."""

    def test_construction_with_valid_fields__tc_ep_021(self) -> None:
        """TC-EP-021: NodeSpec constructed with valid fields."""
        from rdetoolkit.core.node import NodeSpec

        spec = NodeSpec(
            id="read_csv",
            name="read_csv",
            fn=_dummy_fn,
            input_schema={"paths": Path},
            output_schema={"_return": str},
            tags=("io",),
            version="1.0.0",
            idempotent=False,
            source_location="test:read_csv",
        )

        assert spec.id == "read_csv"
        assert spec.name == "read_csv"
        assert spec.fn is _dummy_fn
        assert spec.input_schema == {"paths": Path}
        assert spec.output_schema == {"_return": str}
        assert spec.tags == ("io",)
        assert spec.version == "1.0.0"
        assert spec.idempotent is False
        assert spec.source_location == "test:read_csv"

    def test_construction_missing_required_raises__tc_ep_022(self) -> None:
        """TC-EP-022: NodeSpec without required fields raises TypeError."""
        from rdetoolkit.core.node import NodeSpec

        with pytest.raises(TypeError):
            NodeSpec(id="test")  # type: ignore[call-arg]

    def test_frozen__tc_ep_023(self) -> None:
        """TC-EP-023: NodeSpec fields cannot be reassigned."""
        from rdetoolkit.core.node import NodeSpec

        spec = NodeSpec(
            id="test",
            name="test",
            fn=_dummy_fn,
            input_schema={},
            output_schema={},
            tags=(),
            version="0.0.0",
            idempotent=False,
            source_location="test:test",
        )

        with pytest.raises((AttributeError, TypeError)):
            spec.id = "other"  # type: ignore[misc]

    def test_empty_tags__tc_bv_006(self) -> None:
        """TC-BV-006: NodeSpec with empty tags tuple."""
        from rdetoolkit.core.node import NodeSpec

        spec = NodeSpec(
            id="test",
            name="test",
            fn=_dummy_fn,
            input_schema={},
            output_schema={},
            tags=(),
            version="0.0.0",
            idempotent=False,
            source_location="test:test",
        )

        assert spec.tags == ()


class TestNodeDecorator:
    """Tests for @node decorator."""

    def test_direct_call_transparency__tc_ep_025(self) -> None:
        """TC-EP-025: @node decorated function is directly callable with same result."""
        from rdetoolkit.core.node import node

        @node
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        result = add(2, 3)
        assert result == 5

    def test_node_spec_attached__tc_ep_026(self) -> None:
        """TC-EP-026: @node attaches __node_spec__ attribute."""
        from rdetoolkit.core.node import NodeSpec, node

        @node
        def process(x: int) -> str:
            """Process x."""
            return str(x)

        assert hasattr(process, "__node_spec__")
        assert isinstance(process.__node_spec__, NodeSpec)  # type: ignore[attr-defined]

    def test_wraps_metadata_preserved__tc_ep_027(self) -> None:
        """TC-EP-027: @node preserves __name__ and __doc__."""
        from rdetoolkit.core.node import node

        @node
        def my_func(x: int) -> int:
            """My docstring."""
            return x

        assert my_func.__name__ == "my_func"
        assert my_func.__doc__ == "My docstring."

    def test_type_info_captured__tc_ep_024(self) -> None:
        """TC-EP-024: @node captures input/output type info from signature."""
        from rdetoolkit.core.node import node

        @node
        def transform(paths: Path, count: int) -> str:
            """Transform data."""
            return str(paths) * count

        spec = transform.__node_spec__  # type: ignore[attr-defined]
        assert "paths" in spec.input_schema
        assert "count" in spec.input_schema
        assert spec.output_schema is not None

    def test_custom_tags__tc_ep_028(self) -> None:
        """TC-EP-028: @node with custom tags."""
        from rdetoolkit.core.node import node

        @node(tags=["io", "csv"])
        def read_csv(path: Path) -> str:
            return ""

        spec = read_csv.__node_spec__  # type: ignore[attr-defined]
        assert "io" in spec.tags
        assert "csv" in spec.tags

    def test_custom_version__tc_ep_029(self) -> None:
        """TC-EP-029: @node with custom version."""
        from rdetoolkit.core.node import node

        @node(version="2.1.0")
        def versioned_fn(x: int) -> int:
            return x

        spec = versioned_fn.__node_spec__  # type: ignore[attr-defined]
        assert spec.version == "2.1.0"

    def test_idempotent_flag__tc_ep_030(self) -> None:
        """TC-EP-030: @node with idempotent flag."""
        from rdetoolkit.core.node import node

        @node(idempotent=True)
        def safe_fn(x: int) -> int:
            return x

        spec = safe_fn.__node_spec__  # type: ignore[attr-defined]
        assert spec.idempotent is True

    def test_bare_decorator__tc_ep_031(self) -> None:
        """TC-EP-031: @node without parentheses works."""
        from rdetoolkit.core.node import node

        @node
        def bare_fn(x: int) -> int:
            return x

        assert bare_fn(5) == 5
        assert hasattr(bare_fn, "__node_spec__")

    def test_empty_parens_decorator__tc_ep_032(self) -> None:
        """TC-EP-032: @node() with empty parentheses works."""
        from rdetoolkit.core.node import node

        @node()
        def parens_fn(x: int) -> int:
            return x

        assert parens_fn(5) == 5
        assert hasattr(parens_fn, "__node_spec__")

    def test_no_arg_function__tc_bv_007(self) -> None:
        """TC-BV-007: @node on a no-argument function."""
        from rdetoolkit.core.node import node

        @node
        def no_args() -> str:
            return "hello"

        spec = no_args.__node_spec__  # type: ignore[attr-defined]
        assert spec.input_schema == {}
        assert no_args() == "hello"

    def test_many_args_function__tc_bv_008(self) -> None:
        """TC-BV-008: @node on a function with many arguments."""
        from rdetoolkit.core.node import node

        @node
        def many_args(a: int, b: str, c: float, d: list[int], e: dict[str, Any]) -> bool:
            return True

        spec = many_args.__node_spec__  # type: ignore[attr-defined]
        assert len(spec.input_schema) == 5
        assert "a" in spec.input_schema
        assert "b" in spec.input_schema
        assert "c" in spec.input_schema
        assert "d" in spec.input_schema
        assert "e" in spec.input_schema

    def test_fn_field_is_original_function__tc_ep_033(self) -> None:
        """TC-EP-033: NodeSpec.fn is the original unwrapped function."""
        from rdetoolkit.core.node import node

        def original(x: int) -> int:
            return x

        decorated = node(original)
        spec = decorated.__node_spec__  # type: ignore[attr-defined]
        assert spec.fn is original

    def test_input_schema_values_are_types__tc_ep_034(self) -> None:
        """TC-EP-034: NodeSpec.input_schema values are type objects, not strings."""
        from rdetoolkit.core.node import node

        @node
        def typed_fn(paths: Path, count: int) -> str:
            return ""

        spec = typed_fn.__node_spec__  # type: ignore[attr-defined]
        assert spec.input_schema["paths"] is Path
        assert spec.input_schema["count"] is int

    def test_source_location_format__tc_ep_035(self) -> None:
        """TC-EP-035: NodeSpec.source_location is 'module:qualname' format."""
        from rdetoolkit.core.node import node

        @node
        def located_fn(x: int) -> int:
            return x

        spec = located_fn.__node_spec__  # type: ignore[attr-defined]
        assert ":" in spec.source_location
        parts = spec.source_location.split(":", 1)
        assert len(parts) == 2
        # qualname includes enclosing scope for nested functions
        assert parts[1].endswith("located_fn")

    def test_name_field__tc_ep_036(self) -> None:
        """TC-EP-036: NodeSpec.name equals the function name."""
        from rdetoolkit.core.node import node

        @node
        def my_node_func(x: int) -> int:
            return x

        spec = my_node_func.__node_spec__  # type: ignore[attr-defined]
        assert spec.name == "my_node_func"

    def test_output_schema_dict_with_types__tc_ep_037(self) -> None:
        """TC-EP-037: output_schema is dict[str, type] with port->type mapping."""
        from rdetoolkit.core.node import node

        @node
        def single_out(x: int) -> str:
            return str(x)

        spec = single_out.__node_spec__  # type: ignore[attr-defined]
        assert isinstance(spec.output_schema, dict)
        assert "_return" in spec.output_schema
        assert spec.output_schema["_return"] is str

    def test_output_schema_tuple_return(self) -> None:
        """Tuple return types produce positional output ports."""
        from rdetoolkit.core.node import node

        @node
        def multi_out(x: int) -> tuple[str, int]:
            return str(x), x

        spec = multi_out.__node_spec__  # type: ignore[attr-defined]
        assert "_0" in spec.output_schema
        assert "_1" in spec.output_schema
        assert spec.output_schema["_0"] is str
        assert spec.output_schema["_1"] is int

    def test_output_schema_none_return(self) -> None:
        """None return type produces empty output_schema."""
        from rdetoolkit.core.node import node

        @node
        def void_fn(x: int) -> None:
            pass

        spec = void_fn.__node_spec__  # type: ignore[attr-defined]
        assert spec.output_schema == {}
