"""Normalize legacy and canonical configuration sources for the v2 Runner."""

from __future__ import annotations

import copy
import sys
import warnings
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import ValidationError

from rdetoolkit.errors import ERROR_CATALOG, RdeConfigError
from rdetoolkit.models.config import Config
from rdetoolkit.types import RdeConfig

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib



ConfigOrigin = Literal["v1", "v2"]

_V1_TOP_LEVEL_KEYS = frozenset({"system", "multidata_tile", "smarttable", "traceback", "custom"})
_SYSTEM_KEYS = (
    "extended_mode",
    "save_raw",
    "save_nonshared_raw",
    "save_thumbnail_image",
    "magic_variable",
    "save_invoice_to_structured",
    "feature_description",
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
            # v1 ``extended_mode=None`` means "no mode configured" (invoice
            # by default). Leaving the key out lets ``RdeConfig`` default it to
            # the same ``invoice`` while keeping it out of
            # ``model_fields_set``: writing ``invoice`` here made every v1 job
            # an explicit invoice configuration, so file detection published a
            # false W1001 (review rc1 C02, Design §6.2).
            if converted_system.get("extended_mode") is None:
                converted_system.pop("extended_mode", None)
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

        # ``traceback.*`` is formatter configuration for the v1 entry's stderr
        # traceback, not Runner configuration: it is carried out of band (the
        # v1 ``Config`` reaches ``workflows._run_callback_entry`` unchanged) and
        # deliberately dropped here, silently -- Design §11 rules out new
        # DeprecationWarnings in v2.0 (operator ruling 2026-11-08, F03).

        custom = _legacy_custom(data)
        if custom:
            result["custom"] = custom
        return result

    def _convert_v2(self, data: Mapping[str, Any]) -> dict[str, Any]:
        return copy.deepcopy(dict(data))


def _mapping_section(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = data.get(key)
    return value if isinstance(value, Mapping) else {}


def _legacy_custom(data: Mapping[str, Any]) -> dict[str, Any]:
    """Merge legacy extensions while keeping the explicit custom namespace flat."""
    custom: dict[str, Any] = {}
    for key, value in data.items():
        if key not in _V1_TOP_LEVEL_KEYS:
            warnings.warn(
                f"Legacy configuration key {key!r} is preserved under custom.",
                UserWarning,
                stacklevel=4,
            )
            custom[key] = copy.deepcopy(value)
    explicit = data.get("custom", {})
    if not isinstance(explicit, Mapping):
        reason = "custom must contain a mapping"
        raise _config_error(reason)
    custom.update(copy.deepcopy(explicit))
    return custom


#: Filenames the v1 loader accepts, in its own priority order
#: (``rdetoolkit.config.CONFIG_FILES``).
_V1_CONFIG_FILENAMES = ("rdeconfig.yaml", "rdeconfig.yml", "pyproject.toml")


def _discover_v2_config(root: Path) -> dict[str, Any] | None:
    """Return the v2-form configuration at the project root, if there is one."""
    if root.is_file():
        return _load_mapping(root)
    for path in (root / "rdeconfig.yaml", root / "pyproject.toml"):
        if path.exists():
            discovered = _load_optional_mapping(path)
            if discovered is not None:
                return discovered
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
        return _discover_v2_config(root) or {}
    candidates = _legacy_config_candidates(root)
    for path in candidates:
        if path.exists():
            return _load_mapping(path)
    return {}


def _legacy_config_candidates(root: Path) -> tuple[Path, ...]:
    directories = (root / "data" / "tasksupport", root / "tasksupport", root)
    return tuple(directory / name for directory in directories for name in _V1_CONFIG_FILENAMES)


def _load_mapping(path: Path) -> dict[str, Any]:
    return _load_optional_mapping(path) or {}


def _load_optional_mapping(path: Path) -> dict[str, Any] | None:
    """Distinguish an absent TOML tool table from a present empty configuration."""
    if not path.exists():
        reason = f"configuration file does not exist: {path}"
        raise _config_error(reason)
    try:
        raw = _read_configuration(path)
    except (OSError, tomllib.TOMLDecodeError, yaml.YAMLError) as exc:
        reason = f"could not read {path}: {exc}"
        raise _config_error(reason) from exc
    if raw is None:
        return None if path.suffix.lower() == ".toml" else {}
    if not isinstance(raw, Mapping):
        reason = f"{path.name} must contain a mapping at the top level"
        raise _config_error(reason)
    return copy.deepcopy(dict(raw))


def _read_configuration(path: Path) -> Any:
    if path.suffix.lower() in {".yaml", ".yml"}:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    if path.suffix.lower() == ".toml":
        document = tomllib.loads(path.read_text(encoding="utf-8"))
        return document.get("tool", {}).get("rdetoolkit")
    reason = f"unsupported configuration file: {path.name}"
    raise _config_error(reason)


def _config_error(reason: str) -> RdeConfigError:
    error_def = ERROR_CATALOG[1002]
    message = error_def.message_template.format(reason=reason)
    message = f"{message} Remediation: {error_def.remediation}"
    error_cls: Any = RdeConfigError
    return error_cls(code=1002, name=error_def.name, message=message)
