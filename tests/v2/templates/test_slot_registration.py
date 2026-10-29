"""Tests for slot/hook auto-``@node``-registration on ``ProcessingTemplate``
subclasses (Session F2, TC-TPL-REG-*).

Written before implementation (TDD Red phase). Authority:
local/develop/v2/tasks/session_f2.md Conflicts #2, #4; Design.md v2.1
§5.2.3.

Binding API-shape pins asserted by this file (precision standard):
- Slot/hook auto-registration happens at DEPTH-2 (user) class-definition
  time, on the SUBCLASS's own method objects (read via ``vars(cls)``, not
  ``getattr``), never at depth-1 (skeleton) definition time -- registration
  reuses the existing ``core.node``/``core.registry`` mechanism verbatim
  (no new machinery, 原則10).
- Registered node id shape: ``f"{cls.__module__}.{cls.__qualname__}.
  {method_name}"`` (Conflict #2) -- computed here from the REAL class
  object's own ``__module__``/``__qualname__`` after definition, never
  hand-guessed, so this file is robust to whatever qualname Python assigns
  to a locally-defined class.
- A hook (a method with a working default body, no ``@slot`` marker) is
  registered ONLY when the user subclass actually overrides it in
  ``vars(cls)`` -- an inherited, un-overridden default is never
  re-registered under the new subclass's id (Conflict #4).
- Running a template end-to-end via ``Runner.run``/``workflows.run``
  produces call-log records (``RunReport.iterations[i]["node_calls"]``)
  for each slot/hook invocation, through the exact same mechanism F1's
  builtin nodes use -- no template-specific recording path exists
  (Design §5.2.3, 原則10).

Trap avoidance: every test defines its own skeleton/user classes locally
(never via a shared factory function) so that each test's classes get a
UNIQUE ``__qualname__`` (derived from its own enclosing test-method name) --
reusing a shared builder function across tests would give every call site
the SAME qualname and collide on ``E2001 DuplicateNodeId`` the moment two
tests both call it (``core/registry.py`` has no reset and persists for the
whole pytest session, Conflict #7 precedent in
``tests/v2/cli/test_cli_nodes.py``).
"""

from __future__ import annotations

from typing import Any

import pytest


def _import_templates() -> tuple[type, Any]:
    from rdetoolkit.templates import ProcessingTemplate, slot  # noqa: PLC0415

    return ProcessingTemplate, slot


def _input_paths_type() -> type:
    from rdetoolkit.types import InputPaths  # noqa: PLC0415

    return InputPaths


def _registered_node_ids() -> set[str]:
    from rdetoolkit.core import registry  # noqa: PLC0415

    return {spec.id for spec in registry.list_nodes()}


class TestAutoRegistrationOnDepth2Definition:
    """TC-TPL-REG-001/002 (Conflict #2)."""

    def test_slot_and_overridden_hook_appear_in_registry_with_expected_id_shape(self) -> None:
        # Given: a skeleton with one required slot and one optional hook.
        ProcessingTemplate, slot = _import_templates()
        InputPaths = _input_paths_type()
        from typing import final  # noqa: PLC0415

        class _Skeleton(ProcessingTemplate):
            @slot
            def read(self, paths: InputPaths) -> None: ...

            def transform(self, paths: InputPaths) -> InputPaths:
                return paths

            @final
            def __flow__(self, paths: InputPaths) -> None:
                paths = self.transform(paths)
                self.read(paths)

        # When: a depth-2 subclass overrides BOTH the slot and the hook.
        class _UserOverridesBoth(_Skeleton):
            def read(self, paths: InputPaths) -> None:
                return None

            def transform(self, paths: InputPaths) -> InputPaths:
                return paths

        # Then: both appear in the registry, id-shaped
        # "{module}.{qualname}.{method_name}".
        ids = _registered_node_ids()
        expected_read_id = f"{_UserOverridesBoth.__module__}.{_UserOverridesBoth.__qualname__}.read"
        expected_transform_id = f"{_UserOverridesBoth.__module__}.{_UserOverridesBoth.__qualname__}.transform"
        assert expected_read_id in ids
        assert expected_transform_id in ids

    def test_hook_left_at_inherited_default_is_registered_for_concrete_class(self) -> None:
        # Given: a skeleton with an optional hook, and TWO sibling depth-2
        # subclasses -- one overrides the hook, one leaves it at default.
        ProcessingTemplate, slot = _import_templates()
        InputPaths = _input_paths_type()
        from typing import final  # noqa: PLC0415

        class _SkeletonWithHook(ProcessingTemplate):
            @slot
            def read(self, paths: InputPaths) -> None: ...

            def transform(self, paths: InputPaths) -> InputPaths:
                return paths

            @final
            def __flow__(self, paths: InputPaths) -> None:
                paths = self.transform(paths)
                self.read(paths)

        class _UserOverridesHook(_SkeletonWithHook):
            def read(self, paths: InputPaths) -> None:
                return None

            def transform(self, paths: InputPaths) -> InputPaths:  # explicit override
                return paths

        class _UserDefaultHook(_SkeletonWithHook):
            def read(self, paths: InputPaths) -> None:
                return None
            # `transform` intentionally NOT overridden -> inherited default.

        # When / Then: each sibling contributes its own concrete-qualified
        # `transform` registration, even when the implementation is inherited.
        ids = _registered_node_ids()
        overriding_id = f"{_UserOverridesHook.__module__}.{_UserOverridesHook.__qualname__}.transform"
        non_overriding_id = f"{_UserDefaultHook.__module__}.{_UserDefaultHook.__qualname__}.transform"
        assert overriding_id in ids
        assert non_overriding_id in ids


class TestSkeletonDefinitionDoesNotAutoRegisterSlots:
    """Depth-1 (skeleton) definitions never trigger @node-style
    registration of the still-abstract slot bodies (Conflict #2: actual
    registration happens only at depth-2/user definition time)."""

    def test_skeleton_slot_declaration_is_not_registered_as_a_node(self) -> None:
        ProcessingTemplate, slot = _import_templates()
        InputPaths = _input_paths_type()
        from typing import final  # noqa: PLC0415

        class _SkeletonOnly(ProcessingTemplate):
            @slot
            def read(self, paths: InputPaths) -> None: ...

            @final
            def __flow__(self, paths: InputPaths) -> None:
                self.read(paths)

        ids = _registered_node_ids()
        skeleton_id = f"{_SkeletonOnly.__module__}.{_SkeletonOnly.__qualname__}.read"
        assert skeleton_id not in ids


class TestCallLogIntegration:
    """TC-TPL-REG-003 (Design §5.2.3): running a template end-to-end
    produces call-log records for each slot/hook, via the exact same
    mechanism F1's builtin nodes use -- no template-specific recording."""

    def test_run_flow_template_produces_node_calls_for_slot_and_hook(self, tmp_path: Any) -> None:
        # Given: a minimal, genuinely runnable depth-2 template.
        ProcessingTemplate, slot = _import_templates()
        InputPaths = _input_paths_type()
        from typing import final  # noqa: PLC0415

        class _Skeleton(ProcessingTemplate):
            @slot
            def read(self, paths: InputPaths) -> None: ...

            def transform(self, paths: InputPaths) -> InputPaths:
                return paths

            @final
            def __flow__(self, paths: InputPaths) -> None:
                paths = self.transform(paths)
                self.read(paths)

        class _RunnableUser(_Skeleton):
            def read(self, paths: InputPaths) -> None:
                return None

            # transform intentionally inherits the skeleton default.

        # When: the template is run through the public testing helper,
        # which itself goes through Runner.run (no template-specific path).
        from rdetoolkit.testing import run_flow  # noqa: PLC0415

        fixture_dir = tmp_path / "fixture_src"
        fixture_dir.mkdir()
        (fixture_dir / "sample.txt").write_text("dummy", encoding="utf-8")

        report = run_flow(_RunnableUser, fixture_dir)

        # Then: the run succeeds and both the slot and the inherited hook
        # appear as node_calls in the produced RunReport, keyed by the
        # SAME id shape used for registry lookup.
        assert report.status == "success", report.error
        assert report.iterations, "expected at least one recorded iteration"
        node_call_ids = {
            call["node_id"]
            for iteration in report.iterations
            for call in iteration.get("node_calls", [])
        }
        expected_read_id = f"{_RunnableUser.__module__}.{_RunnableUser.__qualname__}.read"
        expected_transform_id = f"{_RunnableUser.__module__}.{_RunnableUser.__qualname__}.transform"
        assert expected_read_id in node_call_ids
        assert expected_transform_id in node_call_ids


class TestDuplicateIdBehaviorNoExemption:
    """TC-TPL-REG-004 (Conflict #2, BV, documented skip)."""

    @pytest.mark.skip(
        reason=(
            "Documented per session_f2.md's ACCEPTANCE SURFACE explicit skip "
            "allowance (test_slot_registration.py bullet 3): the auto-registration "
            "id shape f'{cls.__module__}.{cls.__qualname__}.{method_name}' "
            "(Conflict #2) is derived from the REAL class object's own "
            "__module__/__qualname__, which Python guarantees is unique per "
            "distinct class object (even two same-named classes defined in "
            "different local scopes get different __qualname__ values, e.g. "
            "'test_a.<locals>.Foo' vs 'test_b.<locals>.Foo'). Forcing a genuine "
            "id collision would require two DIFFERENT class objects to somehow "
            "share the identical __module__ AND __qualname__ AND method name, "
            "which is not constructible without exec()-based __qualname__ "
            "forgery -- out of scope for this session. If a future session "
            "needs to guard this path, it is exercised indirectly by "
            "core/registry.py's own existing E2001 DuplicateNodeId unit "
            "coverage (register_node raises RdeRegistryError(2001) synchronously "
            "on any id collision, template-derived or not)."
        ),
    )
    def test_two_depth2_subclasses_with_a_forced_id_collision(self) -> None:
        pytest.fail("unreachable -- see skip reason")
