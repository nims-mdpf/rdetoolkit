"""Shared harness of the GA debuggability gate (#698).

Every GA cell runs one *entry* (``flow``: a v2 ``@flow`` through
``FlowTarget``; ``callback``: a v1 dataset callback through
``LegacyCallbackTarget``, the path ``workflows.run(custom_dataset_function=...)``
takes since Phase J) on one *mode*'s committed contract input, through the
unified ``Runner``. The public subprocess entry is covered by the
``TC-UM-*-CB-ENTRY-*`` cells of ``tests/v2/contract/test_unified_matrix.py``;
the GA cells stay in-process so a failure shows the Python assertion.

Independent oracles (never v2 output):

* tile counts, output trees, raw digests, invoices and ``job.failed`` text come
  from the frozen v1 observations in ``tests/v2/contract/fixtures/expected/v1``;
* source lines come from this file's (or the generator's) source text;
* catalog codes come from ``ERROR_CATALOG`` and the contracted translation
  table (``tests/v2/contract/flow_error_table.py``).
"""

from __future__ import annotations

import inspect
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from rdetoolkit.api.request import FlowTarget, LegacyCallbackTarget, RunRequest
from rdetoolkit.cli.app import app
from rdetoolkit.core.flow import flow
from rdetoolkit.core.node import node
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.runner.lifecycle import Runner
from rdetoolkit.types import InputPaths, IterationInfo, OutputContext
from tests.v2.contract.fixtures import _generate
from tests.v2.contract.frozen import frozen_observed
from tests.v2.contract.provenance_parity import read_events

MODES = ("invoice", "excelinvoice", "multidatatile", "rdeformat", "smarttable")
MODE_IDS = {
    "invoice": "INV",
    "excelinvoice": "XLS",
    "multidatatile": "MDT",
    "rdeformat": "RDF",
    "smarttable": "SMT",
}
ENTRIES = ("flow", "callback")
ENTRY_IDS = {"flow": "FLOW", "callback": "CB"}

#: Modes whose contract input yields more than one tile (frozen v1 ``ok``).
MULTI_TILE_MODES = ("excelinvoice", "multidatatile", "rdeformat", "smarttable")

#: A per-tile ``metadata.json`` the artifact contract rejects (4002).
INVALID_METADATA = '{"constant": "not-a-mapping", "variable": 3}'

#: The frozen v1 user error: ``_oracle_callback_usererr`` raises exactly this.
STRUCTURED_CODE = 999
STRUCTURED_MESSAGE = _generate.CALLBACK_FAILURE_MESSAGE


def cell_id(entry: str, mode: str, outcome: str) -> str:
    """Return the pytest id of one GA cell, e.g. ``GA-FLOW-INV-STRUCTURED-ERROR``."""
    return f"GA-{ENTRY_IDS[entry]}-{MODE_IDS[mode]}-{outcome.upper().replace('_', '-')}"


def cells(outcome: str, *, entries: tuple[str, ...] = ENTRIES, modes: tuple[str, ...] = MODES) -> list[Any]:
    """Return ``(entry, mode)`` parameters with GA cell ids for one outcome."""
    return [pytest.param(entry, mode, id=cell_id(entry, mode, outcome)) for entry in entries for mode in modes]


def frozen_ok(mode: str) -> dict[str, Any]:
    """Return the frozen v1 observation of a successful callback run."""
    return frozen_observed(f"v1/{mode}/ok")


def tile_count(mode: str) -> int:
    """Return how many tiles v1 ran for this mode's contract input."""
    return int(frozen_ok(mode)["callback_count"])


def v1_config(mode: str) -> Any:
    """Return the v1 ``Config`` the frozen corpus was generated with (seeds ``fail_fast``)."""
    return _generate.oracle_config(mode)


def v2_config(mode: str, **execution: str) -> dict[str, Any]:
    """Return the v2 mapping equivalent of :func:`v1_config` plus an ``execution`` section."""
    extended_mode = {"multidatatile": "MultiDataTile", "rdeformat": "rdeformat"}.get(mode)
    return {
        "system": {
            "extended_mode": extended_mode,
            "save_raw": True,
            "save_nonshared_raw": True,
            "save_thumbnail_image": False,
            "magic_variable": False,
        },
        "smarttable": {"save_table_file": False},
        "execution": {"on_iteration_error": "fail_fast", **execution},
    }


def raise_line(function: Callable[..., Any], needle: str = "raise ") -> int:
    """Return the absolute line number of the first ``needle`` line in ``function``.

    The expectation is read from the source text, so a diagnostic that points
    at the framework instead of the user's raise statement cannot match it.
    """
    lines, start = inspect.getsourcelines(inspect.unwrap(function))
    for offset, text in enumerate(lines):
        if needle in text:
            return start + offset
    msg = f"{function.__qualname__} has no line containing {needle!r}"
    raise AssertionError(msg)


def source_file(function: Callable[..., Any]) -> str:
    """Return the repository-relative POSIX path of ``function``'s module."""
    path = Path(inspect.getsourcefile(inspect.unwrap(function)) or "")
    return path.resolve().relative_to(_generate.REPOSITORY_ROOT).as_posix()


# --------------------------------------------------------------- user code
#
# The nodes and callbacks below are the "user code" of the GA cells. Their raise
# statements are the source lines the diagnostics must point at.


@node(id="tests.v2.ga.structured_failure")
def structured_failure(paths: InputPaths) -> None:
    """Raise the frozen v1 user error from inside a node body."""
    assert paths.inputdata.is_dir()
    raise StructuredError(STRUCTURED_MESSAGE, ecode=STRUCTURED_CODE)


@node(id="tests.v2.ga.plain_failure")
def plain_failure(paths: InputPaths) -> None:
    """Raise an ordinary exception from inside a node body."""
    assert paths.inputdata.is_dir()
    raise ValueError(_generate.PLAIN_FAILURE_MESSAGE)


@node(id="tests.v2.ga.typed")
def typed(value: int) -> int:
    """Accept an ``int`` only; strict type checking rejects anything else."""
    return value + 1


@node(id="tests.v2.ga.write_invalid_metadata")
def write_invalid_metadata(out: OutputContext) -> None:
    """Publish a metadata.json the post-validation contract rejects."""
    out.meta.mkdir(parents=True, exist_ok=True)
    (out.meta / "metadata.json").write_text(INVALID_METADATA, encoding="utf-8")


@node(id="tests.v2.ga.probe")
def probe(index: int) -> int:
    """Succeed; its invocation is what the in-flight event cells observe."""
    return index


@node(id="tests.v2.ga.fail_every_tile")
def fail_every_tile(index: int) -> None:
    """Raise the frozen v1 user error on every tile."""
    raise StructuredError(STRUCTURED_MESSAGE, ecode=STRUCTURED_CODE)


@node(id="tests.v2.ga.fail_tile_zero")
def fail_tile_zero(index: int) -> int:
    """Raise the frozen v1 user error on tile 0 only."""
    if index == 0:
        raise StructuredError(STRUCTURED_MESSAGE, ecode=STRUCTURED_CODE)
    return index


@flow(id="tests.v2.ga.structured_flow")
def structured_flow(paths: InputPaths) -> None:
    structured_failure(paths)


@flow(id="tests.v2.ga.plain_flow")
def plain_flow(paths: InputPaths) -> None:
    plain_failure(paths)


@flow(id="tests.v2.ga.strict_flow")
def strict_flow(iteration: IterationInfo) -> None:
    typed(str(iteration.index))


@flow(id="tests.v2.ga.invalid_metadata_flow")
def invalid_metadata_flow(out: OutputContext) -> None:
    write_invalid_metadata(out)


@flow(id="tests.v2.ga.probe_flow")
def probe_flow(iteration: IterationInfo) -> None:
    probe(iteration.index)


@flow(id="tests.v2.ga.every_tile_fails_flow")
def every_tile_fails_flow(iteration: IterationInfo) -> None:
    fail_every_tile(iteration.index)


@flow(id="tests.v2.ga.first_tile_fails_flow")
def first_tile_fails_flow(iteration: IterationInfo) -> None:
    fail_tile_zero(iteration.index)


def _record(srcpaths: object, resource_paths: object) -> None:
    _generate._record_invocation(srcpaths, resource_paths)  # noqa: SLF001 -- the generator owns the call marker


def strict_callback(srcpaths: object, resource_paths: object) -> None:
    """A v1 callback handing a ``str`` to an ``int`` node."""
    _record(srcpaths, resource_paths)
    typed("not-an-int")  # type: ignore[arg-type]


def invalid_metadata_callback(srcpaths: object, resource_paths: Any) -> None:
    """A v1 callback publishing an invalid metadata.json."""
    _record(srcpaths, resource_paths)
    meta = Path(resource_paths.meta)
    meta.mkdir(parents=True, exist_ok=True)
    (meta / "metadata.json").write_text(INVALID_METADATA, encoding="utf-8")


def probe_callback(srcpaths: object, resource_paths: object) -> None:
    """A v1 callback calling one node per tile."""
    _record(srcpaths, resource_paths)
    probe(_generate._callback_call_count())  # noqa: SLF001


def every_tile_fails_callback(srcpaths: object, resource_paths: object) -> None:
    """A v1 callback raising the frozen user error on every tile."""
    _record(srcpaths, resource_paths)
    raise StructuredError(STRUCTURED_MESSAGE, ecode=STRUCTURED_CODE)


#: The user code of each outcome, per entry. The callback entry reuses the
#: generator's oracle callbacks where one exists, so the user code is the very
#: function the frozen v1 observation was produced with.
USER_CODE: dict[str, dict[str, Callable[..., Any]]] = {
    "ok": {"flow": probe_flow, "callback": _generate._oracle_callback_ok},  # noqa: SLF001
    "structured_error": {"flow": structured_flow, "callback": _generate._oracle_callback_usererr},  # noqa: SLF001
    "plain_exception": {"flow": plain_flow, "callback": _generate.oracle_callback_plain_error},
    "strict_type_mismatch": {"flow": strict_flow, "callback": strict_callback},
    "post_validation_failure": {"flow": invalid_metadata_flow, "callback": invalid_metadata_callback},
    "inflight": {"flow": probe_flow, "callback": probe_callback},
    "all_tiles_failed": {"flow": every_tile_fails_flow, "callback": every_tile_fails_callback},
}

#: Where each failing user code raises: ``(function, needle)``.
RAISE_SITES: dict[str, dict[str, tuple[Callable[..., Any], str]]] = {
    "structured_error": {
        "flow": (structured_failure, "raise "),
        "callback": (_generate._oracle_callback_usererr, "raise "),  # noqa: SLF001
    },
    "plain_exception": {
        "flow": (plain_failure, "raise "),
        "callback": (_generate.oracle_callback_plain_error, "raise "),
    },
}


# ------------------------------------------------------------------ runs


@dataclass(frozen=True)
class GaRun:
    """One finished GA run and the artifacts it left behind."""

    root: Path
    report: RunReport

    @property
    def data_root(self) -> Path:
        return self.root / "data"

    @property
    def logs(self) -> Path:
        return self.data_root / "logs"

    @property
    def report_path(self) -> Path:
        return self.logs / f"run_report_{self.report.run_id}.json"

    @property
    def sidecar_path(self) -> Path:
        return self.logs / f"diagnostics_{self.report.run_id}.json"

    def job_failed(self) -> str | None:
        """Return the normalized ``job.failed`` text, or ``None`` when absent."""
        path = self.data_root / "job.failed"
        if not path.exists():
            return None
        return str(_generate.normalize_snapshot(path.read_text(encoding="utf-8"), roots=(self.root,)))

    def sidecar(self) -> dict[str, Any] | None:
        """Return the diagnostics sidecar of this run, or ``None`` when absent."""
        if not self.sidecar_path.exists():
            return None
        document: dict[str, Any] = json.loads(self.sidecar_path.read_text(encoding="utf-8"))
        return document

    def diagnostics(self) -> list[dict[str, Any]]:
        """Return the sidecar's diagnostics, asserting the versioned document shape."""
        document = self.sidecar()
        assert document is not None, f"failed run {self.report.run_id} wrote no diagnostics sidecar"
        assert (document["format"], document["schema_version"]) == ("rdetoolkit.failure-diagnostics", "1")
        assert (document["run_id"], document["run_status"]) == (self.report.run_id, self.report.status)
        diagnostics: list[dict[str, Any]] = document["diagnostics"]
        return diagnostics

    def events(self) -> list[dict[str, Any]]:
        """Return this run's event JSONL lines."""
        return read_events(self.logs, self.report.run_id)

    def explain(self) -> dict[str, Any]:
        """Return ``rdetoolkit report explain <report> --format json``."""
        result = CliRunner().invoke(app, ["report", "explain", str(self.report_path), "--format", "json"])
        assert result.exit_code == 0, result.output
        document: dict[str, Any] = json.loads(result.stdout)
        return document

    def callback_count(self) -> int:
        """Return how often the generator's call marker was appended to."""
        marker = self.root / _generate.CALLBACK_MARKER_NAME
        return len(marker.read_text(encoding="utf-8").splitlines()) if marker.exists() else 0


def target_for(entry: str, function: Callable[..., Any]) -> FlowTarget | LegacyCallbackTarget:
    """Wrap user code in the execution target of ``entry``."""
    if entry == "flow":
        return FlowTarget(function=function)
    return LegacyCallbackTarget(function=function)


def run_case(
    entry: str,
    mode: str,
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    function: Callable[..., Any],
    config: Any = None,
    materialize: bool = True,
    invalidate_invoice: bool = False,
) -> GaRun:
    """Run user code through one entry on one mode's contract input.

    Args:
        entry: ``flow`` or ``callback``.
        mode: One of :data:`MODES`.
        root: Run root (``<root>/data`` is the data root).
        monkeypatch: Used to make ``root`` the CWD, as the oracle callbacks need.
        function: Flow or v1 callback.
        config: Config source; defaults to :func:`v1_config` (``fail_fast``).
        materialize: Copy the committed input into ``root`` first.
        invalidate_invoice: Break the source invoice (pre-validation failure).

    Returns:
        The finished run.
    """
    if materialize:
        _generate.materialize_sut_case(mode, root)
    if invalidate_invoice:
        _generate._invalidate_invoice(root)  # noqa: SLF001 -- the generator owns the defect
    monkeypatch.chdir(root)
    runner = Runner(root=root, inputdata_path=root / "data" / "inputdata", unpacked_dir_path=root / "data" / "temp")
    source = v1_config(mode) if config is None else config
    report = runner.run(RunRequest(root=root, target=target_for(entry, function), config_source=source))
    return GaRun(root=root, report=report)


def only(items: list[Mapping[str, Any]]) -> Mapping[str, Any]:
    """Return the single item of ``items``, failing with the whole list otherwise."""
    assert len(items) == 1, items
    return items[0]
