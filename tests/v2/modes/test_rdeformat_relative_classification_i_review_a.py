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

BV / negative table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-IRA-7-EV-052 | oracle | v1 on the ancestor layout | v2 matches v1 exactly |
| TC-IRA-7-EV-053 | outside the root | a source that is not below ``data_root`` | no classification, nothing copied |
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.core.flow import flow
from rdetoolkit.modes.rdeformat import RdeFormatRawCopyStrategy
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import InputPaths, RdeConfig
from tests.v2.contract.fixtures import _generate

_V1_ORACLE_WORKER = """
import json, os, sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, os.getcwd())
from rdetoolkit.models.config import Config, MultiDataTileSettings, SmartTableSettings, SystemSettings
from rdetoolkit.workflows import run as v1_run

config = Config(
    system=SystemSettings(
        extended_mode="rdeformat",
        save_raw=True,
        save_nonshared_raw=True,
        save_thumbnail_image=False,
        magic_variable=False,
    ),
    multidata_tile=MultiDataTileSettings(ignore_errors=False),
    smarttable=SmartTableSettings(save_table_file=False),
)

os.chdir(root)
exit_code = 0
try:
    v1_run(custom_dataset_function=lambda a, b: None, config=config)
except SystemExit as error:
    exit_code = int(error.code or 0)

(root / ".rdeformat_observation.json").write_text(
    json.dumps({"exit_code": exit_code}), encoding="utf-8",
)
"""


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


def _observe_tree(data_root: Path) -> dict[str, str]:
    """Hash every published file below the data root, keyed by relative path."""
    return {
        path.relative_to(data_root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(data_root.rglob("*"))
        if path.is_file() and "logs" not in path.relative_to(data_root).parts
    }


def _run_v2(case_root: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    _generate.materialize_sut_case("rdeformat", case_root)
    monkeypatch.chdir(case_root)
    runner = Runner(
        root=case_root,
        inputdata_path=case_root / "data" / "inputdata",
        unpacked_dir_path=case_root / "data" / "temp",
    )
    report = runner.run(_noop_flow, **_overrides())
    assert report.status == "success", report.error
    return _observe_tree(case_root / "data")


def _run_v1(case_root: Path) -> dict[str, str]:
    _generate.materialize_sut_case("rdeformat", case_root)
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _V1_ORACLE_WORKER, str(case_root)],
        cwd=_generate.REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    observation_path = case_root / ".rdeformat_observation.json"
    if not observation_path.exists():
        message = f"v1 RDEFormat oracle failed: {completed.stderr[-1500:]}"
        raise RuntimeError(message)
    assert json.loads(observation_path.read_text(encoding="utf-8"))["exit_code"] == 0
    observation_path.unlink()
    return _observe_tree(case_root / "data")


def test_plain_layout_matches_v1__tc_ira_7_ep_050(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-IRA-7-EP-050: with no misleading ancestor, v2 reproduces v1's tree."""
    # Given: the RDEFormat fixture under an ordinary project directory
    expected = _run_v1(tmp_path / "v1" / "project")

    # When: the v2 Runner processes the same input
    actual = _run_v2(tmp_path / "v2" / "project", monkeypatch)

    # Then: every published file matches, path and content
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
    expected = _run_v1(tmp_path / "v1" / ancestor / "project")

    # When: the v2 Runner processes it from that misleading location
    actual = _run_v2(tmp_path / "v2" / ancestor / "project", monkeypatch)

    # Then: the tree is v1's, not the ancestor's
    assert actual == expected

    # And: each artifact sits in the component its own path names ...
    assert "structured/result.csv" in actual
    assert "divided/0001/meta/metadata.json" in actual
    assert "raw/first.txt" in actual

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
    assert hijacked.isdisjoint(actual)


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
