"""Tests for the rdetoolkit.testing pytest plugin fixtures and builders (Session C2, C2.2).

Written before implementation (TDD Red phase).
Target: make all tests pass in codex-worker Green phase.

Design authority: local/develop/v2/Design.md v2.1 §13
Session authority: local/develop/v2/tasks/session_c2.md

Binding rulings (do not re-litigate — see session_c2.md):
- Fixtures ``rde_paths``/``rde_out``/``rde_config``/``rde_invoice`` come from
  the ``pytest11`` entry-point plugin (``rdetoolkit.testing.plugin``) — no
  local conftest.py is needed for THIS file because it lives under
  ``tests/v2/`` (whose ancestor tree already carries fixtures via normal
  pytest discovery once the entry point is registered); the "conftest-free"
  claim itself is proven separately by ``test_quickstart_doc.py``.
- Builders ``make_input_paths``/``make_output_context``/``make_invoice`` are
  standalone callables re-exported from ``rdetoolkit.testing``, wrapping
  ``rdetoolkit.domain.paths``/``rdetoolkit.domain.output`` (no duplicate
  implementation).

EP Table:
| API                  | Partition                          | Rationale     | Expected                                             | Test ID   |
|-----------------------|--------------------------------------|----------------|--------------------------------------------------------|-----------|
| rde_paths fixture     | normal test function usage           | §13.1          | InputPaths returned; inputdata/invoice/tasksupport real | TC-EP-601 |
| rde_out fixture       | normal test function usage           | §13.1          | OutputContext returned; all 10 dirs real                | TC-EP-602 |
| rde_config fixture    | normal test function usage           | §13.1          | default RdeConfig instance returned                     | TC-EP-603 |
| rde_invoice fixture   | normal test function usage           | §13.1          | minimal schema-conformant InvoiceData (raw non-empty)   | TC-EP-604 |
| make_input_paths      | files=["a.txt", "b.txt"]             | builder §13.1  | files exist under inputdata; InputPaths returned        | TC-EP-605 |
| make_output_context   | normal call                          | builder §13.1  | OutputContext returned; all dirs real (thin wrap)       | TC-EP-606 |
| make_invoice          | overrides={"custom": {...}}          | builder §13.1  | returned InvoiceData.raw reflects overrides             | TC-EP-607 |
| Level 1 pattern       | rde_paths + local @node, direct call | §13.2 level 1  | <=3-line test body, no Runner                            | TC-EP-608 |
| Level 2 pattern       | rde_paths/out/config + local @flow   | §13.2 level 2  | fixtures passed positionally, no DI needed              | TC-EP-609 |

BV Table:
| API                  | Boundary                              | Rationale             | Expected                                    | Test ID   |
|-----------------------|------------------------------------------|-------------------------|------------------------------------------------|-----------|
| rde_paths / rde_out   | two test functions in the same module    | fixture isolation      | separate tmp_path each; no directory mixing | TC-BV-601 |
"""
from __future__ import annotations

from pathlib import Path

import pytest

from rdetoolkit.core.flow import flow
from rdetoolkit.core.node import node
from rdetoolkit.types import InputPaths, InvoiceData, OutputContext, RdeConfig

# Target imports — fail until implementation exists (expected in Red phase):
from rdetoolkit.testing import make_input_paths, make_output_context, make_invoice
from rdetoolkit.testing import plugin as testing_plugin

_OUTPUT_CONTEXT_DIR_ATTRS = (
    "struct",
    "meta",
    "main_image",
    "other_image",
    "thumbnail",
    "attachment",
    "nonshared_raw",
    "raw",
    "invoice",
    "logs",
)


class TestRdePathsFixture:
    """TC-EP-601: rde_paths fixture returns a real InputPaths."""

    def test_rde_paths_fixture_returns_real_input_paths(self, rde_paths: InputPaths) -> None:
        """The rde_paths fixture must return InputPaths with real, existing directories."""
        assert isinstance(rde_paths, InputPaths)
        assert rde_paths.inputdata.is_dir()
        assert rde_paths.invoice.is_dir()
        assert rde_paths.tasksupport.is_dir()


class TestRdeOutFixture:
    """TC-EP-602: rde_out fixture returns a real OutputContext."""

    def test_rde_out_fixture_all_ten_directories_exist(self, rde_out: OutputContext) -> None:
        """The rde_out fixture must return an OutputContext with all 10 dirs real."""
        assert isinstance(rde_out, OutputContext)
        for attr in _OUTPUT_CONTEXT_DIR_ATTRS:
            path = getattr(rde_out, attr)
            assert path.is_dir(), f"{attr} directory does not exist: {path}"


class TestRdeConfigFixture:
    """TC-EP-603: rde_config fixture returns a default RdeConfig."""

    def test_rde_config_fixture_returns_default_instance(self, rde_config: RdeConfig) -> None:
        """The rde_config fixture must return a usable default RdeConfig instance."""
        assert isinstance(rde_config, RdeConfig)
        assert rde_config.execution.type_check == "off"
        assert rde_config.execution.on_iteration_error == "continue"


class TestRdeInvoiceFixture:
    """TC-EP-604: rde_invoice fixture returns a minimal schema-conformant InvoiceData."""

    def test_rde_invoice_fixture_returns_non_empty_invoice(self, rde_invoice: InvoiceData) -> None:
        """The rde_invoice fixture must return InvoiceData with non-empty raw content."""
        assert isinstance(rde_invoice, InvoiceData)
        assert isinstance(rde_invoice.raw, dict)
        assert rde_invoice.raw != {}


class TestMakeInputPathsBuilder:
    """TC-EP-605: make_input_paths builder with explicit files."""

    def test_make_input_paths_creates_requested_files(self, tmp_path: Path) -> None:
        """Files passed via files=[...] must exist under the returned inputdata dir."""
        result = make_input_paths(tmp_path, files=["a.txt", "b.txt"])

        assert isinstance(result, InputPaths)
        assert (result.inputdata / "a.txt").is_file()
        assert (result.inputdata / "b.txt").is_file()


class TestMakeOutputContextBuilder:
    """TC-EP-606: make_output_context builder wraps domain.output thinly."""

    def test_make_output_context_creates_all_directories(self, tmp_path: Path) -> None:
        """All output directories must exist after calling the builder."""
        result = make_output_context(tmp_path)

        assert isinstance(result, OutputContext)
        for attr in _OUTPUT_CONTEXT_DIR_ATTRS:
            assert getattr(result, attr).is_dir()


class TestMakeInvoiceBuilder:
    """TC-EP-607: make_invoice builder reflects overrides in raw."""

    def test_make_invoice_overrides_reflected_in_raw(self) -> None:
        """Keys passed via overrides=... must be present in the returned raw dict."""
        overrides = {"custom": {"sample_name": "demo"}}

        result = make_invoice(overrides=overrides)

        assert isinstance(result, InvoiceData)
        assert result.raw.get("custom") == {"sample_name": "demo"}


@node
def _count_input_files_level1(paths: InputPaths) -> int:
    return len(list(paths.inputdata.iterdir()))


class TestLevel1DirectNodeCallPattern:
    """TC-EP-608: rde_paths + a plain @node call, no Runner, <=3-line test body."""

    def test_level1_pattern_direct_node_call(self, rde_paths: InputPaths) -> None:
        """A node called directly with rde_paths needs no Runner scaffolding."""
        result = _count_input_files_level1(rde_paths)
        assert result == 0


@flow
def _level2_flow(paths: InputPaths, out: OutputContext, config: RdeConfig) -> tuple[InputPaths, OutputContext, RdeConfig]:
    return paths, out, config


class TestLevel2DirectFlowCallPattern:
    """TC-EP-609: rde_paths/rde_out/rde_config passed positionally to a plain @flow call."""

    def test_level2_pattern_direct_flow_call(
        self,
        rde_paths: InputPaths,
        rde_out: OutputContext,
        rde_config: RdeConfig,
    ) -> None:
        """No DI is required to call a flow directly with fixtures as positional args."""
        result = _level2_flow(rde_paths, rde_out, rde_config)
        assert result == (rde_paths, rde_out, rde_config)


class TestFixtureIsolationAcrossTestFunctions:
    """TC-BV-601: rde_paths must not mix directories between two test functions."""

    def test_isolated_tmp_path_first_function(self, rde_paths: InputPaths) -> None:
        """The first test's inputdata dir must contain only what this test wrote."""
        marker = rde_paths.inputdata / "marker_first.txt"
        marker.write_text("first")
        assert list(rde_paths.inputdata.iterdir()) == [marker]

    def test_isolated_tmp_path_second_function(self, rde_paths: InputPaths) -> None:
        """The second test's inputdata dir must contain only what this test wrote."""
        marker = rde_paths.inputdata / "marker_second.txt"
        marker.write_text("second")
        assert list(rde_paths.inputdata.iterdir()) == [marker]


class TestPluginFixtureFactories:
    """Targeted coverage for pytest entry-point fixture factory functions."""

    def test_plugin_fixture_factories_build_expected_values(self, tmp_path: Path) -> None:
        """TC-EP-610: plugin fixture factories delegate to the public builders."""
        # Given: the pytest plugin fixture functions registered by entry point
        # When: invoking their wrapped factory functions directly for coverage
        paths = testing_plugin.rde_paths.__wrapped__(tmp_path)
        out = testing_plugin.rde_out.__wrapped__(tmp_path)
        config = testing_plugin.rde_config.__wrapped__()
        invoice = testing_plugin.rde_invoice.__wrapped__()

        # Then: the factories return the same public types as pytest fixtures
        assert isinstance(paths, InputPaths)
        assert isinstance(out, OutputContext)
        assert isinstance(config, RdeConfig)
        assert isinstance(invoice, InvoiceData)
