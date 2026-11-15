"""Shared fixtures for the v2 graph-engine tests.

v1 graph tests (for example ``tests/graph/test_config.py::TestApplyMatplotlibConfig``)
and direct ``MatplotlibRenderer.render_overlay`` calls mutate the process-global
``matplotlib.rcParams`` and leave figures open. v2 graph tests must neither depend on
nor leak that state, so every test runs inside a fresh rc scope reset to the
Matplotlib defaults and every figure opened during the test is closed afterwards.
"""

from __future__ import annotations

from collections.abc import Iterator

import matplotlib as mpl
import matplotlib.pyplot as plt
import pytest


@pytest.fixture(autouse=True)
def _graph_rc_and_figure_hygiene() -> Iterator[None]:
    """Run each graph test with default rcParams and close its figures afterwards."""
    with mpl.rc_context():
        mpl.rcdefaults()
        yield
    plt.close("all")
