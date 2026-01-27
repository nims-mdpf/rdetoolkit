from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Final

import yaml
from pydantic import ValidationError
from tomlkit.exceptions import TOMLKitError
from tomlkit.toml_file import TOMLFile
from yaml import YAMLError

from rdetoolkit.exceptions import ConfigError
from rdetoolkit.models.config import Config, TracebackSettings, MultiDataTileSettings, SystemSettings, SmartTableSettings
from rdetoolkit.models.rde2types import RdeFsPath

CONFIG_FILE: Final = ["rdeconfig.yaml", "rdeconfig.yml"]
PYPROJECT_CONFIG_FILES: Final = ["pyproject.toml"]
CONFIG_FILES = CONFIG_FILE + PYPROJECT_CONFIG_FILES


def _format_validation_error(
    validation_error: ValidationError,
    file_path: str,
) -> ConfigError:
    """Format pydantic ValidationError into user-friendly ConfigError.

    Args:
        validation_error: The pydantic ValidationError
        file_path: Path to the configuration file

    Returns:
        ConfigError with detailed field-level information
    """
    errors = validation_error.errors()

    if not errors:
        return ConfigError(
            "Configuration validation failed",
            file_path=file_path,
            error_type="validation_error",
        )

    # Take the first error for the main message
    first_error = errors[0]
    field_path = ".".join(str(loc) for loc in first_error["loc"])
    error_msg = first_error["msg"]
    error_type_detail = first_error["type"]

    # Build detailed message
    message_parts = [f"Invalid configuration in '{file_path}'"]

    if field_path:
        message_parts.append(f"Field '{field_path}' validation failed: {error_msg}")
    else:
        message_parts.append(f"Validation failed: {error_msg}")

    # Add information about expected values if available
    if "input" in first_error:
        input_value = first_error["input"]
        message_parts.append(f"Provided value: {input_value!r}")

    # For extended_mode, provide specific guidance
    if "extended_mode" in field_path and "enum" in error_type_detail.lower():
        message_parts.append(
            "Valid values for 'extended_mode': ['rdeformat', 'MultiDataTile']",
        )

    # Add validation error context if multiple errors exist
    if len(errors) > 1:
        message_parts.append(
            f"Note: {len(errors)} validation error(s) found. Showing the first one.",
        )

    full_message = "\n".join(message_parts)

    return ConfigError(
        full_message,
        file_path=file_path,
        error_type="validation_error",
        field_name=field_path,
    )


def parse_config_file(*, path: str | None = None) -> Config:
    """Parse the configuration file and return a Config object.

    Args:
        path (str, optional): The path to the configuration file. If not provided, the function will attempt to find and parse the default configuration file.

    Returns:
        Config: The parsed configuration object.

    Raises:
        ConfigError: If the specified configuration file does not exist or cannot be parsed.

    File Loading Priority:
        1. If `path` is provided and the file extension is ".toml", the function will attempt to read the file as a TOML file.
        2. If `path` is provided and the file extension is ".yaml" or ".yml", the function will attempt to read the file as a YAML file.
        3. If `path` is not provided, the function will attempt to find and parse the default configuration file named "pyproject.toml" in the current working directory.

    Accepted Config Files:
        - "rdeconfig.yaml"
        - "rdeconfig.yml"
        - "pyproject.toml"

    Note:
        - If the specified file is not a recognized config file name (not in CONFIG_FILES),
          an empty Config object will be returned.
        - If the specified file does not exist, ConfigError is raised.
        - If the file contains invalid YAML/TOML syntax, ConfigError is raised with line/column info.
        - If the configuration fails validation, ConfigError is raised with field details.

    Example:
        parse_config_file(path="rdeconfig.yaml")

    """
    config_data: dict[str, Any] = {
        "system": SystemSettings().model_dump(),
        "multidata_tile": MultiDataTileSettings().model_dump(),
        "smarttable": SmartTableSettings().model_dump(),
    }

    # Check file existence when path is provided
    if path is not None:
        path_obj = Path(path)
        if not path_obj.exists():
            msg = (
                f"Configuration file not found: '{path}'. "
                f"Create a configuration file or use 'rdetoolkit gen-config' to generate one."
            )
            raise ConfigError(
                msg,
                file_path=path,
                error_type="file_not_found",
            )

    if path is not None and Path(path).name not in CONFIG_FILES:
        return Config(system=SystemSettings(), multidata_tile=MultiDataTileSettings(), smarttable=SmartTableSettings())

    if path is not None and is_toml(path):
        config_data = __read_pyproject_toml(path)
    elif path is not None and is_yaml(path):
        try:
            with open(path, encoding="utf-8") as f:
                config_data = yaml.safe_load(f)
        except YAMLError as e:
            # Extract line and column information from YAMLError
            line_number = None
            column_number = None

            if hasattr(e, "problem_mark") and e.problem_mark is not None:
                line_number = e.problem_mark.line + 1  # YAML uses 0-indexed lines
                column_number = e.problem_mark.column + 1

            error_msg = "Failed to parse YAML file: invalid syntax"
            if hasattr(e, "problem"):
                error_msg = f"Failed to parse YAML file: {e.problem}"

            raise ConfigError(
                error_msg,
                file_path=path,
                error_type="parse_error",
                line_number=line_number,
                column_number=column_number,
            ) from e
        except OSError as e:
            msg = f"Failed to read YAML file: {e}"
            raise ConfigError(
                msg,
                file_path=path,
                error_type="io_error",
            ) from e
    elif path is None:
        project_path = Path.cwd()
        pyproject_toml = project_path.joinpath(PYPROJECT_CONFIG_FILES[0])
        config_data = __read_pyproject_toml(str(pyproject_toml))
    else:
        return Config(system=SystemSettings(), multidata_tile=MultiDataTileSettings(), smarttable=SmartTableSettings())

    if config_data is None:
        return Config(system=SystemSettings(), multidata_tile=MultiDataTileSettings(), smarttable=SmartTableSettings())

    try:
        return Config(**config_data)
    except ValidationError as e:
        # Use helper to format validation error
        if path:
            raise _format_validation_error(e, path) from e
        # Fallback for when path is None
        msg = f"Configuration validation failed: {str(e)}"
        raise ConfigError(
            msg,
            error_type="validation_error",
        ) from e
    except TypeError as e:
        # This occurs when config_data is not a mapping (e.g., list or string),
        # which makes Config(**config_data) invalid. Normalize it to ConfigError.
        base_msg = "Configuration data must be a mapping (key-value structure)"
        msg = f"{base_msg} in file '{path}'" if path else base_msg
        raise ConfigError(
            msg,
            file_path=path,
            error_type="validation_error",
        ) from e


def __read_pyproject_toml(path: str) -> dict[str, Any]:
    """Read the pyproject.toml file and return the contents as a dictionary.

    Args:
        path: Path to the pyproject.toml file

    Returns:
        dict[str, Any]: The contents of the pyproject.toml file.

    Raises:
        ConfigError: If the file does not exist or cannot be parsed
    """
    # Check file existence first
    path_obj = Path(path)
    if not path_obj.exists():
        msg = (
            f"Configuration file not found: '{path}'. "
            f"Create a pyproject.toml file with [tool.rdetoolkit] section."
        )
        raise ConfigError(
            msg,
            file_path=path,
            error_type="file_not_found",
        )

    try:
        toml = TOMLFile(path)
        obj = toml.read()
        _obj = obj.unwrap()
        return _obj.get("tool", {}).get("rdetoolkit", {})
    except TOMLKitError as e:
        # Extract line information if available
        line_number = None
        if hasattr(e, "line"):
            line_number = e.line

        error_msg = f"Failed to parse TOML file: {str(e)}"

        raise ConfigError(
            error_msg,
            file_path=path,
            error_type="parse_error",
            line_number=line_number,
        ) from e
    except OSError as e:
        msg = f"Failed to read TOML file: {e}"
        raise ConfigError(
            msg,
            file_path=path,
            error_type="io_error",
        ) from e


def is_toml(filename: str) -> bool:
    """Check if the given filename has a .toml extension.

    Args:
        filename (str): The name of the file to check.

    Returns:
        bool: True if the filename has a .toml extension, False otherwise.
    """
    return filename.lower().endswith(".toml")


def is_yaml(filename: str) -> bool:
    """Check if the given filename has a YAML file extension.

    Args:
        filename (str): The name of the file to check.

    Returns:
        bool: True if the filename has a YAML file extension, False otherwise.
    """
    return filename.lower().endswith(".yaml") or filename.lower().endswith(".yml")


def find_config_files(target_dir_path: RdeFsPath) -> list[str]:
    """Find and return a list of configuration files in the given input directory.

    Args:
        target_dir_path: (RdeFsPath): An object containing the paths to the input directories.

    Returns:
        list[str]: A list of configuration file paths.

    """
    files: list[str] = []
    if isinstance(target_dir_path, Path):
        target_dir_path = str(target_dir_path)
    existing_files = os.listdir(target_dir_path)
    if not existing_files:
        return files
    for config_file in CONFIG_FILES:
        if config_file in existing_files:
            files.append(os.path.join(target_dir_path, config_file))
    return sorted(files, key=lambda x: (is_toml(x), is_yaml(x)))


def get_pyproject_toml() -> Path | None:
    """Get the pyproject.toml file.

    Returns:
        Optional[Path]: The path to the pyproject.toml file.
    """
    pyproject_toml_path = Path.cwd().joinpath("pyproject.toml")
    return pyproject_toml_path.exists() and pyproject_toml_path or None


def get_config(target_dir_path: RdeFsPath) -> Config | None:
    """Retrieves the configuration from the specified directory path.

    This function searches for configuration files in the specified directory.
    It parses each found configuration file until it finds a valid configuration,
    which it then returns. If no valid configuration is found in the directory,
    it searches for a pyproject.toml file, parses it, and returns its configuration
    if valid. If no valid configuration is found, it returns None.

    Args:
        target_dir_path (RdeFsPath): The path of the directory to search for configuration files.

    Returns:
        Optional[Config]: The first valid configuration found, or None if no valid configuration is found.

    Raises:
        ConfigError: If the target directory does not exist.
    """
    if isinstance(target_dir_path, str):
        target_dir_path = Path(target_dir_path)
    if not target_dir_path.exists():
        msg = (
            f"Configuration directory not found: '{target_dir_path}'. "
            f"Ensure the directory exists and contains a valid configuration file."
        )
        raise ConfigError(
            msg,
            file_path=str(target_dir_path),
            error_type="directory_not_found",
        )
    for cfg_file in find_config_files(target_dir_path):
        # parse_config_file now converts ValidationError to ConfigError internally
        __config = parse_config_file(path=cfg_file)
        if __config is not None:
            return __config

    pyproject_toml_path = get_pyproject_toml()
    if pyproject_toml_path is not None:
        # parse_config_file now converts ValidationError to ConfigError internally
        __config = parse_config_file(path=str(pyproject_toml_path))
        if __config is not None:
            return __config
    return None


def load_config(tasksupport_path: RdeFsPath, *, config: Config | None = None) -> Config:
    """Loads the configuration for the RDE Toolkit.

    Args:
        tasksupport_path (RdeFsPath): The path to the tasksupport directory.
        config (Optional[Config]): An optional existing configuration object.

    Returns:
        Config: The loaded configuration object.

    """
    __config: Config = Config()
    if config is not None:
        __config = config
    else:
        try:
            __rtn_config = get_config(tasksupport_path)
            __config = Config() if __rtn_config is None else __rtn_config
        except ConfigError as e:
            # Only swallow directory_not_found errors for backward compatibility
            # Re-raise other ConfigError types (parse_error, validation_error, etc.)
            if getattr(e, "error_type", None) == "directory_not_found":
                __config = Config()
            else:
                raise
    return __config


def get_traceback_settings_from_env() -> TracebackSettings | None:
    """Get TracebackSettings from environment variables.

    Reads TRACE_VERBOSE environment variable and creates TracebackSettings.
    TRACE_VERBOSE can contain comma-separated values: context, locals, env
    TRACE_FORMAT can specify output format: compact, python, duplex

    Special values:
    - TRACE_VERBOSE="" (empty): Disabled (returns None)
    - TRACE_VERBOSE="off" or "false": Explicitly disabled (returns disabled settings)
    - TRACE_VERBOSE="context,locals": Enabled with specified options

    Returns:
        TracebackSettings configured from environment, or None if not set.
    """
    trace_verbose = os.environ.get('TRACE_VERBOSE', '')
    if not trace_verbose:
        return None

    if trace_verbose.lower() in ('off', 'false', 'disable', 'disabled'):
        return TracebackSettings(enabled=False)

    verbose_options = [opt.strip().lower() for opt in trace_verbose.split(',')]
    return TracebackSettings(
        enabled=True,
        include_context='context' in verbose_options,
        include_locals='locals' in verbose_options,
        include_env='env' in verbose_options,
        format=os.environ.get('TRACE_FORMAT', 'duplex'),
    )
