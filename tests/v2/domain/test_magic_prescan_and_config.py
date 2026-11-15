"""Review regressions for opt-in scanning and mutable model normalization.

EP/BV: P01 long plain eligible fields stay unchanged; P02 long expression
templates fail4005; P03 mutations inside default child models survive
normalization; P04 an invalid mutated policy is rejected rather than dropped.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rdetoolkit.config.normalize import ConfigNormalizer
from rdetoolkit.domain.magic import MagicOptions
from rdetoolkit.domain.magic_policy import options_from_config
from rdetoolkit.domain.magic_service import apply_interpolation, validate_templates
from rdetoolkit.errors import RdeValidationError
from rdetoolkit.fileops import readf_json, writef_json
from rdetoolkit.types import RdeConfig
from tests.v2.domain.test_magic_service import _bundle


@pytest.mark.parametrize("field", ["dataName", "description"])
@pytest.mark.parametrize("policy", ["auto", "enabled"])
def test_long_plain_field_does_not_opt_in(tmp_path: Path, field: str, policy: str) -> None:
    """P01: Size limits apply to templates rather than unchanged plain text."""
    # Given: a long eligible string without an expression opener
    paths, snapshot = _bundle(tmp_path, "plain")
    invoice = readf_json(paths.invoice / "invoice.json")
    invoice["basic"][field] = "x" * 16385
    writef_json(paths.invoice / "invoice.json", invoice)
    before = (paths.invoice / "invoice.json").read_bytes()
    options = MagicOptions(policy=policy)
    # When: checking static syntax and the actual artifact stage
    assert validate_templates(invoice, options) is False
    apply_interpolation(paths, original_invoice_snapshot=snapshot, options=options, iteration_index=0, mode="invoice")
    # Then: no substitution, schema rewrite, or incidental mutation occurs
    assert (paths.invoice / "invoice.json").read_bytes() == before


@pytest.mark.parametrize("field", ["dataName", "description"])
@pytest.mark.parametrize("policy", ["auto", "enabled"])
def test_long_expression_template_still_fails(field: str, policy: str) -> None:
    """P02: Sharing opt-in detection does not bypass template limits."""
    # Given: an actual expression in an oversized template
    invoice = {"basic": {field: "x" * 16385 + "${filename}"}}
    # When: checking the eligible template
    with pytest.raises(RdeValidationError) as caught:
        validate_templates(invoice, MagicOptions(policy=policy))
    # Then: bounded parsing still identifies the destination
    assert caught.value.code == 4005
    assert f"basic.{field}" in str(caught.value)


@pytest.mark.parametrize("change", ["magic", "raw", "mode", "custom"])
def test_normalization_retains_default_child_mutations(tmp_path: Path, change: str) -> None:
    """P03: Mutated child values do not depend on the parent's fields_set."""
    # Given: a default model changed through its normal mutable API
    config = RdeConfig()
    if change == "magic":
        config.system.magic_variable = False
    elif change == "raw":
        config.system.save_raw = True
    elif change == "mode":
        config.system.extended_mode = "MultiDataTile"
    else:
        config.custom["interpolation"] = {"policy": "disabled"}
    # When: normalizing that already-valid model
    normalized = ConfigNormalizer().normalize(config, root=tmp_path, origin="v2")
    # Then: values and policy-significant child provenance are preserved
    assert normalized.model_dump() == config.model_dump()
    assert options_from_config(normalized).policy == options_from_config(config).policy
    assert ("extended_mode" in normalized.system.model_fields_set) == ("extended_mode" in config.system.model_fields_set)


def test_invalid_mutated_policy_is_not_discarded(tmp_path: Path) -> None:
    """P04: A malformed child setting must not disappear into auto defaults."""
    # Given: an invalid option inserted into the default custom dictionary
    config = RdeConfig()
    config.custom["interpolation"] = {"policy": "invalid"}
    # When: normalizing and validating the effective options
    normalized = ConfigNormalizer().normalize(config, root=tmp_path, origin="v2")
    with pytest.raises(RdeValidationError) as caught:
        options_from_config(normalized)
    # Then: the invalid setting remains visible at its proper validation boundary
    assert caught.value.code == 4005
