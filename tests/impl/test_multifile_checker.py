"""Regression tests for :func:`MultiFileChecker.parse`.

Equivalence Partitioning Table
| API                        | Input/State Partition                  | Rationale                                      | Expected Outcome                         | Test ID     |
| -------------------------- | -------------------------------------- | ---------------------------------------------- | ---------------------------------------- | ----------- |
| `MultiFileChecker.parse`   | Only Excel-invoice helper files exist  | No user payloads should still produce a tile   | Returns `[()]`; skips Excel invoice file | `TC-EP-001` |
| `MultiFileChecker.parse`   | Multiple user payload files exist      | Normal multi-file ingestion case               | Emits one tuple per user file            | `TC-EP-002` |

Boundary Value Table
| API                        | Boundary             | Rationale                              | Expected Outcome                         | Test ID     |
| -------------------------- | -------------------- | -------------------------------------- | ---------------------------------------- | ----------- |
| `MultiFileChecker.parse`   | `min = 0` files      | Absolute lower bound for input payload | Returns `[()]`; no user files detected   | `TC-BV-001` |
| `MultiFileChecker.parse`   | `min+1 = 1` file     | Smallest valid user payload count      | Returns exactly one tuple with that file | `TC-BV-002` |

Test Execution Commands
- Direct: `pytest tests/impl/test_multifile_checker.py -q --maxfail=1 --cov=rdetoolkit --cov-branch --cov-report=term-missing --cov-report=html`
- Via tox: `tox -e py311-module -- tests/impl/test_multifile_checker.py -q --maxfail=1 --cov=rdetoolkit --cov-branch --cov-report=term-missing --cov-report=html`
"""

from pathlib import Path

import pytest

from rdetoolkit.impl.input_controller import MultiFileChecker


@pytest.fixture(name="checker_paths")
def fixture_checker_paths(tmp_path: Path) -> tuple[MultiFileChecker, Path]:
    """Provide a checker and a fresh input directory rooted at tmp_path."""
    input_dir = tmp_path / "inputdata"
    input_dir.mkdir()
    checker = MultiFileChecker(tmp_path / "temp")
    return checker, input_dir


def test_multifile_checker_filters_excel_invoice_and_returns_placeholder__tc_ep_001(checker_paths: tuple[MultiFileChecker, Path]) -> None:
    checker, input_dir = checker_paths
    excel_invoice_file = input_dir / "dataset_excel_invoice.xlsx"
    # Given: inputdata with only Excel-invoice metadata
    excel_invoice_file.touch()

    # When: parsing the directory
    rawfiles, special_file = checker.parse(input_dir)

    # Then: treated as zero payloads to force validation path
    assert rawfiles == [()]
    assert special_file is None


def test_multifile_checker_emits_single_tuple_per_payload__tc_ep_002(checker_paths: tuple[MultiFileChecker, Path]) -> None:
    checker, input_dir = checker_paths
    first = input_dir / "b_sample.txt"
    second = input_dir / "a_sample.txt"
    # Given: two payload files out of order
    first.touch()
    second.touch()

    # When: parsing the directory
    rawfiles, special_file = checker.parse(input_dir)

    # Then: file order is normalized and each tuple contains a single file
    assert rawfiles == [(second,), (first,)]
    assert special_file is None


def test_multifile_checker_empty_directory_returns_placeholder__tc_bv_001(checker_paths: tuple[MultiFileChecker, Path]) -> None:
    checker, input_dir = checker_paths
    # Given: inputdata directory with zero payload files
    assert list(input_dir.iterdir()) == []

    # When: parsing the directory
    rawfiles, special_file = checker.parse(input_dir)

    # Then: emits a single empty tuple so downstream validation still runs
    assert rawfiles == [()]
    assert special_file is None


def test_multifile_checker_single_file_boundary__tc_bv_002(checker_paths: tuple[MultiFileChecker, Path]) -> None:
    checker, input_dir = checker_paths
    payload = input_dir / "only_payload.txt"
    # Given: exactly one payload file
    payload.touch()

    # When: parsing the directory
    rawfiles, special_file = checker.parse(input_dir)

    # Then: returns one tuple with that payload
    assert rawfiles == [(payload,)]
    assert special_file is None
