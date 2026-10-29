"""K4-F7: the CLI's lazy ``workflows`` proxy stays patchable under pytest 9.2.

pytest 9.2.0 (#10644) undoes ``monkeypatch.setattr`` by consulting
``target.__dict__``; a proxy whose names resolve through ``__getattr__`` made
the undo call ``delattr`` on the proxy, which raised, so the stub installed by
``tests/cmd/test_run.py::stub_workflow_run`` leaked into 55 later tests on CI.

| ID | Kind | Scenario | Expected |
|----|------|----------|----------|
| TC-K4F7-EP-001 | EP | ``vars(cli.workflows)`` | the real module's namespace (``run`` present, same object) |
| TC-K4F7-EP-002 | EP | monkeypatch ``run`` through the proxy, then undo | stub visible on both during; original restored after |
| TC-K4F7-BV-001 | BV | proxy private state | ``_module_name`` still readable, forwarding unchanged |
"""

from __future__ import annotations

import pytest

import rdetoolkit.cli as cli_module
import rdetoolkit.workflows as workflows_module


def test_proxy_namespace_is_the_module_namespace__tc_k4f7_ep_001() -> None:
    """TC-K4F7-EP-001: ``vars()`` of the proxy is the module's namespace."""
    namespace = vars(cli_module.workflows)
    assert namespace["run"] is workflows_module.run
    assert namespace is vars(workflows_module)


def test_monkeypatch_through_the_proxy_is_undone__tc_k4f7_ep_002() -> None:
    """TC-K4F7-EP-002: a stub set through the proxy is removed when the patch is undone."""
    original = workflows_module.run

    def _stub(**_: object) -> str:
        return "stub"

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(cli_module.workflows, "run", _stub)
        assert cli_module.workflows.run is _stub
        assert workflows_module.run is _stub

    assert workflows_module.run is original
    assert cli_module.workflows.run is original


def test_proxy_private_state_still_works__tc_k4f7_bv_001() -> None:
    """TC-K4F7-BV-001: the proxy's own fields and forwarding are unchanged."""
    proxy = cli_module.workflows
    assert proxy._module_name == "rdetoolkit.workflows"  # noqa: SLF001
    assert repr(proxy) == "<LazyModuleProxy rdetoolkit.workflows>"
    assert proxy.run is workflows_module.run
