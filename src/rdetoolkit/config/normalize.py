"""Normalize legacy and canonical configuration sources for the v2 Runner."""

from __future__ import annotations

import copy
import tomllib
import warnings
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import ValidationError

from rdetoolkit.errors import ERROR_CATALOG, RdeConfigError
from rdetoolkit.models.config import Config
from rdetoolkit.types import RdeConfig


ConfigOrigin = Literal["v1", "v2"]

_V1_TOP_LEVEL_KEYS = frozenset({"system", "multidata_tile", "smarttable", "traceback"})
_SYSTEM_KEYS = (
    "extended_mode",
    "save_raw",
    "save_nonshared_raw",
    "save_thumbnail_image",
    "magic_variable",
    "save_invoice_to_structured",
    "feature_description",
)
_TRACEBACK_KEYS = (
    "enabled",
    "format",
    "include_context",
    "include_locals",
    "include_env",
    "max_locals_size",
    "sensitive_patterns",
)


class ConfigNormalizer:
    """Convert supported configuration inputs to the canonical ``RdeConfig``."""

    def normalize(
        self,
        source: object | None,
        *,
        root: Path,
        origin: ConfigOrigin,
        data_root: Path | None = None,
    ) -> RdeConfig:
        """Normalize one configuration source at the public API boundary.

        Args:
            source: Explicit model, mapping, file path, or ``None`` for discovery.
            root: Directory anchoring implicit configuration discovery.
            origin: Input contract whose defaults and compatibility rules apply.
            data_root: The run's resolved data root. With ``origin="v2"`` and
                implicit discovery it extends the search to the v1 layout every
                real structured program ships,
                ``<data_root>/tasksupport/rdeconfig.yaml`` (ruling #4).

        Returns:
            Strict canonical v2 configuration.

        Raises:
            RdeConfigError: If the source cannot be loaded or normalized.
            ValueError: If ``origin`` is not a supported contract identifier.
        """
        if origin not in ("v1", "v2"):
            msg = f"Unsupported configuration origin: {origin!r}"
            raise ValueError(msg)

        if source is None and origin == "v2" and data_root is not None:
            discovered = _discover_v2_config(root)
            if discovered is None:
                return self._normalize_tasksupport(root, data_root)
            return self._build(discovered, origin=origin)

        data = self._source_data(source, root=root, origin=origin)
        return self._build(data, origin=origin)

    def _build(self, data: Mapping[str, Any], *, origin: ConfigOrigin) -> RdeConfig:
        normalized = self._convert_v1(data) if origin == "v1" else self._convert_v2(data)
        try:
            return RdeConfig(**normalized)
        except ValidationError as exc:
            raise _config_error(str(exc)) from exc

    def _normalize_tasksupport(self, root: Path, data_root: Path) -> RdeConfig:
        """Read the v1 tasksupport configuration with the v1 loader itself.

        The file is v1 material, so v1 owns its interpretation: whatever
        ``rdetoolkit.config.parse_config_file`` accepts, the unified Runner
        accepts identically. Re-parsing it here would fork the contract.

        Args:
            root: Project root, used only for error reporting.
            data_root: The run's resolved data root.

        Returns:
            Canonical configuration, or the v2 defaults when no file exists.
        """
        _ = root
        path = _find_tasksupport_config(data_root)
        if path is None:
            return RdeConfig()
        # Imported at call time: rdetoolkit.config imports the v1 model layer,
        # and this module is imported from the v2 config package itself.
        from rdetoolkit.config import parse_config_file  # noqa: PLC0415
        from rdetoolkit.exceptions import ConfigError  # noqa: PLC0415

        try:
            legacy = parse_config_file(path=str(path))
        except ConfigError as exc:
            reason = f"could not read {path}: {exc}"
            raise _config_error(reason) from exc
        return self._build(legacy.model_dump(exclude_none=True), origin="v1")

    def _source_data(
        self,
        source: object | None,
        *,
        root: Path,
        origin: ConfigOrigin,
    ) -> dict[str, Any]:
        if source is None:
            return _discover_config(root, origin)
        if isinstance(source, RdeConfig):
            return source.model_dump()
        if isinstance(source, Config):
            return source.model_dump(exclude_none=True)
        if isinstance(source, Mapping):
            return copy.deepcopy(dict(source))
        if isinstance(source, (str, Path)):
            return _load_mapping(Path(source))
        reason = f"unsupported configuration source type {type(source).__name__}"
        raise _config_error(reason)

    def _convert_v1(self, data: Mapping[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {"execution": {"on_iteration_error": "fail_fast"}}

        system = _mapping_section(data, "system")
        if system:
            converted_system = {
                key: copy.deepcopy(system[key])
                for key in _SYSTEM_KEYS
                if key in system
            }
            if converted_system.get("extended_mode") is None:
                converted_system["extended_mode"] = "invoice"
            result["system"] = converted_system

        smarttable = _mapping_section(data, "smarttable")
        if "save_table_file" in smarttable:
            result["smarttable"] = {
                "save_table_file": copy.deepcopy(smarttable["save_table_file"]),
            }

        multidata_tile = _mapping_section(data, "multidata_tile")
        if "ignore_errors" in multidata_tile:
            result["execution"]["on_iteration_error"] = (
                "continue" if multidata_tile["ignore_errors"] else "fail_fast"
            )

        traceback = _mapping_section(data, "traceback")
        for key in _TRACEBACK_KEYS:
            if key in traceback:
                warnings.warn(
                    f"traceback.{key} is deprecated; use TRACE_* environment configuration instead.",
                    DeprecationWarning,
                    stacklevel=3,
                )

        custom: dict[str, Any] = {}
        for key, value in data.items():
            if key not in _V1_TOP_LEVEL_KEYS:
                warnings.warn(
                    f"Legacy configuration key {key!r} is preserved under custom.",
                    UserWarning,
                    stacklevel=3,
                )
                custom[key] = copy.deepcopy(value)
        if custom:
            result["custom"] = custom
        return result

    def _convert_v2(self, data: Mapping[str, Any]) -> dict[str, Any]:
        return copy.deepcopy(dict(data))


def _mapping_section(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = data.get(key)
    return value if isinstance(value, Mapping) else {}


#: Filenames the v1 loader accepts, in its own priority order
#: (``rdetoolkit.config.CONFIG_FILES``).
_V1_CONFIG_FILENAMES = ("rdeconfig.yaml", "rdeconfig.yml", "pyproject.toml")


def _discover_v2_config(root: Path) -> dict[str, Any] | None:
    """Return the v2-form configuration at the project root, if there is one."""
    if root.is_file():
        return _load_mapping(root)
    for path in (root / "rdeconfig.yaml", root / "pyproject.toml"):
        if path.exists():
            return _load_mapping(path)
    return None


def _find_tasksupport_config(data_root: Path) -> Path | None:
    """Return the v1 configuration a structured program ships, if there is one."""
    tasksupport = data_root / "tasksupport"
    for filename in _V1_CONFIG_FILENAMES:
        candidate = tasksupport / filename
        if candidate.exists():
            return candidate
    return None


def _discover_config(root: Path, origin: ConfigOrigin) -> dict[str, Any]:
    if root.is_file():
        return _load_mapping(root)

    candidates: tuple[Path, ...]
    if origin == "v2":
        candidates = (root / "rdeconfig.yaml", root / "pyproject.toml")
    else:
        tasksupport_dirs = (root / "data" / "tasksupport", root / "tasksupport", root)
        candidates = tuple(
            directory / filename
            for directory in tasksupport_dirs
            for filename in ("rdeconfig.yaml", "rdeconfig.yml", "pyproject.toml")
        )
    for path in candidates:
        if path.exists():
            return _load_mapping(path)
    return {}


def _load_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        reason = f"configuration file does not exist: {path}"
        raise _config_error(reason)
    try:
        if path.suffix.lower() in {".yaml", ".yml"}:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        elif path.suffix.lower() == ".toml":
            document = tomllib.loads(path.read_text(encoding="utf-8"))
            raw = document.get("tool", {}).get("rdetoolkit", {})
        else:
            reason = f"unsupported configuration file: {path.name}"
            raise _config_error(reason)
    except (OSError, tomllib.TOMLDecodeError, yaml.YAMLError) as exc:
        reason = f"could not read {path}: {exc}"
        raise _config_error(reason) from exc
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        reason = f"{path.name} must contain a mapping at the top level"
        raise _config_error(reason)
    return copy.deepcopy(dict(raw))


def _config_error(reason: str) -> RdeConfigError:
    error_def = ERROR_CATALOG[1002]
    message = error_def.message_template.format(reason=reason)
    message = f"{message} Remediation: {error_def.remediation}"
    error_cls: Any = RdeConfigError
    return error_cls(code=1002, name=error_def.name, message=message)
