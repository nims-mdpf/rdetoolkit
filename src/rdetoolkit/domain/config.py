"""Domain configuration loading helpers for v2 workflows."""

from __future__ import annotations

from pathlib import Path

from rdetoolkit.config import load_config
from rdetoolkit.models.config import Config
from rdetoolkit.models.rde2types import RdeFsPath


def load_domain_config(tasksupport_path: RdeFsPath, *, config: Config | None = None) -> Config:
    """Load an RDEToolKit configuration for domain services.

    This function delegates parsing and validation to the existing v1
    configuration loader so the Pydantic ``Config`` model remains the single
    source of truth.

    Args:
        tasksupport_path: Directory that may contain ``rdeconfig.yaml`` or
            ``rdeconfig.yml``.
        config: Optional explicit configuration object. When provided it is
            returned unchanged by the underlying loader.

    Returns:
        Loaded ``Config`` instance.

    Raises:
        rdetoolkit.exceptions.ConfigError: If parsing or validation fails.
    """
    return load_config(Path(tasksupport_path), config=config)
