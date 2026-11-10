"""GA587: the #570 ``Meta.assign_vals`` change is an intentional v1 difference.

EP table
| Guide | Partition | Expected | Test ID |
|---|---|---|---|
| ja / en | intentional-differences table | one ``Meta.assign_vals`` ``None`` row citing #570 | GA587-EP-1 |
| ja / en | text after the table | 1.7.1 is the v1 column; no 1.7.x carries the fix yet | GA587-EP-2 |
| public API | ``None`` value / ``None`` unit source | key / unit omitted, file written | GA587-EP-3 |

BV / negative table
| Case | Expected | Test ID |
|---|---|---|
| row is outside the table (other section) | not counted | GA587-NEG-1 |
| non-``None`` unconvertible value | ``StructuredError`` with ecode 1, as the row says | GA587-NEG-2 |
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from rdetoolkit.exceptions import StructuredError
from rdetoolkit.rde2util import Meta

DOCS_DIR = Path(__file__).resolve().parents[3] / "docs"
GUIDES = {"ja": DOCS_DIR / "migration_v1_to_v2.md", "en": DOCS_DIR / "migration_v1_to_v2.en.md"}
HEADINGS = {"ja": "### 意図的な差分", "en": "### Intentional differences"}


def _section(language: str) -> str:
    text = GUIDES[language].read_text(encoding="utf-8")
    start = text.index(HEADINGS[language])
    end = text.index("\n### ", start + 1)
    return text[start:end]


def _table_rows(section: str) -> list[str]:
    return [line for line in section.splitlines() if line.startswith("| ")]


@pytest.mark.parametrize("language", ["ja", "en"])
def test_table_lists_assign_vals_none__ga587_ep_1(language: str) -> None:
    """GA587-EP-1: each guide's table has exactly one #570 row with both outcomes."""
    # Given: the intentional-differences table of one guide
    rows = _table_rows(_section(language))
    # When: selecting the rows about Meta.assign_vals
    matches = [row for row in rows if "Meta.assign_vals" in row]
    # Then: one three-column row cites #570 and states the v1 and v2 outcomes
    assert len(matches) == 1
    row = matches[0]
    assert "#570" in row
    assert "`None`" in row
    assert row.count(" | ") == 2
    assert "ErrorCode=1" in row
    assert "`metadata.json`" in row
    assert '"None"' in row


@pytest.mark.parametrize("language", ["ja", "en"])
def test_note_states_17_line_status__ga587_ep_2(language: str) -> None:
    """GA587-EP-2: the note pins the v1 column to 1.7.1 and the 1.7.x status."""
    # Given: the prose that follows the table
    section = _section(language)
    note = section[section.rindex("| ") :]
    # When / Then: the note names the oracle release and the unreleased 1.7.x line
    assert "1.7.1" in note
    assert "1.7.x" in note
    assert "Meta.assign_vals" in note


@pytest.mark.parametrize("language", ["ja", "en"])
def test_row_outside_table_is_not_counted__ga587_neg_1(language: str) -> None:
    """GA587-NEG-1: only the intentional-differences section supplies the row."""
    # Given: the behaviour-change section that precedes the table
    text = GUIDES[language].read_text(encoding="utf-8")
    before = text[: text.index(HEADINGS[language])]
    # When / Then: the #570 row is not misplaced there
    assert "Meta.assign_vals" not in before


def test_documented_v2_outcome_holds__ga587_ep_3(tmp_path: Path) -> None:
    """GA587-EP-3: the v2 column matches the public Tier 1 API."""
    # Given: a typed field, a string field and a referenced unit, all receiving None
    definition = tmp_path / "metadata-def.json"
    definition.write_text(
        json.dumps(
            {
                "x": {"schema": {"type": "number"}},
                "s": {"schema": {"type": "string"}},
                "y": {"schema": {"type": "number"}, "unit": "$unit"},
            },
        ),
        encoding="utf-8",
    )
    metadata = Meta(definition)
    # When: assigning and writing
    metadata.assign_vals({"x": None, "s": None, "y": 3, "unit": None})
    destination = tmp_path / "metadata.json"
    metadata.writefile(str(destination))
    # Then: the None keys and the None unit are omitted, the file is written
    assert json.loads(destination.read_text(encoding="utf-8")) == {"constant": {"y": {"value": 3}}, "variable": []}


def test_unconvertible_value_still_fails__ga587_neg_2(tmp_path: Path) -> None:
    """GA587-NEG-2: the row's ErrorCode=1 caveat for non-None values holds."""
    # Given: a numeric definition
    definition = tmp_path / "metadata-def.json"
    definition.write_text('{"x": {"schema": {"type": "number"}}}', encoding="utf-8")
    metadata = Meta(definition)
    # When: assigning a non-None value that cannot be cast
    with pytest.raises(StructuredError) as raised:
        metadata.assign_vals({"x": "abc"})
    # Then: the existing cast error and code remain
    assert raised.value.ecode == 1
    assert re.search(r"failed to cast metaDef value", str(raised.value))
