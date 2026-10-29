"""Tests for ``rdetoolkit.templates.ProcessingTemplate`` + ``@slot``
(Session F2, TC-TPL-BASE-*).

Written before implementation (TDD Red phase). Target: make all tests pass
in codex-worker Green phase. Authority: local/develop/v2/tasks/session_f2.md
Conflicts #2, #5, #7; Known Traps #3, #4; local/develop/v2/Design.md v2.1
§5.2.1-5.2.2.

Binding API-shape pins asserted by this file (precision standard):
- ``from rdetoolkit.templates import ProcessingTemplate, slot``.
- Depth 1 ("skeleton"): ``ProcessingTemplate in cls.__bases__`` -- exempt
  from E2101/E2105; declares ``@slot`` methods and ``@final def
  __flow__``. Importing a skeleton with unimplemented slots must NOT raise.
- Depth 2 ("user class"): ``cls.__bases__[0]`` is itself a depth-1
  skeleton -- full E2101/E2102/E2103/E2105 validation applies, enforced at
  *class-definition* (import) time via ``__init_subclass__``.
- Depth 3+: ``E2104 TemplateDeepInheritance``, raised immediately.
- All five violations raise ``rdetoolkit.errors.RdeRegistryError`` with
  ``.code`` set to the matching int (2101..2105, per ``ERROR_CATALOG``) and
  ``.message`` containing BOTH the catalog's ``message_template``-formatted
  text AND ``ERROR_CATALOG[code].remediation`` verbatim (Conflict #7's
  ``_raise_run_interrupted``-style embedding ruling, not
  ``_duplicate_node_error``'s bare shape).
- A depth-2 slot method is directly callable as a plain bound method, with
  no active Runner/CallLogRecorder required (Design §5.2.2 point 3 / §13.2
  level 1).
- W1101 ``TemplateSelfStateUsage`` is deliberately NOT exercised here: it is
  an advisory-only, lint-time-only check (Design §5.2.2 point 3), not an
  import-time ``__init_subclass__`` error -- its tests live in
  ``tests/v2/cli/test_cli_nodes.py`` against real, file-backed fixtures
  under ``tests/v2/templates/fixtures/`` (``inspect.getsource`` cannot
  introspect dynamically-built classes, Known Trap #5).

Trap avoidance (Known Trap #4): ``rdetoolkit.templates`` does not exist yet
in the Red phase, and each violation is detected at *class-definition*
time. All imports and all violating ``class`` statements are therefore
local to each test function body -- never at module scope -- so failures
surface as per-test ``ImportError``/``AttributeError``/``RdeRegistryError``
mismatches, never a whole-file collection error.
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


def _registry_error_type() -> type[Exception]:
    from rdetoolkit.errors import RdeRegistryError  # noqa: PLC0415

    return RdeRegistryError


def _catalog() -> dict[int, Any]:
    from rdetoolkit.errors import ERROR_CATALOG  # noqa: PLC0415

    return ERROR_CATALOG


class TestSkeletonDefinitionExemptFromUserLevelChecks:
    """Depth-1 (skeleton) declarations are exempt from E2101/E2105 --
    unimplemented slots are the whole point at this level."""

    def test_skeleton_with_unimplemented_slots_and_final_flow_imports_cleanly(self) -> None:
        # Given: Design §5.2.1's skeleton shape -- required @slot methods
        # left abstract (body `...`), plus a @final __flow__.
        ProcessingTemplate, slot = _import_templates()
        InputPaths = _input_paths_type()
        from typing import final  # noqa: PLC0415

        # When: the skeleton class body is evaluated (import-time
        # equivalent for a locally-defined class).
        class _Skeleton(ProcessingTemplate):
            @slot
            def read(self, paths: InputPaths) -> None: ...

            @slot
            def extract_meta(self, paths: InputPaths) -> None: ...

            @final
            def __flow__(self, paths: InputPaths) -> None:
                self.read(paths)
                self.extract_meta(paths)

        # Then: no exception is raised even though `read`/`extract_meta`
        # are unimplemented -- __init_subclass__ must not apply depth-2
        # (user-class) validation to a depth-1 skeleton (Known Trap #3).
        assert _Skeleton.__name__ == "_Skeleton"


class TestSlotMissingE2101:
    """E2101 TemplateSlotMissing: a required slot must be concretely
    overridden by a depth-2 subclass."""

    def test_depth2_subclass_implementing_all_slots_imports_cleanly(self) -> None:
        # Given: a skeleton with one required slot.
        ProcessingTemplate, slot = _import_templates()
        InputPaths = _input_paths_type()
        from typing import final  # noqa: PLC0415

        class _Skeleton(ProcessingTemplate):
            @slot
            def read(self, paths: InputPaths) -> None: ...

            @final
            def __flow__(self, paths: InputPaths) -> None:
                self.read(paths)

        # When: a depth-2 subclass overrides the required slot.
        class _UserImplementsSlot(_Skeleton):
            def read(self, paths: InputPaths) -> None:
                return None

        # Then: the class is defined without error.
        assert _UserImplementsSlot.__name__ == "_UserImplementsSlot"

    def test_depth2_subclass_missing_required_slot_raises_e2101(self) -> None:
        # Given: a skeleton with one required slot, `read`.
        ProcessingTemplate, slot = _import_templates()
        InputPaths = _input_paths_type()
        RdeRegistryError = _registry_error_type()
        from typing import final  # noqa: PLC0415

        class _Skeleton(ProcessingTemplate):
            @slot
            def read(self, paths: InputPaths) -> None: ...

            @final
            def __flow__(self, paths: InputPaths) -> None:
                self.read(paths)

        # When / Then: a depth-2 subclass that never overrides `read`
        # raises RdeRegistryError(code=2101) at class-definition time.
        with pytest.raises(RdeRegistryError) as excinfo:

            class _UserMissingSlot(_Skeleton):
                """Deliberately does not override `read`."""

        assert excinfo.value.code == 2101
        assert "read" in excinfo.value.message
        assert _catalog()[2101].remediation in excinfo.value.message


class TestSlotSignatureMismatchE2102:
    """E2102 TemplateSlotSignatureMismatch: a shallow (name + annotation)
    comparison against the skeleton's declared slot signature."""

    def test_override_with_matching_names_and_annotations_imports_cleanly(self) -> None:
        ProcessingTemplate, slot = _import_templates()
        InputPaths = _input_paths_type()
        from typing import final  # noqa: PLC0415

        class _Skeleton(ProcessingTemplate):
            @slot
            def read(self, paths: InputPaths) -> None: ...

            @final
            def __flow__(self, paths: InputPaths) -> None:
                self.read(paths)

        class _UserMatchingSignature(_Skeleton):
            def read(self, paths: InputPaths) -> None:
                return None

        assert _UserMatchingSignature.__name__ == "_UserMatchingSignature"

    def test_override_with_renamed_parameter_raises_e2102(self) -> None:
        # Given: skeleton declares `read(self, paths: InputPaths)`.
        ProcessingTemplate, slot = _import_templates()
        InputPaths = _input_paths_type()
        RdeRegistryError = _registry_error_type()
        from typing import final  # noqa: PLC0415

        class _Skeleton(ProcessingTemplate):
            @slot
            def read(self, paths: InputPaths) -> None: ...

            @final
            def __flow__(self, paths: InputPaths) -> None:
                self.read(paths)

        # When / Then: overriding with a renamed parameter (same type,
        # different name) raises RdeRegistryError(code=2102).
        with pytest.raises(RdeRegistryError) as excinfo:

            class _UserRenamedParam(_Skeleton):
                def read(self, p: InputPaths) -> None:  # noqa: ANN001 - deliberate rename
                    return None

        assert excinfo.value.code == 2102
        assert "read" in excinfo.value.message
        assert _catalog()[2102].remediation in excinfo.value.message

    def test_override_with_changed_annotation_raises_e2102(self) -> None:
        # Given: skeleton declares `read(self, paths: InputPaths)`.
        ProcessingTemplate, slot = _import_templates()
        InputPaths = _input_paths_type()
        RdeRegistryError = _registry_error_type()
        from typing import final  # noqa: PLC0415

        class _Skeleton(ProcessingTemplate):
            @slot
            def read(self, paths: InputPaths) -> None: ...

            @final
            def __flow__(self, paths: InputPaths) -> None:
                self.read(paths)

        # When / Then: overriding with the same parameter name but a
        # different (unrelated) annotation raises RdeRegistryError(code=2102).
        with pytest.raises(RdeRegistryError) as excinfo:

            class _UserChangedAnnotation(_Skeleton):
                def read(self, paths: int) -> None:  # deliberate annotation change
                    return None

        assert excinfo.value.code == 2102
        assert "read" in excinfo.value.message
        assert _catalog()[2102].remediation in excinfo.value.message


class TestFinalOverrideE2103:
    """E2103 TemplateFinalOverride: a depth-2 subclass must not redefine
    the skeleton's ``@final def __flow__``."""

    def test_depth2_subclass_not_touching_flow_imports_cleanly(self) -> None:
        ProcessingTemplate, slot = _import_templates()
        InputPaths = _input_paths_type()
        from typing import final  # noqa: PLC0415

        class _Skeleton(ProcessingTemplate):
            @slot
            def read(self, paths: InputPaths) -> None: ...

            @final
            def __flow__(self, paths: InputPaths) -> None:
                self.read(paths)

        class _UserNoFlowOverride(_Skeleton):
            def read(self, paths: InputPaths) -> None:
                return None

        assert _UserNoFlowOverride.__name__ == "_UserNoFlowOverride"

    def test_depth2_subclass_redefining_flow_raises_e2103(self) -> None:
        # Given: skeleton owns `__flow__`.
        ProcessingTemplate, slot = _import_templates()
        InputPaths = _input_paths_type()
        RdeRegistryError = _registry_error_type()
        from typing import final  # noqa: PLC0415

        class _Skeleton(ProcessingTemplate):
            @slot
            def read(self, paths: InputPaths) -> None: ...

            @final
            def __flow__(self, paths: InputPaths) -> None:
                self.read(paths)

        # When / Then: a depth-2 subclass redefining `__flow__` raises
        # RdeRegistryError(code=2103) at class-definition time.
        with pytest.raises(RdeRegistryError) as excinfo:

            class _UserOverridesFlow(_Skeleton):
                def read(self, paths: InputPaths) -> None:
                    return None

                def __flow__(self, paths: InputPaths) -> None:  # deliberate re-definition
                    self.read(paths)

        assert excinfo.value.code == 2103
        assert "__flow__" in excinfo.value.message
        assert _catalog()[2103].remediation in excinfo.value.message


class TestDeepInheritanceE2104:
    """E2104 TemplateDeepInheritance: exactly one level of user
    inheritance is allowed (skeleton -> user); a second level fails."""

    def test_exactly_one_level_of_user_inheritance_imports_cleanly(self) -> None:
        ProcessingTemplate, slot = _import_templates()
        InputPaths = _input_paths_type()
        from typing import final  # noqa: PLC0415

        class _Skeleton(ProcessingTemplate):
            @slot
            def read(self, paths: InputPaths) -> None: ...

            @final
            def __flow__(self, paths: InputPaths) -> None:
                self.read(paths)

        class _UserOneLevel(_Skeleton):
            def read(self, paths: InputPaths) -> None:
                return None

        assert _UserOneLevel.__name__ == "_UserOneLevel"

    def test_second_level_of_user_inheritance_raises_e2104(self) -> None:
        # Given: a valid depth-2 user class.
        ProcessingTemplate, slot = _import_templates()
        InputPaths = _input_paths_type()
        RdeRegistryError = _registry_error_type()
        from typing import final  # noqa: PLC0415

        class _Skeleton(ProcessingTemplate):
            @slot
            def read(self, paths: InputPaths) -> None: ...

            @final
            def __flow__(self, paths: InputPaths) -> None:
                self.read(paths)

        class _UserOneLevel(_Skeleton):
            def read(self, paths: InputPaths) -> None:
                return None

        # When / Then: subclassing the already-concrete user class raises
        # RdeRegistryError(code=2104) immediately, mirroring
        # PhaseF_prompts.md's explicit "2 段継承" wording.
        with pytest.raises(RdeRegistryError) as excinfo:

            class _UserTwoLevels(_UserOneLevel):
                """A second level of user inheritance -- forbidden."""

        assert excinfo.value.code == 2104
        assert "_UserTwoLevels" in excinfo.value.message
        assert _catalog()[2104].remediation in excinfo.value.message


class TestCtorNotDefaultE2105:
    """E2105 TemplateCtorNotDefault: a depth-2 user class must be
    constructible with no arguments (Runner/CLI build it via ``cls()``)."""

    def test_depth2_subclass_without_init_imports_cleanly_and_constructs(self) -> None:
        ProcessingTemplate, slot = _import_templates()
        InputPaths = _input_paths_type()
        from typing import final  # noqa: PLC0415

        class _Skeleton(ProcessingTemplate):
            @slot
            def read(self, paths: InputPaths) -> None: ...

            @final
            def __flow__(self, paths: InputPaths) -> None:
                self.read(paths)

        class _UserNoInit(_Skeleton):
            def read(self, paths: InputPaths) -> None:
                return None

        instance = _UserNoInit()
        assert isinstance(instance, _UserNoInit)

    def test_depth2_subclass_with_only_defaulted_init_args_imports_cleanly_and_constructs(self) -> None:
        ProcessingTemplate, slot = _import_templates()
        InputPaths = _input_paths_type()
        from typing import final  # noqa: PLC0415

        class _Skeleton(ProcessingTemplate):
            @slot
            def read(self, paths: InputPaths) -> None: ...

            @final
            def __flow__(self, paths: InputPaths) -> None:
                self.read(paths)

        class _UserDefaultedInit(_Skeleton):
            def __init__(self, optional_value: int = 3) -> None:
                self.optional_value = optional_value

            def read(self, paths: InputPaths) -> None:
                return None

        instance = _UserDefaultedInit()
        assert instance.optional_value == 3

    def test_depth2_subclass_requiring_a_positional_init_arg_raises_e2105(self) -> None:
        # Given: skeleton is otherwise valid.
        ProcessingTemplate, slot = _import_templates()
        InputPaths = _input_paths_type()
        RdeRegistryError = _registry_error_type()
        from typing import final  # noqa: PLC0415

        class _Skeleton(ProcessingTemplate):
            @slot
            def read(self, paths: InputPaths) -> None: ...

            @final
            def __flow__(self, paths: InputPaths) -> None:
                self.read(paths)

        # When / Then: a depth-2 subclass whose __init__ requires a
        # positional argument raises RdeRegistryError(code=2105) at
        # class-definition time -- not later when `cls()` happens to be
        # called by the Runner/CLI.
        with pytest.raises(RdeRegistryError) as excinfo:

            class _UserRequiredInitArg(_Skeleton):
                def __init__(self, required_value: int) -> None:
                    self.required_value = required_value

                def read(self, paths: InputPaths) -> None:
                    return None

        assert excinfo.value.code == 2105
        assert "_UserRequiredInitArg" in excinfo.value.message
        assert _catalog()[2105].remediation in excinfo.value.message


class TestSlotDirectCallability:
    """Design §5.2.2 point 3 / §13.2 level 1: a depth-2 slot method is
    "事実上ただの関数" -- callable directly, with no active
    Runner/CallLogRecorder."""

    def test_depth2_slot_method_is_directly_callable_without_active_run(self) -> None:
        # Given: a depth-2 instance built with no Runner involvement at all.
        ProcessingTemplate, slot = _import_templates()
        InputPaths = _input_paths_type()
        from typing import final  # noqa: PLC0415

        class _Skeleton(ProcessingTemplate):
            @slot
            def read(self, paths: InputPaths) -> str: ...

            @final
            def __flow__(self, paths: InputPaths) -> None:
                self.read(paths)

        class _User(_Skeleton):
            def read(self, paths: InputPaths) -> str:
                return "read-result"

        instance = _User()

        # When: the slot is called directly, pytest-style, exactly as
        # ``RigakuRasProcessing().read(fake_paths)`` in Design §5.2.2.
        result = instance.read(object())

        # Then: it behaves as a plain method -- no recorder, no Runner.
        assert result == "read-result"


class TestMultipleSimultaneousViolationsRaiseExactlyOne:
    """Robustness guard: a class that violates more than one constraint at
    once must still raise a single, well-formed RdeRegistryError (never an
    uncaught secondary exception or a crash during validation)."""

    def test_missing_slot_and_flow_override_together_raise_one_registry_error(self) -> None:
        # Given: a subclass that BOTH omits the required slot AND
        # redefines __flow__ -- two independent violations at once.
        ProcessingTemplate, slot = _import_templates()
        InputPaths = _input_paths_type()
        RdeRegistryError = _registry_error_type()
        from typing import final  # noqa: PLC0415

        class _Skeleton(ProcessingTemplate):
            @slot
            def read(self, paths: InputPaths) -> None: ...

            @final
            def __flow__(self, paths: InputPaths) -> None:
                self.read(paths)

        with pytest.raises(RdeRegistryError) as excinfo:

            class _DoublyBroken(_Skeleton):
                def __flow__(self, paths: InputPaths) -> None:  # noqa: ARG002
                    return None

        # Then: exactly one RdeRegistryError surfaces, whose code is one of
        # the two applicable violations (implementation's own check-order
        # choice) -- never both, and never an unrelated exception type.
        assert excinfo.value.code in {2101, 2103}
