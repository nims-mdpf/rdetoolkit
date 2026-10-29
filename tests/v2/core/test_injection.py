"""Tests for flow-boundary type-based DI (Session C2, C2.1).

Written before implementation (TDD Red phase).
Target: make all tests pass in codex-worker Green phase.

Design authority: local/develop/v2/Design.md v2.1 §4.3
Session authority: local/develop/v2/tasks/session_c2.md

Binding rulings (do not re-litigate — see session_c2.md):
- ``resolve_flow_kwargs(flow_fn, run_context) -> dict[str, Any]`` lives in
  ``rdetoolkit.core.injection``. Resolution is TYPE-ANNOTATION-ONLY (R1); a
  parameter's *name* never determines injection.
- Strict 3-step priority per parameter: (1) annotated with one of the 5
  reserved types -> inject from ``run_context`` by type match, even if the
  corresponding slot is ``None`` (type-match alone decides — do NOT reuse
  ``RunContext.reserved_values()``, which drops ``None`` entries); (2) not
  reserved-type-annotated but has a default -> omit from the dict, let
  Python apply the default; (3) neither -> raise
  ``RdeRegistryError(code=2003, ...)`` before any flow code runs.
- Duplicate reserved-type annotations across parameters -> raise
  ``RdeRegistryError(code=2006, ...)``.
- Both E2003/E2006 messages embed the catalog remediation text
  substantively in the message string itself (Conflict #2).
- No DI inside ``@node`` — ``core/node.py`` must not import
  ``core.injection`` (regression guard, TC-EP-509).

EP Table:
| API                    | Partition                                    | Rationale                    | Expected                                            | Test ID    |
|------------------------|-----------------------------------------------|-------------------------------|------------------------------------------------------|------------|
| resolve_flow_kwargs    | recommended names (paths/out/config/...)      | DI case 1 (kickoff C-3-3)     | all 5 injected with matching values                  | TC-EP-501  |
| resolve_flow_kwargs    | renamed param (input_paths: InputPaths)       | DI case 2 — R1 core           | injected under "input_paths", not "paths"             | TC-EP-502  |
| resolve_flow_kwargs    | mixed with defaulted non-reserved param       | DI case 3                     | "paths" present, "threshold" absent                    | TC-EP-503  |
| resolve_flow_kwargs    | unresolved param (no reserved type, no default)| DI case 4 — E2003             | RdeRegistryError code 2003, remediation-ish message   | TC-EP-504  |
| resolve_flow_kwargs    | duplicate reserved type across two params      | DI case 5 — E2006             | RdeRegistryError code 2006, both param names in message| TC-EP-505 |
| resolve_flow_kwargs    | RunContext slot is None, type annotation match | "DI 解決アルゴリズムの確定仕様" core | no exception; None injected as-is                | TC-EP-506  |
| resolve_flow_kwargs    | no-parameter flow                              | minimal form                  | returns {}                                            | TC-EP-507  |
| resolve_flow_kwargs    | name is "paths" but type is unrelated (str), no default | R1 counter-example  | NOT injected by name; E2003 (name alone never resolves)| TC-EP-508 |
| core/node.py            | source inspection                              | C-2 prohibition                | does not import core.injection                       | TC-EP-509  |

BV Table:
| API                                    | Boundary                                | Rationale                | Expected                                          | Test ID    |
|-----------------------------------------|-------------------------------------------|----------------------------|-----------------------------------------------------|------------|
| resolve_flow_kwargs                     | E2003 message content                     | remediation embed (Conflict #2) | message contains a reserved type name or "default value" | TC-BV-501 |
| resolve_flow_kwargs                     | E2006 message content                     | remediation embed (Conflict #2) | message contains "once" (catalog remediation core word)   | TC-BV-502 |
| resolve_flow_kwargs                     | *args/**kwargs signature                  | variadic handling         | skipped, no error, no injection                     | TC-BV-503  |
| resolve_flow_kwargs                     | keyword-only reserved-type param          | signature shape coverage  | injected same as positional                          | TC-BV-504  |
| resolve_flow_kwargs x testing kit builders | real RunContext built from builders,   | Conflict #1 e2e evidence  | flow(**resolve_flow_kwargs(flow, ctx)) actually runs | TC-BV-505  |
|                                          | renamed param flow                        |                            |                                                       | (integration) |
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.core.context import RunContext
from rdetoolkit.errors import RdeRegistryError
from rdetoolkit.types import InputPaths, InvoiceData, IterationInfo, OutputContext, RdeConfig

# Target import — fails until implementation exists (expected in Red phase):
from rdetoolkit.core.injection import resolve_flow_kwargs


def _make_input_paths(tmp_path: Path) -> InputPaths:
    inputdata = tmp_path / "inputdata"
    invoice = tmp_path / "invoice"
    tasksupport = tmp_path / "tasksupport"
    for d in (inputdata, invoice, tasksupport):
        d.mkdir(parents=True, exist_ok=True)
    return InputPaths(inputdata=inputdata, invoice=invoice, tasksupport=tasksupport)


def _make_output_context(tmp_path: Path) -> OutputContext:
    from rdetoolkit.domain.output import create_output_context  # noqa: PLC0415

    return create_output_context(tmp_path / "out", create=True)


def _full_run_context(tmp_path: Path) -> RunContext:
    return RunContext(
        paths=_make_input_paths(tmp_path),
        out=_make_output_context(tmp_path),
        config=RdeConfig(),
        invoice=InvoiceData(),
        iteration=IterationInfo(index=0, total=1, mode="invoice"),
    )


class TestResolveFlowKwargsHappyPath:
    """TC-EP-501/502/503/506/507: successful resolution across shapes."""

    def test_recommended_names_all_five_injected(self, tmp_path: Path) -> None:
        """TC-EP-501: all 5 reserved-type params, recommended names, all injected."""
        ctx = _full_run_context(tmp_path)

        def flow(
            paths: InputPaths,
            out: OutputContext,
            config: RdeConfig,
            invoice: InvoiceData,
            iteration: IterationInfo,
        ) -> None:
            ...

        kwargs = resolve_flow_kwargs(flow, ctx)

        assert kwargs["paths"] is ctx.paths
        assert kwargs["out"] is ctx.out
        assert kwargs["config"] is ctx.config
        assert kwargs["invoice"] is ctx.invoice
        assert kwargs["iteration"] is ctx.iteration
        assert set(kwargs) == {"paths", "out", "config", "invoice", "iteration"}

    def test_renamed_param_injected_under_actual_name(self, tmp_path: Path) -> None:
        """TC-EP-502: renamed param (input_paths: InputPaths) injects under its own name."""
        ctx = _full_run_context(tmp_path)

        def flow(input_paths: InputPaths) -> None:
            ...

        kwargs = resolve_flow_kwargs(flow, ctx)

        assert "input_paths" in kwargs
        assert kwargs["input_paths"] is ctx.paths
        assert "paths" not in kwargs

    def test_defaulted_non_reserved_param_is_omitted(self, tmp_path: Path) -> None:
        """TC-EP-503: reserved-type param injected; defaulted plain param omitted."""
        ctx = _full_run_context(tmp_path)

        def flow(paths: InputPaths, threshold: float = 0.3) -> None:
            ...

        kwargs = resolve_flow_kwargs(flow, ctx)

        assert kwargs["paths"] is ctx.paths
        assert "threshold" not in kwargs

    def test_none_slot_injected_as_none_without_error(self, tmp_path: Path) -> None:
        """TC-EP-506: type match alone decides injection, even for a None RunContext slot."""
        ctx = RunContext(paths=_make_input_paths(tmp_path), out=None)

        def flow(paths: InputPaths, out: OutputContext) -> None:
            ...

        kwargs = resolve_flow_kwargs(flow, ctx)

        assert kwargs["paths"] is ctx.paths
        assert "out" in kwargs
        assert kwargs["out"] is None

    def test_no_parameter_flow_returns_empty_dict(self, tmp_path: Path) -> None:
        """TC-EP-507: a flow with no parameters resolves to an empty dict."""
        ctx = _full_run_context(tmp_path)

        def flow() -> None:
            ...

        assert resolve_flow_kwargs(flow, ctx) == {}


class TestResolveFlowKwargsErrorCases:
    """TC-EP-504/505/508, TC-BV-501/502: E2003/E2006 raising and message content."""

    def test_unresolved_param_raises_e2003(self, tmp_path: Path) -> None:
        """TC-EP-504: a non-reserved, non-defaulted param raises E2003."""
        ctx = _full_run_context(tmp_path)

        def flow(mystery: str) -> None:
            ...

        with pytest.raises(RdeRegistryError) as exc_info:
            resolve_flow_kwargs(flow, ctx)

        assert exc_info.value.code == 2003

    def test_duplicate_reserved_type_raises_e2006_with_both_names(self, tmp_path: Path) -> None:
        """TC-EP-505: two params annotated with the same reserved type raise E2006."""
        ctx = _full_run_context(tmp_path)

        def flow(a: InputPaths, b: InputPaths) -> None:
            ...

        with pytest.raises(RdeRegistryError) as exc_info:
            resolve_flow_kwargs(flow, ctx)

        assert exc_info.value.code == 2006
        message = str(exc_info.value)
        assert "a" in message
        assert "b" in message

    def test_name_alone_never_resolves_e2003_even_with_reserved_looking_name(self, tmp_path: Path) -> None:
        """TC-EP-508: a param literally named "paths" but typed str still raises E2003."""
        ctx = _full_run_context(tmp_path)

        def flow(paths: str) -> None:
            ...

        with pytest.raises(RdeRegistryError) as exc_info:
            resolve_flow_kwargs(flow, ctx)

        assert exc_info.value.code == 2003

    def test_unresolved_forward_reference_falls_back_to_e2003(self, tmp_path: Path) -> None:
        """TC-EP-510: unresolved annotation strings do not bypass E2003 validation."""
        ctx = _full_run_context(tmp_path)

        def flow(mystery: "MissingType") -> None:  # noqa: F821
            ...

        with pytest.raises(RdeRegistryError) as exc_info:
            resolve_flow_kwargs(flow, ctx)

        assert exc_info.value.code == 2003

    def test_e2003_message_embeds_remediation_content(self, tmp_path: Path) -> None:
        """TC-BV-501: E2003 message names a reserved type or mentions a default value."""
        ctx = _full_run_context(tmp_path)

        def flow(mystery: str) -> None:
            ...

        with pytest.raises(RdeRegistryError) as exc_info:
            resolve_flow_kwargs(flow, ctx)

        message = str(exc_info.value)
        reserved_type_names = ("InputPaths", "OutputContext", "RdeConfig", "InvoiceData", "IterationInfo")
        assert any(name in message for name in reserved_type_names) or "default value" in message.lower()

    def test_e2006_message_embeds_remediation_content(self, tmp_path: Path) -> None:
        """TC-BV-502: E2006 message substantively conveys the "declare once" remediation."""
        ctx = _full_run_context(tmp_path)

        def flow(a: InputPaths, b: InputPaths) -> None:
            ...

        with pytest.raises(RdeRegistryError) as exc_info:
            resolve_flow_kwargs(flow, ctx)

        message = str(exc_info.value)
        assert "once" in message.lower()


class TestResolveFlowKwargsSignatureShapes:
    """TC-BV-503/504: variadic and keyword-only parameter handling."""

    def test_variadic_params_are_skipped_without_error(self, tmp_path: Path) -> None:
        """TC-BV-503: *args/**kwargs are neither injected into nor treated as errors."""
        ctx = _full_run_context(tmp_path)

        def flow(paths: InputPaths, *args: Any, **kwargs: Any) -> None:
            ...

        result = resolve_flow_kwargs(flow, ctx)

        assert result["paths"] is ctx.paths
        assert "args" not in result
        assert "kwargs" not in result

    def test_keyword_only_reserved_param_is_injected(self, tmp_path: Path) -> None:
        """TC-BV-504: a keyword-only reserved-type param is injected like a positional one."""
        ctx = _full_run_context(tmp_path)

        def flow(*, config: RdeConfig) -> None:
            ...

        result = resolve_flow_kwargs(flow, ctx)

        assert result["config"] is ctx.config


class TestResolveFlowKwargsIntegrationWithTestingKit:
    """TC-BV-505: integration test using the testing kit builders (Conflict #1 evidence)."""

    def test_resolved_kwargs_actually_run_a_renamed_param_flow(self, tmp_path: Path) -> None:
        """TC-BV-505: builders build real data; resolve_flow_kwargs feeds a real flow call."""
        from rdetoolkit.testing import make_input_paths, make_output_context  # noqa: PLC0415

        input_paths = make_input_paths(tmp_path / "in")
        output_context = make_output_context(tmp_path / "out")
        ctx = RunContext(paths=input_paths, out=output_context)

        calls: list[tuple[InputPaths, OutputContext]] = []

        def flow(input_paths: InputPaths, output_context: OutputContext) -> None:
            calls.append((input_paths, output_context))

        flow(**resolve_flow_kwargs(flow, ctx))

        assert calls == [(input_paths, output_context)]


class TestNoDependencyInjectionInsideNode:
    """TC-EP-509: regression guard — core/node.py must not import core.injection."""

    def test_node_module_does_not_import_injection(self) -> None:
        """core/node.py must have zero references to the injection module (no DI in @node)."""
        import rdetoolkit.core.node as node_module  # noqa: PLC0415

        source = inspect.getsource(node_module)
        tree = ast.parse(source)

        imported_modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)

        assert not any("injection" in name for name in imported_modules)
