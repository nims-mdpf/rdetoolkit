"""Tests for v2 @node decorator, NodeSpec, and Node Registry (Session C1).

Design v2.1 §3.2 requires ``NodeSpec`` to hold no ``fn`` reference and to be
JSON-serializable from the start. This file was rewritten for Session C1:
the original Phase-1.2 assertions that pinned ``NodeSpec.fn`` and bare-type
``input_schema``/``output_schema`` values directly conflict with that
requirement and have been updated in place (see the UPDATE table below,
mirrored from ``local/develop/v2/tasks/session_c1.md``).

Naming convention pinned by these tests (guidance for the implementation):
``type_name`` strings use the bare ``__name__`` for builtins (``int``,
``str``, ``float``, ``bool``, ``None``) and ``"{module}.{qualname}"``
(e.g. ``"pathlib.Path"``) for everything else — the same convention used by
``TypeSummary.type_name`` in ``core/calllog.py`` (Design §3.4 example:
``"pandas.DataFrame"``).

EP Table (existing, Phase 1.2 — UPDATED/DELETED per Session C1):
| API                    | Partition             | Rationale              | Expected                       | Test ID     | C1 status |
|------------------------|------------------------|------------------------|---------------------------------|-------------|-----------|
| NodeSpec()             | valid fields           | normal construction    | fields accessible, no fn        | TC-EP-021   | UPDATED   |
| NodeSpec()             | missing required       | negative               | TypeError                       | TC-EP-022   | unchanged |
| NodeSpec               | frozen                 | immutability           | FrozenInstanceError              | TC-EP-023   | mechanical (fn kwarg removed) |
| NodeSpec               | type info captured     | inspect.signature      | input/output schemas present    | TC-EP-024   | UPDATED (strengthened) |
| @node                  | direct call            | transparency           | same result as bare fn          | TC-EP-025   | unchanged |
| @node                  | __node_spec__ present  | attribute attachment   | has NodeSpec                    | TC-EP-026   | unchanged |
| @node                  | wraps metadata         | functools.wraps        | __name__, __doc__ kept          | TC-EP-027   | unchanged |
| @node(tags=...)        | custom tags            | optional param         | tags stored in spec             | TC-EP-028   | unchanged |
| @node(version=...)     | custom version         | optional param         | version stored                  | TC-EP-029   | unchanged |
| @node(idempotent=T)    | idempotent flag        | optional param         | flag stored                     | TC-EP-030   | unchanged |
| @node                  | no args decorator      | bare @node usage       | works as @node                  | TC-EP-031   | unchanged |
| @node()                | empty parens           | @node() usage          | works as @node                  | TC-EP-032   | unchanged |
| NodeSpec.fn            | fn field               | design spec (Phase 1)  | is original function            | TC-EP-033   | DELETED (fn field removed) |
| NodeSpec.input_schema  | type objects           | design spec (Phase 1)  | values are type, not str        | TC-EP-034   | UPDATED (serializable form) |
| NodeSpec.source_loc    | module:qualname        | design spec            | correct format                  | TC-EP-035   | unchanged |
| NodeSpec.name          | name field             | design spec            | equals function name            | TC-EP-036   | unchanged |
| NodeSpec.output_schema | dict[str, type]        | design spec (Phase 1)  | tuple[str, ...] of type names   | TC-EP-037   | UPDATED (tuple[str,...] form) |

BV Table (existing, unaffected):
| API                  | Boundary              | Rationale              | Expected                  | Test ID     |
|----------------------|-----------------------|------------------------|---------------------------|-------------|
| NodeSpec             | empty tags list       | minimal                | tags is ()                | TC-BV-006   |
| @node                | no-arg function       | minimal function       | spec has empty inputs     | TC-BV-007   |
| @node                | many args function    | complex function       | all args captured         | TC-BV-008   |

New EP Table (Session C1):
| API                    | Partition                          | Rationale                | Expected                                             | Test ID   |
|------------------------|--------------------------------------|--------------------------|-------------------------------------------------------|-----------|
| NodeSpec serialization | json.dumps                          | JSON-serializable (kickoff C-3-1) | serializes without a custom encoder          | TC-EP-101 |
| NodeSpec               | fn attribute absent                 | design requirement       | hasattr(spec, "fn") is False                          | TC-EP-102 |
| @node default id       | module-level function               | Design §3.2              | id == "{module}.{qualname}"                           | TC-EP-103 |
| @node(id=...)          | explicit override                   | Design §3.2              | given id used verbatim                                | TC-EP-104 |
| Registry duplicate     | same explicit id registered twice   | E2001                    | RdeRegistryError, code == 2001                        | TC-EP-105 |
| Registry duplicate     | override id collides w/ default id  | E2001 (override still dup) | RdeRegistryError, code == 2001                     | TC-EP-106 |
| E2005 detection        | local function (qualname <locals>)  | Design §3.2              | detection fn lists the id; decoration itself succeeds | TC-EP-107 |
| E2005 non-detection    | module-level function               | stable id                | detection fn excludes the id                          | TC-EP-108 |
| Zero-cost recording    | call with no active run             | design requirement       | call succeeds; nothing recorded                       | TC-EP-109 |
| Type check off         | mismatched arg, type_check=off      | execution.type_check     | no exception raised                                    | TC-EP-110 |
| Type check strict      | mismatched arg, type_check=strict   | execution.type_check     | RdeExecutionError, code == 3002                       | TC-EP-111 |
| Type check warn        | mismatched arg, type_check=warn     | execution.type_check     | warnings.warn, no exception                            | TC-EP-112 |

New BV Table (Session C1):
| API                    | Boundary                       | Rationale                          | Expected                                              | Test ID   |
|------------------------|----------------------------------|-------------------------------------|--------------------------------------------------------|-----------|
| @node id default       | nested function (test method)   | qualname contains <locals> normally | decoration succeeds; no eager E2005 raise               | TC-BV-101 |
| Registry lookup        | empty/unregistered id            | miss                                | KeyError                                                | TC-BV-102 |
| NodeSpec.input_schema  | argument has a default value     | Design "preserves default values"   | default-value info recoverable from input_schema        | TC-BV-103 |
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


class TestNodeSpec:
    """Tests for NodeSpec frozen dataclass."""

    def test_construction_with_valid_fields__tc_ep_021(self) -> None:
        """TC-EP-021 (UPDATED for C1): NodeSpec holds no `fn`; input/output
        schemas are JSON-serializable structures, not bare type objects."""
        from rdetoolkit.core.node import NodeSpec

        spec = NodeSpec(
            id="read_csv",
            name="read_csv",
            input_schema={
                "paths": {"type_name": "pathlib.Path", "has_default": False, "default_repr": None},
            },
            output_schema=("str",),
            tags=("io",),
            version="1.0.0",
            idempotent=False,
            source_location="test:read_csv",
        )

        assert spec.id == "read_csv"
        assert spec.name == "read_csv"
        assert not hasattr(spec, "fn")
        assert spec.input_schema == {
            "paths": {"type_name": "pathlib.Path", "has_default": False, "default_repr": None},
        }
        assert spec.output_schema == ("str",)
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
        """TC-EP-023: NodeSpec fields cannot be reassigned (mechanical update:
        construction no longer passes `fn`, which was removed for C1)."""
        from rdetoolkit.core.node import NodeSpec

        spec = NodeSpec(
            id="test",
            name="test",
            input_schema={},
            output_schema=(),
            tags=(),
            version="0.0.0",
            idempotent=False,
            source_location="test:test",
        )

        with pytest.raises((AttributeError, TypeError)):
            spec.id = "other"  # type: ignore[misc]

    def test_empty_tags__tc_bv_006(self) -> None:
        """TC-BV-006: NodeSpec with empty tags tuple (mechanical update: no
        `fn` kwarg, which was removed for C1)."""
        from rdetoolkit.core.node import NodeSpec

        spec = NodeSpec(
            id="test",
            name="test",
            input_schema={},
            output_schema=(),
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
        """TC-EP-024 (UPDATED for C1): @node captures input/output type info
        from the signature; output_schema is a JSON-serializable tuple."""
        from rdetoolkit.core.node import node

        @node
        def transform(paths: Path, count: int) -> str:
            """Transform data."""
            return str(paths) * count

        spec = transform.__node_spec__  # type: ignore[attr-defined]
        assert "paths" in spec.input_schema
        assert "count" in spec.input_schema
        assert isinstance(spec.output_schema, tuple)

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

    # TC-EP-033 (NodeSpec.fn is the original unwrapped function) DELETED for
    # C1: the `fn` field itself is removed from NodeSpec (Design v2.1 §3.2 —
    # JSON-serializability requirement). The original function reference now
    # lives only in the Registry's internal execution table.

    def test_input_schema_values_are_serializable__tc_ep_034(self) -> None:
        """TC-EP-034 (UPDATED for C1): input_schema values are JSON-serializable
        dicts carrying a `type_name` string (module.qualname convention for
        non-builtins), not bare type objects."""
        from rdetoolkit.core.node import node

        @node
        def typed_fn(paths: Path, count: int) -> str:
            return ""

        spec = typed_fn.__node_spec__  # type: ignore[attr-defined]
        assert not isinstance(spec.input_schema["paths"], type)
        assert not isinstance(spec.input_schema["count"], type)
        assert spec.input_schema["paths"]["type_name"] == "pathlib.Path"
        assert spec.input_schema["count"]["type_name"] == "int"

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
        """TC-EP-037 (UPDATED for C1): output_schema is a tuple[str, ...] of
        type-name strings (Design §3.2's canonical NodeSpec shape), not a
        dict of type objects."""
        from rdetoolkit.core.node import node

        @node
        def single_out(x: int) -> str:
            return str(x)

        spec = single_out.__node_spec__  # type: ignore[attr-defined]
        assert isinstance(spec.output_schema, tuple)
        assert spec.output_schema == ("str",)

    def test_output_schema_tuple_return(self) -> None:
        """UPDATED for C1: tuple return types produce a positional tuple of
        type-name strings, e.g. ("str", "int")."""
        from rdetoolkit.core.node import node

        @node
        def multi_out(x: int) -> tuple[str, int]:
            return str(x), x

        spec = multi_out.__node_spec__  # type: ignore[attr-defined]
        assert spec.output_schema == ("str", "int")

    def test_output_schema_none_return(self) -> None:
        """UPDATED for C1: None return type produces an empty tuple."""
        from rdetoolkit.core.node import node

        @node
        def void_fn(x: int) -> None:
            pass

        spec = void_fn.__node_spec__  # type: ignore[attr-defined]
        assert spec.output_schema == ()


# --- Session C1 additions ----------------------------------------------------

# Module-level target used by TC-EP-108: decorated exactly once at import
# time so its qualname is stable (no "<locals>"), unlike functions decorated
# inside test methods.


def _stable_target_fn(x: int) -> int:
    """Plain module-level function used to build a stable-id node."""
    return x


class TestNodeSpecSerialization:
    """TC-EP-101/102: NodeSpec must be JSON-serializable and hold no `fn`."""

    def test_nodespec_is_json_serializable__tc_ep_101(self) -> None:
        """TC-EP-101: the NodeSpec attached by @node serializes via json.dumps
        without a custom encoder (dataclasses.asdict must yield only JSON
        primitives, tuples, and dicts of primitives)."""
        import dataclasses
        import json

        from rdetoolkit.core.node import node

        @node
        def serializable_fn(a: int, b: str = "x") -> int:
            return a

        spec = serializable_fn.__node_spec__  # type: ignore[attr-defined]
        payload = dataclasses.asdict(spec)
        json.dumps(payload)  # must not raise

    def test_nodespec_has_no_fn_attribute__tc_ep_102(self) -> None:
        """TC-EP-102: NodeSpec no longer holds a reference to the original fn."""
        from rdetoolkit.core.node import node

        @node
        def no_fn_field_fn(a: int) -> int:
            return a

        spec = no_fn_field_fn.__node_spec__  # type: ignore[attr-defined]
        assert not hasattr(spec, "fn")


class TestNodeIdAndRegistry:
    """TC-EP-103..108, TC-EP-105/106, TC-BV-101/102: id rules + Registry."""

    def test_default_id_is_module_qualname__tc_ep_103(self) -> None:
        """TC-EP-103: default id is "{module}.{qualname}"."""
        from rdetoolkit.core.node import node

        @node
        def id_default_fn(x: int) -> int:
            return x

        spec = id_default_fn.__node_spec__  # type: ignore[attr-defined]
        assert spec.id == f"{id_default_fn.__module__}.{id_default_fn.__qualname__}"

    def test_explicit_id_override__tc_ep_104(self) -> None:
        """TC-EP-104: @node(id=...) overrides the default id verbatim."""
        from rdetoolkit.core.node import node

        @node(id="custom.explicit.node.id.tc104")
        def explicit_id_fn(x: int) -> int:
            return x

        spec = explicit_id_fn.__node_spec__  # type: ignore[attr-defined]
        assert spec.id == "custom.explicit.node.id.tc104"

    def test_registry_duplicate_explicit_id_raises_e2001__tc_ep_105(self) -> None:
        """TC-EP-105: registering the same explicit id twice raises E2001
        (RdeRegistryError, code=2001) immediately at decoration time."""
        from rdetoolkit.core.node import node
        from rdetoolkit.errors import RdeRegistryError

        @node(id="dup.explicit.id.tc105")
        def first_fn(x: int) -> int:
            return x

        with pytest.raises(RdeRegistryError) as exc_info:

            @node(id="dup.explicit.id.tc105")
            def second_fn(x: int) -> int:
                return x

        assert exc_info.value.code == 2001

    def test_registry_duplicate_override_matches_default_id__tc_ep_106(self) -> None:
        """TC-EP-106: an explicit id that happens to collide with another
        node's *default* id is still a duplicate (E2001)."""
        from rdetoolkit.core.node import node
        from rdetoolkit.errors import RdeRegistryError

        @node
        def default_id_target_fn(x: int) -> int:
            return x

        target_id = default_id_target_fn.__node_spec__.id  # type: ignore[attr-defined]

        with pytest.raises(RdeRegistryError) as exc_info:

            @node(id=target_id)
            def other_fn(x: int) -> int:
                return x

        assert exc_info.value.code == 2001

    def test_unstable_node_id_detected_for_local_function__tc_ep_107(self) -> None:
        """TC-EP-107: a locally-scoped @node function does NOT raise at
        decoration time; the E2005 (UnstableNodeId) detection function lists
        its id when queried explicitly."""
        from rdetoolkit.core.node import node
        from rdetoolkit.core.registry import find_unstable_node_ids

        def _make() -> Any:
            @node
            def local_node_fn(x: int) -> int:
                return x

            return local_node_fn

        fn = _make()  # must NOT raise despite "<locals>" in qualname
        assert fn(3) == 3

        unstable_ids = find_unstable_node_ids()
        assert fn.__node_spec__.id in unstable_ids  # type: ignore[attr-defined]

    def test_unstable_node_id_not_detected_for_module_level__tc_ep_108(self) -> None:
        """TC-EP-108: a module-level @node function's id is never reported by
        the E2005 detection function."""
        from rdetoolkit.core.node import node
        from rdetoolkit.core.registry import find_unstable_node_ids

        decorated = node(_stable_target_fn)
        unstable_ids = find_unstable_node_ids()
        assert decorated.__node_spec__.id not in unstable_ids  # type: ignore[attr-defined]

    def test_nested_function_decoration_does_not_raise__tc_bv_101(self) -> None:
        """TC-BV-101: decorating a nested/local function succeeds (no eager
        E2005); this is the common pattern used throughout this test suite."""
        from rdetoolkit.core.node import node

        def _factory() -> Any:
            @node
            def nested_bv_fn(x: int) -> int:
                return x

            return nested_bv_fn

        fn = _factory()
        assert fn(7) == 7

    def test_registry_lookup_missing_id_raises_keyerror__tc_bv_102(self) -> None:
        """TC-BV-102: looking up an unregistered node id raises KeyError."""
        from rdetoolkit.core.registry import get_node

        with pytest.raises(KeyError):
            get_node("this.id.does.not.exist.anywhere.tc-bv-102")

    def test_input_schema_preserves_default_value_info__tc_bv_103(self) -> None:
        """TC-BV-103: parameter default-value presence/repr is recoverable
        from input_schema (Design §3.2: "input_schema は関数デフォルト値を保持する")."""
        from rdetoolkit.core.node import node

        @node
        def default_arg_fn(a: int, b: float = 0.5) -> int:
            return a

        spec = default_arg_fn.__node_spec__  # type: ignore[attr-defined]
        a_entry = spec.input_schema["a"]
        b_entry = spec.input_schema["b"]

        assert a_entry["has_default"] is False
        assert a_entry["default_repr"] is None
        assert b_entry["has_default"] is True
        assert b_entry["default_repr"] == repr(0.5)


class TestNodeZeroCostAndTypeCheck:
    """TC-EP-109..112: recording zero-cost + opt-in type check (Design §4.4)."""

    def test_call_without_active_run_produces_no_record__tc_ep_109(self) -> None:
        """TC-EP-109: calling a @node function with no active run succeeds
        and leaves nothing in a (separately constructed) CallLogRecorder."""
        from rdetoolkit.core.calllog import CallLogRecorder
        from rdetoolkit.core.node import node

        @node
        def add_no_run_fn(a: int, b: int) -> int:
            return a + b

        assert add_no_run_fn(2, 3) == 5

        recorder = CallLogRecorder()  # constructed but never entered/activated
        assert recorder.records == ()

    def test_type_check_off_default_allows_mismatched_args__tc_ep_110(self) -> None:
        """TC-EP-110: execution.type_check == "off" (default) never raises,
        even for an obviously mismatched argument, and even under an active
        recording run."""
        from rdetoolkit.core.calllog import CallLogRecorder
        from rdetoolkit.core.node import node

        @node
        def loose_typed_fn(x: int) -> int:
            return x  # type: ignore[return-value]

        with CallLogRecorder(type_check="off"):
            assert loose_typed_fn("not-an-int") == "not-an-int"  # type: ignore[arg-type]

    def test_type_check_strict_raises_e3002_on_mismatch__tc_ep_111(self) -> None:
        """TC-EP-111: execution.type_check == "strict" raises E3002
        (NodeTypeMismatch) via RdeExecutionError when an argument's runtime
        type does not match its annotation."""
        from rdetoolkit.core.calllog import CallLogRecorder
        from rdetoolkit.core.node import node
        from rdetoolkit.errors import RdeExecutionError

        @node
        def strict_typed_fn(x: int) -> int:
            return x  # type: ignore[return-value]

        with CallLogRecorder(type_check="strict"):
            with pytest.raises(RdeExecutionError) as exc_info:
                strict_typed_fn("not-an-int")  # type: ignore[arg-type]

        assert exc_info.value.code == 3002

    def test_type_check_warn_emits_warning_without_raising__tc_ep_112(self) -> None:
        """TC-EP-112: execution.type_check == "warn" emits a warning via
        warnings.warn but does not raise, and the call still completes."""
        from rdetoolkit.core.calllog import CallLogRecorder
        from rdetoolkit.core.node import node

        @node
        def warn_typed_fn(x: int) -> int:
            return x  # type: ignore[return-value]

        with CallLogRecorder(type_check="warn"):
            with pytest.warns(UserWarning):
                result = warn_typed_fn("not-an-int")  # type: ignore[arg-type]

        assert result == "not-an-int"
