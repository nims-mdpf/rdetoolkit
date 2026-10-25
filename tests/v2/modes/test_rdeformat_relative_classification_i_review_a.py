"""RDEFormat classifies relative to the data root (Session I-REVIEW-A, #7 / R1).

``RdeFormatRawCopyStrategy`` searched the **absolute** ``source.parts`` for
``raw`` / ``meta`` / ``structured`` / ..., so an ancestor directory outside the
project decided where an unpacked file landed. v1 never had that exposure: its
entry point works from a CWD-relative ``data/temp/0000/raw/...``.

Review R1's counterexample: the ordinary RDEFormat fixture placed under
``<tmp>/raw/<project>/`` publishes ``result.csv`` into ``data/raw/`` instead of
``data/structured/``, and the run still succeeds.

EP table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-IRA-7-EP-050 | ancestor-free | ``<tmp>/project`` | the v1 output tree |
| TC-IRA-7-EP-051 | ancestor ``raw`` | ``<tmp>/raw/project`` | the same tree and contents |
| TC-IRA-7-EP-054 | ancestor ``meta`` | ``<tmp>/meta/project`` | the same tree and contents |
| TC-IRA-7-EP-055 | ancestor ``structured`` | ``<tmp>/structured/project`` | the same tree and contents |
| TC-IRA-7-EP-056 | ancestor ``main_image`` | ``<tmp>/main_image/project`` | the same tree and contents |

Component priority matters for what an ancestor *could* hijack: the strategy
checks ``raw, main_image, other_image, meta, structured, logs, nonshared_raw``
in that order and stops at the first match. Under absolute-path
classification a ``raw`` ancestor therefore hijacked every file, ``main_image``
hijacked the ``meta`` and ``structured`` files, ``meta`` hijacked the
``structured`` file, while a ``structured`` ancestor could hijack nothing in
this fixture (every file's own component outranks it). EP-055 is kept as the
review asked for it and pins the correct outcome; EP-051/054/056 are the seats
that go red when the relative classification is lost.

The expectation is v1's: the frozen ``rdeformat/ok`` observation. v1's entry
point works from a CWD-relative ``data/`` tree, so its output is the same under
any ancestor; until Session K1 each cell re-ran v1 below the same ancestor to
show it, and K1 ruling #4 replaced that live "v1 half" with the frozen snapshot.
The comparison is the full parity observation (tree, raw digests, invoices,
artifact digests), which is stronger than the per-file digest walk it replaced.

BV / negative table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-IRA-7-EV-052 | oracle | the ancestor layout | v2 matches the frozen v1 observation exactly |
| TC-IRA-7-EV-053 | outside the root | a source that is not below ``data_root`` | no classification, nothing copied |
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.core.flow import flow
from rdetoolkit.modes.rdeformat import RdeFormatRawCopyStrategy
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import InputPaths, RdeConfig
from tests.v2.contract.fixtures import _generate
from tests.v2.contract.frozen import frozen_observed
from tests.v2.contract.observe import parity_pair

@flow
def _noop_flow(paths: InputPaths) -> None:
    """Consume one tile without writing anything the Runner does not own."""
    assert paths.inputdata.is_dir()


def _overrides() -> dict[str, Any]:
    return {
        "system": {
            "extended_mode": "rdeformat",
            "save_raw": True,
            "save_nonshared_raw": True,
            "save_thumbnail_image": False,
            "magic_variable": False,
        },
        "smarttable": {"save_table_file": False},
    }


def _run_v2(case_root: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run the RDEFormat case through the v2 Runner; return (actual, expected) parity views."""
    expected = frozen_observed("v1/rdeformat/ok")
    _generate.materialize_sut_case("rdeformat", case_root)
    monkeypatch.chdir(case_root)
    runner = Runner(
        root=case_root,
        inputdata_path=case_root / "data" / "inputdata",
        unpacked_dir_path=case_root / "data" / "temp",
    )
    report = runner.run(_noop_flow, **_overrides())
    assert report.status == "success", report.error
    return parity_pair(case_root, expected)


def _published(view: dict[str, Any]) -> set[str]:
    """Return the ``data``-relative paths of every published file of a parity view."""
    return {path.removeprefix("data/") for path in view["output_tree"]["files"]}


def test_plain_layout_matches_v1__tc_ira_7_ep_050(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-IRA-7-EP-050: with no misleading ancestor, v2 reproduces v1's tree."""
    # Given: the RDEFormat fixture under an ordinary project directory
    # When: the v2 Runner processes it
    actual, expected = _run_v2(tmp_path / "v2" / "project", monkeypatch)

    # Then: every published file matches the frozen v1 run, path and content
    assert actual == expected


@pytest.mark.parametrize(
    "ancestor",
    [
        pytest.param("raw", id="TC-IRA-7-EP-051-raw"),
        pytest.param("meta", id="TC-IRA-7-EP-054-meta"),
        pytest.param("structured", id="TC-IRA-7-EP-055-structured"),
        pytest.param("main_image", id="TC-IRA-7-EP-056-main_image"),
    ],
)
def test_ancestor_named_like_a_component_does_not_reclassify__tc_ira_7_ep_051_054_055_056_ev_052(
    ancestor: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-IRA-7-EP-051/054/055/056 + EV-052: a component-named ancestor changes nothing.

    This is review R1's counterexample and its required test: the same ZIP is
    processed below an ancestor named after a classification component. Before
    this session ``result.csv`` landed in ``data/raw/`` under a ``raw``
    ancestor; a ``meta`` or ``structured`` ancestor would have hijacked every
    file into that component instead, because the first matching component of
    the *absolute* path won.
    """
    # Given: the same fixture below an ancestor directory named like a component
    # When: the v2 Runner processes it from that misleading location
    actual, expected = _run_v2(tmp_path / "v2" / ancestor / "project", monkeypatch)

    # Then: the tree is v1's, not the ancestor's
    assert actual == expected

    # And: each artifact sits in the component its own path names ...
    published = _published(actual)
    assert "structured/result.csv" in published
    assert "divided/0001/meta/metadata.json" in published
    assert "raw/first.txt" in published

    # ... and nowhere else: the ancestor's component hijacked nothing
    hijacked = {
        "raw/result.csv",
        "raw/metadata.json",
        "divided/0001/raw/metadata.json",
        "meta/first.txt",
        "meta/result.csv",
        "divided/0001/meta/日本語データ.txt",
        "structured/first.txt",
        "structured/metadata.json",
        "divided/0001/structured/日本語データ.txt",
        "divided/0001/structured/metadata.json",
        "main_image/first.txt",
        "main_image/result.csv",
        "divided/0001/main_image/日本語データ.txt",
        "divided/0001/main_image/metadata.json",
    }
    assert hijacked.isdisjoint(published)


def test_source_outside_the_data_root_is_not_classified__tc_ira_7_ev_053(tmp_path: Path) -> None:
    """TC-IRA-7-EV-053: a source the data root does not contain is skipped."""
    # Given: an input file that lives outside the run's data root
    data_root = tmp_path / "data"
    outside = tmp_path / "elsewhere" / "raw" / "stray.txt"
    outside.parent.mkdir(parents=True)
    outside.write_text("stray", encoding="utf-8")
    raw_dir = data_root / "raw"
    nonshared_raw_dir = data_root / "nonshared_raw"
    for directory in (raw_dir, nonshared_raw_dir):
        directory.mkdir(parents=True)

    # When: the RDEFormat strategy publishes it
    RdeFormatRawCopyStrategy().copy(
        (outside,),
        raw_dir=raw_dir,
        nonshared_raw_dir=nonshared_raw_dir,
        config=RdeConfig(),
        data_root=data_root,
    )

    # Then: no component matched, so nothing was published anywhere
    assert list(raw_dir.iterdir()) == []
    assert list(nonshared_raw_dir.iterdir()) == []
