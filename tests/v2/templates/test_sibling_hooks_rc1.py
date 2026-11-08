"""Concrete template siblings must not share or poison one hook (RC1 F04).

Review ``interrogate_v2.0.0rc1`` F04: ``_register_implementations`` wrote
``self: FirstConcrete`` into the skeleton's own function object for an
inherited hook (``annotations.setdefault("self", cls)``), so the second
sibling inherited the first sibling's ``self`` type: strict type checking
failed its default hook with 3002 and its NodeSpec named the wrong class.

Each test defines its own classes so their qualnames (and node ids) are
unique for the whole pytest session (``core/registry.py`` has no reset).

EP table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-RC1-F04-EP-001 | strict, siblings | default hook on both siblings | both succeed |
| TC-RC1-F04-EP-002 | NodeSpec | both siblings' hook specs | ``self`` names each own class |
| TC-RC1-F04-EP-003 | own callable | both siblings' wrapped hooks | distinct, each ``self`` is its class |
| TC-RC1-F04-EP-004 | copy fidelity | defaults, kw-only defaults, closure, dict | preserved on every sibling |
| TC-RC1-F04-EP-005 | call log | default hook on both siblings | records under each sibling's id |

BV / negative table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-RC1-F04-NEG-001 | immutability | skeleton hook/slot after N siblings | same object, annotations unchanged |
| TC-RC1-F04-NEG-002 | immutability | a sibling's own overriding method | annotations unchanged |
| TC-RC1-F04-NEG-003 | strict still checks | sibling hook called with the other sibling | 3002 on ``self`` |
| TC-RC1-F04-NEG-004 | explicit self | skeleton hook annotating ``self`` itself | explicit annotation kept |
| TC-RC1-F04-NEG-005 | non-function hook | builtin hook | registered, never mutated |
| TC-RC1-F04-BV-001 | count | three siblings | all three pass strict |
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from rdetoolkit.core import registry
from rdetoolkit.core.calllog import CallLogRecorder
from rdetoolkit.errors import RdeExecutionError
from rdetoolkit.templates import ProcessingTemplate, slot


def _spec(cls: type, method_name: str) -> Any:
    node_id = f"{cls.__module__}.{cls.__qualname__}.{method_name}"
    return next(spec for spec in registry.list_nodes() if spec.id == node_id)


def _self_type_name(cls: type) -> str:
    return f"{cls.__module__}.{cls.__qualname__}"


class TestSiblingHooksAreIndependent:
    def test_default_hook_passes_strict_on_every_sibling__tc_rc1_f04_ep_001(self) -> None:
        # Given: two concrete siblings inheriting one default hook
        class Skeleton(ProcessingTemplate):
            @slot
            def read(self) -> int: ...

            def hook(self, value: int) -> int:
                return value

            def __flow__(self) -> int:
                return self.hook(self.read())

        class First(Skeleton):
            def read(self) -> int:
                return 1

        class Second(Skeleton):
            def read(self) -> int:
                return 2

        # When: each sibling runs its flow under strict type checking
        with CallLogRecorder(type_check="strict") as recorder:
            results = (First().__flow__(), Second().__flow__())

        # Then: both default hooks succeed and are recorded under their own ids
        assert results == (1, 2)
        assert [record.status for record in recorder.records] == ["completed"] * 4
        hook_ids = [record.node_id for record in recorder.records if record.node_id.endswith(".hook")]
        assert hook_ids == [_spec(First, "hook").id, _spec(Second, "hook").id]

    def test_node_spec_names_each_sibling__tc_rc1_f04_ep_002(self) -> None:
        # Given: two siblings sharing a default hook
        class Skeleton(ProcessingTemplate):
            @slot
            def read(self) -> int: ...

            def hook(self, value: int) -> int:
                return value

            def __flow__(self) -> int:
                return self.hook(self.read())

        class First(Skeleton):
            def read(self) -> int:
                return 1

        class Second(Skeleton):
            def read(self) -> int:
                return 2

        # When: their registered NodeSpecs are read
        first_spec = _spec(First, "hook")
        second_spec = _spec(Second, "hook")

        # Then: each spec's self type is its own class
        assert first_spec.input_schema["self"]["type_name"] == _self_type_name(First)
        assert second_spec.input_schema["self"]["type_name"] == _self_type_name(Second)
        assert _spec(Second, "read").input_schema["self"]["type_name"] == _self_type_name(Second)

    def test_each_sibling_gets_its_own_callable__tc_rc1_f04_ep_003(self) -> None:
        # Given: two siblings sharing a default hook
        class Skeleton(ProcessingTemplate):
            @slot
            def read(self) -> int: ...

            def hook(self, value: int) -> int:
                return value

            def __flow__(self) -> int:
                return self.hook(self.read())

        class First(Skeleton):
            def read(self) -> int:
                return 1

        class Second(Skeleton):
            def read(self) -> int:
                return 2

        # When: the wrapped hooks are inspected
        first_impl = vars(First)["hook"].__wrapped__
        second_impl = vars(Second)["hook"].__wrapped__

        # Then: neither is the skeleton function and each carries its own self
        skeleton_hook = vars(Skeleton)["hook"]
        assert first_impl is not second_impl
        assert first_impl is not skeleton_hook
        assert second_impl is not skeleton_hook
        assert first_impl.__annotations__["self"] is First
        assert second_impl.__annotations__["self"] is Second
        assert first_impl.__code__ is skeleton_hook.__code__

    def test_copy_preserves_defaults_closure_and_attributes__tc_rc1_f04_ep_004(self) -> None:
        # Given: a default hook with defaults, kw-only defaults, a closure and an attribute
        offset = 10

        class Skeleton(ProcessingTemplate):
            @slot
            def read(self) -> int: ...

            def hook(self, value: int, scale: int = 2, *, bias: int = 1) -> int:
                """Scale, bias and offset the value."""
                return value * scale + bias + offset

            hook.marker = "kept"  # type: ignore[attr-defined]

            def __flow__(self) -> int:
                return self.hook(self.read())

        class First(Skeleton):
            def read(self) -> int:
                return 1

        class Second(Skeleton):
            def read(self) -> int:
                return 2

        # When: the default hook runs with omitted arguments on both siblings
        with CallLogRecorder(type_check="strict"):
            results = (First().__flow__(), Second().__flow__(), Second().hook(3, bias=0))

        # Then: defaults, kw-only defaults and the closure behave as declared
        assert results == (13, 15, 16)
        for cls in (First, Second):
            impl = vars(cls)["hook"].__wrapped__
            assert impl.__defaults__ == (2,)
            assert impl.__kwdefaults__ == {"bias": 1}
            assert impl.__qualname__ == vars(Skeleton)["hook"].__qualname__
            assert impl.__module__ == Skeleton.__module__
            assert impl.__doc__ == "Scale, bias and offset the value."
            assert impl.marker == "kept"
            assert list(inspect.signature(impl).parameters) == ["self", "value", "scale", "bias"]

    def test_three_siblings_all_pass_strict__tc_rc1_f04_bv_001(self) -> None:
        # Given: three siblings of one skeleton
        class Skeleton(ProcessingTemplate):
            @slot
            def read(self) -> int: ...

            def hook(self, value: int) -> int:
                return value

            def __flow__(self) -> int:
                return self.hook(self.read())

        class First(Skeleton):
            def read(self) -> int:
                return 1

        class Second(Skeleton):
            def read(self) -> int:
                return 2

        class Third(Skeleton):
            def read(self) -> int:
                return 3

        # When / Then: every sibling passes strict
        with CallLogRecorder(type_check="strict"):
            assert [cls().__flow__() for cls in (First, Second, Third)] == [1, 2, 3]


class TestSkeletonIsNeverMutated:
    def test_skeleton_functions_unchanged_after_siblings__tc_rc1_f04_neg_001(self) -> None:
        # Given: a skeleton and snapshots of its hook and slot function objects
        class Skeleton(ProcessingTemplate):
            @slot
            def read(self) -> int: ...

            def hook(self, value: int) -> int:
                return value

            def __flow__(self) -> int:
                return self.hook(self.read())

        hook_before = vars(Skeleton)["hook"]
        read_before = vars(Skeleton)["read"]
        hook_annotations = dict(hook_before.__annotations__)
        read_annotations = dict(read_before.__annotations__)

        # When: two concrete siblings are defined
        class First(Skeleton):
            def read(self) -> int:
                return 1

        class Second(Skeleton):
            def read(self) -> int:
                return 2

        # Then: the skeleton's function objects and annotations are untouched
        assert vars(Skeleton)["hook"] is hook_before
        assert vars(Skeleton)["read"] is read_before
        assert hook_before.__annotations__ == hook_annotations
        assert read_before.__annotations__ == read_annotations
        assert "self" not in hook_before.__annotations__
        assert not hasattr(hook_before, "__node_spec__")
        assert (First, Second) != ()

    def test_overriding_method_object_is_not_mutated__tc_rc1_f04_neg_002(self) -> None:
        # Given: a sibling's own overriding method, captured before registration
        captured: dict[str, Any] = {}

        class Skeleton(ProcessingTemplate):
            @slot
            def read(self) -> int: ...

            def __flow__(self) -> int:
                return self.read()

        def read(self) -> int:  # noqa: ANN001
            return 1

        original_annotations = dict(read.__annotations__)
        captured["read"] = read

        # When: the concrete class adopting that function is defined
        First = type("First", (Skeleton,), {"read": read, "__module__": __name__, "__qualname__": "RC1F04NegFirst"})

        # Then: the user's function object keeps its own annotations
        assert captured["read"].__annotations__ == original_annotations
        assert vars(First)["read"].__wrapped__ is not read

    def test_strict_still_rejects_the_wrong_sibling_as_self__tc_rc1_f04_neg_003(self) -> None:
        # Given: two siblings sharing a default hook
        class Skeleton(ProcessingTemplate):
            @slot
            def read(self) -> int: ...

            def hook(self, value: int) -> int:
                return value

            def __flow__(self) -> int:
                return self.hook(self.read())

        class First(Skeleton):
            def read(self) -> int:
                return 1

        class Second(Skeleton):
            def read(self) -> int:
                return 2

        # When / Then: Second's hook called with a First instance is a self mismatch
        with CallLogRecorder(type_check="strict"), pytest.raises(RdeExecutionError) as exc_info:
            Second.hook(First(), 1)  # type: ignore[arg-type]
        assert exc_info.value.code == 3002
        assert "self" in str(exc_info.value)

    def test_explicit_self_annotation_is_kept__tc_rc1_f04_neg_004(self) -> None:
        # Given: a skeleton hook that annotates self explicitly with the skeleton
        class Skeleton(ProcessingTemplate):
            @slot
            def read(self) -> int: ...

            def hook(self: Skeleton, value: int) -> int:
                return value

            def __flow__(self) -> int:
                return self.hook(self.read())

        class First(Skeleton):
            def read(self) -> int:
                return 1

        # When: the copy's annotations are read
        impl = vars(First)["hook"].__wrapped__

        # Then: the explicit annotation wins over the injected class
        assert impl.__annotations__["self"] == "Skeleton"

    def test_non_function_hook_is_registered_unmodified__tc_rc1_f04_neg_005(self) -> None:
        # Given: a skeleton whose public hook is a builtin, not a Python function
        class Skeleton(ProcessingTemplate):
            @slot
            def read(self) -> int: ...

            measure = staticmethod(abs)

            def __flow__(self) -> int:
                return self.read()

        # When: a concrete class is defined
        class First(Skeleton):
            def read(self) -> int:
                return 1

        # Then: the builtin is registered as it is and never written to
        assert vars(First)["measure"].__wrapped__ is abs
        assert _spec(First, "measure").name == "abs"
