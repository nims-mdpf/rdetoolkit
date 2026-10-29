"""Tests for v2 domain validation facade.

EP Table:
| API                         | Partition      | Rationale       | Expected       | Test ID   |
|-----------------------------|----------------|-----------------|----------------|-----------|
| MetadataValidator.validate  | json_obj only  | normal path     | returns dict   | TC-EP-001 |
| MetadataValidator.validate  | no input       | error path      | ValueError     | TC-EP-002 |
| metadata_validate           | missing path   | error path      | FileNotFoundError | TC-EP-003 |

BV Table:
| API                         | Boundary       | Rationale       | Expected       | Test ID   |
|-----------------------------|----------------|-----------------|----------------|-----------|
| InvoiceValidator._remove_none_values | nested None | cleanup boundary | None removed | TC-BV-001 |
"""

from __future__ import annotations

from pathlib import Path

import pytest


class TestDomainValidation:
    """Tests for validation logic moved into domain.validation."""

    def test_metadata_validator_json_obj__tc_ep_001(self) -> None:
        """TC-EP-001: MetadataValidator accepts json_obj input."""
        from rdetoolkit.domain.validation import MetadataValidator

        # Given: a minimal metadata object accepted by the v1 model
        validator = MetadataValidator()
        metadata = {"constant": {}, "variable": []}

        # When: validating an object directly
        result = validator.validate(json_obj=metadata)

        # Then: the validated object is returned
        assert result == metadata

    def test_metadata_validator_no_input_raises__tc_ep_002(self) -> None:
        """TC-EP-002: MetadataValidator rejects missing input."""
        from rdetoolkit.domain.validation import MetadataValidator

        # Given: a metadata validator
        validator = MetadataValidator()

        # When / Then: no input is invalid
        with pytest.raises(ValueError, match="At least one"):
            validator.validate()

    def test_metadata_validate_missing_path_raises__tc_ep_003(self, tmp_path: Path) -> None:
        """TC-EP-003: metadata_validate rejects missing paths."""
        from rdetoolkit.domain.validation import metadata_validate

        # Given: a missing metadata path
        metadata_path = tmp_path / "metadata.json"

        # When / Then: validation fails before schema validation
        with pytest.raises(FileNotFoundError, match="metadata.json"):
            metadata_validate(metadata_path)

    def test_remove_none_values_nested__tc_bv_001(self, tmp_path: Path) -> None:
        """TC-BV-001: InvoiceValidator removes nested None values."""
        from rdetoolkit.domain.validation import InvoiceValidator

        # Given: an InvoiceValidator instance without invoking schema loading
        validator = object.__new__(InvoiceValidator)

        # When: cleaning nested data
        result = validator._remove_none_values({"a": 1, "b": None, "c": [None, {"d": None, "e": 2}]})

        # Then: all None values are removed
        assert result == {"a": 1, "c": [{"e": 2}]}
