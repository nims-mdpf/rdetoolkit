"""Production config discovery (Session I-REVIEW-A, ruling #4 / review F2).

A real RDE structured program ships its configuration as
``data/tasksupport/rdeconfig.yaml``. The v2 entry point searched only
``<root>/rdeconfig.yaml`` and ``<root>/pyproject.toml``, so every such program
silently ran with ``RdeConfig()`` defaults — no ``save_raw``, no thumbnails, a
different error policy. The canary parity tests hid the gap by injecting the
recorded effective config as overrides.

Discovery is now: ``<root>/rdeconfig.yaml`` -> ``<root>/pyproject.toml`` (v2
form) -> ``<data_root>/tasksupport/{rdeconfig.yaml, rdeconfig.yml,
pyproject.toml}`` (v1 form, read with the **v1 loader** and converted through
``ConfigNormalizer(origin="v1")``).

EP table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-IRA-4-EP-060 | v1 layout | ``data/tasksupport/rdeconfig.yaml`` | its values reach the Runner |
| TC-IRA-4-EP-061 | precedence | both root and tasksupport configs | the root v2 file wins |
| TC-IRA-4-EP-062 | alias-flat | ``<root>/tasksupport/rdeconfig.yaml`` | found through the resolved data root |
| TC-IRA-4-EP-063 | extensions | ``rdeconfig.yml`` / ``pyproject.toml`` | both are discovered |

BV / negative table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-IRA-4-EV-064 | nothing | no config anywhere | canonical v2 defaults, ``continue`` |
| TC-IRA-4-EV-065 | v1 default | a tasksupport config | ``execution.on_iteration_error`` is ``fail_fast`` |
| TC-IRA-4-EV-066 | unknown keys | v1 keys outside the v1 contract | preserved under ``custom`` |
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from rdetoolkit.runner.config_loader import load_config
from rdetoolkit.types import RdeConfig


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")


def test_tasksupport_config_reaches_the_runner__tc_ira_4_ep_060(tmp_path: Path) -> None:
    """TC-IRA-4-EP-060: the layout every real structured program ships is read."""
    # Given: a project root whose only configuration is the v1 tasksupport file
    _write(
        tmp_path / "data" / "tasksupport" / "rdeconfig.yaml",
        """
        system:
          save_raw: true
          save_nonshared_raw: false
          save_thumbnail_image: true
        """,
    )

    # When: the Runner loads its configuration for that data root
    config = load_config(tmp_path, data_root=tmp_path / "data")

    # Then: the program's own switches are in force
    assert config.system.save_raw is True
    assert config.system.save_nonshared_raw is False
    assert config.system.save_thumbnail_image is True


def test_root_v2_config_wins_over_tasksupport__tc_ira_4_ep_061(tmp_path: Path) -> None:
    """TC-IRA-4-EP-061: an explicit v2 file at the root keeps precedence."""
    # Given: a v2 config at the root and a v1 config in tasksupport
    _write(
        tmp_path / "rdeconfig.yaml",
        """
        system:
          save_raw: false
        """,
    )
    _write(
        tmp_path / "data" / "tasksupport" / "rdeconfig.yaml",
        """
        system:
          save_raw: true
        """,
    )

    # When: the Runner loads its configuration
    config = load_config(tmp_path, data_root=tmp_path / "data")

    # Then: the root file decides, and no v1 default leaks in
    assert config.system.save_raw is False
    assert config.execution.on_iteration_error == "continue"


def test_alias_flat_root_finds_its_tasksupport__tc_ira_4_ep_062(tmp_path: Path) -> None:
    """TC-IRA-4-EP-062: discovery follows the single resolved data root."""
    # Given: an alias-flat root, whose tasksupport sits directly below it
    _write(
        tmp_path / "tasksupport" / "rdeconfig.yaml",
        """
        system:
          save_thumbnail_image: true
        """,
    )

    # When: the Runner loads its configuration for that root as the data root
    config = load_config(tmp_path, data_root=tmp_path)

    # Then: the alias-flat program's configuration is honored
    assert config.system.save_thumbnail_image is True


@pytest.mark.parametrize(
    ("filename", "content"),
    [
        pytest.param(
            "rdeconfig.yml",
            "system:\n  save_thumbnail_image: true\n",
            id="TC-IRA-4-EP-063-yml",
        ),
        pytest.param(
            "pyproject.toml",
            "[tool.rdetoolkit.system]\nsave_thumbnail_image = true\n",
            id="TC-IRA-4-EP-063-toml",
        ),
    ],
)
def test_every_v1_filename_is_discovered__tc_ira_4_ep_063(
    filename: str,
    content: str,
    tmp_path: Path,
) -> None:
    """TC-IRA-4-EP-063: the v1 loader's whole filename set is searched."""
    # Given: a tasksupport directory holding one of the accepted filenames
    _write(tmp_path / "data" / "tasksupport" / filename, content)

    # When: the Runner loads its configuration
    config = load_config(tmp_path, data_root=tmp_path / "data")

    # Then: the file is found and interpreted by the v1 loader
    assert config.system.save_thumbnail_image is True


def test_no_configuration_keeps_the_v2_defaults__tc_ira_4_ev_064(tmp_path: Path) -> None:
    """TC-IRA-4-EV-064: discovery must not invent a config where none exists."""
    # Given: a project root with no configuration file at all
    (tmp_path / "data" / "tasksupport").mkdir(parents=True)

    # When: the Runner loads its configuration
    config = load_config(tmp_path, data_root=tmp_path / "data")

    # Then: the canonical v2 defaults apply, including the v2 error policy
    assert config == RdeConfig()
    assert config.execution.on_iteration_error == "continue"


def test_tasksupport_config_seeds_the_v1_error_policy__tc_ira_4_ev_065(tmp_path: Path) -> None:
    """TC-IRA-4-EV-065: a v1-form config brings v1's fail-fast default with it.

    ``ConfigNormalizer._convert_v1`` seeds ``execution.on_iteration_error`` with
    ``fail_fast`` because that is v1's behavior when ``multidata_tile.ignore_errors``
    is unset. Discovering a v1 file therefore also adopts v1's policy; this is
    contracted, not accidental.
    """
    # Given: a tasksupport config that says nothing about error handling
    _write(
        tmp_path / "data" / "tasksupport" / "rdeconfig.yaml",
        """
        system:
          save_raw: true
        """,
    )

    # When: the Runner loads its configuration
    config = load_config(tmp_path, data_root=tmp_path / "data")

    # Then: the v1 default policy travels with the v1 file
    assert config.execution.on_iteration_error == "fail_fast"


def test_ignore_errors_still_projects_to_continue__tc_ira_4_ev_065b(tmp_path: Path) -> None:
    """TC-IRA-4-EV-065b: an explicit v1 ``ignore_errors`` still decides."""
    # Given: a tasksupport config that asks v1 to keep going
    _write(
        tmp_path / "data" / "tasksupport" / "rdeconfig.yaml",
        """
        system:
          save_raw: true
        multidata_tile:
          ignore_errors: true
        """,
    )

    # When: the Runner loads its configuration
    config = load_config(tmp_path, data_root=tmp_path / "data")

    # Then: the v1 flag projects onto the v2 policy
    assert config.execution.on_iteration_error == "continue"


def test_unknown_v1_keys_are_preserved__tc_ira_4_ev_066(tmp_path: Path) -> None:
    """TC-IRA-4-EV-066: the v1 loader's interpretation is not narrowed here."""
    # Given: a tasksupport config carrying a key outside the v1 contract
    _write(
        tmp_path / "data" / "tasksupport" / "rdeconfig.yaml",
        """
        system:
          save_raw: true
        vendor_extension:
          answer: 42
        """,
    )

    # When: the Runner loads its configuration
    with pytest.warns(UserWarning, match="vendor_extension"):
        config = load_config(tmp_path, data_root=tmp_path / "data")

    # Then: the unknown section survives under custom, as origin="v1" defines
    assert config.custom["vendor_extension"] == {"answer": 42}
