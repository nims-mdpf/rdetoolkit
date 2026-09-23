"""Shared registry isolation for mode-planning tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

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
