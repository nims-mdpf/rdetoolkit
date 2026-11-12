"""MultiDataTile tile order is configurable (issue #597).

Both the v1 framework checker and the unified Runner number MultiDataTile tiles
by file name (``sorted(key=str)``). A v1 structured program that listed
``inputdata/`` itself (``for f in inputdata.glob("*")``) numbered its
``divided/NNNN`` tiles in directory order instead, which a v2 rewrite could not
reproduce. ``multidata_tile.order`` selects between the two:

* ``name`` (default) -- the frozen v1 framework contract, unchanged.
* ``filesystem`` -- the order ``Path.glob("*")`` returns the input files in.

The default must stay invisible: ``MultiDataTileSettings().model_dump()`` is
recorded in the frozen contract fixtures, so the v1 model only serializes
``order`` when it is not the default.

EP table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-597-EP-001 | v1 default | ``MultiDataTileSettings()`` | ``order == "name"``, dump unchanged |
| TC-597-EP-002 | v1 explicit | ``order="filesystem"`` | dumped and round-tripped |
| TC-597-EP-003 | v1 file | ``multidata_tile.order`` in rdeconfig.yaml | parsed by the v1 loader |
| TC-597-EP-004 | v1 -> v2 | normalizer, both directions | value preserved |
| TC-597-EP-005 | v2 file | ``multidata_tile.order`` in v2 config | accepted |
| TC-597-EP-006 | checker name | directory order differs from name order | name order |
| TC-597-EP-007 | checker filesystem | directory order differs from name order | directory order |
| TC-597-EP-008 | Runner | ``order=filesystem`` via v2 overrides | tile 0 is the first listed file |
| TC-597-EP-009 | v1 entry | ``order: filesystem`` in tasksupport | tile 0 is the first listed file |

Negative table:
| TC | Class | Input | Expected |
|----|-------|-------|----------|
| TC-597-NG-001 | v1 invalid | ``order="random"`` | ``ValidationError`` |
| TC-597-NG-002 | v2 invalid | ``multidata_tile.order: random`` | ``RdeConfigError`` |
| TC-597-NG-003 | v2 v1-only key | ``multidata_tile.ignore_errors`` in v2 form | ``RdeConfigError`` |
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from rdetoolkit.compat.v1.callback import to_legacy_config
from rdetoolkit.config import parse_config_file
from rdetoolkit.config.normalize import ConfigNormalizer
from rdetoolkit.core.flow import flow
from rdetoolkit.errors import RdeConfigError
from rdetoolkit.impl.input_controller import MultiFileChecker
from rdetoolkit.models.config import Config, MultiDataTileSettings
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import InputPaths, IterationInfo, RdeConfig

#: Name order puts ``643_x.dat`` first; the patched directory order lists
#: ``EIKO_y.dat`` first -- the exact layout reported in issue #597.
_NAME_ORDER = ("643_x.dat", "EIKO_y.dat", "b_z.dat")
_LISTED_ORDER = ("EIKO_y.dat", "b_z.dat", "643_x.dat")


@pytest.fixture
def listed_inputdata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create ``data/inputdata`` whose ``glob("*")`` lists ``_LISTED_ORDER``."""
    inputdata = tmp_path / "data" / "inputdata"
    inputdata.mkdir(parents=True)
    for name in _NAME_ORDER:
        (inputdata / name).write_text(name, encoding="utf-8")
    original_glob = Path.glob

    def directory_order_glob(self: Path, pattern: str, *args: Any, **kwargs: Any) -> Iterator[Path]:
        found = list(original_glob(self, pattern, *args, **kwargs))
        if self == inputdata and pattern == "*":
            rank = {name: idx for idx, name in enumerate(_LISTED_ORDER)}
            found.sort(key=lambda path: rank.get(path.name, len(rank)))
        return iter(found)

    monkeypatch.setattr(Path, "glob", directory_order_glob)
    return inputdata


# --------------------------------------------------------------------------
# Configuration models
# --------------------------------------------------------------------------
def test_v1_default_is_name_and_dump_is_unchanged__tc_597_ep_001() -> None:
    """TC-597-EP-001: the default keeps the frozen v1 dump byte-identical."""
    settings = MultiDataTileSettings()
    assert settings.order == "name"
    assert settings.model_dump() == {"ignore_errors": False}
    assert Config().model_dump(mode="json")["multidata_tile"] == {"ignore_errors": False}


def test_v1_explicit_order_is_dumped_and_round_trips__tc_597_ep_002() -> None:
    """TC-597-EP-002: a non-default order survives model_dump -> Config."""
    settings = MultiDataTileSettings(order="filesystem")
    dumped = settings.model_dump()
    assert dumped == {"ignore_errors": False, "order": "filesystem"}
    assert MultiDataTileSettings(**dumped).order == "filesystem"
    config = Config(multidata_tile=settings)
    assert Config(**config.model_dump(exclude_none=True)).multidata_tile.order == "filesystem"  # type: ignore[union-attr]


def test_v1_invalid_order_is_rejected__tc_597_ng_001() -> None:
    """TC-597-NG-001: only the two documented orders are accepted."""
    with pytest.raises(ValidationError):
        MultiDataTileSettings(order="random")  # type: ignore[arg-type]


def test_v1_loader_reads_order_from_yaml__tc_597_ep_003(tmp_path: Path) -> None:
    """TC-597-EP-003: the v1 tasksupport loader parses ``multidata_tile.order``."""
    path = tmp_path / "rdeconfig.yaml"
    path.write_text(
        "system:\n  extended_mode: MultiDataTile\nmultidata_tile:\n  order: filesystem\n",
        encoding="utf-8",
    )
    config = parse_config_file(path=str(path))
    assert config.multidata_tile is not None
    assert config.multidata_tile.order == "filesystem"


@pytest.mark.parametrize("order", ["name", "filesystem"])
def test_normalizer_preserves_order_both_directions__tc_597_ep_004(tmp_path: Path, order: str) -> None:
    """TC-597-EP-004: v1 -> canonical -> v1 keeps the order."""
    source = Config(multidata_tile=MultiDataTileSettings(order=order))  # type: ignore[arg-type]
    canonical = ConfigNormalizer().normalize(source, root=tmp_path, origin="v1")
    assert canonical.multidata_tile.order == order
    legacy = to_legacy_config(canonical)
    assert legacy.multidata_tile is not None
    assert legacy.multidata_tile.order == order


def test_v2_config_accepts_order__tc_597_ep_005(tmp_path: Path) -> None:
    """TC-597-EP-005: the strict v2 config has a ``multidata_tile.order`` key."""
    assert RdeConfig().multidata_tile.order == "name"
    canonical = ConfigNormalizer().normalize(
        {"multidata_tile": {"order": "filesystem"}},
        root=tmp_path,
        origin="v2",
    )
    assert canonical.multidata_tile.order == "filesystem"


@pytest.mark.parametrize(
    "section",
    [
        pytest.param({"order": "random"}, id="invalid-order"),
        pytest.param({"ignore_errors": True}, id="v1-only-key"),
    ],
)
def test_v2_config_rejects_invalid_section__tc_597_ng_002_003(tmp_path: Path, section: dict[str, Any]) -> None:
    """TC-597-NG-002/003: v2 keeps the section strict (ignore_errors is execution.*)."""
    with pytest.raises(RdeConfigError):
        ConfigNormalizer().normalize({"multidata_tile": section}, root=tmp_path, origin="v2")


# --------------------------------------------------------------------------
# Checker
# --------------------------------------------------------------------------
def test_checker_default_orders_by_name__tc_597_ep_006(listed_inputdata: Path, tmp_path: Path) -> None:
    """TC-597-EP-006: the default stays the v1 ``sorted(key=str)`` contract."""
    rawfiles, special = MultiFileChecker(tmp_path / "temp").parse(listed_inputdata)
    assert special is None
    assert [group[0].name for group in rawfiles] == list(_NAME_ORDER)


def test_checker_filesystem_keeps_listing_order__tc_597_ep_007(listed_inputdata: Path, tmp_path: Path) -> None:
    """TC-597-EP-007: ``filesystem`` keeps the ``glob("*")`` order."""
    rawfiles, _ = MultiFileChecker(tmp_path / "temp", order="filesystem").parse(listed_inputdata)
    assert [group[0].name for group in rawfiles] == list(_LISTED_ORDER)


# --------------------------------------------------------------------------
# End to end
# --------------------------------------------------------------------------
_RECORD = "tile_order.jsonl"


@flow
def _record_tile_order(paths: InputPaths, iteration: IterationInfo) -> None:
    record = paths.inputdata.parent.parent / _RECORD
    with record.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps([iteration.index, paths.rawfiles[0].name]) + "\n")


def _recorded(root: Path) -> list[str]:
    lines = (root / _RECORD).read_text(encoding="utf-8").splitlines()
    return [name for _index, name in sorted(json.loads(line) for line in lines)]


@pytest.mark.parametrize(
    ("order", "expected"),
    [
        pytest.param("name", _NAME_ORDER, id="name"),
        pytest.param("filesystem", _LISTED_ORDER, id="filesystem"),
    ],
)
def test_runner_numbers_tiles_by_configured_order__tc_597_ep_008(
    listed_inputdata: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    order: str,
    expected: tuple[str, ...],
) -> None:
    """TC-597-EP-008: tile 0 (``data/``) is the first file of the chosen order."""
    _seed_task(tmp_path / "data")
    monkeypatch.chdir(tmp_path)
    runner = Runner(
        root=tmp_path,
        inputdata_path=listed_inputdata,
        unpacked_dir_path=tmp_path / "data" / "temp",
    )
    report = runner.run(
        _record_tile_order,
        system={"extended_mode": "MultiDataTile"},
        multidata_tile={"order": order},
    )
    assert report.status == "success"
    assert _recorded(tmp_path) == list(expected)
    assert (tmp_path / "data" / "raw").is_dir()
    assert sorted(path.name for path in (tmp_path / "data" / "divided").iterdir()) == ["0001", "0002"]


def test_v1_entry_reads_order_from_tasksupport__tc_597_ep_009(
    listed_inputdata: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-597-EP-009: a v1 program opts in from ``tasksupport/rdeconfig.yaml``."""
    from rdetoolkit import workflows  # noqa: PLC0415

    data = tmp_path / "data"
    _seed_task(data)
    (data / "tasksupport" / "rdeconfig.yaml").write_text(
        "system:\n  extended_mode: MultiDataTile\n  save_raw: true\nmultidata_tile:\n  order: filesystem\n",
        encoding="utf-8",
    )
    seen: list[str] = []

    def dataset(srcpaths: Any, resource_paths: Any) -> None:
        seen.append(resource_paths.rawfiles[0].name)

    monkeypatch.chdir(tmp_path)
    workflows.run(custom_dataset_function=dataset)

    assert seen == list(_LISTED_ORDER)
    assert (data / "raw" / _LISTED_ORDER[0]).is_file()
    assert (data / "divided" / "0001" / "raw" / _LISTED_ORDER[1]).is_file()


def _seed_task(data: Path) -> None:
    (data / "invoice").mkdir(exist_ok=True)
    (data / "tasksupport").mkdir(exist_ok=True)
    (data / "invoice" / "invoice.json").write_text(json.dumps(_minimal_invoice()), encoding="utf-8")
    (data / "tasksupport" / "invoice.schema.json").write_text(json.dumps(_minimal_schema()), encoding="utf-8")


def _minimal_invoice() -> dict[str, Any]:
    return {
        "datasetId": "00000000-0000-0000-0000-000000000000",
        "basic": {
            "dateSubmitted": "2026-11-12",
            "dataOwnerId": "0" * 56,
            "dataName": "issue-597",
            "experimentId": None,
            "description": None,
        },
        "custom": None,
        "sample": None,
    }


def _minimal_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://rde.nims.go.jp/rde/dataset-templates/issue597/invoice.schema.json",
        "description": "issue 597",
        "type": "object",
        "required": [],
        "properties": {},
    }
