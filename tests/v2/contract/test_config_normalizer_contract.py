"""Phase H contract for ``ConfigNormalizer``.

The future public method is fixed as
``ConfigNormalizer.normalize(source, *, root: Path, origin: Literal["v1", "v2"])``.

EP table (``config_mapping.md`` §C):

| v1 input | v2 output | Classification | Test ID |
|---|---|---|---|
| ``system.extended_mode`` | ``system.extended_mode`` | mechanical | TC-EP-G2-201 |
| six ``system`` artifact keys | same paths | mechanical | TC-EP-G2-201 |
| ``smarttable.save_table_file`` | same path | mechanical | TC-EP-G2-201 |
| ``multidata_tile.ignore_errors`` | ``execution.on_iteration_error`` | inverted mechanical | TC-EP-G2-202 |
| each of seven ``traceback`` keys | discarded with deprecation warning | deprecated | TC-EP-G2-203 |
| unknown v1 top-level key | ``custom`` | warning-backed preservation | TC-EP-G2-204 |
| unknown v2 top-level key | error 1002 | invalid | TC-EP-G2-205 |
| v1 Config / dict / v1 YAML / v2 YAML | ``RdeConfig`` | accepted origins | TC-EP-G2-206..209 |

BV table:

| Input boundary | Expected | Test ID |
|---|---|---|
| omitted v1-origin error policy | ``fail_fast`` | TC-BV-G2-201 |
| omitted v2-origin error policy | ``continue`` | TC-BV-G2-201 |
| ``extended_mode=None`` | ``invoice`` | TC-BV-G2-202 |
"""

from pathlib import Path
from typing import Any

import pytest


def _nested_value(value: object, path: str) -> object:
    """Read a dotted attribute path from a normalized model."""
    current = value
    for component in path.split("."):
        current = getattr(current, component)
    return current


@pytest.mark.parametrize(
    "source_path,source_value,target_path,expected",
    [
        pytest.param("system.extended_mode", "rdeformat", "system.extended_mode", "rdeformat", id="extended-mode"),
        pytest.param("system.save_raw", True, "system.save_raw", True, id="save-raw"),
        pytest.param(
            "system.save_nonshared_raw",
            False,
            "system.save_nonshared_raw",
            False,
            id="save-nonshared-raw",
        ),
        pytest.param(
            "system.save_thumbnail_image",
            True,
            "system.save_thumbnail_image",
            True,
            id="save-thumbnail-image",
        ),
        pytest.param("system.magic_variable", True, "system.magic_variable", True, id="magic-variable"),
        pytest.param(
            "system.save_invoice_to_structured",
            True,
            "system.save_invoice_to_structured",
            True,
            id="save-invoice-to-structured",
        ),
        pytest.param(
            "system.feature_description",
            False,
            "system.feature_description",
            False,
            id="feature-description",
        ),
        pytest.param(
            "smarttable.save_table_file",
            True,
            "smarttable.save_table_file",
            True,
            id="save-table-file",
        ),
    ],
)
def test_machine_mapped_v1_keys__tc_ep_g2_201(
    tmp_path: Path,
    source_path: str,
    source_value: object,
    target_path: str,
    expected: object,
) -> None:
    """TC-EP-G2-201: Every direct §C mapping reaches its canonical v2 field."""
    from rdetoolkit.config.normalize import ConfigNormalizer

    # Given: one mechanically convertible v1 configuration key
    section, key = source_path.split(".")
    source = {section: {key: source_value}}

    # When: normalizing the v1-origin mapping
    config = ConfigNormalizer().normalize(source, root=tmp_path, origin="v1")

    # Then: the mapped v2 field contains the source value
    assert _nested_value(config, target_path) == expected


@pytest.mark.parametrize(
    "ignore_errors,expected",
    [
        pytest.param(True, "continue", id="ignore-errors"),
        pytest.param(False, "fail_fast", id="fail-fast"),
    ],
)
def test_ignore_errors_is_inverted__tc_ep_g2_202(
    tmp_path: Path,
    ignore_errors: bool,
    expected: str,
) -> None:
    """TC-EP-G2-202: v1 ignore_errors maps to the inverse v2 policy."""
    from rdetoolkit.config.normalize import ConfigNormalizer

    # Given: an explicit v1 multidata-tile error policy
    source = {"multidata_tile": {"ignore_errors": ignore_errors}}

    # When: normalizing the v1-origin mapping
    config = ConfigNormalizer().normalize(source, root=tmp_path, origin="v1")

    # Then: the semantically equivalent v2 policy is selected
    assert config.execution.on_iteration_error == expected


@pytest.mark.parametrize(
    "key,value",
    [
        pytest.param("enabled", True, id="enabled"),
        pytest.param("format", "compact", id="format"),
        pytest.param("include_context", True, id="include-context"),
        pytest.param("include_locals", True, id="include-locals"),
        pytest.param("include_env", True, id="include-env"),
        pytest.param("max_locals_size", 1024, id="max-locals-size"),
        pytest.param("sensitive_patterns", ["TOKEN"], id="sensitive-patterns"),
    ],
)
def test_traceback_keys_warn_and_are_discarded__tc_ep_g2_203(
    tmp_path: Path,
    key: str,
    value: object,
) -> None:
    """TC-EP-G2-203: Every legacy traceback key emits migration guidance."""
    from rdetoolkit.config.normalize import ConfigNormalizer

    # Given: one of the seven legacy traceback settings
    source = {"traceback": {key: value}}

    # When: normalizing the unsupported setting
    with pytest.warns(DeprecationWarning, match=rf"traceback\.{key}.*TRACE_"):
        config = ConfigNormalizer().normalize(source, root=tmp_path, origin="v1")

    # Then: traceback settings are not admitted to the strict v2 model
    assert "traceback" not in config.model_dump()


def test_unknown_v1_key_moves_to_custom_with_warning__tc_ep_g2_204(
    tmp_path: Path,
) -> None:
    """TC-EP-G2-204: Unknown v1 keys survive in custom with an explicit warning."""
    from rdetoolkit.config.normalize import ConfigNormalizer

    # Given: a v1-origin vendor extension accepted by the legacy model
    extension = {"enabled": True}
    source = {"vendor_extension": extension}

    # When: normalizing the unknown v1 key
    with pytest.warns(UserWarning, match="vendor_extension.*custom"):
        config = ConfigNormalizer().normalize(source, root=tmp_path, origin="v1")

    # Then: the value is preserved in the explicit extension bucket
    assert config.custom["vendor_extension"] == extension


def test_unknown_v2_key_raises_e1002__tc_ep_g2_205(tmp_path: Path) -> None:
    """TC-EP-G2-205: Unknown v2-origin keys fail with catalog error 1002."""
    from rdetoolkit.config.normalize import ConfigNormalizer
    from rdetoolkit.errors import ERROR_CATALOG, RdeConfigError

    # Given: an unknown key declared as strict v2 input
    source = {"vendor_extension": {"enabled": True}}

    # When / Then: normalization rejects it with the cataloged config error
    with pytest.raises(RdeConfigError) as exc_info:
        ConfigNormalizer().normalize(source, root=tmp_path, origin="v2")
    assert exc_info.value.code == 1002
    assert ERROR_CATALOG[1002].remediation in str(exc_info.value)


def test_v1_config_model_is_accepted__tc_ep_g2_206(tmp_path: Path) -> None:
    """TC-EP-G2-206: A legacy Config model is a supported normalization source."""
    from rdetoolkit.config.normalize import ConfigNormalizer
    from rdetoolkit.models.config import Config

    # Given: a legacy Config model containing a converted artifact key
    source = Config(system={"save_raw": True})

    # When: normalizing the legacy model
    config = ConfigNormalizer().normalize(source, root=tmp_path, origin="v1")

    # Then: it produces the strict canonical model with the mapped value
    assert config.system.save_raw is True


def test_plain_mapping_is_accepted__tc_ep_g2_207(tmp_path: Path) -> None:
    """TC-EP-G2-207: A plain mapping is a supported normalization source."""
    from rdetoolkit.config.normalize import ConfigNormalizer
    from rdetoolkit.types import RdeConfig

    # Given: a plain v2-origin configuration mapping
    source = {"execution": {"type_check": "strict"}}

    # When: normalizing the mapping
    config = ConfigNormalizer().normalize(source, root=tmp_path, origin="v2")

    # Then: it produces the strict canonical model
    assert isinstance(config, RdeConfig)
    assert config.execution.type_check == "strict"


def test_v1_yml_is_discovered__tc_ep_g2_208(tmp_path: Path) -> None:
    """TC-EP-G2-208: Legacy rdeconfig.yml discovery remains supported."""
    from rdetoolkit.config.normalize import ConfigNormalizer

    # Given: a legacy-named YAML file under the normalization root
    (tmp_path / "rdeconfig.yml").write_text("system:\n  save_raw: true\n", encoding="utf-8")

    # When: normalizing an implicit v1 configuration source
    config = ConfigNormalizer().normalize(None, root=tmp_path, origin="v1")

    # Then: the legacy file is discovered and converted
    assert config.system.save_raw is True


def test_v2_yaml_is_discovered__tc_ep_g2_209(tmp_path: Path) -> None:
    """TC-EP-G2-209: Canonical rdeconfig.yaml is a supported v2 source."""
    from rdetoolkit.config.normalize import ConfigNormalizer

    # Given: a canonical v2 YAML file under the normalization root
    (tmp_path / "rdeconfig.yaml").write_text(
        "execution:\n  type_check: warn\n",
        encoding="utf-8",
    )

    # When: normalizing an implicit v2 configuration source
    config = ConfigNormalizer().normalize(None, root=tmp_path, origin="v2")

    # Then: canonical fields are loaded without legacy conversion
    assert config.execution.type_check == "warn"


@pytest.mark.parametrize(
    "origin,expected",
    [
        pytest.param("v1", "fail_fast", id="v1-origin"),
        pytest.param("v2", "continue", id="v2-origin"),
    ],
)
def test_error_policy_default_depends_on_origin__tc_bv_g2_201(
    tmp_path: Path,
    origin: str,
    expected: str,
) -> None:
    """TC-BV-G2-201: Omitted error policy preserves each API's default."""
    from rdetoolkit.config.normalize import ConfigNormalizer

    # Given: an empty configuration from a known input origin
    # When: normalizing without an explicit iteration error policy
    config = ConfigNormalizer().normalize({}, root=tmp_path, origin=origin)

    # Then: v1 is fail-fast while v2 continues
    assert config.execution.on_iteration_error == expected


def test_none_extended_mode_becomes_invoice__tc_bv_g2_202(tmp_path: Path) -> None:
    """TC-BV-G2-202: The legacy None mode normalizes to canonical invoice."""
    from rdetoolkit.config.normalize import ConfigNormalizer

    # Given: the v1 boundary value for an unspecified extended mode
    source: dict[str, Any] = {"system": {"extended_mode": None}}

    # When: normalizing the legacy value
    config = ConfigNormalizer().normalize(source, root=tmp_path, origin="v1")

    # Then: the strict v2 model receives its canonical mode string
    assert config.system.extended_mode == "invoice"
