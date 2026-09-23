"""Configuration loading for the v2 Runner."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from rdetoolkit.config.normalize import ConfigNormalizer
from rdetoolkit.types import RdeConfig


def load_config(
    root: Path,
    overrides: Mapping[str, Any] | None = None,
    *,
    data_root: Path | None = None,
) -> RdeConfig:
    """Load strict v2 Runner configuration.

    The discovery chain is ``<root>/rdeconfig.yaml``, then ``<root>/pyproject.toml``
    ``[tool.rdetoolkit]``, then — when ``data_root`` is known — the v1 layout a
    real structured program ships,
    ``<data_root>/tasksupport/{rdeconfig.yaml, rdeconfig.yml, pyproject.toml}``
    (Session I-REVIEW-A ruling #4), and finally ``RdeConfig()`` defaults.
    Explicit overrides win over file values.

    Args:
        root: Directory containing optional config files.
        overrides: Values merged over the loaded config.
        data_root: The run's resolved data root, enabling tasksupport discovery.

    Returns:
        Effective v2 configuration.

    Raises:
        RdeConfigError: If a file or override contains unknown or invalid keys
            for ``RdeConfig`` or its child models.
    """
    normalizer = ConfigNormalizer()
    config_data = normalizer.normalize(None, root=root, origin="v2", data_root=data_root).model_dump()
    if overrides:
        config_data = _deep_merge(config_data, dict(overrides))
    return normalizer.normalize(config_data, root=root, origin="v2")

def _deep_merge(base: Mapping[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(base))
    for key, value in overlay.items():
        existing = result.get(key)
        if isinstance(existing, dict) and isinstance(value, Mapping):
            result[key] = _deep_merge(existing, value)
        else:
            result[key] = copy.deepcopy(value)
    return result
