"""Shared fixtures for tests/v2/nodes/ (Session F1).

``FIXTURES_DIR`` points at small, deliberately-constructed on-disk assets
under ``tests/v2/nodes/fixtures/`` (generated once and committed -- see the
Session F1 tdd-enforcer test manifest for how each binary/encoded fixture was
built and independently smoke-verified against the actual libraries involved
before being pinned here: ``pandas``, ``PIL``, stdlib ``zipfile``, and v1's
``rdetoolkit.rde2util.Meta``/``CharDecEncoding``).

Known traps this file deliberately avoids (do not "fix" without checking the
Session F1 task file first):
    - No fixture here imports ``rdetoolkit.nodes`` (it does not exist yet at
      RED time); doing so at conftest-collection time would break collection
      for every test file in this directory, not just the ones that need it.
    - ``matplotlib`` is never imported at module scope in this conftest --
      only ``tests/v2/nodes/test_plot.py`` needs it, and it must call
      ``matplotlib.use("Agg")`` before any ``pyplot`` import (Known Trap 7).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from rdetoolkit.testing.builders import make_output_context
from rdetoolkit.types import OutputContext

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def output_context(tmp_path: Path) -> OutputContext:
    """A fully-materialized ``OutputContext`` with all ten canonical directories created."""
    return make_output_context(tmp_path)
