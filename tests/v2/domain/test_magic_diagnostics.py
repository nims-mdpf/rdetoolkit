"""Source-location regressions found by independent issue #704 review.

EP/BV: D01 invalid expression at nonzero offset retains its position in preview;
D02 runtime syntax failure identifies destination and tile without source values.
"""

from pathlib import Path

import pytest

from rdetoolkit.domain.magic import MagicOptions, ResolutionContext, preview_invoice
from rdetoolkit.domain.magic_service import apply_interpolation
from rdetoolkit.errors import RdeValidationError
from tests.v2.domain.test_magic_service import _bundle


def test_preview_syntax_offset() -> None:
    """D01: Preview location agrees with the parser's source position."""
    # Given: a malformed expression after a four-character literal
    context = ResolutionContext.from_sources(original_invoice={}, current_invoice={"basic": {"dataName": "abc_${}"}})
    # When: previewing its redacted syntax diagnosis
    result = preview_invoice(context)
    # Then: offset and destination are structured, rather than only in prose
    assert result.diagnostics[0].offset == 4
    assert result.diagnostics[0].destination == "basic.dataName"
    assert result.diagnostics[0].code == 4009


def test_runtime_syntax_location(tmp_path: Path) -> None:
    """D02: Runtime syntax errors retain concrete destination and tile."""
    # Given: a tile with a malformed requested expression
    paths, snapshot = _bundle(tmp_path, "abc_${}")
    # When: running the actual filesystem boundary
    with pytest.raises(RdeValidationError) as caught:
        apply_interpolation(paths, original_invoice_snapshot=snapshot, options=MagicOptions(), iteration_index=7, mode="invoice")
    # Then: diagnostic context does not disappear during dependency scanning
    assert caught.value.code == 4009
    assert "basic.dataName" in str(caught.value)
    assert "tile 7" in str(caught.value)
    assert "offset 4" in str(caught.value)
