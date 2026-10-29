"""Tests for Runner/CLI acceptance of ``type[ProcessingTemplate]`` targets
(Session F2, TC-TPL-RUN-*).

Written before implementation (TDD Red phase). Authority:
local/develop/v2/tasks/session_f2.md Conflict #3, Known Trap #9;
local/develop/v2/Design.md v2.1 §5.2.3, §4.3, §6.1.

Binding API-shape pins asserted by this file (precision standard):
- ``rdetoolkit.workflows.run(flow=TemplateSubclass)`` and
  ``Runner(...).run(TemplateSubclass, ...)`` both accept a
  ``type[ProcessingTemplate]`` in addition to the existing ``FlowFn`` path,
  normalizing to a plain callable at a SINGLE point inside ``Runner.run``
  (Conflict #3) -- both entry points are exercised independently here.
- ``RunReport.flow_id`` identifies the CONCRETE subclass actually run
  (``f"{cls.__module__}.{cls.__qualname__}"``, matching
  ``runner/lifecycle.py``'s existing ``_flow_id`` algorithm), never the
  skeleton's ``__flow__`` definition site (Known Trap #9a).
- DI on ``__flow__``'s signature follows §4.3's type-based resolution
  exactly -- verified with a NON-canonical parameter order/naming
  (``cfg: RdeConfig, p: InputPaths``) to prove the wrapper's
  ``__signature__`` exposes ``__flow__``'s real, bound parameters (no
  leftover ``self``/``*args``/``**kwargs`` masking them), not just that a
  canonically-named flow happens to run (Known Trap #9b).
- A plain (non-``ProcessingTemplate``) class target is never silently
  treated as runnable: ``Runner.run`` must not attempt ``cls()`` +
  ``__flow__`` on it. The exact surfaced error is Codex's implementation
  choice (documented as a blocked-stop question if none of Runner's
  existing error paths fit) -- this file accepts either a raised exception
  or ``RunReport.status == "failed"``, but never a silent "success".

Fixture convention: mirrors ``tests/v2/cli/test_cli_run.py``'s
``_build_data_fixture``/``data/{inputdata,invoice,tasksupport,temp}``
layout (workflows.run(flow=...) hardcodes ``unpacked_dir_path=data_root /
"temp"``, per that file's own module docstring) -- reproduced here
self-contained (no cross-file test-helper imports, matching
``tests/v2/e2e/test_run_flow.py``'s stated convention).
"""

from __future__ import annotations

import json
import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest


def _import_templates() -> tuple[type, Any]:
    from rdetoolkit.templates import ProcessingTemplate, slot  # noqa: PLC0415

    return ProcessingTemplate, slot


_SEED_INVOICE_JSON: dict = {
    "datasetId": "seed-dataset-f2",
    "basic": {
        "dateSubmitted": "2026-07-14",
        "dataOwnerId": "0" * 56,
        "dataName": "seed-f2",
    },
}


def _build_data_fixture(root: Path) -> None:
    """Build a ``data/{inputdata,invoice,tasksupport,temp}`` tree matching
    ``workflows.run(flow=...)``'s actual dispatch convention (see module
    docstring)."""
    inputdata = root / "data" / "inputdata"
    inputdata.mkdir(parents=True)
    (inputdata / "sample.txt").write_text("dummy", encoding="utf-8")
    (root / "data" / "invoice").mkdir(parents=True)
    (root / "data" / "invoice" / "invoice.json").write_text(json.dumps(_SEED_INVOICE_JSON), encoding="utf-8")
    (root / "data" / "tasksupport").mkdir(parents=True)
    (root / "data" / "tasksupport" / "invoice.schema.json").write_text(json.dumps({"properties": {}}), encoding="utf-8")
    (root / "data" / "tasksupport" / "metadata-def.json").write_text(
        json.dumps({"constant": {}, "variable": []}),
        encoding="utf-8",
    )
    (root / "data" / "temp").mkdir(parents=True)


@contextmanager
def _chdir(path: Path) -> Generator[None, None, None]:
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


class TestWorkflowsRunAcceptsTemplateSubclass:
    """TC-TPL-RUN-001: ``workflows.run(flow=TemplateSubclass)`` succeeds,
    DI resolves on ``__flow__``'s signature, and ``RunReport.flow_id``
    identifies the concrete subclass (Conflict #3, Known Trap #9a)."""

    def test_run_succeeds_with_di_and_reports_concrete_subclass_flow_id(self, tmp_path: Path) -> None:
        # Given: a skeleton whose __flow__ takes all four reserved types
        # used by Design §5.2.1's worked example, capturing what it
        # actually received for later inspection.
        ProcessingTemplate, slot = _import_templates()
        from typing import final  # noqa: PLC0415

        from rdetoolkit.types import InputPaths, InvoiceData, OutputContext, RdeConfig  # noqa: PLC0415

        captured: dict[str, Any] = {}

        class _Skeleton(ProcessingTemplate):
            @slot
            def read(self, paths: InputPaths) -> None: ...

            @final
            def __flow__(
                self,
                paths: InputPaths,
                out: OutputContext,
                config: RdeConfig,
                invoice: InvoiceData,
            ) -> None:
                self.read(paths)
                captured["paths"] = paths
                captured["out"] = out
                captured["config"] = config
                captured["invoice"] = invoice

        class RunAcceptanceFixtureUser(_Skeleton):
            def read(self, paths: InputPaths) -> None:
                return None

        _build_data_fixture(tmp_path)

        # When: run(flow=...) is invoked exactly as CLI/workflows callers do.
        import rdetoolkit.workflows as workflows  # noqa: PLC0415

        with _chdir(tmp_path):
            report = workflows.run(flow=RunAcceptanceFixtureUser)

        # Then: the run succeeds ...
        assert report.status == "success", report.error

        # ... flow_id identifies the CONCRETE subclass, not the skeleton ...
        expected_flow_id = f"{RunAcceptanceFixtureUser.__module__}.{RunAcceptanceFixtureUser.__qualname__}"
        assert report.flow_id == expected_flow_id
        assert _Skeleton.__qualname__ not in report.flow_id

        # ... and DI resolved the real reserved-type values onto __flow__'s
        # actual signature (proving the wrapper exposes __flow__'s
        # signature, not a generic passthrough).
        assert isinstance(captured["paths"], InputPaths)
        assert isinstance(captured["out"], OutputContext)
        assert isinstance(captured["config"], RdeConfig)
        assert isinstance(captured["invoice"], InvoiceData)


class TestWorkflowsRunRejectsSkeleton:
    """FIX-3 EP/BV: only registered depth-2 concrete templates execute."""

    def test_depth1_skeleton_raises_type_error_with_remediation__tc_tpl_run_005(self) -> None:
        # Given: a registered depth-1 skeleton rather than a concrete user class
        ProcessingTemplate, slot = _import_templates()

        class SkeletonOnly(ProcessingTemplate):
            @slot
            def read(self) -> None: ...

        # When: the Python API is asked to execute the skeleton
        import rdetoolkit.workflows as workflows  # noqa: PLC0415

        with pytest.raises(TypeError) as exc_info:
            workflows.run(flow=SkeletonOnly)

        # Then: rejection explains how to provide a runnable concrete class
        message = str(exc_info.value).lower()
        assert "skeleton" in message
        assert "subclass" in message
        assert "slot" in message


class TestRunnerRunAcceptsTemplateSubclassDirectly:
    """TC-TPL-RUN-002: ``Runner(...).run(TemplateSubclass, ...)`` succeeds
    one layer below ``workflows.run`` -- proving the normalization lives in
    ``Runner.run`` itself (Conflict #3), not in ``workflows.py``."""

    def test_runner_run_direct_succeeds_and_reports_concrete_subclass_flow_id(self, tmp_path: Path) -> None:
        # Given: a minimal, genuinely runnable template, run via the public
        # rdetoolkit.testing helper -- which itself constructs a Runner and
        # calls Runner.run directly, never going through workflows.run.
        ProcessingTemplate, slot = _import_templates()
        from typing import final  # noqa: PLC0415

        from rdetoolkit.types import InputPaths  # noqa: PLC0415

        class _Skeleton(ProcessingTemplate):
            @slot
            def read(self, paths: InputPaths) -> None: ...

            @final
            def __flow__(self, paths: InputPaths) -> None:
                self.read(paths)

        class DirectRunnerFixtureUser(_Skeleton):
            def read(self, paths: InputPaths) -> None:
                return None

        from rdetoolkit.testing import run_flow  # noqa: PLC0415

        fixture_dir = tmp_path / "fixture_src"
        fixture_dir.mkdir()
        (fixture_dir / "sample.txt").write_text("dummy", encoding="utf-8")

        # When
        report = run_flow(DirectRunnerFixtureUser, fixture_dir)

        # Then
        assert report.status == "success", report.error
        expected_flow_id = f"{DirectRunnerFixtureUser.__module__}.{DirectRunnerFixtureUser.__qualname__}"
        assert report.flow_id == expected_flow_id


class TestDiSignatureCorrectnessAfterWrapping:
    """TC-TPL-RUN-003 (Known Trap #9b): a non-canonically ordered/named
    ``__flow__`` signature must still resolve correctly by TYPE, proving
    the wrapper's exposed signature is __flow__'s real, bound parameter
    list -- not a masking ``*args``/``**kwargs`` passthrough."""

    def test_non_canonical_param_order_and_names_still_resolve_by_type(self, tmp_path: Path) -> None:
        ProcessingTemplate, slot = _import_templates()
        from typing import final  # noqa: PLC0415

        from rdetoolkit.types import InputPaths, RdeConfig  # noqa: PLC0415

        captured: dict[str, Any] = {}

        class _Skeleton(ProcessingTemplate):
            @slot
            def read(self, paths: InputPaths) -> None: ...

            # Deliberately non-canonical: RdeConfig first, non-standard
            # parameter names ("cfg"/"p" instead of "config"/"paths") --
            # §4.3 R1 says DI is type-based only, parameter names are free.
            @final
            def __flow__(self, cfg: RdeConfig, p: InputPaths) -> None:
                self.read(p)
                captured["cfg_type"] = type(cfg)
                captured["p_type"] = type(p)

        class NonCanonicalSignatureUser(_Skeleton):
            def read(self, paths: InputPaths) -> None:
                return None

        _build_data_fixture(tmp_path)
        import rdetoolkit.workflows as workflows  # noqa: PLC0415

        with _chdir(tmp_path):
            report = workflows.run(flow=NonCanonicalSignatureUser)

        assert report.status == "success", report.error
        assert captured["cfg_type"] is RdeConfig
        assert captured["p_type"] is InputPaths


class TestNonTemplateClassRejectedByRunnerRun:
    """TC-TPL-RUN-004 (BV): an arbitrary plain class (not a
    ``ProcessingTemplate`` subclass, not a callable flow) must never be
    silently treated as runnable."""

    def test_plain_class_target_never_silently_succeeds(self, tmp_path: Path) -> None:
        class NotATemplateAtAll:
            """A plain class -- no ProcessingTemplate ancestry, no
            __flow__, not callable as a flow function."""

        _build_data_fixture(tmp_path)

        from rdetoolkit.runner.lifecycle import Runner  # noqa: PLC0415

        root = tmp_path
        data_root = root / "data"

        with _chdir(tmp_path):
            runner = Runner(
                root=root,
                inputdata_path=data_root / "inputdata",
                unpacked_dir_path=data_root / "temp",
            )
            try:
                report = runner.run(NotATemplateAtAll)
            except Exception:  # noqa: BLE001 - raising directly is an accepted "clear error"
                return

        # If Runner.run did not raise, it must have gone through its own
        # internal failure path (a failed RunReport), never "success".
        assert report.status == "failed", (
            "a plain (non-ProcessingTemplate) class target must not be "
            f"silently treated as runnable -- got status={report.status!r}"
        )
