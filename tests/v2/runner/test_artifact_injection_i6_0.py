"""Runner-owned artifact service injection for Session I6-0 (PhaseI §I6-0.3).

I0 added the per-tile artifact hook but left it unwired, so no production run
ever published raw or image artifacts. The Runner now injects the services by
default; the services themselves consume ``save_raw`` / ``save_nonshared_raw``
/ ``save_thumbnail_image``, so configuration alone decides whether a tile
publishes anything.

Equivalence partitions (EP):

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| ``Runner.run`` | default services, ``save_nonshared_raw`` on | raw input published to nonshared_raw/ | TC-EP-I60-201 |
| ``Runner.run`` | default services, both raw switches off | nothing published | TC-EP-I60-202 |
| ``Runner.run`` | default services, ``save_raw`` on | raw input published to raw/ | TC-EP-I60-203 |
| ``Runner.run`` | failed tile | raw published (v1 order), post-invoke artifacts not | TC-EP-I60-204 |

Boundary values (BV):

| API | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| ``Runner`` | caller-supplied executor | injection does not override it | TC-BV-I60-201 |
| ``Runner`` | default construction | both services are real instances | TC-BV-I60-202 |
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from rdetoolkit import flow
from rdetoolkit.domain.artifacts import ImageArtifactService, RawArtifactService
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.report.events import MemoryEventSink
from rdetoolkit.runner.executor import TileExecutor
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import InputPaths
from tests.v2.contract.fixtures import _generate

_RAW_INPUT_NAME = "invoice_input.txt"


@flow
def _noop_flow(paths: InputPaths) -> None:
    """Write nothing so only Runner-published artifacts appear in the tree."""
    assert paths.inputdata.is_dir()


@flow
def _failing_flow(paths: InputPaths) -> None:
    """Fail the tile before any artifact publication can happen."""
    assert paths.inputdata.is_dir()
    raise StructuredError("artifact publication must not run", ecode=999)


def _run(root: Path, monkeypatch: pytest.MonkeyPatch, system: dict[str, Any], *, target: Any = _noop_flow) -> None:
    _generate.materialize_sut_case("invoice", root)
    monkeypatch.chdir(root)
    runner = Runner(
        root=root,
        inputdata_path=root / "data" / "inputdata",
        unpacked_dir_path=root / "data" / "unpacked",
    )
    runner.run(target, system=system)


def test_default_injection_publishes_nonshared_raw__tc_ep_i60_201(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-EP-I60-201: a default Runner publishes raw inputs when configured."""
    # Given: an invoice fixture and the canonical default of save_nonshared_raw
    root = tmp_path / "invoice"

    # When: running a flow that writes nothing itself
    _run(root, monkeypatch, {"save_raw": False, "save_nonshared_raw": True})

    # Then: only the non-shared destination receives the raw input
    assert (root / "data" / "nonshared_raw" / _RAW_INPUT_NAME).is_file()
    assert not (root / "data" / "raw" / _RAW_INPUT_NAME).exists()


def test_both_raw_switches_off_publish_nothing__tc_ep_i60_202(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-EP-I60-202: injection is inert when configuration disables it."""
    # Given: an invoice fixture with every raw switch turned off
    root = tmp_path / "invoice"

    # When: running the same flow
    _run(root, monkeypatch, {"save_raw": False, "save_nonshared_raw": False})

    # Then: neither destination gains a file
    assert not (root / "data" / "raw" / _RAW_INPUT_NAME).exists()
    assert not (root / "data" / "nonshared_raw" / _RAW_INPUT_NAME).exists()


def test_save_raw_publishes_shared_raw__tc_ep_i60_203(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-EP-I60-203: save_raw routes the same input into the shared raw dir."""
    # Given: an invoice fixture configured for shared raw only
    root = tmp_path / "invoice"

    # When: running the same flow
    _run(root, monkeypatch, {"save_raw": True, "save_nonshared_raw": False})

    # Then: only the shared destination receives the raw input
    assert (root / "data" / "raw" / _RAW_INPUT_NAME).is_file()
    assert not (root / "data" / "nonshared_raw" / _RAW_INPUT_NAME).exists()


def test_failed_tile_keeps_raw_and_skips_post_invoke__tc_ep_i60_204(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-EP-I60-204: a failed tile keeps its raw copies and gains nothing else.

    Updated in Session I6-1: v1 copies raw inputs before the dataset callback
    (FileCopier precedes DatasetRunner in every pipeline of
    ``processing/factories.py``), so a failing tile is still expected to hold
    the inputs. Publication that v1 performs *after* the callback — thumbnail,
    structured invoice, magic variable, description — must not happen.
    """
    # Given: an invoice fixture whose flow fails with a user error
    root = tmp_path / "invoice"

    # When: running the failing flow with publication enabled
    _run(
        root,
        monkeypatch,
        {
            "save_raw": True,
            "save_nonshared_raw": True,
            "save_thumbnail_image": True,
            "save_invoice_to_structured": True,
        },
        target=_failing_flow,
    )

    # Then: the raw copies exist and no post-invoke artifact was produced
    assert (root / "data" / "raw" / _RAW_INPUT_NAME).is_file()
    assert (root / "data" / "nonshared_raw" / _RAW_INPUT_NAME).is_file()
    assert not (root / "data" / "structured" / "invoice.json").exists()
    assert not any((root / "data" / "thumbnail").iterdir())


def test_caller_supplied_executor_is_not_overridden__tc_bv_i60_201(tmp_path: Path) -> None:
    """TC-BV-I60-201: an injected executor keeps whatever services it was given."""
    # Given: an executor deliberately constructed without artifact services
    executor = TileExecutor(event_sink=MemoryEventSink())

    # When: handing it to a Runner
    runner = Runner(root=tmp_path, executor=executor)

    # Then: the Runner uses that executor as-is
    assert runner._executor is executor
    assert executor._raw_artifact_service is None
    assert executor._image_artifact_service is None


def test_default_runner_injects_both_services__tc_bv_i60_202(tmp_path: Path) -> None:
    """TC-BV-I60-202: the default executor carries both production services."""
    # Given/When: a Runner built without an explicit executor
    runner = Runner(root=tmp_path)

    # Then: both artifact services are real, config-consuming instances
    assert isinstance(runner._executor._raw_artifact_service, RawArtifactService)
    assert isinstance(runner._executor._image_artifact_service, ImageArtifactService)
