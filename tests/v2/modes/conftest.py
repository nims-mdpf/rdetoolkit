"""Shared registry isolation for mode-planning tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

# The frozen-oracle comparison helpers assert outside a test module; rewriting
# them makes a mismatch show its diff instead of a bare AssertionError.
pytest.register_assert_rewrite("tests.v2.modes.smarttable_builder_support")

from rdetoolkit.modes.install import install_default_handlers
from rdetoolkit.modes.registry import clear


@pytest.fixture
def empty_mode_registry() -> Iterator[None]:
    """Run one test against an empty handler registry.

    The default handlers are reinstalled on teardown so the suite stays
    order-independent in both directions: an isolated test can observe the
    planner fallback, and later tests still see the production registry
    regardless of which tests ran before them.
    """
    clear()
    try:
        yield
    finally:
        clear()
        install_default_handlers()
