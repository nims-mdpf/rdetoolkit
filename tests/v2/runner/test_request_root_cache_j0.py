"""``_apply_request_root`` invalidates the data-root cache (Session J0, debt 4).

``Runner._data_root`` caches the four-tier ``resolve_data_root`` answer so an
alias-flat root cannot silently move once tile 0 gains a ``data`` child
(Session I-REVIEW-A ruling #1). ``_apply_request_root`` rebased ``root``,
``inputdata_path`` and ``unpacked_dir_path`` but left that cache alone, so a
Runner driven through the step-by-step API -- ``load_config`` (which touches
``data_root``) and only then a root change -- kept answering with the *first*
root. ``Runner.run`` re-resolves immediately after applying the request root,
which is why no production path was affected and why nothing in the suite
noticed (contracts.md §I-REVIEW-A debt 4).

EP table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-J0-ROOT-EP-001 | idempotent | the same root re-applied after caching | the cached answer is unchanged |

BV / negative table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-J0-ROOT-EV-002 | stale cache | cache primed on A, then rebased to B | ``data_root`` is ``B/data``, never ``A/data`` |
| TC-J0-ROOT-EV-003 | four-tier re-run | A nested, B alias-flat | ``data_root`` is ``B`` itself, not ``B/data`` |
| TC-J0-ROOT-EV-004 | consumer | ``pre_validate`` after the rebase | B's invalid invoice is the one reported (4001) |
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.errors import RdeValidationError
from rdetoolkit.runner.lifecycle import Runner

#: Catalog code ``pre_validate`` reports for an invoice that violates its schema.
_INVOICE_VALIDATION_CODE = 4001

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"basic": {"type": "object", "properties": {"dataName": {"type": "string"}}}},
}


def _valid_invoice() -> dict[str, Any]:
    return {
        "datasetId": "j0-root-cache",
        "basic": {
            "dateSubmitted": "2026-09-28",
            "dataOwnerId": "0" * 56,
            "dataName": "j0",
        },
    }


def _invalid_invoice() -> dict[str, Any]:
    invoice = _valid_invoice()
    # ``dataName`` must be a string, so an int is a schema violation the
    # run-level invoice validation reports.
    invoice["basic"]["dataName"] = 1
    return invoice


def _build_nested(root: Path, *, invoice: dict[str, Any] | None = None) -> Path:
    """Build a standard project root whose RDE directories live under ``data``."""
    data_root = root / "data"
    (data_root / "inputdata").mkdir(parents=True)
    (data_root / "invoice").mkdir(parents=True)
    (data_root / "invoice" / "invoice.json").write_text(
        json.dumps(_valid_invoice() if invoice is None else invoice),
        encoding="utf-8",
    )
    (data_root / "tasksupport").mkdir(parents=True)
    (data_root / "tasksupport" / "invoice.schema.json").write_text(json.dumps(_SCHEMA), encoding="utf-8")
    return data_root


def _build_alias_flat(root: Path) -> Path:
    """Build an alias-flat project root: the RDE markers sit directly below it."""
    (root / "inputdata").mkdir(parents=True)
    (root / "invoice").mkdir(parents=True)
    (root / "invoice" / "invoice.json").write_text(json.dumps(_valid_invoice()), encoding="utf-8")
    (root / "tasksupport").mkdir(parents=True)
    (root / "tasksupport" / "invoice.schema.json").write_text(json.dumps(_SCHEMA), encoding="utf-8")
    return root


def test_reapplying_the_same_root_keeps_the_cached_answer__tc_j0_root_ep_001(tmp_path: Path) -> None:
    """TC-J0-ROOT-EP-001: invalidation must not change the answer for one root."""
    # Given: a Runner whose data root has already been resolved once
    root = tmp_path / "a"
    expected = _build_nested(root)
    runner = Runner(root=root)
    assert runner.data_root == expected

    # When: the same root is applied again
    runner._apply_request_root(root)  # noqa: SLF001 -- the step-by-step seam under test

    # Then: the resolved data root is still the very same directory
    assert runner.data_root == expected


def test_rebasing_the_root_drops_the_previous_data_root__tc_j0_root_ev_002(tmp_path: Path) -> None:
    """TC-J0-ROOT-EV-002: a primed cache must not survive a root change."""
    # Given: two independent project roots, with the cache primed on the first
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    _build_nested(root_a)
    expected = _build_nested(root_b)
    runner = Runner(root=root_a)
    runner.load_config()
    assert runner.data_root == root_a / "data"

    # When: the request root is rebased onto the second project
    runner._apply_request_root(root_b)  # noqa: SLF001

    # Then: every later consumer sees the second project's data root
    assert runner.data_root == expected
    assert runner.data_root != root_a / "data"


def test_rebasing_re_evaluates_the_alias_flat_rule__tc_j0_root_ev_003(tmp_path: Path) -> None:
    """TC-J0-ROOT-EV-003: the four-tier rule re-runs, it is not string surgery.

    A nested root answers ``<root>/data`` and an alias-flat root answers
    ``<root>`` itself, so swapping between the two proves the cache was
    re-resolved rather than merely re-prefixed.
    """
    # Given: a nested root cached first, and an alias-flat root to move to
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    _build_nested(root_a)
    _build_alias_flat(root_b)
    runner = Runner(root=root_a)
    assert runner.data_root == root_a / "data"

    # When: rebasing onto the alias-flat root
    runner._apply_request_root(root_b)  # noqa: SLF001

    # Then: the alias-flat root IS the data root
    assert runner.data_root == root_b
    assert not (root_b / "data").exists()


def test_pre_validate_reads_the_rebased_root__tc_j0_root_ev_004(tmp_path: Path) -> None:
    """TC-J0-ROOT-EV-004: a data-root consumer follows the rebase, not the cache.

    ``pre_validate`` is the first step-by-step consumer after ``load_config``.
    With the stale cache it validated A's valid invoice and reported success for
    a run that was really pointed at B.
    """
    # Given: a valid project A and a schema-invalid project B
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    _build_nested(root_a)
    _build_nested(root_b, invoice=_invalid_invoice())
    runner = Runner(root=root_a)
    config = runner.load_config()
    runner.pre_validate(config)

    # When: rebasing onto B and validating again
    runner._apply_request_root(root_b)  # noqa: SLF001

    # Then: B's defect is what gets reported
    with pytest.raises(RdeValidationError) as exc_info:
        runner.pre_validate(config)

    assert exc_info.value.code == _INVOICE_VALIDATION_CODE
