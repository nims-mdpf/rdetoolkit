"""Tests for issue #640 (RDE-004): conflicting flow ids are rejected.

``register_flow`` used ``dict.setdefault`` for both the spec map and the
callable map, so a second, different flow declaring an already-used id was
silently dropped while its decorated function stayed directly callable. The
contract now mirrors ``register_node``:

- first registration of an id succeeds;
- re-registering the *same* callable object with an equal spec is a no-op;
- any other callable under a used id raises ``RdeRegistryError`` code 2007
  (``DuplicateFlowId``) at decoration time, naming the id and both source
  locations, and leaves the registry untouched (spec and callable maps never
  disagree);
- a source location is not proof of identity: ``importlib.reload`` makes a
  new function object and therefore raises as well.

EP Table:
| API                     | Partition                                         | Expected                                         | Test ID         |
|-------------------------|---------------------------------------------------|--------------------------------------------------|-----------------|
| register_flow           | first registration                                | registered; spec and callable both retrievable   | TC-640-EP-001   |
| register_flow           | same object + equal spec again                    | idempotent no-op, still one entry                | TC-640-EP-002   |
| flow decorator          | two explicit ids in one module                    | RdeRegistryError 2007 at second decoration       | TC-640-EP-003   |
| flow decorator          | same explicit id across two modules               | importing the second module raises 2007          | TC-640-EP-004   |
| flow decorator          | default-id collision (factory ``<locals>`` flow)  | RdeRegistryError 2007                            | TC-640-EP-005   |
| register_flow           | same object, different spec                       | RdeRegistryError 2007                            | TC-640-EP-006   |
| register_flow           | different object, identical spec                  | RdeRegistryError 2007 (no source-location proof) | TC-640-EP-007   |
| importlib.reload        | module defining a flow is reloaded                | RdeRegistryError 2007; original pair retained    | TC-640-EP-008   |
| after failed duplicate  | registry lookup / list / function map             | first flow still owns the id                     | TC-640-EP-009   |
| after failed duplicate  | direct invocation of the surviving flow           | plain call semantics, body exceptions unchanged  | TC-640-EP-010   |
| after failed duplicate  | CLI ``flows show`` / ``flows list``               | reports the first flow                           | TC-640-EP-011   |
| CLI ``--module``        | module whose import hits a duplicate flow id      | exit 3, message names DuplicateFlowId            | TC-640-EP-012   |
| CLI ``run <ref>``       | flow module whose import hits a duplicate flow id | exit 3, message names DuplicateFlowId            | TC-640-EP-015   |
| error payload           | message / detail                                  | id + both source locations, catalog remediation  | TC-640-EP-013   |
| node registry           | duplicate node id                                 | still RdeRegistryError 2001                      | TC-640-EP-014   |
| suite registry guard    | flow defined locally / by executed snippet        | dropped after the test                           | TC-640-GUARD-EP-001 |
| suite registry guard    | flow bound in an imported module                  | kept (matches the import cache)                  | TC-640-GUARD-EP-002 |

BV Table:
| API            | Boundary                                    | Expected                                   | Test ID       |
|----------------|---------------------------------------------|--------------------------------------------|---------------|
| flow decorator | explicit id equal to another flow's default | RdeRegistryError 2007                      | TC-640-BV-001 |
| flow decorator | ids differing only by one character         | both register                              | TC-640-BV-002 |
| flow decorator | double decoration ``flow(flow(fn))``        | RdeRegistryError 2007 (different wrapper)  | TC-640-BV-003 |
"""

from __future__ import annotations

import importlib
import json
import sys
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from rdetoolkit.cli.app import app
from rdetoolkit.core import registry
from rdetoolkit.core.flow import flow
from rdetoolkit.core.node import node
from rdetoolkit.core.registry import FlowSpec, get_flow, get_flow_function, list_flows, register_flow
from rdetoolkit.errors import ERROR_CATALOG, RdeRegistryError

_DUPLICATE_FLOW_CODE = 2007


@pytest.fixture(autouse=True)
def _isolated_flow_registry() -> Iterator[None]:
    """Drop every flow and node a case registers, so ids can repeat across runs."""
    saved = {name: dict(getattr(registry, name)) for name in ("_flow_specs", "_flow_functions", "_node_specs", "_node_wrappers", "_node_functions")}
    yield
    for name, snapshot in saved.items():
        current = getattr(registry, name)
        current.clear()
        current.update(snapshot)


@pytest.fixture
def unique_id() -> str:
    return f"tests.v2.core.issue640.{uuid.uuid4().hex}"


@pytest.fixture
def module_dir(tmp_path: Path) -> Iterator[Path]:
    """A sys.path entry for throwaway project modules, removed afterwards."""
    before = set(sys.modules)
    sys.path.insert(0, str(tmp_path))
    yield tmp_path
    sys.path.remove(str(tmp_path))
    for name in set(sys.modules) - before:
        del sys.modules[name]


def _write_module(directory: Path, name: str, flow_id: str, body: str = "return 'ok'") -> None:
    source = f"from rdetoolkit.core.flow import flow\n\n\n@flow(id={flow_id!r})\ndef entry() -> str:\n    {body}\n"
    (directory / f"{name}.py").write_text(source, encoding="utf-8")


def _assert_duplicate_flow(exc_info: pytest.ExceptionInfo[RdeRegistryError], flow_id: str) -> None:
    assert exc_info.type is RdeRegistryError
    assert exc_info.value.code == _DUPLICATE_FLOW_CODE
    assert exc_info.value.name == "DuplicateFlowId"
    assert flow_id in exc_info.value.message


def _flow_factory(flow_id: str | None = None) -> Callable[..., Any]:
    """Build a fresh local flow; repeated calls share the default qualname id."""

    def produced() -> str:
        return "produced"

    return flow(id=flow_id)(produced) if flow_id is not None else flow(produced)


class TestFirstAndIdempotentRegistration:
    """TC-640-EP-001/002."""

    def test_first_registration_succeeds__tc_640_ep_001(self, unique_id: str) -> None:
        # Given / When: a single flow with a fresh id
        @flow(id=unique_id)
        def first() -> str:
            return "first"

        # Then: spec and callable are both registered under the id
        assert get_flow(unique_id) is first.__flow_spec__
        assert get_flow_function(unique_id) is first

    def test_same_object_and_spec_is_idempotent__tc_640_ep_002(self, unique_id: str) -> None:
        # Given: a registered flow
        @flow(id=unique_id)
        def first() -> str:
            return "first"

        # When: the exact same object and spec are registered again
        register_flow(first.__flow_spec__, first)

        # Then: nothing changes and the id appears once
        assert get_flow_function(unique_id) is first
        assert get_flow(unique_id) is first.__flow_spec__
        assert [spec.id for spec in list_flows()].count(unique_id) == 1


class TestDuplicateRejected:
    """TC-640-EP-003/004/005/006/007, BV-001/003."""

    def test_two_explicit_ids_in_one_module_raise__tc_640_ep_003(self, unique_id: str) -> None:
        # Given: a flow owning the id
        @flow(id=unique_id)
        def first() -> str:
            return "first"

        # When / Then: a second, different flow with the same id fails at decoration
        with pytest.raises(RdeRegistryError) as exc_info:

            @flow(id=unique_id)
            def second() -> str:
                return "second"

        _assert_duplicate_flow(exc_info, unique_id)

    def test_same_id_across_two_modules_raises_on_second_import__tc_640_ep_004(self, module_dir: Path, unique_id: str) -> None:
        # Given: two project modules declaring the same explicit flow id
        stem = f"issue640_{uuid.uuid4().hex}"
        _write_module(module_dir, f"{stem}_a", unique_id)
        _write_module(module_dir, f"{stem}_b", unique_id)
        module_a = importlib.import_module(f"{stem}_a")

        # When / Then: importing the second module raises the duplicate error
        with pytest.raises(RdeRegistryError) as exc_info:
            importlib.import_module(f"{stem}_b")

        _assert_duplicate_flow(exc_info, unique_id)
        assert f"{stem}_a:entry" in exc_info.value.message
        assert f"{stem}_b:entry" in exc_info.value.message
        assert get_flow_function(unique_id) is module_a.entry
        assert f"{stem}_b" not in sys.modules

    def test_default_qualname_collision_raises__tc_640_ep_005(self) -> None:
        # Given: a factory whose local flow gets the same default id every call
        produced = _flow_factory()
        flow_id = produced.__flow_spec__.id
        assert "<locals>" in flow_id

        # When / Then: a second call collides on the default qualified name
        with pytest.raises(RdeRegistryError) as exc_info:
            _flow_factory()

        _assert_duplicate_flow(exc_info, flow_id)
        assert get_flow_function(flow_id) is produced

    def test_same_object_with_different_spec_raises__tc_640_ep_006(self, unique_id: str) -> None:
        # Given: a registered flow
        @flow(id=unique_id)
        def first() -> str:
            return "first"

        other_spec = FlowSpec(id=unique_id, name="renamed", source_location="elsewhere:renamed")

        # When / Then: re-registering the same object with a different spec is a conflict
        with pytest.raises(RdeRegistryError) as exc_info:
            register_flow(other_spec, first)

        _assert_duplicate_flow(exc_info, unique_id)
        assert get_flow(unique_id) is first.__flow_spec__

    def test_different_object_with_identical_spec_raises__tc_640_ep_007(self, unique_id: str) -> None:
        # Given: a registered flow
        @flow(id=unique_id)
        def first() -> str:
            return "first"

        # When / Then: an equal spec does not prove identity of a different callable
        def impostor() -> str:
            return "impostor"

        with pytest.raises(RdeRegistryError) as exc_info:
            register_flow(first.__flow_spec__, impostor)

        _assert_duplicate_flow(exc_info, unique_id)
        assert get_flow_function(unique_id) is first

    def test_explicit_id_equal_to_existing_default_raises__tc_640_bv_001(self) -> None:
        # Given: a flow registered under its default qualified-name id
        @flow
        def default_owner() -> str:
            return "default"

        default_id = default_owner.__flow_spec__.id

        # When / Then: another flow explicitly claiming that id collides
        with pytest.raises(RdeRegistryError) as exc_info:

            @flow(id=default_id)
            def claimant() -> str:
                return "claimant"

        _assert_duplicate_flow(exc_info, default_id)

    def test_ids_differing_by_one_character_both_register__tc_640_bv_002(self, unique_id: str) -> None:
        # Given / When: two flows whose ids differ by a single trailing character
        @flow(id=f"{unique_id}a")
        def left() -> str:
            return "left"

        @flow(id=f"{unique_id}b")
        def right() -> str:
            return "right"

        # Then: both own their own id
        assert get_flow_function(f"{unique_id}a") is left
        assert get_flow_function(f"{unique_id}b") is right

    def test_double_decoration_raises__tc_640_bv_003(self) -> None:
        # Given: a decorated flow
        def plain() -> str:
            return "plain"

        decorated = flow(plain)

        # When / Then: decorating the wrapper again creates a different object for the same id
        with pytest.raises(RdeRegistryError) as exc_info:
            flow(decorated)

        _assert_duplicate_flow(exc_info, decorated.__flow_spec__.id)
        assert get_flow_function(decorated.__flow_spec__.id) is decorated


class TestReload:
    """TC-640-EP-008."""

    def test_reload_raises_and_keeps_original_pair__tc_640_ep_008(self, module_dir: Path, unique_id: str) -> None:
        # Given: an imported project module defining a flow
        name = f"issue640_reload_{uuid.uuid4().hex}"
        _write_module(module_dir, name, unique_id)
        module = importlib.import_module(name)
        original = module.entry

        # When / Then: reloading re-executes the decorator with a new object and is rejected
        with pytest.raises(RdeRegistryError) as exc_info:
            importlib.reload(module)

        _assert_duplicate_flow(exc_info, unique_id)
        # Then: no stale or mixed pair -- spec and callable still belong to the original
        assert get_flow_function(unique_id) is original
        assert get_flow(unique_id) is original.__flow_spec__
        assert module.entry is original

    def test_reload_after_registration_removed_succeeds__tc_640_ep_008_isolation(self, module_dir: Path, unique_id: str) -> None:
        # Given: an imported module whose registration a test fixture removed (registry isolation)
        name = f"issue640_reload_ok_{uuid.uuid4().hex}"
        _write_module(module_dir, name, unique_id)
        module = importlib.import_module(name)
        registry._flow_specs.pop(unique_id)
        registry._flow_functions.pop(unique_id)

        # When: the module is reloaded
        reloaded = importlib.reload(module)

        # Then: the new object owns the id, spec and callable agree
        assert get_flow_function(unique_id) is reloaded.entry
        assert get_flow(unique_id) is reloaded.entry.__flow_spec__


class TestRegistryAfterFailedDuplicate:
    """TC-640-EP-009/010/011/012."""

    def _register_then_fail(self, flow_id: str) -> Callable[..., Any]:
        @flow(id=flow_id)
        def survivor(value: int) -> int:
            if value < 0:
                msg = "negative"
                raise ValueError(msg)
            return value * 2

        with pytest.raises(RdeRegistryError):

            @flow(id=flow_id)
            def loser(value: int) -> int:
                return value

        return survivor

    def test_lookup_maps_agree_on_first_flow__tc_640_ep_009(self, unique_id: str) -> None:
        # Given: a lookup before the failed duplicate
        survivor = self._register_then_fail(unique_id)

        # Then: spec, callable and listing all name the first flow exactly once
        spec = get_flow(unique_id)
        assert spec is survivor.__flow_spec__
        assert spec.name == "survivor"
        assert get_flow_function(unique_id) is survivor
        assert [s.id for s in list_flows()].count(unique_id) == 1
        assert set(registry._flow_specs) == set(registry._flow_functions)

    def test_direct_invocation_is_unchanged__tc_640_ep_010(self, unique_id: str) -> None:
        # Given: the surviving flow after a failed duplicate
        survivor = self._register_then_fail(unique_id)

        # When / Then: it is still a plain call, and body exceptions propagate unwrapped
        assert survivor(3) == 6
        with pytest.raises(ValueError, match="negative") as exc_info:
            survivor(-1)
        assert exc_info.type is ValueError

    def test_cli_describe_and_list_report_first_flow__tc_640_ep_011(self, unique_id: str) -> None:
        # Given: a CLI view before the duplicate attempt
        runner = CliRunner()
        survivor = self._register_then_fail(unique_id)

        # When: the flow is described and listed
        described = runner.invoke(app, ["flows", "show", unique_id, "--json"])
        listed = runner.invoke(app, ["flows", "list", "--json"])

        # Then: the first flow's metadata is reported, once
        assert described.exit_code == 0
        assert json.loads(described.output) == {
            "id": unique_id,
            "name": "survivor",
            "source_location": survivor.__flow_spec__.source_location,
        }
        assert listed.exit_code == 0
        assert [entry["id"] for entry in json.loads(listed.output)].count(unique_id) == 1

    def test_cli_module_with_duplicate_flow_exits_3__tc_640_ep_012(self, module_dir: Path, unique_id: str) -> None:
        # Given: a module already registered and a second module reusing its flow id
        stem = f"issue640_cli_{uuid.uuid4().hex}"
        _write_module(module_dir, f"{stem}_a", unique_id)
        _write_module(module_dir, f"{stem}_b", unique_id)
        importlib.import_module(f"{stem}_a")

        # When: the CLI is asked to import the conflicting module
        result = CliRunner().invoke(app, ["flows", "show", unique_id, "--module", f"{stem}_b"])

        # Then: usage-error exit code and an actionable message
        assert result.exit_code == 3
        assert "DuplicateFlowId" in result.output
        assert unique_id in result.output

    def test_cli_run_ref_with_duplicate_flow_exits_3__tc_640_ep_015(self, module_dir: Path, unique_id: str) -> None:
        # Given: a module already registered and a second module reusing its flow id
        stem = f"issue640_run_{uuid.uuid4().hex}"
        _write_module(module_dir, f"{stem}_a", unique_id)
        _write_module(module_dir, f"{stem}_b", unique_id)
        importlib.import_module(f"{stem}_a")

        # When: ``run <ref>`` resolves a flow in the conflicting module
        result = CliRunner().invoke(app, ["run", f"{stem}_b:entry", "--validate-only"])

        # Then: the Design §9.3 usage-error code, not a traceback
        assert result.exit_code == 3, result.output
        assert not isinstance(result.exception, RdeRegistryError)
        assert "DuplicateFlowId" in result.output
        assert unique_id in result.output


class TestErrorPayload:
    """TC-640-EP-013/014."""

    def test_catalog_entry_and_detail_are_actionable__tc_640_ep_013(self, unique_id: str) -> None:
        # Given: a flow owning the id
        @flow(id=unique_id)
        def first() -> str:
            return "first"

        # When: a different flow claims the id
        with pytest.raises(RdeRegistryError) as exc_info:

            @flow(id=unique_id)
            def second() -> str:
                return "second"

        # Then: the catalog entry exists with remediation, and the error names both locations
        entry = ERROR_CATALOG[_DUPLICATE_FLOW_CODE]
        assert entry.name == "DuplicateFlowId"
        assert entry.retired is False
        assert "@flow(id=" in entry.remediation
        error = exc_info.value
        assert first.__flow_spec__.source_location in error.message
        assert error.message.endswith("second")
        assert error.detail == {
            "flow_id": unique_id,
            "registered_source_location": first.__flow_spec__.source_location,
            "rejected_source_location": f"{__name__}:{self.test_catalog_entry_and_detail_are_actionable__tc_640_ep_013.__qualname__}.<locals>.second",
            "remediation": entry.remediation,
        }
        assert error.to_dict()["code"] == _DUPLICATE_FLOW_CODE

    def test_node_duplicate_still_raises_2001__tc_640_ep_014(self, unique_id: str) -> None:
        # Given: a node owning an id
        @node(id=unique_id)
        def first(value: int) -> int:
            return value

        # When / Then: the node registry keeps its own code
        with pytest.raises(RdeRegistryError) as exc_info:

            @node(id=unique_id)
            def second(value: int) -> int:
                return value

        assert exc_info.value.code == 2001


class TestSuiteRegistryGuard:
    """TC-640-GUARD-EP-001/002: the tests/v2 conftest isolation keeps import-cached flows only."""

    def test_module_bound_flow_is_kept__tc_640_guard_ep_002(self, module_dir: Path, unique_id: str) -> None:
        from tests.v2.conftest import _bound_in_loaded_module

        # Given: a flow bound as an attribute of an imported module
        name = f"issue640_guard_{uuid.uuid4().hex}"
        _write_module(module_dir, name, unique_id)
        module = importlib.import_module(name)

        # When / Then: the guard recognises it as owned by the import cache
        assert _bound_in_loaded_module(module.entry) is True

    def test_local_flow_is_dropped__tc_640_guard_ep_001(self) -> None:
        from tests.v2.conftest import _bound_in_loaded_module

        # Given: a flow defined inside a factory function
        produced = _flow_factory()

        # When / Then: it is not reachable from its module, so the guard drops it
        assert _bound_in_loaded_module(produced) is False

    def test_executed_snippet_flow_is_dropped__tc_640_guard_ep_001_exec(self, unique_id: str) -> None:
        from tests.v2.conftest import _bound_in_loaded_module

        # Given: a flow created by executing a snippet in a module-less namespace
        namespace: dict[str, object] = {}
        exec(  # noqa: S102
            f"from rdetoolkit.core.flow import flow\n@flow(id={unique_id!r})\ndef snippet() -> None:\n    return None\n",
            namespace,
        )

        # When / Then: no loaded module exposes it
        assert _bound_in_loaded_module(namespace["snippet"]) is False

    def test_module_attribute_replaced_is_dropped__tc_640_guard_ep_001_shadowed(
        self,
        module_dir: Path,
        unique_id: str,
    ) -> None:
        from tests.v2.conftest import _bound_in_loaded_module

        # Given: an imported module whose attribute no longer is the registered flow
        name = f"issue640_guard_shadow_{uuid.uuid4().hex}"
        _write_module(module_dir, name, unique_id)
        module = importlib.import_module(name)
        original = module.entry
        module.entry = lambda: "shadow"

        # When / Then: identity, not the name, decides
        assert _bound_in_loaded_module(original) is False
