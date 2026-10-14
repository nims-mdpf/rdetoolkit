"""Contract for the ``artifact_sha256`` observation key (review F4, ruling #1).

The PR #539 reviewer's falsification was concrete: the parity observer compared
``output_tree`` (paths), ``raw_sha256`` (``raw``/``nonshared_raw`` bytes) and
``invoices`` (parsed ``invoice/invoice.json``), so writing ``b"broken"`` into a
correctly named ``data/thumbnail/1.jpg`` passed "full artifact parity". This
module pins the new key that closes the hole and, just as importantly, pins
what it must *not* claim to own.

Equivalence partitions prepared before implementation:

| TC | Class | Input | Expected |
| --- | --- | --- | --- |
| TC-IRB-F4-EP-001 | run-produced non-raw artifact | meta / structured / thumbnail / main_image / other_image / attachment / temp files | digest per ``data/``-relative path |

Boundary and negative partitions prepared before implementation:

| TC | Class | Input | Expected |
| --- | --- | --- | --- |
| TC-IRB-F4-EV-002 | corrupted artifact bytes | same tree, thumbnail bytes replaced | ``output_tree`` unchanged, ``artifact_sha256`` differs |
| TC-IRB-F4-EV-003 | input material and logs | inputdata / tasksupport / logs / invoice.json | never observed |
| TC-IRB-F4-EV-004 | raw ownership | raw / nonshared_raw files | observed by ``raw_sha256`` only |
| TC-IRB-F4-BV-005 | missing mandatory parity key | frozen view without ``invoices`` | ``KeyError`` |
| TC-IRB-F4-EV-006 | pending-freeze narrowing | live observation vs pre-ritual snapshot | only ``artifact_sha256`` is dropped |
| TC-IRB-F4-EV-007 | run root below ``logs``/``inputdata``/``raw`` | same tree, ancestor-renamed | identical observation — classification ignores ancestors |
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tests.v2.contract.fixtures import _generate
from tests.v2.contract.observe import (
    PARITY_KEYS,
    PENDING_FREEZE_KEYS,
    parity_view,
    pending_freeze_view,
)

#: One file per artifact family ruling #1 declares in scope, plus the families
#: that must stay out of it.
_ARTIFACT_FILES = {
    "meta/metadata.json": '{"constant": {}, "variable": []}\n',
    "structured/result.csv": "x,y\n1,2\n",
    "thumbnail/1.jpg": "thumbnail bytes\n",
    "main_image/1.jpg": "main image bytes\n",
    "other_image/2.jpg": "other image bytes\n",
    "attachment/note.txt": "attached\n",
    "temp/invoice_org.json": '{"datasetId": "seed"}\n',
    "temp/fsmarttable_full_0000.csv": "col\nvalue\n",
    "divided/0001/meta/metadata.json": '{"constant": {}, "variable": []}\n',
}
_EXCLUDED_FILES = {
    "inputdata/source.txt": "input material\n",
    "tasksupport/invoice.schema.json": '{"properties": {}}\n',
    "logs/rdesys_20260922_000000.log": "log line\n",
    "invoice/invoice.json": '{"datasetId": "seed"}\n',
    "divided/0001/invoice/invoice.json": '{"datasetId": "seed"}\n',
    "raw/first.txt": "raw payload\n",
    "nonshared_raw/first.txt": "raw payload\n",
}


def _materialize(data_root: Path) -> None:
    """Write one representative tree covering every in-scope and excluded family."""
    for relative, content in {**_ARTIFACT_FILES, **_EXCLUDED_FILES}.items():
        path = data_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def test_every_run_produced_non_raw_artifact_is_digested__tc_irb_f4_ep_001(tmp_path: Path) -> None:
    """TC-IRB-F4-EP-001: each in-scope family contributes its true digest."""
    # Given: a data root holding one file per in-scope artifact family
    data_root = tmp_path / "data"
    _materialize(data_root)

    # When: observing the artifacts the run produced
    observed = _generate._artifact_hashes(data_root)  # noqa: SLF001 -- the generator owns the walker

    # Then: every family is present with the digest of its actual bytes
    assert observed == {
        f"data/{relative}": _digest(content) for relative, content in _ARTIFACT_FILES.items()
    }


def test_corrupted_artifact_bytes_break_parity__tc_irb_f4_ev_002(tmp_path: Path) -> None:
    """TC-IRB-F4-EV-002: the reviewer's counterexample no longer passes.

    ``thumbnail/1.jpg`` keeps its name and its place in the output tree, so the
    three pre-F4 parity keys are blind to the corruption.
    """
    # Given: two identical trees, one with a corrupted thumbnail
    intact = tmp_path / "intact" / "data"
    corrupted = tmp_path / "corrupted" / "data"
    _materialize(intact)
    _materialize(corrupted)
    (corrupted / "thumbnail" / "1.jpg").write_bytes(b"broken")

    # When: observing both with the generator walkers
    intact_tree = _generate._output_tree(intact)  # noqa: SLF001
    corrupted_tree = _generate._output_tree(corrupted)  # noqa: SLF001
    intact_hashes = _generate._artifact_hashes(intact)  # noqa: SLF001
    corrupted_hashes = _generate._artifact_hashes(corrupted)  # noqa: SLF001

    # Then: the pre-F4 observation is identical while the new key diverges
    assert corrupted_tree == intact_tree
    assert _generate._raw_hashes(corrupted) == _generate._raw_hashes(intact)  # noqa: SLF001
    assert corrupted_hashes != intact_hashes
    assert corrupted_hashes["data/thumbnail/1.jpg"] != intact_hashes["data/thumbnail/1.jpg"]


def test_input_material_and_logs_are_never_observed__tc_irb_f4_ev_003(tmp_path: Path) -> None:
    """TC-IRB-F4-EV-003: reading inputs or writing logs cannot break artifact parity.

    ``data/logs/`` is the one directory whose contents are contractually
    asymmetric between v1 and v2 (Design §6.3 addendum), and ``invoice.json``
    belongs to ``invoices`` where a value diff is readable.
    """
    # Given: a tree whose excluded families are all populated
    data_root = tmp_path / "data"
    _materialize(data_root)

    # When: observing the artifacts
    observed = _generate._artifact_hashes(data_root)  # noqa: SLF001

    # Then: no excluded path is claimed by the new key
    assert [path for path in observed if "/inputdata/" in path] == []
    assert [path for path in observed if "/tasksupport/" in path] == []
    assert [path for path in observed if "/logs/" in path] == []
    assert [path for path in observed if path.endswith("invoice/invoice.json")] == []


def test_raw_artifacts_stay_owned_by_raw_sha256__tc_irb_f4_ev_004(tmp_path: Path) -> None:
    """TC-IRB-F4-EV-004: the two digest keys partition the tree, never overlap."""
    # Given: a tree carrying both raw and non-raw artifacts
    data_root = tmp_path / "data"
    _materialize(data_root)

    # When: observing both digest keys
    raw = _generate._raw_hashes(data_root)  # noqa: SLF001
    artifacts = _generate._artifact_hashes(data_root)  # noqa: SLF001

    # Then: the key sets are disjoint and raw keeps its own files
    assert raw.keys() & artifacts.keys() == set()
    assert set(raw) == {"data/raw/first.txt", "data/nonshared_raw/first.txt"}


@pytest.mark.parametrize("missing", PARITY_KEYS)
def test_a_missing_mandatory_parity_key_is_fatal__tc_irb_f4_bv_005(missing: str) -> None:
    """TC-IRB-F4-BV-005: every parity key is mandatory once the corpus is frozen.

    ``artifact_sha256`` was the pending key between ritual steps (a) and (c);
    after the 2026-09-23 re-freeze nothing is pending, so a frozen observation
    that lacks *any* parity key -- the new one included -- is an error, never a
    silently narrower comparison.
    """
    # Given: nothing is pending and a frozen observation lost one parity key
    assert PENDING_FREEZE_KEYS == ()
    frozen: dict[str, object] = {
        key: ({"directories": [], "files": []} if key == "output_tree" else {})
        for key in PARITY_KEYS
        if key != missing
    }

    # When/Then: the omission is fatal
    with pytest.raises(KeyError, match=missing):
        parity_view(frozen)


def test_pending_freeze_view_is_the_identity_after_the_refreeze__tc_irb_f4_ev_006() -> None:
    """TC-IRB-F4-EV-006: no narrowing survives the re-freeze.

    Every frozen snapshot now carries ``artifact_sha256``, so the live
    observation is compared in full; a frozen snapshot that still lacked the
    key would be a stale corpus, not a reason to skip the comparison.
    """
    # Given: a live observation next to its (re-frozen) snapshot
    frozen_path = _generate.EXPECTED_ROOT / "invoice" / "ok.json"
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))["observed"]
    assert "artifact_sha256" in frozen
    live = {**frozen, "artifact_sha256": {"data/meta/metadata.json": "deadbeef"}}

    # When: passing it through the (now identity) narrowing helper
    narrowed = pending_freeze_view(live, frozen)

    # Then: nothing is dropped, so a content difference stays visible
    assert narrowed == live
    assert narrowed != frozen

    # And: a snapshot that lost the key does not get the comparison narrowed
    stale = {key: value for key, value in frozen.items() if key != "artifact_sha256"}
    assert pending_freeze_view(live, stale) == live


@pytest.mark.parametrize(
    "ancestor",
    [
        pytest.param(name, id=f"TC-IRB-F4-EV-007-{name}")
        for name in sorted(_generate._NON_ARTIFACT_COMPONENTS)  # noqa: SLF001
    ],
)
def test_classification_ignores_ancestors_of_the_data_root__tc_irb_f4_ev_007(
    ancestor: str,
    tmp_path: Path,
) -> None:
    """TC-IRB-F4-EV-007: where a run lives cannot change what it is observed to be.

    Both walkers used to classify on the *absolute* path, so a project checked
    out below a directory named ``logs`` produced an empty ``artifact_sha256``
    and one below ``raw`` had every artifact counted as a raw copy — in both
    cases silently, because v1 and v2 would have agreed on the wrong answer.
    This is the ancestor-sensitivity class the reviewer reported as R1.
    """
    # Given: the same tree twice, once below a neutral ancestor and once below
    # a directory whose name is a classification keyword
    neutral = tmp_path / "project" / "data"
    shadowed = tmp_path / ancestor / "project" / "data"
    _materialize(neutral)
    _materialize(shadowed)

    # When: observing both
    neutral_artifacts = _generate._artifact_hashes(neutral)  # noqa: SLF001
    shadowed_artifacts = _generate._artifact_hashes(shadowed)  # noqa: SLF001
    neutral_raw = _generate._raw_hashes(neutral)  # noqa: SLF001
    shadowed_raw = _generate._raw_hashes(shadowed)  # noqa: SLF001

    # Then: the observation is identical, and neither key is empty
    assert shadowed_artifacts == neutral_artifacts
    assert shadowed_raw == neutral_raw
    assert shadowed_artifacts
    assert shadowed_raw
