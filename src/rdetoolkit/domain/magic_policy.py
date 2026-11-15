"""Configuration boundary for the versioned v2 interpolation policy."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal, cast

from rdetoolkit.domain.magic import MagicOptions
from rdetoolkit.domain.service_errors import validation_error
from rdetoolkit.types import RdeConfig


def options_from_config(config: RdeConfig) -> MagicOptions:
    """Read strict interpolation options without changing v1 boolean semantics.

    Args:
        config: Canonical flow configuration. ``custom.interpolation`` accepts
            ``policy`` and ``missing``. An omitted boolean means auto.

    Returns:
        Validated policy and missing-value behavior.

    Raises:
        RdeValidationError: Code 4005 for invalid or contradictory options.
    """
    configured = "magic_variable" in config.system.model_fields_set
    boolean_policy = "enabled" if config.system.magic_variable else "disabled"
    data = config.custom.get("interpolation", {})
    if not isinstance(data, Mapping) or set(data) - {"policy", "missing"}:
        raise validation_error(4005, "custom.interpolation accepts only policy and missing options.")
    policy = data.get("policy", boolean_policy if configured else "auto")
    missing = data.get("missing", "error")
    options = MagicOptions(
        policy=cast(Literal["auto", "enabled", "disabled"], policy),
        missing=cast(Literal["error", "omit"], missing),
    )
    _check_compatibility(configured, boolean_policy, data, policy)
    return options


def _check_compatibility(configured: bool, boolean_policy: str, data: Mapping[str, object], policy: object) -> None:
    if configured and "policy" in data and policy != boolean_policy:
        raise validation_error(4005, "custom.interpolation.policy conflicts with explicit system.magic_variable.")
