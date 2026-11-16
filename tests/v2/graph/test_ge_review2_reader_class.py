"""Fix round 2 / F3: a reader plugin published as a class is instantiated before use.

A class object with class-level ``reader_id`` / ``extensions`` / ``read`` (or with
properties) passes the runtime-checkable ``TableReader`` check, so it used to be
returned as the reader itself and failed later. Rule: a loaded class is called with
no arguments first (constructor failure -> ``ReaderPluginError`` naming the entry
point, chained); an instance is used as is; a non-class zero-argument factory is
called as before.

EP table:
| TC | Partition | Entry-point target | Expected |
|----|-----------|--------------------|----------|
| TC-FIX2-F3-EP-001 | class with class attributes | ``:ClassAttrReader`` | instance built, read_table returns its table |
| TC-FIX2-F3-EP-002 | class with properties and defaulted args | vendor ``:InstrumentReader`` | instance built, reads the vendor frame |
| TC-FIX2-F3-EP-003 | instance (unchanged) | vendor ``:READER`` | that very object is used |
| TC-FIX2-F3-EP-004 | non-class zero-arg factory (unchanged) | vendor ``:make_reader`` | factory result used |

Negative table:
| TC | Partition | Entry-point target | Expected |
|----|-----------|--------------------|----------|
| TC-FIX2-F3-NEG-001 | class whose __init__ raises | ``:FailingInitReader`` | ReaderPluginError naming the entry point, __cause__ RuntimeError |
| TC-FIX2-F3-NEG-002 | class requiring arguments | ``:NeedsArgsReader`` | ReaderPluginError, __cause__ TypeError |
| TC-FIX2-F3-NEG-003 | class whose instance is not a reader | ``:NotAReaderClass`` | ReaderPluginError "not a TableReader" |
| TC-FIX2-F3-NEG-004 | class whose id differs from the entry-point name | ``:ClassAttrReader`` as "other" | ReaderPluginError "must equal the reader id" |
| TC-FIX2-F3-NEG-005 | two class entry points with one name (unchanged) | ``:ClassAttrReader`` twice | DuplicateReaderError naming both targets |
"""

from __future__ import annotations

from importlib.metadata import EntryPoint
from pathlib import Path

import pandas as pd
import pytest

from rdetoolkit.graph import ColumnProvenance, DuplicateReaderError, ReaderPluginError, TableData, discover_readers, read_table
from rdetoolkit.graph.readers import READER_ENTRY_POINT_GROUP, registry
from tests.v2.graph.fixtures.reader_plugin_pkg import vendor

HERE = "tests.v2.graph.test_ge_review2_reader_class"
VENDOR = "tests.v2.graph.fixtures.reader_plugin_pkg.vendor"
FIXTURES = Path(__file__).parent / "fixtures"


class ClassAttrReader:
    """Reader whose protocol members are class attributes (the class passes isinstance)."""

    reader_id = "vendor.cls"
    extensions = (".vendor",)

    def read(self, path: Path) -> TableData:
        """Read a plain CSV file with a header row."""
        frame = pd.read_csv(path)
        columns = tuple(ColumnProvenance(str(name), "header", index) for index, name in enumerate(frame.columns))
        return TableData(frame, self.reader_id, columns)


class FailingInitReader(ClassAttrReader):
    """Its constructor fails (for example a missing licence)."""

    reader_id = "vendor.failing"

    def __init__(self) -> None:
        msg = "vendor licence file missing"
        raise RuntimeError(msg)


class NeedsArgsReader(ClassAttrReader):
    """Its constructor needs an argument, so it is not a zero-argument factory."""

    reader_id = "vendor.args"

    def __init__(self, licence: str) -> None:
        self.licence = licence


class NotAReaderClass:
    """Instances lack the protocol members."""


def _patch(monkeypatch: pytest.MonkeyPatch, *entries: tuple[str, str]) -> None:
    points = tuple(EntryPoint(name=name, value=value, group=READER_ENTRY_POINT_GROUP) for name, value in entries)
    monkeypatch.setattr(registry.metadata, "entry_points", lambda *, group: points if group == READER_ENTRY_POINT_GROUP else ())


def _vendor_file(tmp_path: Path) -> Path:
    source = tmp_path / "table.vendor"
    pd.DataFrame({"x": [1, 2, 3], "y": [2, 3, 5]}).to_csv(source, index=False)
    return source


def test_class_with_class_attributes_is_instantiated__tc_fix2_f3_ep_001(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-FIX2-F3-EP-001: the class is called, its instance reads the file."""
    # Given: an entry point targeting the class itself
    _patch(monkeypatch, ("vendor.cls", f"{HERE}:ClassAttrReader"))
    # When
    table = read_table(_vendor_file(tmp_path), reader="vendor.cls")
    reader = discover_readers().get("vendor.cls")
    # Then
    assert table.reader_id == "vendor.cls"
    assert table.frame.to_dict("list") == {"x": [1, 2, 3], "y": [2, 3, 5]}
    assert type(reader) is ClassAttrReader


def test_class_with_properties_is_instantiated__tc_fix2_f3_ep_002(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-FIX2-F3-EP-002: a property-based class with defaulted arguments works too."""
    _patch(monkeypatch, ("vendor.instrument", f"{VENDOR}:InstrumentReader"))
    source = tmp_path / "sample.instrument"
    source.write_bytes((FIXTURES / "sample.instrument").read_bytes())
    table = read_table(source, reader="vendor.instrument")
    assert table.reader_id == "vendor.instrument"
    assert list(table.frame.columns) == ["time (s)", "signal (mV)"]


def test_instance_target_is_used_as_is__tc_fix2_f3_ep_003(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-FIX2-F3-EP-003: an instance is not called."""
    _patch(monkeypatch, ("vendor.instrument", f"{VENDOR}:READER"))
    assert discover_readers().get("vendor.instrument") is vendor.READER


def test_factory_target_is_called__tc_fix2_f3_ep_004(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-FIX2-F3-EP-004: a non-class zero-argument factory is called as before."""
    _patch(monkeypatch, ("vendor.instrument", f"{VENDOR}:make_reader"))
    reader = discover_readers().get("vendor.instrument")
    assert isinstance(reader, vendor.InstrumentReader)
    assert reader is not vendor.READER


@pytest.mark.parametrize(
    ("name", "target", "cause", "fragment"),
    [
        ("vendor.failing", "FailingInitReader", RuntimeError, "vendor licence file missing"),
        ("vendor.args", "NeedsArgsReader", TypeError, "failed to load"),
    ],
    ids=["neg001-init-raises", "neg002-needs-args"],
)
def test_class_constructor_failure_is_a_plugin_error__tc_fix2_f3_neg_001_002(
    name: str, target: str, cause: type[BaseException], fragment: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-FIX2-F3-NEG-001/002: constructor failures are chained ReaderPluginErrors naming the entry point."""
    # Given
    _patch(monkeypatch, (name, f"{HERE}:{target}"))
    # When/Then
    with pytest.raises(ReaderPluginError) as caught:
        discover_readers().get(name)
    assert f"Reader plugin {name!r} ({HERE}:{target})" in str(caught.value)
    assert fragment in str(caught.value)
    assert type(caught.value.__cause__) is cause


def test_class_whose_instance_is_not_a_reader__tc_fix2_f3_neg_003(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-FIX2-F3-NEG-003: the built instance is still checked against the protocol."""
    _patch(monkeypatch, ("vendor.none", f"{HERE}:NotAReaderClass"))
    with pytest.raises(ReaderPluginError, match="is not a TableReader instance") as caught:
        discover_readers().get("vendor.none")
    assert caught.value.__cause__ is None


def test_class_with_a_different_id__tc_fix2_f3_neg_004(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-FIX2-F3-NEG-004: the instance's id must equal the entry-point name."""
    _patch(monkeypatch, ("other", f"{HERE}:ClassAttrReader"))
    with pytest.raises(ReaderPluginError, match="must equal the reader id"):
        discover_readers().get("other")


def test_duplicate_class_entry_points_fail_closed__tc_fix2_f3_neg_005(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-FIX2-F3-NEG-005: duplicate names still fail at discovery, naming both targets."""
    _patch(monkeypatch, ("vendor.cls", f"{HERE}:ClassAttrReader"), ("vendor.cls", f"{HERE}:FailingInitReader"))
    with pytest.raises(DuplicateReaderError) as caught:
        discover_readers()
    assert f"{HERE}:ClassAttrReader" in str(caught.value)
    assert f"{HERE}:FailingInitReader" in str(caught.value)
