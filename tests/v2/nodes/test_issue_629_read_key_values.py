"""Tests for the ``read_key_values`` builtin node (#629).

v1 templates read ``tasksupport/default_value.csv`` (``key,value`` rows) with
``rde2util.get_default_values``. The node is its call-logged v2 form: with the
default options it returns exactly what the v1 helper returns.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from rdetoolkit import rde2util
from rdetoolkit.core import registry
from rdetoolkit.nodes import build_meta, read_key_values

_DEFAULTS = "key,value\ncommon.data_origin,experiments\nmeasurement.method_category,分光法\n"


def _write(path: Path, text: str, encoding: str) -> Path:
    path.write_bytes(text.encode(encoding))
    return path


_EXPECTED = {"common.data_origin": "experiments", "measurement.method_category": "分光法"}


_JAPANESE = "key,value\nmeasurement.method,X線光電子分光法\nmeasurement.instrument,走査型電子顕微鏡\nnote,特になし\n"


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig"])
def test_default_options_match_v1_get_default_values(tmp_path: Path, encoding: str) -> None:
    source = _write(tmp_path / "default_value.csv", _DEFAULTS, encoding)

    result = read_key_values(source)

    assert result == _EXPECTED
    assert result == rde2util.get_default_values(source)


def test_detected_shift_jis_matches_v1(tmp_path: Path) -> None:
    source = _write(tmp_path / "default_value.csv", _JAPANESE, "cp932")

    result = read_key_values(source)

    assert result["measurement.method"] == "X線光電子分光法"
    assert result == rde2util.get_default_values(source)


def test_short_shift_jis_file_reads_with_explicit_encoding(tmp_path: Path) -> None:
    # chardet can misdetect this mostly ASCII file, in v1 and here.
    source = _write(tmp_path / "default_value.csv", _DEFAULTS, "cp932")

    assert read_key_values(source, encoding="cp932") == _EXPECTED


def test_custom_columns_and_explicit_encoding(tmp_path: Path) -> None:
    source = _write(tmp_path / "params.csv", "name,unit,setting\ntemp,K,300\nmode,,スキャン\n", "cp932")

    result = read_key_values(source, key="name", value="setting", encoding="cp932")

    assert result == {"temp": "300", "mode": "スキャン"}


def test_values_stay_strings(tmp_path: Path) -> None:
    source = _write(tmp_path / "default_value.csv", "key,value\ncount,3\nflag,true\nempty,\n", "utf-8")

    assert read_key_values(source) == {"count": "3", "flag": "true", "empty": ""}


def test_missing_file_raises_by_default(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_key_values(tmp_path / "default_value.csv")


def test_missing_file_returns_empty_dict_with_missing_ok(tmp_path: Path) -> None:
    assert read_key_values(tmp_path / "default_value.csv", missing_ok=True) == {}


def test_missing_column_names_the_column(tmp_path: Path) -> None:
    source = _write(tmp_path / "default_value.csv", "name,value\na,1\n", "utf-8")

    with pytest.raises(ValueError, match=r"'key'.*\['name', 'value'\]"):
        read_key_values(source)


def test_row_without_value_cell_is_rejected(tmp_path: Path) -> None:
    source = _write(tmp_path / "default_value.csv", "key,value\na,1\nb\n", "utf-8")

    with pytest.raises(ValueError, match="line 3"):
        read_key_values(source)


def test_output_feeds_build_meta(tmp_path: Path) -> None:
    source = _write(tmp_path / "default_value.csv", "key,value\norigin,experiments\ncount,3\n", "utf-8")
    metadef = {
        "origin": {"name": {"ja": "由来", "en": "origin"}, "schema": {"type": "string"}},
        "count": {"name": {"ja": "回数", "en": "count"}, "schema": {"type": "integer"}},
    }

    metadata = build_meta({**read_key_values(source), "count": "5"}, metadef)

    assert metadata.custom == {"origin": "experiments", "count": 5}


def test_registered_as_builtin_io_node() -> None:
    spec = next(spec for spec in registry.list_nodes() if spec.id.endswith("read_key_values"))

    assert {"builtin", "io"} <= set(spec.tags)
