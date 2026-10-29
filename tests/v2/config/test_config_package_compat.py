"""Compatibility tests for relocating ``rdetoolkit.config`` to a package.

EP table:

| API | Partition | Expected | Test ID |
|---|---|---|---|
| ``rdetoolkit.config`` | every former stub declaration | importable | TC-EP-H1-001 |

BV table:

| Boundary | Expected | Test ID |
|---|---|---|
| constants, models, and functions | all three declaration kinds remain | TC-BV-H1-001 |
"""

import rdetoolkit.config as config


def test_former_config_stub_surface_remains_importable__tc_ep_h1_001() -> None:
    """TC-EP-H1-001/TC-BV-H1-001: The complete former stub surface remains public."""
    # Given: every declaration from the pre-relocation config.pyi
    public_names = (
        "CONFIG_FILE",
        "PYPROJECT_CONFIG_FILES",
        "CONFIG_FILES",
        "Config",
        "MultiDataTileSettings",
        "SmartTableSettings",
        "SystemSettings",
        "TracebackSettings",
        "RdeFsPath",
        "parse_config_file",
        "is_toml",
        "is_yaml",
        "find_config_files",
        "get_pyproject_toml",
        "get_config",
        "load_config",
        "get_traceback_settings_from_env",
    )

    # When: resolving each name from the relocated package
    resolved = {name: getattr(config, name) for name in public_names}

    # Then: constants, model aliases, and functions all remain importable
    assert set(resolved) == set(public_names)
    assert all(value is not None for value in resolved.values())
