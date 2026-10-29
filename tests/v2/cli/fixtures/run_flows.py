"""Fixture flows/nodes for ``rdetoolkit run --flow`` CLI tests (Session E1).

These are real, module-scope ``@node``/``@flow`` definitions living in an
actual dotted-importable package (``tests.v2.cli.fixtures.run_flows``) --
required because Conflict #11 (session_e1.md) restricts ``--flow``
resolution to ``importlib.import_module(<dotted pkg.mod>)`` + ``getattr``,
with no file-path support (unlike the legacy ``target::attr`` syntax).

Each pipeline below is used by exactly one or two TC-CLI-RUN-* cases in
``tests/v2/cli/test_cli_run.py`` -- see that file's module docstring for the
mapping. Node ids are explicit (``@node(id=...)``) so re-imports across the
pytest session never collide (module import is cached by Python, so
decorators here execute exactly once regardless of how many CLI
invocations resolve this module).
"""

from __future__ import annotations

from typing import final

from rdetoolkit.core.flow import flow
from rdetoolkit.core.node import node
from rdetoolkit.types import InputPaths, IterationInfo

# Session F2 (TC-CLI-RUN-EP-014): `rdetoolkit.templates` does not exist yet
# in the Red phase. This module is imported by EVERY existing TC-CLI-RUN-*
# case in tests/v2/cli/test_cli_run.py (via --flow's dotted-path
# resolution), so an unconditional top-level
# `from rdetoolkit.templates import ProcessingTemplate, slot` would break
# ALL of them with a whole-module ImportError the instant this file is
# imported -- not just the new template-specific test. Guard it instead:
# pre-F2, the two Template fixture classes below are simply absent (their
# names unresolvable -> a clean AttributeError -> usage_error -> exit 3),
# which is the correct RED signal for TC-CLI-RUN-EP-014 alone, leaving
# every other fixture in this module fully importable.
try:
    from rdetoolkit.templates import ProcessingTemplate, slot
except ImportError:  # pragma: no cover - Session F2 Red phase only.
    ProcessingTemplate = None  # type: ignore[assignment,misc]
    slot = None  # type: ignore[assignment]

# TC-CLI-RUN-EP-009/EP-010: appended to by validate_only_pipeline. Must
# remain empty after any ``run --flow ... --validate-only`` invocation --
# this is the E1.3-mandated side-effect sentinel (Conflict #3). Tests must
# snapshot ``len(VALIDATE_ONLY_SENTINEL)`` before invoking the CLI and
# assert it is unchanged afterward (module-level list persists across the
# whole pytest session, so a bare emptiness check is not reliable on its
# own if some other test happens to invoke this same pipeline for a
# real, non-validate-only run in the future).
VALIDATE_ONLY_SENTINEL: list[str] = []


@node(id="e1_cli_fixture_touch_success")
def _touch_success(paths: InputPaths) -> None:
    return None


@flow(id="e1_cli_fixture_success_pipeline")
def success_pipeline(paths: InputPaths) -> None:
    """TC-CLI-RUN-EP-001: every tile succeeds unconditionally."""
    _touch_success(paths)


@node(id="e1_cli_fixture_touch_always_fail")
def _touch_always_fail(paths: InputPaths) -> None:
    msg = "e1_cli_fixture_touch_always_fail: intentional failure"
    raise RuntimeError(msg)


@flow(id="e1_cli_fixture_failing_pipeline")
def failing_pipeline(paths: InputPaths) -> None:
    """TC-CLI-RUN-EP-003: every tile fails unconditionally (single-tile
    invoice-mode fixture -> completed_count == 0 -> RunReport.status ==
    "failed" regardless of the on_iteration_error policy)."""
    _touch_always_fail(paths)


@node(id="e1_cli_fixture_touch_second_tile")
def _touch_second_tile(paths: InputPaths, iteration: IterationInfo) -> None:
    if iteration.index == 1:
        msg = "e1_cli_fixture_touch_second_tile: intentional failure on tile index 1"
        raise RuntimeError(msg)


@flow(id="e1_cli_fixture_second_tile_fails_pipeline")
def second_tile_fails_pipeline(paths: InputPaths, iteration: IterationInfo) -> None:
    """TC-CLI-RUN-EP-002/EP-012: first of two tiles succeeds, second always
    fails. Under the default ``on_iteration_error="continue"`` this yields
    RunReport.status == "partial"; under an ``execution.on_iteration_error:
    fail_fast`` override it yields "failed" (EP-012's observable
    --config-changes-the-outcome proof)."""
    _touch_second_tile(paths, iteration)


@node(id="e1_cli_fixture_touch_validate_only_sentinel")
def _touch_validate_only_sentinel(paths: InputPaths) -> None:
    VALIDATE_ONLY_SENTINEL.append("called")


@flow(id="e1_cli_fixture_validate_only_pipeline")
def validate_only_pipeline(paths: InputPaths) -> None:
    """TC-CLI-RUN-EP-009/EP-010: appends to VALIDATE_ONLY_SENTINEL when
    actually called. ``run --flow ... --validate-only`` must NEVER call
    this flow (Conflict #3) -- the sentinel must stay unchanged."""
    _touch_validate_only_sentinel(paths)


class NotAFunctionTarget:
    """TC-CLI-RUN-EP-006 (Session F2 UPDATE, session_f2.md Conflict #9): a
    plain class that is deliberately NOT a ``ProcessingTemplate`` subclass.
    ``--flow`` resolving to a class target must still be rejected as a
    usage error, exit 3 -- but the message must now assert the precise,
    always-true reason ("not a ProcessingTemplate subclass"), replacing the
    Session E1-era, now factually-stale "not supported until Phase F"
    wording (Phase F is real as of this session).
    """


if ProcessingTemplate is not None:

    class _Ep014Skeleton(ProcessingTemplate):  # type: ignore[misc]
        """TC-CLI-RUN-EP-014 (session_f2.md UPDATE table, Conflict #9):
        a minimal depth-1 skeleton fixture -- never a production template
        (Conflict #10 forbids shipping any concrete skeleton under
        src/rdetoolkit/templates/ in this session)."""

        @slot
        def read(self, paths: InputPaths) -> None: ...

        @final
        def __flow__(self, paths: InputPaths) -> None:
            self.read(paths)

    class ValidTemplateTarget(_Ep014Skeleton):
        """TC-CLI-RUN-EP-014: a minimal, genuinely runnable depth-2
        ProcessingTemplate subclass -- proves ``--flow`` accepts and runs a
        Template class target end-to-end (Design §5.2.3's Runner/CLI dual
        acceptance clause, Conflict #3's flow_id-identity ruling)."""

        def read(self, paths: InputPaths) -> None:
            return None
