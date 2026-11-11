"""Configuration loading for the v2 Runner."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from rdetoolkit.config.normalize import ConfigNormalizer
from rdetoolkit.runner.paths import resolve_data_root
from rdetoolkit.types import RdeConfig


def load_run_config(
    root: Path | str | None = None,
    *,
    overrides: Mapping[str, Any] | None = None,
) -> RdeConfig:
    """Load configuration using the Runner's discovery and override rules.

    Uses the shared data-root resolver and config loader (Design §6.3).
    Project-root ``rdeconfig.yaml`` and ``pyproject.toml`` take priority over
    legacy files in the resolved data root's ``tasksupport`` directory.
    Overrides are merged recursively over the discovered settings; their
    non-null mode values count as explicit for W1001 (Design §6.2).
    Pass the returned object to ``workflows.run(flow=..., config=...)`` to
    use these effective settings as the whole configuration.

    Args:
        root: Project or data directory. Defaults to the current directory.
        overrides: Optional mapping merged over the discovered configuration.
            A null ``system.extended_mode`` clears an explicitly set mode.

    Returns:
        Effective configuration without creating any run directories.

    Raises:
        RdeConfigError: If a discovered file or override is invalid (E1002).
    """
    root_path = Path.cwd() if root is None else Path(root)
    return load_config(root_path, overrides, data_root=resolve_data_root(root_path))


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
    discovered = normalizer.normalize(None, root=root, origin="v2", data_root=data_root)
    # Only the keys a source actually set are carried into the merge. Dumping
    # the defaulted model re-entered every default as a value, so an implicit
    # ``extended_mode`` became "explicitly configured" and file detection of a
    # SmartTable / ExcelInvoice input published a false W1001 (review rc1 C02,
    # Design §6.2). ``exclude_unset`` is applied recursively to the nested
    # section models, and every omitted key takes the same default again, so
    # the effective values are unchanged.
    config_data = discovered.model_dump(exclude_unset=True)
    if overrides:
        config_data = _deep_merge(config_data, dict(overrides))
    return normalizer.normalize(config_data, root=root, origin="v2")


def compute_config_digest(config: RdeConfig) -> str:
    """Return the digest that identifies an effective config by value.

    The digest is sha256 over the config's JSON dump written canonically:
    mapping keys sorted at every depth, compact separators, UTF-8. Two
    configs holding the same values therefore share a digest however their
    free-form mappings (such as ``custom``) were ordered, while list order and
    JSON value types (``1`` vs ``1.0``) still count. ``RunReport.config_digest``
    and ``repro export`` both use this function, so "same config" has one
    definition.

    Args:
        config: Effective v2 configuration.

    Returns:
        ``"sha256:"`` followed by 64 lowercase hex digits.
    """
    canonical = json.dumps(
        config.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _deep_merge(base: Mapping[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(base))
    for key, value in overlay.items():
        existing = result.get(key)
        if isinstance(existing, dict) and isinstance(value, Mapping):
            result[key] = _deep_merge(existing, value)
        else:
            result[key] = copy.deepcopy(value)
    return result
