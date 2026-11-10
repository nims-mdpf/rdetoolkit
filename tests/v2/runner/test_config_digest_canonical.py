"""``compute_config_digest`` identifies a config by value, not by key order.

``RunReport.config_digest`` is stored in every report and is what
``repro export`` matches against, so two configs that hold the same values
must get the same digest however their free-form mappings were ordered.

Test design (equivalence partitioning / boundary values):

    Case                 | Input                                              | Expected
    ---------------------|----------------------------------------------------|---------------------------
    TC-D1-EP-001         | custom keys in different insertion orders          | same digest
    TC-D1-EP-002         | nested custom keys in different orders             | same digest
    TC-D1-EP-003         | system fields set in different orders              | same digest
    TC-D1-EP-004         | different values                                   | different digest
    TC-D1-EP-005         | list items in different orders                     | different digest (lists are ordered)
    TC-D1-EP-006         | non-ASCII custom value                             | stable, equals the canonical hash
    TC-D1-BV-001         | all defaults                                       | ``sha256:`` + 64 lowercase hex
    TC-D1-BV-002         | int 1 vs float 1.0                                 | different digest (JSON keeps them apart)
"""

from __future__ import annotations

import hashlib
import json
import re

from rdetoolkit.runner.config_loader import compute_config_digest
from rdetoolkit.types import RdeConfig


def test_custom_key_order_does_not_change_digest__tc_d1_ep_001() -> None:
    """TC-D1-EP-001: the same custom mapping in two orders is one config."""
    # Given: two configs whose custom keys were inserted in different orders
    first = RdeConfig(custom={"a": 1, "b": 2, "z": 3})
    second = RdeConfig(custom={"z": 3, "b": 2, "a": 1})
    # When / Then: their digests are equal
    assert compute_config_digest(first) == compute_config_digest(second)


def test_nested_custom_key_order_does_not_change_digest__tc_d1_ep_002() -> None:
    """TC-D1-EP-002: ordering is ignored at every depth."""
    # Given: nested mappings in different orders
    first = RdeConfig(custom={"outer": {"y": 1, "b": {"q": 1, "c": 2}}, "a": 0})
    second = RdeConfig(custom={"a": 0, "outer": {"b": {"c": 2, "q": 1}, "y": 1}})
    # When / Then: their digests are equal
    assert compute_config_digest(first) == compute_config_digest(second)


def test_field_set_order_does_not_change_digest__tc_d1_ep_003() -> None:
    """TC-D1-EP-003: the order fields were validated in is not part of identity."""
    # Given: configs built from mappings whose sections appear in different orders
    first = RdeConfig.model_validate({"system": {"save_raw": False, "save_nonshared_raw": True}, "custom": {"k": 1}})
    second = RdeConfig.model_validate({"custom": {"k": 1}, "system": {"save_nonshared_raw": True, "save_raw": False}})
    # When / Then: their digests are equal
    assert compute_config_digest(first) == compute_config_digest(second)


def test_different_values_change_digest__tc_d1_ep_004() -> None:
    """TC-D1-EP-004: a changed value is a different config."""
    # Given: configs that differ in one value
    first = RdeConfig(custom={"a": 1})
    second = RdeConfig(custom={"a": 2})
    # When / Then: their digests differ
    assert compute_config_digest(first) != compute_config_digest(second)


def test_list_order_changes_digest__tc_d1_ep_005() -> None:
    """TC-D1-EP-005: only mapping keys are normalized; list order stays meaningful."""
    # Given: configs whose list items are in different orders
    first = RdeConfig(custom={"items": [1, 2]})
    second = RdeConfig(custom={"items": [2, 1]})
    # When / Then: their digests differ
    assert compute_config_digest(first) != compute_config_digest(second)


def test_non_ascii_value_hashes_canonical_utf8_json__tc_d1_ep_006() -> None:
    """TC-D1-EP-006: the digest is sha256 over compact, key-sorted UTF-8 JSON."""
    # Given: a config with a non-ASCII value
    config = RdeConfig(custom={"名前": "試料", "a": 1})
    canonical = json.dumps(config.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    # When: the digest is computed
    digest = compute_config_digest(config)
    # Then: it is the hash of that canonical form
    assert digest == "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def test_default_config_digest_format__tc_d1_bv_001() -> None:
    """TC-D1-BV-001: the digest keeps the ``sha256:<hex>`` form reports already carry."""
    # Given / When: the digest of an all-default config
    digest = compute_config_digest(RdeConfig())
    # Then: it is sha256-prefixed lowercase hex of the right length
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", digest)


def test_int_and_float_stay_distinct__tc_d1_bv_002() -> None:
    """TC-D1-BV-002: normalization does not merge values JSON keeps apart."""
    # Given: configs holding 1 and 1.0
    first = RdeConfig(custom={"v": 1})
    second = RdeConfig(custom={"v": 1.0})
    # When / Then: their digests differ
    assert compute_config_digest(first) != compute_config_digest(second)
