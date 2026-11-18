r"""QA-02 (#737): frozen v1 oracle lock and the v1-unchanged / v2-intentional contract tables.

``parity_oracle_lock.json`` records the verified v1 baseline (the oracle tag and
the revision that wrote every snapshot), the reviewed v2 SHA, and a semantic
digest of every frozen snapshot. A snapshot that is edited, re-frozen, added or
removed without updating the lock in the same commit turns this gate red, so the
expected values the parity tests compare against cannot drift silently.

:data:`CONTRACT_ROWS` is the explicit contract table of the GA release: every
cross-feature behaviour of ``test_cross_feature_737.py`` is a row that is either
*v1 unchanged* (the callback entry keeps 1.7.1 behaviour; the expectation is a
frozen v1 observation or the unchanged input) or *v2 intentional* (a versioned
behaviour change with a migration note). Each parent epic has at least one
*sentinel* row whose test turns red when its core fix is reverted.

EP table:

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| oracle lock | every frozen snapshot | digest equals the lock | QA02-LOCK-001 |
| oracle lock | snapshot ``source`` | the recorded tag and writer revision | QA02-LOCK-002 |
| oracle lock | baseline record | full SHAs; generator tag agrees | QA02-LOCK-003 |
| oracle lock | five modes | each has a frozen success observation with artifacts | QA02-LOCK-004 |
| oracle lock | edited / unlocked / missing snapshot | defect named | QA02-LOCK-NEG-* |
| contract table | every row / every scenario | the row's test is collected; no scenario lacks a row | QA02-TABLE-001 |
| contract table | rows, epics, migration notes | no defect | QA02-TABLE-002 |
| contract table | duplicate id / missing epic sentinel / v2 row without note / note phrase absent / v1 row with note | defect named | QA02-TABLE-NEG-* |

BV table:

| API | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| oracle lock | one changed byte of meaning (one value) | QA02-LOCK-NEG-EDITED | QA02-LOCK-NEG-EDITED |
| contract table | exactly one sentinel per epic is enough; zero is a defect | QA02-TABLE-NEG-NO-SENTINEL | QA02-TABLE-NEG-NO-SENTINEL |
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pytest

from tests.v2.contract.fixtures import _generate
from tests.v2.ga import _harness as ga

LOCK_PATH = Path(__file__).with_name("parity_oracle_lock.json")
SNAPSHOT_ROOT = _generate.FIXTURE_ROOT / "expected"
SCENARIOS = "tests/v2/ga/test_cross_feature_737.py"
EPICS = {703: "Graph", 704: "Magic", 705: "Modes"}
_SHA = re.compile(r"[0-9a-f]{40}")

Kind = Literal["v1_unchanged", "v2_intentional"]


@dataclass(frozen=True)
class ContractRow:
    """One row of the GA contract table.

    Attributes:
        id: Stable row id (``QA02-...``).
        epic: Parent epic issue number.
        kind: ``v1_unchanged`` or ``v2_intentional``.
        behaviour: What is guaranteed, in one sentence.
        test: The collected pytest id asserting it.
        sentinel_for: The child issue whose core fix the test pins (reverting
            that fix turns the test red), or ``None``.
        note: For a v2 change, ``(document, phrase)`` of its migration note.
    """

    id: str
    epic: int
    kind: Kind
    behaviour: str
    test: str
    sentinel_for: int | None = None
    note: tuple[str, str] | None = None


_MAGIC_NOTE = "docs/usage/config/magic_variable_v2.en.md"
_MIGRATION = "docs/migration_v1_to_v2.en.md"
_CONCURRENCY_NOTE = "| Two runs on the same data root at the same time (threads or processes) (#737) |"

CONTRACT_ROWS: tuple[ContractRow, ...] = (
    # ---- Magic (#704)
    ContractRow(
        "QA02-MAGIC-NORAW-FLOW", 704, "v2_intentional",
        "invoice:basic and metadata:constant expand on a tile without raw files",
        f"{SCENARIOS}::test_invoice_and_metadata_magic_expand_without_rawfiles__qa02_magic_noraw_flow",
        sentinel_for=722, note=(_MAGIC_NOTE, "Invoice and metadata expressions work without raw attachments."),
    ),
    ContractRow(
        "QA02-MAGIC-NORAW-CB", 704, "v1_unchanged",
        "the v1 callback entry applies magic variables only with a raw file; the template stays verbatim",
        f"{SCENARIOS}::test_callback_keeps_the_v1_rawfiles_gate__qa02_magic_noraw_cb",
    ),
    ContractRow(
        "QA02-MAGIC-NORAW-FILENAME", 704, "v2_intentional",
        "${filename} on a tile without raw files fails with 4010 and leaves the invoice untouched",
        f"{SCENARIOS}::test_filename_without_rawfile_fails_and_keeps_the_invoice__qa02_magic_noraw_filename",
        sentinel_for=722, note=(_MAGIC_NOTE, "Zero or multiple raw inputs are an\nerror only when filename is requested."),
    ),
    ContractRow(
        "QA02-MAGIC-PARTIAL-FAILFAST", 704, "v2_intentional",
        "a magic failure on a later tile keeps earlier tiles published and never half-writes its own invoice",
        f"{SCENARIOS}::test_magic_failure_after_partial_publication[QA02-MAGIC-PARTIAL-FAILFAST]",
        note=(_MAGIC_NOTE, "Any expression, schema, or\npublication failure leaves the invoice unchanged."),
    ),
    ContractRow(
        "QA02-MAGIC-PARTIAL-CONTINUE", 704, "v2_intentional",
        "under continue the same failure is a partial run without job.failed",
        f"{SCENARIOS}::test_magic_failure_after_partial_publication[QA02-MAGIC-PARTIAL-CONTINUE]",
        note=(_MAGIC_NOTE, "Any expression, schema, or\npublication failure leaves the invoice unchanged."),
    ),
    *(
        ContractRow(
            f"QA02-MAGIC-MALFORMED-{suffix}", 704, "v2_intentional",
            f"malformed expression ({suffix.lower().replace('-', ' ')}) fails with 4009 before invoice persistence",
            f"{SCENARIOS}::test_malformed_expression_fails_before_invoice_persistence[QA02-MAGIC-MALFORMED-{suffix}]",
            sentinel_for=723, note=(_MAGIC_NOTE, "Internal whitespace, extra segments,\nempty keys, nested expressions, and unknown sources are invalid."),
        )
        for suffix in ("EXTRA-SEGMENT", "FILENAME-ARITY", "EMPTY", "UNCLOSED", "UNKNOWN-SOURCE")
    ),
    # ---- Modes (#705)
    ContractRow(
        "QA02-MODE-MIXED-FLOW", 705, "v2_intentional",
        "a SmartTable table next to an ExcelInvoice workbook is ambiguous (1007) before any tile or extraction",
        f"{SCENARIOS}::test_mixed_special_inputs_fail_before_mutation__qa02_mode_mixed_flow",
        sentinel_for=730, note=(_MIGRATION, "Mixed tables, duplicate workbooks, and ambiguous special archives fail before\nregistration."),
    ),
    ContractRow(
        "QA02-MODE-MIXED-CB", 705, "v1_unchanged",
        "the v1 callback entry keeps SmartTable-before-ExcelInvoice precedence and produces the frozen v1 SmartTable run",
        f"{SCENARIOS}::test_mixed_special_inputs_keep_v1_smarttable_precedence__qa02_mode_mixed_cb",
    ),
    *(
        ContractRow(
            f"QA02-MODE-ALIAS-{suffix}", 705, "v2_intentional",
            f"extended_mode {spelling!r} selects MultiDataTile with the frozen v1 tile count, never Invoice",
            f"{SCENARIOS}::test_multidatatile_spellings_select_multidatatile[QA02-MODE-ALIAS-{suffix}]",
            sentinel_for=729, note=(_MIGRATION, "Use the canonical names `invoice`, `multidatatile`, `smarttable`,"),
        )
        for suffix, spelling in (("CANONICAL", "multidatatile"), ("LEGACY", "MultiDataTile"))
    ),
    *(
        ContractRow(
            f"QA02-MODE-INVALID-{suffix}", 705, "v2_intentional",
            f"an unknown extended_mode spelling ({suffix.lower()}) fails with 1002 listing the valid names",
            f"{SCENARIOS}::test_unknown_mode_names_fail_before_any_tile[QA02-MODE-INVALID-{suffix}]",
            sentinel_for=729, note=(_MIGRATION, "Other spellings fail with a list of valid names."),
        )
        for suffix in ("SNAKE", "CASE", "TYPO")
    ),
    # ---- Graph (#703)
    *(
        ContractRow(
            f"QA02-GRAPH-DUPLABEL-{suffix}", 703, "v2_intentional",
            f"case-colliding labels give one distinct figure per series on every tile ({suffix.lower()} entry)",
            f"{SCENARIOS}::test_duplicate_labels_give_distinct_figures_on_every_tile[QA02-GRAPH-DUPLABEL-{suffix}]",
            sentinel_for=708, note=(_MIGRATION, "| IC-3 |"),
        )
        for suffix in ("FLOW", "CB")
    ),
    ContractRow(
        "QA02-GRAPH-INVALID-MODE", 703, "v2_intentional",
        "a plot mode other than overlay/individual fails before any figure is written",
        f"{SCENARIOS}::test_invalid_plot_mode_fails_before_any_figure__qa02_graph_invalid_mode",
        sentinel_for=707, note=(_MIGRATION, "| IC-1 |"),
    ),
    # ---- Runner: one run per data root (#737, under the release-gate epic #706)
    *(
        ContractRow(
            f"QA02-CONC-{ga.ENTRY_IDS[entry]}-{ga.MODE_IDS[mode]}", 706, "v2_intentional",
            f"a second {entry} run on a {mode} root another run owns is refused with 3008 and writes nothing",
            f"{SCENARIOS}::test_a_second_run_on_a_busy_root_is_refused[QA02-CONC-{ga.ENTRY_IDS[entry]}-{ga.MODE_IDS[mode]}]",
            sentinel_for=737, note=(_MIGRATION, _CONCURRENCY_NOTE),
        )
        for entry in ga.ENTRIES
        for mode in ga.MODES
    ),
    *(
        ContractRow(
            f"QA02-CONC-RACE-{ga.MODE_IDS[mode]}", 706, "v2_intentional",
            f"two {mode} runs released together end in success or 3008 and leave the frozen v1 artifacts",
            f"{SCENARIOS}::test_simultaneous_runs_never_corrupt_each_other[QA02-CONC-RACE-{ga.MODE_IDS[mode]}]",
            sentinel_for=737, note=(_MIGRATION, _CONCURRENCY_NOTE),
        )
        for mode in ga.MODES
    ),
)


# ------------------------------------------------------------------ validators


def _canonical_digest(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _snapshot_digests(root: Path) -> dict[str, str]:
    return {path.relative_to(root).as_posix(): _canonical_digest(json.loads(path.read_text(encoding="utf-8"))) for path in sorted(root.rglob("*.json"))}


def lock_defects(locked: Mapping[str, str], actual: Mapping[str, str]) -> list[str]:
    """Return every difference between the locked and the on-disk snapshot digests."""
    defects = [f"unlocked snapshot {name} (digest {actual[name]})" for name in sorted(set(actual) - set(locked))]
    defects += [f"locked snapshot {name} is missing" for name in sorted(set(locked) - set(actual))]
    defects += [
        f"snapshot {name} changed: locked {locked[name]}, now {actual[name]}"
        for name in sorted(set(locked) & set(actual))
        if locked[name] != actual[name]
    ]
    return defects


def table_defects(rows: Iterable[ContractRow], *, epics: Iterable[int], repository: Path) -> list[str]:
    """Return every structural defect of a contract table."""
    rows = tuple(rows)
    defects: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if row.id in seen:
            defects.append(f"duplicate row id {row.id}")
        seen.add(row.id)
        if row.kind == "v2_intentional":
            defects += _note_defects(row, repository)
        elif row.note is not None or row.sentinel_for is not None:
            defects.append(f"{row.id}: a v1-unchanged row has no migration note and pins no v2 fix")
    for epic in epics:
        if not any(row.epic == epic and row.sentinel_for is not None for row in rows):
            defects.append(f"epic #{epic} has no sentinel row")
    return defects


def _note_defects(row: ContractRow, repository: Path) -> list[str]:
    if row.note is None:
        return [f"{row.id}: a v2-intentional row needs a migration note"]
    document, phrase = row.note
    path = repository / document
    if not path.is_file():
        return [f"{row.id}: migration note {document} does not exist"]
    if phrase not in path.read_text(encoding="utf-8"):
        return [f"{row.id}: migration note {document} lacks {phrase!r}"]
    return []


def _lock() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    return document


# ------------------------------------------------------------------ oracle lock


def test_every_frozen_snapshot_matches_the_lock__qa02_lock_001() -> None:
    """QA02-LOCK-001: the expected values are exactly the reviewed ones."""
    # Given: the lock and the frozen corpus on disk
    locked = _lock()["snapshots"]

    # When: every snapshot is digested semantically
    actual = _snapshot_digests(SNAPSHOT_ROOT)

    # Then: nothing was edited, added or removed behind the lock
    assert lock_defects(locked, actual) == []


def test_every_snapshot_was_written_by_the_locked_v1_revision__qa02_lock_002() -> None:
    """QA02-LOCK-002: one verified v1 baseline wrote the whole corpus."""
    # Given: the recorded v1 baseline
    baseline = _lock()["v1_oracle"]
    expected = {"commit": baseline["writer_commit"][:12], "tag": baseline["tag"]}

    # When: each snapshot's provenance is read
    sources = {
        path.relative_to(SNAPSHOT_ROOT).as_posix(): json.loads(path.read_text(encoding="utf-8"))["source"]
        for path in sorted(SNAPSHOT_ROOT.rglob("*.json"))
    }

    # Then: every snapshot names that baseline
    assert {name: source for name, source in sources.items() if source != expected} == {}


def test_the_baseline_record_is_complete__qa02_lock_003() -> None:
    """QA02-LOCK-003: full SHAs for the v1 oracle and the reviewed v2 revision."""
    # Given: the lock document
    lock = _lock()

    # Then: it is the versioned format with full revisions
    assert (lock["format"], lock["schema_version"]) == ("rdetoolkit.parity-oracle-lock", "1")
    for sha in (lock["v1_oracle"]["tag_commit"], lock["v1_oracle"]["writer_commit"], lock["reviewed_v2"]["commit"]):
        assert _SHA.fullmatch(sha), sha
    assert lock["reviewed_v2"]["branch"] == "develop/v2"

    # And: the generator still names the same oracle tag
    assert lock["v1_oracle"]["tag"] == _generate.SOURCE_TAG


@pytest.mark.parametrize("mode", ga.MODES)
def test_each_mode_has_an_independent_frozen_success_oracle__qa02_lock_004(mode: str) -> None:
    """QA02-LOCK-004: every mode has locked v1 artifacts to compare against."""
    # Given: the lock
    locked = _lock()["snapshots"]

    # When: the mode's success observation is read
    observed = ga.frozen_ok(mode)

    # Then: it is locked and carries artifacts, invoices and a tile count
    assert f"v1/{mode}/ok.json" in locked
    assert observed["callback_count"] >= 1
    assert observed["output_tree"]["files"]
    assert observed["invoices"]
    assert observed["job_failed_text"] is None


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        pytest.param("edited", "snapshot v1/invoice/ok.json changed", id="QA02-LOCK-NEG-EDITED"),
        pytest.param("added", "unlocked snapshot v1/invoice/extra.json", id="QA02-LOCK-NEG-UNLOCKED"),
        pytest.param("removed", "locked snapshot v1/invoice/ok.json is missing", id="QA02-LOCK-NEG-MISSING"),
    ],
)
def test_lock_drift_is_named(change: str, expected: str, tmp_path: Path) -> None:
    """QA02-LOCK-NEG-*: a re-freeze that skips the lock is caught."""
    # Given: a copy of the corpus, changed in one way
    corpus = tmp_path / "expected"
    target = corpus / "v1" / "invoice" / "ok.json"
    target.parent.mkdir(parents=True)
    target.write_text((SNAPSHOT_ROOT / "v1" / "invoice" / "ok.json").read_text(encoding="utf-8"), encoding="utf-8")
    locked = _snapshot_digests(corpus)
    if change == "edited":
        value = json.loads(target.read_text(encoding="utf-8"))
        value["observed"]["callback_count"] += 1
        target.write_text(json.dumps(value), encoding="utf-8")
    elif change == "added":
        (target.parent / "extra.json").write_text("{}", encoding="utf-8")
    else:
        target.unlink()

    # When: the copy is checked against its original lock
    defects = lock_defects(locked, _snapshot_digests(corpus))

    # Then: exactly that drift is reported
    assert len(defects) == 1
    assert defects[0].startswith(expected)


def test_line_endings_do_not_change_the_lock(tmp_path: Path) -> None:
    """QA02-LOCK-001 (BV): a CRLF checkout of the same snapshot keeps its digest."""
    # Given: one snapshot rewritten with CRLF line endings
    source = SNAPSHOT_ROOT / "v1" / "invoice" / "ok.json"
    crlf = tmp_path / "ok.json"
    crlf.write_bytes(source.read_bytes().replace(b"\n", b"\r\n"))

    # Then: the semantic digest is unchanged
    assert _snapshot_digests(tmp_path)["ok.json"] == _lock()["snapshots"]["v1/invoice/ok.json"]


# ------------------------------------------------------------------ contract tables


def test_every_contract_row_is_a_collected_test__qa02_table_001() -> None:
    """QA02-TABLE-001: no row points at a test that does not exist, and no scenario is unlisted."""
    # Given: the referenced test ids
    referenced = {row.test for row in CONTRACT_ROWS}

    # When: pytest collects the scenario module
    completed = subprocess.run(  # noqa: S603 -- fixed interpreter and arguments
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", "-o", "addopts=", SCENARIOS],
        cwd=_generate.REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )
    assert completed.returncode == 0, completed.stdout[-4000:] + completed.stderr[-4000:]
    collected = {line.strip() for line in completed.stdout.splitlines() if "::" in line}

    # Then: every row is collected
    assert sorted(referenced - collected) == []

    # And: every scenario has a row
    assert sorted(collected - referenced) == []


def test_the_contract_table_is_well_formed__qa02_table_002() -> None:
    """QA02-TABLE-002: unique ids, one sentinel per epic, every v2 change has its note."""
    # Then: the table has no structural defect
    assert table_defects(CONTRACT_ROWS, epics=EPICS, repository=_generate.REPOSITORY_ROOT) == []

    # And: v1-unchanged rows exist for the entries with a v1 counterpart
    assert {row.epic for row in CONTRACT_ROWS if row.kind == "v1_unchanged"} == {704, 705}


def _valid_row(**changes: Any) -> ContractRow:
    base = ContractRow("QA02-X", 703, "v2_intentional", "b", "t", sentinel_for=707, note=(_MIGRATION, "| IC-1 |"))
    return dataclasses.replace(base, **changes)


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        pytest.param((_valid_row(), _valid_row()), "duplicate row id QA02-X", id="QA02-TABLE-NEG-DUPLICATE"),
        pytest.param((_valid_row(sentinel_for=None),), "epic #703 has no sentinel row", id="QA02-TABLE-NEG-NO-SENTINEL"),
        pytest.param((_valid_row(note=None),), "QA02-X: a v2-intentional row needs a migration note", id="QA02-TABLE-NEG-NO-NOTE"),
        pytest.param((_valid_row(note=(_MIGRATION, "no such phrase")),), "QA02-X: migration note", id="QA02-TABLE-NEG-PHRASE"),
        pytest.param((_valid_row(note=("docs/absent.md", "x")),), "QA02-X: migration note docs/absent.md does not exist", id="QA02-TABLE-NEG-NO-DOC"),
        pytest.param(
            (_valid_row(), _valid_row(id="QA02-Y", kind="v1_unchanged")),
            "QA02-Y: a v1-unchanged row has no migration note",
            id="QA02-TABLE-NEG-V1-NOTE",
        ),
    ],
)
def test_contract_table_defects_are_named(rows: tuple[ContractRow, ...], expected: str) -> None:
    """QA02-TABLE-NEG-*: each kind of table defect makes the gate red."""
    # When: a defective table is validated for the Graph epic only
    defects = table_defects(rows, epics=(703,), repository=_generate.REPOSITORY_ROOT)

    # Then: the defect is named
    assert any(defect.startswith(expected) for defect in defects), defects
