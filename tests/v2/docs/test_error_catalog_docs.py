"""Documentation guards for the generated v2 error catalog.

EP table
========

=================  ==================  ============================  ====================
Input              Partition           Expected                      Test ID
=================  ==================  ============================  ====================
generated catalog  required v2 codes   E2101-E2105 and W1101 present TC-DOC-ERR-EP-001
mkdocs navigation  ja and en locales   catalog linked twice          TC-DOC-ERR-EP-002
=================  ==================  ============================  ====================

BV table
========

=================  ==================  ============================  ====================
Input              Boundary            Expected                      Test ID
=================  ==================  ============================  ====================
other docs pages   zero catalog copies no handwritten catalog table TC-DOC-ERR-BV-001
=================  ==================  ============================  ====================
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[3]
CATALOG = ROOT / "docs" / "rdetoolkit" / "error_catalog.md"


def test_generated_catalog_contains_template_codes__tc_doc_err_ep_001() -> None:
    """TC-DOC-ERR-EP-001: generated docs expose every Phase F template code."""
    # Given: the generated catalog page
    text = CATALOG.read_text(encoding="utf-8")
    # When: checking the required Phase F entries
    required = {"| 2101 |", "| 2102 |", "| 2103 |", "| 2104 |", "| 2105 |", "| W1101 |"}
    # Then: all entries are present in the generated source
    assert all(entry in text for entry in required)


def test_catalog_is_in_both_locale_navs__tc_doc_err_ep_002() -> None:
    """TC-DOC-ERR-EP-002: both mkdocs locale trees link the generated catalog."""
    # Given: the bilingual mkdocs navigation
    text = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    # When: counting catalog page references
    count = text.count("rdetoolkit/error_catalog.md")
    # Then: Japanese and English each contain one navigation entry
    assert count == 2


def test_no_handwritten_catalog_table_exists__tc_doc_err_bv_001() -> None:
    """TC-DOC-ERR-BV-001: catalog tables only exist in the generated page."""
    # Given: every handwritten Markdown page under docs
    pages = [path for path in (ROOT / "docs").rglob("*.md") if path != CATALOG]
    # When: looking for the generated catalog table's canonical header
    copies = [path for path in pages if "| Code | Name | Message template |" in path.read_text(encoding="utf-8")]
    # Then: no handwritten duplicate can drift from ERROR_CATALOG
    assert copies == []
