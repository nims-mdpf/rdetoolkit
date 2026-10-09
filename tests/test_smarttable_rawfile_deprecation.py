"""Regression tests for the smarttable_rowfile -> smarttable_rawfile rename.

Equivalence Partitioning:

| Input/State Partition                                              | Expected Outcome                                          | Test ID   |
| -------------------------------------------------------------------- | ----------------------------------------------------------- | --------- |
| RdeOutputResourcePath.smarttable_rowfile read                       | DeprecationWarning raised, same value as smarttable_rawfile | TC-EP-001 |
| RdeOutputResourcePath.smarttable_rowfile assigned                   | DeprecationWarning raised, smarttable_rawfile updated       | TC-EP-002 |
| RdeDatasetPaths.smarttable_rowfile read                             | DeprecationWarning raised, same value as smarttable_rawfile | TC-EP-003 |
| ProcessingContext.smarttable_rowfile read                           | DeprecationWarning raised, same value as smarttable_rawfile | TC-EP-004 |
| ProcessingContext.smarttable_rawfile with rawfiles fsmarttable_ file | No fallback; returns None                                    | TC-EP-005 |
| RdeOutputResourcePath(smarttable_rowfile=...) constructor kwarg      | DeprecationWarning raised, smarttable_rawfile populated      | TC-EP-006 |
| Constructor with both smarttable_rawfile and smarttable_rowfile      | smarttable_rawfile wins, DeprecationWarning still raised     | TC-EP-007 |
| Constructor without either keyword                                   | No warning, smarttable_rawfile is None                       | TC-EP-008 |
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rdetoolkit.models.rde2types import (
    RdeDatasetPaths,
    RdeInputDirPaths,
    RdeOutputResourcePath,
    create_default_config,
)
from rdetoolkit.processing.context import ProcessingContext


def _build_resource_paths(base_dir: Path, *, smarttable_rawfile: Path | None, rawfiles: tuple[Path, ...] = ()) -> RdeOutputResourcePath:
    """Construct a minimal RdeOutputResourcePath for deprecation testing."""
    return RdeOutputResourcePath(
        raw=base_dir / "raw",
        nonshared_raw=base_dir / "nonshared_raw",
        rawfiles=rawfiles,
        struct=base_dir / "structured",
        main_image=base_dir / "main_image",
        other_image=base_dir / "other_image",
        meta=base_dir / "meta",
        thumbnail=base_dir / "thumbnail",
        logs=base_dir / "logs",
        invoice=base_dir / "invoice",
        invoice_schema_json=base_dir / "tasksupport" / "invoice.schema.json",
        invoice_org=base_dir / "invoice" / "invoice.json",
        smarttable_rawfile=smarttable_rawfile,
    )


def test_rde_output_resource_path_rowfile_read_is_deprecated_alias__tc_ep_001(tmp_path: Path) -> None:
    """TC-EP-001: Reading smarttable_rowfile emits DeprecationWarning and returns smarttable_rawfile value."""
    # Given: a resource path with smarttable_rawfile set
    row_csv = tmp_path / "temp" / "fsmarttable_test_0000.csv"
    resource_paths = _build_resource_paths(tmp_path, smarttable_rawfile=row_csv)

    # When: reading the deprecated alias
    with pytest.warns(DeprecationWarning):
        value = resource_paths.smarttable_rowfile

    # Then: the same value as smarttable_rawfile is returned
    assert value == row_csv
    assert value == resource_paths.smarttable_rawfile


def test_rde_output_resource_path_rowfile_assignment_is_deprecated_alias__tc_ep_002(tmp_path: Path) -> None:
    """TC-EP-002: Assigning smarttable_rowfile emits DeprecationWarning and updates smarttable_rawfile."""
    # Given: a resource path without a row CSV set
    resource_paths = _build_resource_paths(tmp_path, smarttable_rawfile=None)
    new_row_csv = tmp_path / "temp" / "fsmarttable_test_0001.csv"

    # When: assigning through the deprecated alias
    with pytest.warns(DeprecationWarning):
        resource_paths.smarttable_rowfile = new_row_csv

    # Then: smarttable_rawfile reflects the new value
    assert resource_paths.smarttable_rawfile == new_row_csv


def test_rde_dataset_paths_rowfile_read_is_deprecated_alias__tc_ep_003(tmp_path: Path) -> None:
    """TC-EP-003: RdeDatasetPaths.smarttable_rowfile emits DeprecationWarning and returns smarttable_rawfile value."""
    # Given: an RdeDatasetPaths wrapping a resource path with a row CSV set
    row_csv = tmp_path / "temp" / "fsmarttable_test_0000.csv"
    resource_paths = _build_resource_paths(tmp_path, smarttable_rawfile=row_csv)
    srcpaths = RdeInputDirPaths(
        inputdata=tmp_path / "inputdata",
        invoice=tmp_path / "invoice",
        tasksupport=tmp_path / "tasksupport",
        config=create_default_config(),
    )
    dataset_paths = RdeDatasetPaths(srcpaths, resource_paths)

    # When: reading the deprecated alias
    with pytest.warns(DeprecationWarning):
        value = dataset_paths.smarttable_rowfile

    # Then: the same value as smarttable_rawfile is returned
    assert value == row_csv
    assert value == dataset_paths.smarttable_rawfile


def test_processing_context_rowfile_read_is_deprecated_alias__tc_ep_004(tmp_path: Path) -> None:
    """TC-EP-004: ProcessingContext.smarttable_rowfile emits DeprecationWarning and returns smarttable_rawfile value."""
    # Given: a ProcessingContext with a row CSV set on resource_paths
    row_csv = tmp_path / "temp" / "fsmarttable_test_0000.csv"
    resource_paths = _build_resource_paths(tmp_path, smarttable_rawfile=row_csv)
    srcpaths = RdeInputDirPaths(
        inputdata=tmp_path / "inputdata",
        invoice=tmp_path / "invoice",
        tasksupport=tmp_path / "tasksupport",
        config=create_default_config(),
    )
    context = ProcessingContext(
        index="0",
        srcpaths=srcpaths,
        resource_paths=resource_paths,
        datasets_function=None,
        mode_name="smarttable",
        smarttable_file=tmp_path / "inputdata" / "smarttable_test.csv",
    )

    # When: reading the deprecated alias
    with pytest.warns(DeprecationWarning):
        value = context.smarttable_rowfile

    # Then: the same value as smarttable_rawfile is returned
    assert value == row_csv
    assert value == context.smarttable_rawfile


def test_processing_context_rawfile_does_not_fall_back_to_rawfiles__tc_ep_005(tmp_path: Path) -> None:
    """TC-EP-005: smarttable_rawfile must not fall back to rawfiles[0] even if it looks like a row CSV.

    Regression test: the rawfiles[0]/`fsmarttable_` prefix heuristic was removed in
    favor of the explicit smarttable_rawfile field. This test guards against the
    fallback heuristic being reintroduced.
    """
    # Given: resource_paths.smarttable_rawfile is None but rawfiles contains a file
    # that would have matched the old fallback heuristic (fsmarttable_ prefix, .csv suffix)
    look_alike_csv = tmp_path / "temp" / "fsmarttable_test_0000.csv"
    resource_paths = _build_resource_paths(tmp_path, smarttable_rawfile=None, rawfiles=(look_alike_csv,))
    srcpaths = RdeInputDirPaths(
        inputdata=tmp_path / "inputdata",
        invoice=tmp_path / "invoice",
        tasksupport=tmp_path / "tasksupport",
        config=create_default_config(),
    )
    context = ProcessingContext(
        index="0",
        srcpaths=srcpaths,
        resource_paths=resource_paths,
        datasets_function=None,
        mode_name="smarttable",
        smarttable_file=tmp_path / "inputdata" / "smarttable_test.csv",
    )

    # When: reading smarttable_rawfile (not the deprecated alias)
    value = context.smarttable_rawfile

    # Then: no fallback occurs; None is returned without any warning
    assert value is None


def _base_constructor_kwargs(base_dir: Path) -> dict[str, Path | tuple[Path, ...]]:
    """Return the required RdeOutputResourcePath keyword arguments."""
    return {
        "raw": base_dir / "raw",
        "nonshared_raw": base_dir / "nonshared_raw",
        "rawfiles": (),
        "struct": base_dir / "structured",
        "main_image": base_dir / "main_image",
        "other_image": base_dir / "other_image",
        "meta": base_dir / "meta",
        "thumbnail": base_dir / "thumbnail",
        "logs": base_dir / "logs",
        "invoice": base_dir / "invoice",
        "invoice_schema_json": base_dir / "tasksupport" / "invoice.schema.json",
        "invoice_org": base_dir / "invoice" / "invoice.json",
    }


def test_constructor_accepts_deprecated_rowfile_keyword__tc_ep_006(tmp_path: Path) -> None:
    """TC-EP-006: The legacy smarttable_rowfile constructor keyword still works with a DeprecationWarning.

    Backward compatibility: pre-v1.7.0 code constructs RdeOutputResourcePath with
    smarttable_rowfile=... and must keep working until the alias is removed in v2.0.
    """
    # Given: constructor arguments using the legacy keyword
    row_csv = tmp_path / "temp" / "fsmarttable_test_0000.csv"

    # When: constructing with smarttable_rowfile=
    with pytest.warns(DeprecationWarning):
        resource_paths = RdeOutputResourcePath(**_base_constructor_kwargs(tmp_path), smarttable_rowfile=row_csv)

    # Then: the value is transferred to smarttable_rawfile
    assert resource_paths.smarttable_rawfile == row_csv


def test_constructor_new_keyword_wins_over_deprecated_one__tc_ep_007(tmp_path: Path) -> None:
    """TC-EP-007: When both keywords are given, smarttable_rawfile takes precedence."""
    # Given: constructor arguments using both the new and the legacy keyword
    new_csv = tmp_path / "temp" / "fsmarttable_new_0000.csv"
    old_csv = tmp_path / "temp" / "fsmarttable_old_0000.csv"

    # When: constructing with both keywords
    with pytest.warns(DeprecationWarning):
        resource_paths = RdeOutputResourcePath(
            **_base_constructor_kwargs(tmp_path),
            smarttable_rawfile=new_csv,
            smarttable_rowfile=old_csv,
        )

    # Then: the new keyword wins
    assert resource_paths.smarttable_rawfile == new_csv


def test_constructor_without_row_keywords_emits_no_warning__tc_ep_008(tmp_path: Path) -> None:
    """TC-EP-008: Constructing without either keyword emits no DeprecationWarning."""
    # Given/When: constructing without smarttable_rawfile / smarttable_rowfile
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        resource_paths = RdeOutputResourcePath(**_base_constructor_kwargs(tmp_path))

    # Then: no warning was raised and the field defaults to None
    assert resource_paths.smarttable_rawfile is None
