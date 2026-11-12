"""#629: ``read_key_values`` reads a tasksupport ``key,value`` CSV into a dict.

v1 templates read ``tasksupport/default_value.csv`` with
``rde2util.get_default_values``. The node is its call-logged v2 form: with the
default options it returns exactly what the v1 helper returns. The node raises
builtin exceptions (no StructuredError catalog code), like the other read nodes.

EP table
========

===============  ==============================  ======================================  ============
API              Partition                       Expected                                Test ID
===============  ==============================  ======================================  ============
read_key_values  UTF-8 / UTF-8-SIG defaults      equals get_default_values (v1)          629-EP-001
read_key_values  detected Shift-JIS              decoded, equals get_default_values      629-EP-002
read_key_values  explicit encoding               used instead of detection               629-EP-003
read_key_values  custom key / value columns      other columns ignored                   629-EP-004
read_key_values  numeric / boolean / empty text  values stay strings                     629-EP-005
read_key_values  defaults merged for build_meta  measured value wins, schema cast        629-EP-006
read_key_values  registry                        builtin + io tags                       629-EP-007
read_key_values  missing file, missing_ok=True   empty dict                              629-EP-008
read_key_values  missing file (default)          FileNotFoundError                       629-EP-009
read_key_values  key column absent               ValueError naming column and header     629-EP-010
read_key_values  value column absent             ValueError naming column and header     629-EP-011
read_key_values  custom key column absent        ValueError naming the custom column     629-EP-012
read_key_values  unknown encoding name           LookupError                             629-EP-013
read_key_values  wrong explicit encoding         UnicodeDecodeError                      629-EP-014
read_key_values  directory, missing_ok=True      IsADirectoryError (only absence is ok)  629-EP-015
===============  ==============================  ======================================  ============

BV table
========

===============  ==============================  ======================================  ============
API              Boundary                        Expected                                Test ID
===============  ==============================  ======================================  ============
read_key_values  short, mostly ASCII Shift-JIS   read with encoding="cp932"              629-BV-001
read_key_values  header row only                 empty dict                              629-BV-002
read_key_values  repeated key                    last value kept (v1 dict assignment)    629-BV-003
read_key_values  0-byte file                     ValueError, empty header                629-BV-004
read_key_values  row with no value cell          ValueError naming the line              629-BV-005
read_key_values  malformed file, missing_ok      ValueError (missing_ok does not hide)   629-BV-006
read_key_values  BOM read as explicit utf-8      ValueError, BOM left in header          629-BV-007
read_key_values  row with no key cell            ValueError naming the line              629-BV-008
===============  ==============================  ======================================  ============
"""
from __future__ import annotations

from pathlib import Path

import pytest

from rdetoolkit import rde2util
from rdetoolkit.core import registry
from rdetoolkit.nodes import build_meta, read_key_values

_DEFAULTS = "key,value\ncommon.data_origin,experiments\nmeasurement.method_category,分光法\n"
_EXPECTED = {"common.data_origin": "experiments", "measurement.method_category": "分光法"}
_JAPANESE = "key,value\nmeasurement.method,X線光電子分光法\nmeasurement.instrument,走査型電子顕微鏡\nnote,特になし\n"


def _write(path: Path, text: str, encoding: str) -> Path:
    path.write_bytes(text.encode(encoding))
    return path


class TestReadKeyValuesNormal:
    @pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig"])
    def test_default_options_match_v1__629_ep_001(self, tmp_path: Path, encoding: str) -> None:
        """629-EP-001: UTF-8 defaults equal the v1 get_default_values result."""
        # Given: a default_value.csv in a UTF-8 encoding
        source = _write(tmp_path / "default_value.csv", _DEFAULTS, encoding)
        # When: reading it with the default options
        result = read_key_values(source)
        # Then: the result is the expected dict and the v1 helper's result
        assert result == _EXPECTED
        assert result == rde2util.get_default_values(source)

    def test_detected_shift_jis_matches_v1__629_ep_002(self, tmp_path: Path) -> None:
        """629-EP-002: a Shift-JIS file with enough Japanese text is detected like v1."""
        # Given: a Shift-JIS file with several Japanese values
        source = _write(tmp_path / "default_value.csv", _JAPANESE, "cp932")
        # When: reading it with encoding detection
        result = read_key_values(source)
        # Then: the text decodes and matches the v1 helper
        assert result["measurement.method"] == "X線光電子分光法"
        assert result == rde2util.get_default_values(source)

    def test_explicit_encoding_is_used__629_ep_003(self, tmp_path: Path) -> None:
        """629-EP-003: an explicit encoding replaces detection."""
        # Given: a Shift-JIS file
        source = _write(tmp_path / "default_value.csv", _JAPANESE, "cp932")
        # When: reading it with encoding="cp932"
        result = read_key_values(source, encoding="cp932")
        # Then: the values decode as written
        assert result["note"] == "特になし"

    def test_custom_columns__629_ep_004(self, tmp_path: Path) -> None:
        """629-EP-004: key= and value= choose the columns; others are ignored."""
        # Given: a three-column CSV with differently named columns
        source = _write(tmp_path / "params.csv", "name,unit,setting\ntemp,K,300\nmode,,スキャン\n", "utf-8")
        # When: reading it with custom column names
        result = read_key_values(source, key="name", value="setting")
        # Then: only the chosen columns form the dict
        assert result == {"temp": "300", "mode": "スキャン"}

    def test_values_stay_strings__629_ep_005(self, tmp_path: Path) -> None:
        """629-EP-005: numeric, boolean and empty cells are not converted."""
        # Given: values that look like numbers, booleans and an empty cell
        source = _write(tmp_path / "default_value.csv", "key,value\ncount,3\nflag,true\nempty,\n", "utf-8")
        # When: reading the file
        result = read_key_values(source)
        # Then: every value is the cell text
        assert result == {"count": "3", "flag": "true", "empty": ""}

    def test_output_feeds_build_meta__629_ep_006(self, tmp_path: Path) -> None:
        """629-EP-006: defaults merged under measured values reach build_meta."""
        # Given: defaults for two keys and a measured value for one of them
        source = _write(tmp_path / "default_value.csv", "key,value\norigin,experiments\ncount,3\n", "utf-8")
        metadef = {
            "origin": {"name": {"ja": "由来", "en": "origin"}, "schema": {"type": "string"}},
            "count": {"name": {"ja": "回数", "en": "count"}, "schema": {"type": "integer"}},
        }
        # When: building metadata from the merged values
        metadata = build_meta({**read_key_values(source), "count": "5"}, metadef)
        # Then: the default fills origin and the measured count wins, cast to int
        assert metadata.custom == {"origin": "experiments", "count": 5}

    def test_registered_as_builtin_io_node__629_ep_007(self) -> None:
        """629-EP-007: the node is registered with the builtin and io tags."""
        # Given: the builtin nodes imported through rdetoolkit.nodes
        # When: looking up the node spec in the registry
        spec = next(spec for spec in registry.list_nodes() if spec.id.endswith("read_key_values"))
        # Then: it carries the builtin io tags
        assert {"builtin", "io"} <= set(spec.tags)

    def test_missing_file_with_missing_ok__629_ep_008(self, tmp_path: Path) -> None:
        """629-EP-008: missing_ok=True turns an absent file into an empty dict."""
        # Given: a path that does not exist
        source = tmp_path / "default_value.csv"
        # When: reading it with missing_ok=True
        result = read_key_values(source, missing_ok=True)
        # Then: the result is empty
        assert result == {}

    def test_short_shift_jis_with_explicit_encoding__629_bv_001(self, tmp_path: Path) -> None:
        """629-BV-001: a short, mostly ASCII Shift-JIS file reads with encoding="cp932"."""
        # Given: a short Shift-JIS file that chardet can misdetect (in v1 too)
        source = _write(tmp_path / "default_value.csv", _DEFAULTS, "cp932")
        # When: reading it with the encoding named
        result = read_key_values(source, encoding="cp932")
        # Then: the Japanese value decodes correctly
        assert result == _EXPECTED

    def test_header_only__629_bv_002(self, tmp_path: Path) -> None:
        """629-BV-002: a header row without data rows gives an empty dict."""
        # Given: a file with the header only
        source = _write(tmp_path / "default_value.csv", "key,value\n", "utf-8")
        # When: reading it
        result = read_key_values(source)
        # Then: the result is empty
        assert result == {}

    def test_repeated_key_keeps_last_value__629_bv_003(self, tmp_path: Path) -> None:
        """629-BV-003: a repeated key keeps its last value, as in v1."""
        # Given: the same key on two rows
        source = _write(tmp_path / "default_value.csv", "key,value\na,1\na,2\n", "utf-8")
        # When: reading it
        result = read_key_values(source)
        # Then: the later row wins, like the v1 helper
        assert result == {"a": "2"}
        assert result == rde2util.get_default_values(source)


class TestReadKeyValuesErrors:
    def test_missing_file_raises__629_ep_009(self, tmp_path: Path) -> None:
        """629-EP-009: an absent file raises FileNotFoundError by default."""
        # Given: a path that does not exist
        source = tmp_path / "default_value.csv"
        # When / Then: reading it raises FileNotFoundError
        with pytest.raises(FileNotFoundError):
            read_key_values(source)

    def test_key_column_absent__629_ep_010(self, tmp_path: Path) -> None:
        """629-EP-010: a header without the key column raises ValueError."""
        # Given: a header that names the key column differently
        source = _write(tmp_path / "default_value.csv", "name,value\na,1\n", "utf-8")
        # When / Then: the error names the column and the header found
        with pytest.raises(ValueError, match=r"column 'key' not in the header .*\['name', 'value'\]"):
            read_key_values(source)

    def test_value_column_absent__629_ep_011(self, tmp_path: Path) -> None:
        """629-EP-011: a header without the value column raises ValueError."""
        # Given: a header that names the value column differently
        source = _write(tmp_path / "default_value.csv", "key,setting\na,1\n", "utf-8")
        # When / Then: the error names the value column
        with pytest.raises(ValueError, match=r"column 'value' not in the header .*\['key', 'setting'\]"):
            read_key_values(source)

    def test_custom_key_column_absent__629_ep_012(self, tmp_path: Path) -> None:
        """629-EP-012: a custom key column missing from the header raises ValueError."""
        # Given: a default-header file and a custom key column name
        source = _write(tmp_path / "default_value.csv", _DEFAULTS, "utf-8")
        # When / Then: the error names the custom column
        with pytest.raises(ValueError, match=r"column 'name' not in the header"):
            read_key_values(source, key="name")

    def test_unknown_encoding__629_ep_013(self, tmp_path: Path) -> None:
        """629-EP-013: an unknown encoding name raises LookupError."""
        # Given: a valid file
        source = _write(tmp_path / "default_value.csv", _DEFAULTS, "utf-8")
        # When / Then: naming a codec that does not exist raises LookupError
        with pytest.raises(LookupError):
            read_key_values(source, encoding="no-such-codec")

    def test_wrong_explicit_encoding__629_ep_014(self, tmp_path: Path) -> None:
        """629-EP-014: an explicit encoding that does not fit the bytes is not hidden."""
        # Given: a Shift-JIS file
        source = _write(tmp_path / "default_value.csv", _JAPANESE, "cp932")
        # When / Then: reading it as UTF-8 raises UnicodeDecodeError
        with pytest.raises(UnicodeDecodeError):
            read_key_values(source, encoding="utf-8")

    def test_directory_with_missing_ok__629_ep_015(self, tmp_path: Path) -> None:
        """629-EP-015: missing_ok covers only an absent path, not a directory."""
        # Given: a directory at the CSV path
        source = tmp_path / "default_value.csv"
        source.mkdir()
        # When / Then: reading it with missing_ok=True still raises
        with pytest.raises(IsADirectoryError):
            read_key_values(source, encoding="utf-8", missing_ok=True)

    def test_zero_byte_file__629_bv_004(self, tmp_path: Path) -> None:
        """629-BV-004: a 0-byte file has no header and raises ValueError."""
        # Given: an empty file
        source = _write(tmp_path / "default_value.csv", "", "utf-8")
        # When / Then: the error reports the empty header
        with pytest.raises(ValueError, match=r"column 'key' not in the header .*\[\]"):
            read_key_values(source)

    def test_row_without_value_cell__629_bv_005(self, tmp_path: Path) -> None:
        """629-BV-005: a row without a value cell raises ValueError naming its line."""
        # Given: the third line has only a key cell
        source = _write(tmp_path / "default_value.csv", "key,value\na,1\nb\n", "utf-8")
        # When / Then: the error names line 3
        with pytest.raises(ValueError, match=r"line 3 has no 'key'/'value' cell"):
            read_key_values(source)

    def test_row_without_key_cell__629_bv_008(self, tmp_path: Path) -> None:
        """629-BV-008: a row that ends before the key column raises ValueError."""
        # Given: the key column comes second and line 2 has only the value cell
        source = _write(tmp_path / "default_value.csv", "value,key\n1\n", "utf-8")
        # When / Then: the error names line 2
        with pytest.raises(ValueError, match=r"line 2 has no 'key'/'value' cell"):
            read_key_values(source)

    def test_malformed_file_with_missing_ok__629_bv_006(self, tmp_path: Path) -> None:
        """629-BV-006: missing_ok does not hide a malformed existing file."""
        # Given: an existing file without the key column
        source = _write(tmp_path / "default_value.csv", "name,value\na,1\n", "utf-8")
        # When / Then: reading it with missing_ok=True still raises ValueError
        with pytest.raises(ValueError, match=r"column 'key'"):
            read_key_values(source, missing_ok=True)

    def test_bom_read_as_plain_utf8__629_bv_007(self, tmp_path: Path) -> None:
        """629-BV-007: explicit utf-8 keeps the BOM in the first header cell."""
        # Given: a UTF-8-SIG file read with encoding="utf-8" instead of detection
        source = _write(tmp_path / "default_value.csv", _DEFAULTS, "utf-8-sig")
        # When / Then: the BOM stays in the first header cell, so the key column is absent
        with pytest.raises(ValueError, match=r"column 'key' not in the header .*\\ufeffkey"):
            read_key_values(source, encoding="utf-8")
