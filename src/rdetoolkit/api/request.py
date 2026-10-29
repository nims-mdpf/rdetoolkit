"""Normalized requests shared by future execution entry points."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rdetoolkit.errors import ERROR_CATALOG, RdeConfigError


@dataclass(frozen=True, slots=True)
class FlowTarget:
    """A v2 flow selected for execution.

    Attributes:
        function: Flow callable preserved from the public API boundary.
    """

    function: Callable[..., object]


@dataclass(frozen=True, slots=True)
class LegacyCallbackTarget:
    """A v1-compatible dataset callback selected for execution.

    Attributes:
        function: Dataset callback, or ``None`` for callback-free v1 runs.
    """

    function: Callable[..., object] | None


ExecutionTarget = FlowTarget | LegacyCallbackTarget


@dataclass(frozen=True, slots=True)
class RunRequest:
    """Normalized execution request consumed by the unified Runner.

    Attributes:
        root: Root directory of the run.
        target: Flow or legacy callback execution target.
        config_source: Opaque configuration source for boundary normalization.
        validate_only: Whether execution stops after validation.
    """

    root: Path
    target: ExecutionTarget
    config_source: object | None = None
    validate_only: bool = False


def build_run_request(
    *,
    flow: Callable[..., object] | None,
    custom_dataset_function: Callable[..., object] | None,
    config: object | None,
    root: Path | None = None,
    validate_only: bool = False,
) -> RunRequest:
    """Normalize public execution arguments into one request contract.

    Args:
        flow: v2 flow callable, if selected.
        custom_dataset_function: v1 dataset callback, if selected.
        config: Configuration source retained for later normalization.
        root: Run root. Defaults to the current working directory.
        validate_only: Whether the future Runner should only validate inputs.

    Returns:
        A normalized, immutable run request.

    Raises:
        RdeConfigError: If both public entry points are supplied.
        TypeError: If a supplied entry point is not callable.
    """
    if flow is not None and custom_dataset_function is not None:
        error_def = ERROR_CATALOG[1001]
        message = f"{error_def.message_template} Remediation: {error_def.remediation}"
        error_cls: Any = RdeConfigError
        raise error_cls(
            code=1001,
            name=error_def.name,
            message=message,
        )

    normalized_flow = flow
    if flow is not None:
        from rdetoolkit.templates.base import (  # noqa: PLC0415
            flow_from_template,
            is_concrete_template_class,
            is_template_class,
        )

        if is_template_class(flow):
            if not is_concrete_template_class(flow):
                msg = (
                    "A ProcessingTemplate skeleton cannot be executed. Create a "
                    "subclass that implements every required slot and pass that concrete class."
                )
                raise TypeError(msg)
            normalized_flow = flow_from_template(flow)
        elif isinstance(flow, type):
            msg = "Flow class target is not a ProcessingTemplate subclass"
            raise TypeError(msg)

    if normalized_flow is not None and not callable(normalized_flow):
        msg = (
            "flow must be callable or None. Remediation: pass a callable flow "
            "such as a function decorated with @flow."
        )
        raise TypeError(msg)
    if custom_dataset_function is not None and not callable(custom_dataset_function):
        msg = (
            "custom_dataset_function must be callable or None. Remediation: pass "
            "the dataset callback function itself, not its return value."
        )
        raise TypeError(msg)

    target: ExecutionTarget = (
        FlowTarget(function=normalized_flow)
        if normalized_flow is not None
        else LegacyCallbackTarget(function=custom_dataset_function)
    )

    return RunRequest(
        root=Path.cwd() if root is None else root,
        target=target,
        config_source=config,
        validate_only=validate_only,
    )
