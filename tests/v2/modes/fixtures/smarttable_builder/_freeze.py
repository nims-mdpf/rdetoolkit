"""Freeze v1's SmartTable invoice initializer as a unit-level oracle (Session K2-0).

Writer revision: each snapshot's ``source.commit``. Re-run this script; never
hand-edit a snapshot.

Ruling #1: until Session K2-0 ``tests/v2/modes/test_smarttable_invoice_builder_i6_c.py``
executed v1's ``SmartTableInvoiceInitializer`` live, on byte-identical inputs,
as the oracle of ``SmartTableInvoiceBuilder``. That processor is deleted in
Phase K2, so every observation it made is frozen here first: one registered
:class:`BuilderCase` (row CSV per step, base invoice, schema, metadata
definition, pre-existing metadata) -> the written tile ``invoice.json``, the
written ``meta/metadata.json``, the returned row dictionary, or the normalized
error, plus the source invoice after the last step.

This module is the **only** place in ``tests/v2`` that imports
``rdetoolkit.processing``, and it does so only inside the oracle worker
(:func:`_v1_step_runner`): each case runs in its own subprocess because v1
keeps the base invoice in a process-global class cache (``_BASE_INVOICE_CACHE``),
so two cases in one interpreter could observe each other.

The materialization (:func:`materialize_case` / :func:`step_paths`) and the
observation (:func:`observe_case`) are shared verbatim by the freezer and by
the v2 tests -- only the step runner differs -- so a frozen value and a v2
observation can only differ by what the two implementations did.

Pending policy (ruling #4): a registered case whose snapshot does not exist
yet is "pending freeze" while ``_generate.ALLOW_PENDING_SNAPSHOTS`` holds -- the
single switch of the K1 ritual governs both freezers. ``--check`` lists it
without failing and ``frozen.require_builder_snapshot`` skips.

Usage -- always with the gate interpreter ``.tox/py312-module/bin/python`` (the
environment the full ``tox -e py312-module`` suite compares in), and after
``_generate.py`` in the same ritual (its hygiene gate rejects dirty builder
snapshots; this one accepts dirty K1 snapshots)::

    .tox/py312-module/bin/python tests/v2/modes/fixtures/smarttable_builder/_freeze.py          # write (clean tree)
    .tox/py312-module/bin/python tests/v2/modes/fixtures/smarttable_builder/_freeze.py --check  # re-observe and compare
"""

from __future__ import annotations

import argparse
import copy
import csv
import dataclasses
import hashlib
import io
import json
import math
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tests.v2.contract.fixtures import _generate  # noqa: E402

FIXTURE_ROOT = Path(__file__).resolve().parent
_FIXTURE_RELATIVE_ROOT = FIXTURE_ROOT.relative_to(REPOSITORY_ROOT)

#: The v1 class every snapshot observed.
ORACLE = "rdetoolkit.processing.processors.invoice.SmartTableInvoiceInitializer"

#: ``--check`` prefix for a registered but not-yet-frozen snapshot (shared with K1).
PENDING_FREEZE_PREFIX = _generate.PENDING_FREEZE_PREFIX

#: Placeholder for the materialized case root inside an observation.
ROOT_PLACEHOLDER = "<ROOT>"

#: Name of the observation file the oracle worker leaves in the case root.
_OBSERVATION_NAME = ".oracle_observation.json"

#: Families: ``i6c`` -- the I6-C merge rules and the G2-G8 gaps;
#: ``k2`` -- the R3 port of the v1 initializer test files, original TC ids.
FAMILIES = ("i6c", "k2")


# --------------------------------------------------------------------------
# Case model
# --------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Step:
    """One SmartTable row the run builds, in order.

    Attributes:
        csv_text: Row CSV content; ``None`` keeps the reference but writes no
            file (an unreadable row CSV).
        dist: ``tile`` (``divided/0001/invoice/invoice.json``) or ``source``
            (the run's ``invoice/invoice.json``, as v1's tile 0 does).
        row_reference: ``False`` gives the tile no row CSV at all.
        pop_source_sample_keys: ``sample`` keys removed from the source invoice
            on disk before this step (an external mutation between rows).
    """

    csv_text: str | None
    dist: str = "tile"
    row_reference: bool = True
    pop_source_sample_keys: tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True)
class BuilderCase:
    """One frozen v1 initializer observation.

    Attributes:
        family: One of :data:`FAMILIES`.
        test_id: The TC id of the test that consumes the case.
        steps: Rows built in order by one run (one builder / one class cache).
        invoice: Source ``invoice/invoice.json``; ``None`` leaves it absent.
        schema: ``tasksupport/invoice.schema.json``.
        metadata_def: ``tasksupport/metadata-def.json``; ``None`` leaves it absent.
        metadata: Pre-existing tile ``meta/metadata.json``; ``None`` leaves it absent.
        variant: Optional scenario name; the stem is ``<test_id>[__<variant>]``.
    """

    family: str
    test_id: str
    steps: tuple[Step, ...]
    invoice: Mapping[str, Any] | None
    schema: Mapping[str, Any]
    metadata_def: Any = None
    metadata: Mapping[str, Any] | None = None
    variant: str | None = None

    @property
    def stem(self) -> str:
        """Snapshot file stem: ``<test_id>[__<variant>]``."""
        return self.test_id if self.variant is None else f"{self.test_id}__{self.variant}"

    @property
    def case_id(self) -> str:
        """Stable identifier ``<family>/<stem>``."""
        return f"{self.family}/{self.stem}"

    def snapshot_path(self, root: Path | None = None) -> Path:
        """Return the frozen snapshot path below ``root`` (default: this directory)."""
        return (root if root is not None else FIXTURE_ROOT) / self.family / f"{self.stem}.json"


@dataclasses.dataclass(frozen=True)
class StepPaths:
    """The concrete files one step reads and writes below a case root."""

    root: Path
    rowfile: Path | None
    invoice_org: Path
    schema_path: Path
    dist_path: Path
    metadata_def_path: Path
    metadata_path: Path

    @property
    def tile_dir(self) -> Path:
        """The tile output directory (``divided/0001``)."""
        return self.root / "divided" / "0001"


#: A step runner executes one implementation on one step and returns its row dictionary.
StepRunner = Callable[[StepPaths], "dict[str, Any] | None"]


# --------------------------------------------------------------------------
# Shared inputs
# --------------------------------------------------------------------------

_SAMPLEFILE = REPOSITORY_ROOT / "tests" / "samplefile"


def _load_samplefile(name: str) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((_SAMPLEFILE / name).read_text(encoding="utf-8"))
    return loaded


def _row_csv(row: Mapping[str, str]) -> str:
    """Render one row the way v1's initializer tests wrote it (``csv.DictWriter``)."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(row))
    writer.writeheader()
    writer.writerow(dict(row))
    return buffer.getvalue()


OWNER_ID = "0" * 55 + "1"
SAMPLE_OWNER_ID = "0" * 55 + "5"
CSV_OWNER_ID = "0" * 55 + "9"
GENERAL_TERM = "3adf9874-7bcb-e5f8-99cb-3d6fd9d7b55e"
CLASS_ID = "01cb3c01-37a4-5a43-d8ca-f523ca99a75b"
SPECIFIC_TERM = "3250c45d-0ed6-1438-43b5-eb679918604a"
LINKED_SAMPLE_ID = "00000000-0000-0000-0000-000000000009"

SAMPLE_SCHEMA: dict[str, Any] = _load_samplefile("invoice.schema.json")

BASE_INVOICE: dict[str, Any] = {
    "datasetId": "seed-dataset",
    "basic": {
        "dateSubmitted": "2026-09-01",
        "dataOwnerId": OWNER_ID,
        "dataName": "inherited-name",
        "instrumentId": "inherited-instrument",
    },
    "custom": {"sample9": "inherited-custom"},
    "sample": {
        "sampleId": "00000000-0000-0000-0000-000000000001",
        "names": ["inherited-sample"],
        "description": "inherited description",
        "composition": "inherited composition",
        "referenceUrl": "https://example.invalid/inherited",
        "ownerId": SAMPLE_OWNER_ID,
        "generalAttributes": [{"termId": GENERAL_TERM, "value": "inherited-general"}],
        "specificAttributes": [
            {"classId": CLASS_ID, "termId": SPECIFIC_TERM, "value": "inherited-specific"},
        ],
    },
}

#: A base invoice whose sample declares neither attribute container.
NO_SAMPLE_ATTRIBUTE_INVOICE: dict[str, Any] = {
    "basic": {"dateSubmitted": "2026-09-01", "dataOwnerId": OWNER_ID, "dataName": "inherited-name"},
    "custom": {},
    "sample": {"sampleId": "00000000-0000-0000-0000-000000000001"},
}

#: A base invoice with no ``basic`` section, which v1 tolerates.
NO_BASIC_INVOICE: dict[str, Any] = {
    "datasetId": "seed-dataset",
    "custom": {},
    "sample": {"names": ["inherited-sample"]},
}

METADATA_DEF: dict[str, Any] = {
    "comment": {"name": {"ja": "コメント", "en": "Comment"}, "schema": {"type": "string"}},
    "temperature": {
        "name": {"ja": "温度", "en": "Temperature"},
        "schema": {"type": "number"},
        "unit": "C",
    },
    # A definition that declares no type: v1 stores the raw string.
    "untyped": {"name": {"ja": "型なし", "en": "Untyped"}, "schema": {}},
}


def _with_basic(invoice: Mapping[str, Any], **changes: Any) -> dict[str, Any]:
    """Return a deep copy of ``invoice`` whose ``basic`` keys are replaced; ``None`` removes one."""
    updated = copy.deepcopy(dict(invoice))
    for key, value in changes.items():
        if value is None:
            updated["basic"].pop(key, None)
        else:
            updated["basic"][key] = value
    return updated


def _with_sample(invoice: Mapping[str, Any], **changes: Any) -> dict[str, Any]:
    """Return a deep copy of ``invoice`` whose ``sample`` keys are replaced."""
    updated = copy.deepcopy(dict(invoice))
    updated["sample"].update(changes)
    return updated


def _repository_safe(invoice: Mapping[str, Any], *, owner_id: str = OWNER_ID) -> dict[str, Any]:
    """Replace the real owner hashes of a ``tests/samplefile`` invoice.

    The legacy sample files predate the fixture PII policy; the frozen corpus
    is public, so -- exactly like ``_generate._smarttable_invoice`` -- the owner
    identities are synthetic. No rule under test depends on their value.
    """
    safe = copy.deepcopy(dict(invoice))
    safe["basic"]["dataOwnerId"] = owner_id
    if safe.get("sample", {}).get("ownerId") is not None:
        safe["sample"]["ownerId"] = SAMPLE_OWNER_ID
    return safe


#: ``tests/samplefile/invoice.json`` as the R3 initializer tests copied it.
R3_SAMPLE_INVOICE: dict[str, Any] = _repository_safe(_load_samplefile("invoice.json"))


def _dummy_sample_invoice() -> dict[str, Any]:
    """``_build_invoice_with_dummy_sample`` of the v1 initializer tests (issue #455)."""
    invoice = copy.deepcopy(R3_SAMPLE_INVOICE)
    invoice["sample"].update(
        {
            "sampleId": "aaaabbbb-1111-2222-3333-ccccddddeeee",
            "description": "Dummy description",
            "composition": "Dummy composition",
            "referenceUrl": "https://dummy.example.com",
        },
    )
    for attribute in (*invoice["sample"]["generalAttributes"], *invoice["sample"]["specificAttributes"]):
        attribute["value"] = "dummy_value"
    return invoice


R3_DUMMY_SAMPLE_INVOICE: dict[str, Any] = _dummy_sample_invoice()
R3_RESTRUCTURED_INVOICE: dict[str, Any] = _repository_safe(
    _load_samplefile("invoice_restructured.json"),
    owner_id="0" * 55 + "2",
)
R3_FULL_SCHEMA: dict[str, Any] = _load_samplefile("invoice.schema.full.json")


def _issue_429_schema(field_name: str, field_schema: Mapping[str, Any] | None) -> dict[str, Any]:
    """``_update_custom_schema_field`` of the v1 issue-429 tests."""
    schema = copy.deepcopy(SAMPLE_SCHEMA)
    custom_properties = schema["properties"]["custom"]["properties"]
    custom_properties.pop(field_name, None)
    if field_schema is not None:
        custom_properties[field_name] = dict(field_schema)
    return schema


_TEMPERATURE_LABEL = {"ja": "温度", "en": "Temperature"}


# --------------------------------------------------------------------------
# Case registry
# --------------------------------------------------------------------------


def _single(  # noqa: PLR0913 -- one keyword per case input
    test_id: str,
    csv_text: str | None,
    *,
    family: str = "i6c",
    variant: str | None = None,
    invoice: Mapping[str, Any] | None = BASE_INVOICE,
    schema: Mapping[str, Any] = SAMPLE_SCHEMA,
    metadata_def: Any = METADATA_DEF,
    metadata: Mapping[str, Any] | None = None,
    dist: str = "tile",
    row_reference: bool = True,
) -> BuilderCase:
    return BuilderCase(
        family=family,
        test_id=test_id,
        steps=(Step(csv_text, dist=dist, row_reference=row_reference),),
        invoice=invoice,
        schema=schema,
        metadata_def=metadata_def,
        metadata=metadata,
        variant=variant,
    )


_HEADER_FULL = (
    "basic/dataName,custom/sample2,custom/sample3,custom/invert_phase_axis,"
    f"sample/names,sample/description,sample/generalAttributes.{GENERAL_TERM},"
    f"sample/specificAttributes.{CLASS_ID}.{SPECIFIC_TERM},meta/comment,meta/temperature,inputdata1"
)

#: TC-I6-C merge partitions, inputs exactly as the live-oracle module had them.
I6C_MERGE_ROWS: tuple[tuple[str, str, Mapping[str, Any] | None], ...] = (
    ("TC-I6-C-EP-001", "basic/dataName\nrow-name\n", BASE_INVOICE),
    (
        "TC-I6-C-EP-002",
        "custom/sample2,custom/sample3,custom/invert_phase_axis,custom/sample9\n2.5,7,true,text\n",
        BASE_INVOICE,
    ),
    ("TC-I6-C-EP-003", "sample/names,sample/description\nnew-sample,fresh\n", BASE_INVOICE),
    (
        "TC-I6-C-EP-004",
        f"sample/sampleId,sample/generalAttributes.{GENERAL_TERM},"
        f"sample/specificAttributes.{CLASS_ID}.{SPECIFIC_TERM}\n"
        f"{LINKED_SAMPLE_ID},general-a,specific-a\n",
        BASE_INVOICE,
    ),
    ("TC-I6-C-EP-006", "basic/dataName,basic/instrumentId,custom/sample9\nkept,,\n", BASE_INVOICE),
    ("TC-I6-C-EP-007", "sample/ownerId,basic/dataName\n" + "0" * 55 + "7,owned\n", BASE_INVOICE),
    ("TC-I6-C-EP-008", "basic/dataName\nno-base\n", None),
    (
        "TC-I6-C-EP-010",
        _HEADER_FULL + "\nrow-name,2.5,7,false,new-sample,fresh,general-a,specific-a,memo,20.5,input/row.txt\n",
        BASE_INVOICE,
    ),
    (
        "TC-I6-C-EP-011",
        f"sample/sampleId,sample/generalAttributes.{GENERAL_TERM},"
        f"sample/specificAttributes.{CLASS_ID}.{SPECIFIC_TERM},sample/composition\n"
        f"{LINKED_SAMPLE_ID},,,\n",
        BASE_INVOICE,
    ),
    (
        "TC-I6-C-EP-012",
        f"sample/sampleId,sample/generalAttributes.{GENERAL_TERM},"
        f"sample/specificAttributes.{CLASS_ID}.{SPECIFIC_TERM}\n"
        f"{LINKED_SAMPLE_ID},general-new,specific-new\n",
        NO_SAMPLE_ATTRIBUTE_INVOICE,
    ),
    ("TC-I6-C-EP-013", f"sample/sampleId\n{LINKED_SAMPLE_ID}\n", NO_BASIC_INVOICE),
    (
        "TC-I6-C-EP-014",
        "sample/sampleId,sample/specificAttributes.classonly,sample/specificAttributes.emptyonly\n"
        f"{LINKED_SAMPLE_ID},specific-x,\n",
        BASE_INVOICE,
    ),
    (
        "TC-I6-C-EP-016",
        f"sample/names,sample/description,sample/composition,sample/generalAttributes.{GENERAL_TERM}\n"
        "new-sample,,,\n",
        BASE_INVOICE,
    ),
    (
        "TC-I6-C-EP-017",
        "sample/sampleId,sample/generalAttributes.11111111-1111-1111-1111-111111111111,"
        f"sample/specificAttributes.{CLASS_ID}.22222222-2222-2222-2222-222222222222\n"
        f"{LINKED_SAMPLE_ID},general-added,specific-added\n",
        BASE_INVOICE,
    ),
    ("TC-I6-C-EP-015", "meta/untyped\nraw-value\n", BASE_INVOICE),
)

_EV021_SCHEMA: dict[str, Any] = {
    "properties": {
        "custom": {
            "type": "object",
            "label": {"ja": "c", "en": "c"},
            "properties": {"untyped": {"label": {"ja": "u", "en": "u"}}},
        },
    },
}

#: TC-I6-C rejected rows: (id, row, schema, metadata definition).
I6C_FAILURE_ROWS: tuple[tuple[str, str, Mapping[str, Any], Any], ...] = (
    ("TC-I6-C-EV-020", "custom/unknown_field\nvalue\n", SAMPLE_SCHEMA, METADATA_DEF),
    ("TC-I6-C-EV-021", "custom/untyped\nvalue\n", _EV021_SCHEMA, METADATA_DEF),
    ("TC-I6-C-EV-022", "custom/sample3\nnot-an-int\n", SAMPLE_SCHEMA, METADATA_DEF),
    ("TC-I6-C-EV-023", "custom/invert_phase_axis\nyes\n", SAMPLE_SCHEMA, METADATA_DEF),
    ("TC-I6-C-EV-024", "custom/sample2\ninf\n", SAMPLE_SCHEMA, METADATA_DEF),
    ("TC-I6-C-EV-025", "meta/undefined\nvalue\n", SAMPLE_SCHEMA, METADATA_DEF),
    (
        "TC-I6-C-EV-026",
        "meta/comment\nvalue\n",
        SAMPLE_SCHEMA,
        {"comment": {"variable": True, "schema": {"type": "string"}}},
    ),
    ("TC-I6-C-EV-027", "meta/comment\nvalue\n", SAMPLE_SCHEMA, {"comment": {"schema": {"type": "array"}}}),
    ("TC-I6-C-EV-032", "custom/sample2\nnot-a-number\n", SAMPLE_SCHEMA, METADATA_DEF),
    ("TC-I6-C-EV-033", "meta/temperature\nnot-a-number\n", SAMPLE_SCHEMA, METADATA_DEF),
    ("TC-I6-C-EV-034", "meta/comment\nvalue\n", SAMPLE_SCHEMA, ["not", "an", "object"]),
)

_EXISTING_METADATA: dict[str, Any] = {"constant": {"existing": {"value": "keep"}}, "variable": [{"seq": 1}]}

#: G8: a metadata.json that already holds the column's key, with another unit.
_OVERWRITTEN_METADATA: dict[str, Any] = {
    "constant": {"comment": {"value": "old", "unit": "note"}, "other": {"value": "preserve"}},
    "variable": [{"cycle": {"value": "A"}}],
}
_UNIT_METADATA_DEF: dict[str, Any] = {
    "comment": {
        "name": {"ja": "コメント", "en": "Comment"},
        "schema": {"type": "string"},
        "unit": "updated-unit",
    },
}


def _i6c_cases() -> list[BuilderCase]:
    """Every observation the former live-oracle module made (G1)."""
    cases = [_single(test_id, csv_text, invoice=invoice) for test_id, csv_text, invoice in I6C_MERGE_ROWS]
    cases.extend(
        _single(test_id, csv_text, schema=schema, metadata_def=metadata_def)
        for test_id, csv_text, schema, metadata_def in I6C_FAILURE_ROWS
    )
    scalar_container = _with_sample(BASE_INVOICE, generalAttributes="not-a-list")
    cases.extend(
        [
            _single("TC-I6-C-EP-005", "meta/comment,meta/temperature\nmemo-a,20.5\n"),
            _single("TC-I6-C-EP-009", "meta/comment\nmemo-a\n", metadata=_EXISTING_METADATA),
            _single("TC-I6-C-BV-040", "custom/sample2\n3\n"),
            _single(
                "TC-I6-C-EV-029",
                f"sample/sampleId,sample/generalAttributes.{GENERAL_TERM}\nkeep,general-a\n",
                invoice=scalar_container,
            ),
            _single("TC-I6-C-EV-028", "basic/dataName,meta/comment\nrow-name,memo-a\n", metadata_def=None),
            _single("TC-I6-C-EV-030", "basic/dataName\n"),
            _single("TC-I6-C-EV-031", None),
        ],
    )
    return cases


def _gap_cases() -> list[BuilderCase]:
    """G2-G8 of ``deletion_coverage.md`` §2: merge rules no case pinned yet."""
    no_containers = _with_sample(BASE_INVOICE, generalAttributes=None, specificAttributes=None)
    return [
        # G2 (#292/#429): boolean cells ignore case and surrounding blanks.
        _single(
            "TC-I6-C-BV-046",
            "custom/invert_phase_axis,custom/enable_feature,custom/flag_lowercase,custom/flag_mixed\n"
            "FALSE,TRUE,true,False\n",
            variant="mixed_case",
        ),
        _single(
            "TC-I6-C-BV-046",
            "custom/invert_phase_axis,custom/enable_feature\n TRUE , false \n",
            variant="padded",
        ),
        # G3: an empty or blank sampleId is no sample reference.
        _single("TC-I6-C-EP-018", "sample/names,sample/sampleId\nnew-sample,\n"),
        _single("TC-I6-C-EP-019", "sample/names,sample/sampleId\nnew-sample,   \n"),
        # G4: without a dataOwnerId the inherited sample.ownerId stays.
        _single("TC-I6-C-EP-020", "sample/names\nnew-sample\n", variant="missing", invoice=_with_basic(BASE_INVOICE, dataOwnerId=None)),
        _single("TC-I6-C-EP-020", "sample/names\nnew-sample\n", variant="empty", invoice=_with_basic(BASE_INVOICE, dataOwnerId="")),
        # G5: null attribute containers become lists.
        _single(
            "TC-I6-C-EP-021",
            f"sample/sampleId,sample/generalAttributes.{GENERAL_TERM},"
            f"sample/specificAttributes.{CLASS_ID}.{SPECIFIC_TERM}\n"
            f"{LINKED_SAMPLE_ID},general-n,specific-n\n",
            invoice=no_containers,
        ),
        # G6: two classIds x two termIds map to three distinct entries.
        _single(
            "TC-I6-C-EP-022",
            "sample/sampleId,sample/specificAttributes.class1.term1,"
            "sample/specificAttributes.class1.term2,sample/specificAttributes.class2.term1\n"
            f"{LINKED_SAMPLE_ID},value1,value2,value3\n",
            invoice=NO_SAMPLE_ATTRIBUTE_INVOICE,
        ),
        # G7: an integer column rejects a decimal; low magnitudes keep their type.
        _single("TC-I6-C-EV-035", "custom/sample3\n30.1\n"),
        _single("TC-I6-C-BV-040", "custom/sample2\n-1\n", variant="number_minus_one"),
        _single("TC-I6-C-BV-040", "custom/sample2\n0\n", variant="number_zero"),
        _single("TC-I6-C-BV-040", "custom/sample2\n0.0\n", variant="number_zero_point_zero"),
        _single("TC-I6-C-BV-040", "custom/sample3\n-1\n", variant="integer_minus_one"),
        # G8: the same metadata key is replaced (value and unit), others kept.
        _single(
            "TC-I6-C-EP-009",
            "meta/comment,basic/dataName\nnew comment,dataset\n",
            variant="overwrite",
            metadata=_OVERWRITTEN_METADATA,
            metadata_def=_UNIT_METADATA_DEF,
        ),
    ]


def _r3(test_id: str, row: Mapping[str, str], *, invoice: Mapping[str, Any] = R3_DUMMY_SAMPLE_INVOICE, schema: Mapping[str, Any] = SAMPLE_SCHEMA) -> BuilderCase:
    """One R3 port: v1 wrote the tile over the source invoice and had no metadata-def."""
    return _single(test_id, _row_csv(row), family="k2", invoice=invoice, schema=schema, metadata_def=None, dist="source")


def _r3_initializer_cases() -> list[BuilderCase]:
    """``tests/test_smarttable_invoice_initializer.py`` (R3), original TC ids."""
    general = R3_SAMPLE_INVOICE["sample"]["generalAttributes"][0]["termId"]
    specific = R3_SAMPLE_INVOICE["sample"]["specificAttributes"][0]
    specific_key = f"sample/specificAttributes.{specific['classId']}.{specific['termId']}"
    explicit_uuid = "12345678-abcd-ef01-2345-6789abcdef01"
    return [
        BuilderCase(
            family="k2",
            test_id="TC-EP-001",
            steps=(
                Step(_row_csv({"sample/names": "sample-one"}), dist="source"),
                Step(
                    _row_csv({"sample/names": "sample-two", "sample/relatedSample[0]": "sample-one"}),
                    pop_source_sample_keys=("ownerId",),
                ),
            ),
            invoice=R3_SAMPLE_INVOICE,
            schema=SAMPLE_SCHEMA,
        ),
        _r3("TC-BV-001", {"sample/names": "sample-one"}, invoice=R3_SAMPLE_INVOICE),
        _single("TC-EP-002", None, family="k2", invoice=R3_SAMPLE_INVOICE, metadata_def=None, dist="source", row_reference=False),
        _r3("TC-EP-003", {"sample/names": "sample-one"}, invoice=_with_basic(R3_SAMPLE_INVOICE, dataOwnerId=None)),
        _r3("TC-BV-003", {"sample/names": "sample-one"}, invoice=_with_basic(R3_SAMPLE_INVOICE, dataOwnerId="")),
        # The CSV owner is synthetic (v1 used a mnemonic string) so the frozen
        # corpus meets the owner-identity policy of TC-H4-PII-003.
        _r3("TC-EP-004", {"sample/names": "sample-one", "sample/ownerId": CSV_OWNER_ID}, invoice=R3_SAMPLE_INVOICE),
        _r3("TC-EP-005", {"sample/names": "New Sample"}),
        _r3("TC-EP-006", {"sample/names": "Existing Sample", "sample/sampleId": explicit_uuid}),
        _r3("TC-EP-007", {"basic/dataName": "Only Basic Update"}),
        _r3("TC-EP-008", {"sample/names": "Brand New", "sample/sampleId": ""}),
        _r3("TC-EP-009", {"sample/names": "New Sample"}),
        _r3(
            "TC-EP-010",
            {
                "sample/names": "Brand New Fixed Header",
                "sample/sampleId": "",
                "sample/description": "",
                f"sample/generalAttributes.{general}": "",
                specific_key: "",
            },
        ),
        _r3("TC-EP-011", {"sample/names": "Existing Sample", "sample/sampleId": explicit_uuid, "sample/description": ""}),
        _r3(
            "TC-EP-012",
            {"sample/generalAttributes.7cc57dfb-8b70-4b3a-5315-fbce4cbf73d0": "pellet"},
            invoice=R3_RESTRUCTURED_INVOICE,
            schema=R3_FULL_SCHEMA,
        ),
        _r3(
            "TC-EP-013",
            {f"sample/specificAttributes.{CLASS_ID}.{SPECIFIC_TERM}": "single crystal"},
            invoice=R3_RESTRUCTURED_INVOICE,
            schema=R3_FULL_SCHEMA,
        ),
        _r3("TC-BV-004", {"sample/names": "Sample BV-004", "sample/sampleId": ""}),
        _r3("TC-BV-005", {"sample/names": "Sample BV-005", "sample/sampleId": "fedcba98-7654-3210-fedc-ba9876543210"}),
        _r3("TC-BV-006", {"sample/names": "Brand New BV-006", "sample/sampleId": "   "}),
    ]


def _r3_issue_429_cases() -> list[BuilderCase]:
    """``tests/test_smarttable_invoice_initializer_issue_429.py`` (R3), original TC ids."""
    number = {"label": _TEMPERATURE_LABEL, "type": "number"}
    integer = {"label": _TEMPERATURE_LABEL, "type": "integer"}
    boolean = {"label": {"ja": "有効化", "en": "Enable feature"}, "type": "boolean"}
    temperature = "process_key_temperature"
    rows: tuple[tuple[str, str, str, str, Mapping[str, Any] | None], ...] = (
        ("TC-EP-429-001", temperature, "30", temperature, number),
        ("TC-EP-429-002", temperature, "30.5", temperature, number),
        ("TC-EP-429-005", temperature, "abc", temperature, number),
        ("TC-EP-429-006", temperature, "30.1", temperature, integer),
        ("TC-EP-429-007", "enable_feature", "yes", "enable_feature", boolean),
        ("TC-EP-429-008", temperature, "30", temperature, None),
    )
    return [
        _r3(test_id, {f"custom/{column}": value}, invoice=R3_SAMPLE_INVOICE, schema=_issue_429_schema(field, field_schema))
        for test_id, column, value, field, field_schema in rows
    ]


#: Every registered case, in snapshot inventory order.
BUILDER_CASES: tuple[BuilderCase, ...] = (
    *_i6c_cases(),
    *_gap_cases(),
    *_r3_initializer_cases(),
    *_r3_issue_429_cases(),
)

_CASES_BY_ID: dict[str, BuilderCase] = {case.case_id: case for case in BUILDER_CASES}


def builder_case(case_id: str) -> BuilderCase:
    """Return the registered case ``<family>/<stem>``.

    Raises:
        KeyError: If no such case is registered.
    """
    return _CASES_BY_ID[case_id]


def snapshot_relpath(case_id: str) -> str:
    """Return the repository-relative POSIX path of a registered case's snapshot."""
    return builder_case(case_id).snapshot_path().relative_to(REPOSITORY_ROOT).as_posix()


# --------------------------------------------------------------------------
# Materialization and observation (shared by the freezer and the v2 tests)
# --------------------------------------------------------------------------


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def materialize_case(case: BuilderCase, root: Path) -> None:
    """Write the case's run-level inputs below ``root``.

    Layout (identical to the former live-oracle module)::

        root/invoice/invoice.json             source invoice (optional)
        root/tasksupport/invoice.schema.json
        root/tasksupport/metadata-def.json    (optional)
        root/divided/0001/meta/metadata.json  pre-existing metadata (optional)
        root/temp/fsmarttable_case_000N.csv   one row CSV per step
    """
    (root / "invoice").mkdir(parents=True, exist_ok=True)
    (root / "divided" / "0001" / "invoice").mkdir(parents=True, exist_ok=True)
    (root / "divided" / "0001" / "meta").mkdir(parents=True, exist_ok=True)
    (root / "temp").mkdir(parents=True, exist_ok=True)
    _write_json(root / "tasksupport" / "invoice.schema.json", case.schema)
    if case.invoice is not None:
        _write_json(root / "invoice" / "invoice.json", case.invoice)
    if case.metadata_def is not None:
        _write_json(root / "tasksupport" / "metadata-def.json", case.metadata_def)
    if case.metadata is not None:
        _write_json(root / "divided" / "0001" / "meta" / "metadata.json", case.metadata)


def step_paths(case: BuilderCase, root: Path, index: int) -> StepPaths:
    """Prepare step ``index`` of ``case`` below ``root`` and return its files."""
    step = case.steps[index]
    invoice_org = root / "invoice" / "invoice.json"
    rowfile: Path | None = None
    if step.row_reference:
        rowfile = root / "temp" / f"fsmarttable_case_{index:04d}.csv"
        if step.csv_text is not None:
            with rowfile.open("w", encoding="utf-8", newline="") as stream:
                stream.write(step.csv_text)
    if step.pop_source_sample_keys:
        source = json.loads(invoice_org.read_text(encoding="utf-8"))
        for key in step.pop_source_sample_keys:
            source["sample"].pop(key, None)
        _write_json(invoice_org, source)
    tile = root / "divided" / "0001"
    return StepPaths(
        root=root,
        rowfile=rowfile,
        invoice_org=invoice_org,
        schema_path=root / "tasksupport" / "invoice.schema.json",
        dist_path=invoice_org if step.dist == "source" else tile / "invoice" / "invoice.json",
        metadata_def_path=root / "tasksupport" / "metadata-def.json",
        metadata_path=tile / "meta" / "metadata.json",
    )


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


#: How a missing (``NaN``) row cell is recorded: unambiguous and JSON-equal.
NAN_CELL = {"float": "nan"}


def jsonable_row_data(row_data: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Return a JSON round-trippable form of the row dictionary.

    ``pandas`` reads the row CSV with ``dtype=str`` and represents an empty cell
    as ``NaN``, which compares unequal to itself. It is recorded as
    :data:`NAN_CELL` -- not ``None`` -- so a ``NaN``/``None`` difference stays
    observable.
    """
    if row_data is None:
        return None
    recorded: dict[str, Any] = {}
    for key, value in row_data.items():
        if isinstance(value, float) and math.isnan(value):
            recorded[str(key)] = dict(NAN_CELL)
        elif value is None or isinstance(value, (str, bool, int, float)):
            recorded[str(key)] = value
        else:
            recorded[str(key)] = {"repr": repr(value)}
    return recorded


def _error_record(error: BaseException) -> dict[str, Any]:
    return {
        "type": type(error).__name__,
        "message": str(error),
        "ecode": getattr(error, "ecode", None),
    }


def _written(paths: StepPaths) -> dict[str, Any]:
    return {"invoice": _read_json(paths.dist_path), "metadata": _read_json(paths.metadata_path)}


#: pydantic quotes its own ``major.minor`` in every error URL
#: (``https://errors.pydantic.dev/2.12/v/missing``). That token belongs to the
#: environment, not to the v1 contract, and no v1 oracle will remain to
#: re-freeze after a pydantic upgrade, so it is replaced on both sides.
_PYDANTIC_URL_VERSION = re.compile(r"errors\.pydantic\.dev/\d+\.\d+/")
PYDANTIC_URL_PLACEHOLDER = "errors.pydantic.dev/<ver>/"


def normalize_observation(value: Any, root: Path) -> Any:
    """Normalize the environment out of an observation.

    The case root (as given and resolved) becomes :data:`ROOT_PLACEHOLDER` and
    pydantic's version in its error URLs becomes :data:`PYDANTIC_URL_PLACEHOLDER`.
    The freezer and the v2 tests both observe through :func:`observe_case`, so
    the rule is applied symmetrically.
    """
    if isinstance(value, Mapping):
        return {str(key): normalize_observation(item, root) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_observation(item, root) for item in value]
    if isinstance(value, str):
        for candidate in sorted({str(root), str(root.resolve())}, key=len, reverse=True):
            value = value.replace(candidate, ROOT_PLACEHOLDER)
        return _PYDANTIC_URL_VERSION.sub(PYDANTIC_URL_PLACEHOLDER, value)
    return value


def observe_case(case: BuilderCase, root: Path, run_step: StepRunner) -> dict[str, Any]:
    """Materialize ``case`` below ``root``, run every step and observe it.

    A failing step is recorded with the files it left behind and ends the run,
    as a failing v1 tile ended v1's pipeline.

    Args:
        case: The registered case.
        root: Empty directory owned by this observation.
        run_step: The implementation under observation.

    Returns:
        ``{"steps": [...], "source_invoice": ...}``, normalized.
    """
    materialize_case(case, root)
    steps: list[dict[str, Any]] = []
    for index in range(len(case.steps)):
        paths = step_paths(case, root, index)
        try:
            row_data = run_step(paths)
        except Exception as error:  # noqa: BLE001 -- the type is part of the observation
            steps.append({"error": _error_record(error), **_written(paths)})
            break
        steps.append({"row_data": jsonable_row_data(row_data), **_written(paths)})
    observation = {"steps": steps, "source_invoice": _read_json(root / "invoice" / "invoice.json")}
    normalized: dict[str, Any] = normalize_observation(observation, root)
    return normalized


# --------------------------------------------------------------------------
# The v1 oracle (worker process only)
# --------------------------------------------------------------------------


def _v1_step_runner() -> StepRunner:
    """Return a step runner over v1's initializer (imports ``rdetoolkit.processing``)."""
    from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath  # noqa: PLC0415
    from rdetoolkit.processing.context import ProcessingContext  # noqa: PLC0415
    from rdetoolkit.processing.processors.invoice import SmartTableInvoiceInitializer  # noqa: PLC0415

    def _run_v1_oracle(paths: StepPaths) -> dict[str, Any] | None:
        tile = paths.tile_dir
        resource_paths = RdeOutputResourcePath(
            raw=tile / "raw",
            nonshared_raw=tile / "nonshared_raw",
            rawfiles=(paths.rowfile,) if paths.rowfile is not None else (),
            struct=tile / "structured",
            main_image=tile / "main_image",
            other_image=tile / "other_image",
            meta=paths.metadata_path.parent,
            thumbnail=tile / "thumbnail",
            logs=tile / "logs",
            invoice=paths.dist_path.parent,
            invoice_schema_json=paths.schema_path,
            invoice_org=paths.invoice_org,
            smarttable_rawfile=paths.rowfile,
            attachment=tile / "attachment",
        )
        context = ProcessingContext(
            index="0001",
            srcpaths=RdeInputDirPaths(
                inputdata=paths.root / "temp",
                invoice=paths.invoice_org.parent,
                tasksupport=paths.schema_path.parent,
            ),
            resource_paths=resource_paths,
            datasets_function=None,
            mode_name="smarttable",
            # Only its presence matters to the initializer (SmartTable mode).
            smarttable_file=paths.root / "inputdata" / "smarttable_case.xlsx",
        )
        # A fresh instance per row, as v1's pipeline built one per tile; the
        # class cache is what spans the rows of one run (one worker process).
        SmartTableInvoiceInitializer().process(context)
        row_data: dict[str, Any] | None = resource_paths.smarttable_row_data
        return row_data

    return _run_v1_oracle


def _run_oracle_worker(case_id: str, root: Path) -> int:
    observation = observe_case(builder_case(case_id), root, _v1_step_runner())
    (root / _OBSERVATION_NAME).write_text(json.dumps(observation, ensure_ascii=False), encoding="utf-8")
    return 0


def observe_v1(case: BuilderCase) -> dict[str, Any]:
    """Observe one case through v1 in an isolated worker process.

    Raises:
        RuntimeError: If the worker failed to produce an observation.
    """
    with tempfile.TemporaryDirectory(prefix="rdetoolkit-k2-builder-") as temporary:
        root = Path(temporary) / "case"
        root.mkdir()
        command = [sys.executable, str(Path(__file__).resolve()), "--oracle-worker", case.case_id, str(root)]
        completed = subprocess.run(  # noqa: S603
            command,
            cwd=REPOSITORY_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        observation_path = root / _OBSERVATION_NAME
        if completed.returncode != 0 or not observation_path.exists():
            message = (
                f"v1 oracle worker failed for {case.case_id}: "
                f"exit={completed.returncode}; stderr={completed.stderr[-1000:]}"
            )
            raise RuntimeError(message)
        observed: dict[str, Any] = json.loads(observation_path.read_text(encoding="utf-8"))
        return observed


# --------------------------------------------------------------------------
# Snapshots, provenance and the CLI
# --------------------------------------------------------------------------


def _digest(value: Any) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def case_record(case: BuilderCase) -> dict[str, Any]:
    """Return the ``case`` block of a snapshot.

    The rows are recorded verbatim; the larger JSON inputs by digest, which is
    what lets a test detect that a registry input changed after the freeze.
    """
    return {
        "id": case.case_id,
        "family": case.family,
        "test_id": case.test_id,
        "variant": case.variant,
        "steps": [dataclasses.asdict(step) | {"pop_source_sample_keys": list(step.pop_source_sample_keys)} for step in case.steps],
        "inputs_sha256": {
            "invoice": _digest(case.invoice),
            "schema": _digest(case.schema),
            "metadata_def": _digest(case.metadata_def),
            "metadata": _digest(case.metadata),
        },
    }


def snapshot_paths() -> list[Path]:
    """Return the complete snapshot inventory, derived from the registry."""
    return [case.snapshot_path() for case in BUILDER_CASES]


def _frozen_source(path: Path, *, check: bool, stamped_commit: str | None) -> dict[str, Any]:
    """Carry the frozen provenance forward in check mode; stamp it when writing."""
    if check and path.exists():
        source: dict[str, Any] = json.loads(path.read_text(encoding="utf-8")).get(
            "source",
            {"oracle": ORACLE, "commit": "<unrecorded>"},
        )
        return source
    return {"oracle": ORACLE, "commit": stamped_commit}


def _recorded_commits() -> set[str]:
    recorded: set[str] = set()
    for path in sorted(FIXTURE_ROOT.rglob("*.json")):
        commit = json.loads(path.read_text(encoding="utf-8")).get("source", {}).get("commit")
        recorded.add(commit if isinstance(commit, str) else "<unrecorded>")
    return recorded


def provenance_errors() -> list[str]:
    """Return fatal errors for an unauditable recorded ``source.commit``."""
    return [
        f"frozen source.commit {commit!r} is unauditable. Remediation: {_generate._PROVENANCE_REMEDIATION}"  # noqa: SLF001
        for commit in sorted(_recorded_commits())
        if not commit or commit == "<unrecorded>" or "-dirty" in commit
    ]


def provenance_warnings(current_commit: str) -> list[str]:
    """Return non-failing warnings for snapshots written at an older revision."""
    return [
        f"warning: frozen source.commit {commit} differs from current revision {current_commit}"
        for commit in sorted(_recorded_commits())
        if commit not in {current_commit, "<unrecorded>"} and "-dirty" not in commit
    ]


def require_write_tree_hygiene(dirty_paths: Sequence[Path] | None = None) -> None:
    """Refuse to freeze unless only snapshot files are dirty.

    Builder snapshots and the K1 ``expected`` snapshots may be dirty (the two
    freezers run back to back in one ritual); anything else means the code the
    snapshot would be stamped with is not the committed one.

    Raises:
        RuntimeError: If a code path is dirty.
    """
    paths = _generate._git_dirty_paths() if dirty_paths is None else tuple(dirty_paths)  # noqa: SLF001
    allowed_roots = (
        _generate.EXPECTED_ROOT.relative_to(REPOSITORY_ROOT),
        _generate.CANARY_EXPECTED_ROOT.relative_to(REPOSITORY_ROOT),
    )
    disallowed = [
        path
        for path in paths
        if not (path.suffix == ".json" and _FIXTURE_RELATIVE_ROOT in path.parents)
        and not any(path == root or root in path.parents for root in allowed_roots)
    ]
    if disallowed:
        rendered = ", ".join(path.as_posix() for path in disallowed)
        msg = (
            f"builder snapshot freezing requires a clean code tree; dirty paths: {rendered}. "
            f"Remediation: {_generate._PROVENANCE_REMEDIATION}"  # noqa: SLF001
        )
        raise RuntimeError(msg)


def _snapshot_message(case: BuilderCase, mismatch: str) -> str:
    path = case.snapshot_path()
    if not path.exists() and _generate.ALLOW_PENDING_SNAPSHOTS:
        return f"{PENDING_FREEZE_PREFIX}{path.relative_to(REPOSITORY_ROOT).as_posix()}"
    return f"{case.case_id}: {mismatch}"


def freeze(*, check: bool, observe: Callable[[BuilderCase], dict[str, Any]] = observe_v1) -> list[str]:
    """Write (or, with ``check``, compare) every registered builder snapshot.

    Args:
        check: Compare only; never write.
        observe: The v1 observation (a test seam; the default runs the worker).

    Returns:
        Mismatch messages; a pending one starts with :data:`PENDING_FREEZE_PREFIX`.
    """
    stamped_commit = None if check else _generate._git_revision()  # noqa: SLF001
    messages: list[str] = []
    for case in BUILDER_CASES:
        path = case.snapshot_path()
        payload = {
            "source": _frozen_source(path, check=check, stamped_commit=stamped_commit),
            "case": case_record(case),
            "observed": observe(case),
        }
        if not check:
            _generate.write_json_snapshot(path, payload)
            continue
        mismatch = _generate.compare_snapshot(path, payload)
        if mismatch is not None:
            messages.append(_snapshot_message(case, mismatch))
    return messages


def run_check(*, observe: Callable[[BuilderCase], dict[str, Any]] = observe_v1) -> int:
    """Run ``--check``: provenance, then the v1 re-observation of every case."""
    errors = provenance_errors()
    if errors:
        print("\n".join(errors), file=sys.stderr)  # noqa: T201
        return 1
    for warning in provenance_warnings(_generate._git_revision()):  # noqa: SLF001
        print(warning, file=sys.stderr)  # noqa: T201
    messages = freeze(check=True, observe=observe)
    pending = [message for message in messages if message.startswith(PENDING_FREEZE_PREFIX)]
    mismatches = [message for message in messages if not message.startswith(PENDING_FREEZE_PREFIX)]
    print(f"{len(BUILDER_CASES)} registered builder case(s)")  # noqa: T201
    if pending:
        print(f"{len(pending)} registered snapshot(s) await the freeze ritual:")  # noqa: T201
        print("\n".join(pending))  # noqa: T201
    if mismatches:
        print("\n".join(mismatches), file=sys.stderr)  # noqa: T201
        return 1
    print("all frozen builder snapshots match their v1 re-observation")  # noqa: T201
    return 0


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="re-observe v1 and compare only")
    parser.add_argument("--oracle-worker", nargs=2, metavar=("CASE_ID", "ROOT"), help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Freeze, check, or (internally) observe one case in a worker."""
    args = _parse_args(argv)
    if args.oracle_worker is not None:
        case_id, root = args.oracle_worker
        return _run_oracle_worker(case_id, Path(root))
    if args.check:
        return run_check()
    require_write_tree_hygiene()
    freeze(check=False)
    print(f"froze {len(BUILDER_CASES)} v1 SmartTable initializer snapshot(s)")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
