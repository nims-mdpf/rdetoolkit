"""Documentation test proving the rdetoolkit.testing quickstart works with zero conftest.

Written before implementation (TDD Red phase).
Target: make this test pass in codex-worker Green phase.

Design authority: local/develop/v2/Design.md v2.1 §13
Session authority: local/develop/v2/tasks/session_c2.md (kickoff C-3-5)

This is the single test that proves BOTH acceptance criteria at once:
1. "Usable without a user conftest" — the ``pytest11`` entry-point plugin
   (``rdetoolkit.testing.plugin``) makes ``rde_*`` fixtures available in a
   totally isolated temp project that has NO conftest.py of its own.
2. "Quickstart snippet as a documentation test" — the snippet embedded below
   is itself the quickstart example; a test body of <=3 lines using an
   ``rde_*`` fixture, with no manual InputPaths/OutputContext construction.

``runpytest_subprocess()`` is used deliberately (NOT the in-process
``runpytest()``) because only a real subprocess, started with the installed
interpreter, exercises ``importlib.metadata`` entry_points discovery the way
a real user's ``pip install`` environment would.

Test ID: TC-EP-701 (kickoff C-3-5, main evidence).
"""
from __future__ import annotations

import pytest

pytest_plugins = ["pytester"]

QUICKSTART_SNIPPET = '''
from rdetoolkit.types import InputPaths


def test_quickstart_counts_input_files(rde_paths: InputPaths, rde_out, rde_config, rde_invoice) -> None:
    files = list(rde_paths.inputdata.iterdir())
    assert files == [] and rde_out.struct.is_dir()
    assert rde_config.execution.on_iteration_error == "continue" and rde_invoice.raw
'''


class TestQuickstartSnippetWithoutUserConftest:
    """TC-EP-701: entry-point plugin discovery proven via an isolated subprocess run."""

    def test_quickstart_snippet_passes_without_conftest(
        self,
        pytester: pytest.Pytester,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A <=3-line rde_paths test passes in a temp project with NO conftest.py."""
        for name in ("COV_CORE_SOURCE", "COV_CORE_CONFIG", "COV_CORE_DATAFILE", "COVERAGE_PROCESS_START"):
            monkeypatch.delenv(name, raising=False)
        pytester.makepyfile(test_quickstart=QUICKSTART_SNIPPET)

        result = pytester.runpytest_subprocess("-p", "no:cacheprovider")

        result.assert_outcomes(passed=1)
