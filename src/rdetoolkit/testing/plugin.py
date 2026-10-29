"""Pytest plugin fixtures for v2 workflow tests."""

from __future__ import annotations  # pragma: no cover

from pathlib import Path  # pragma: no cover
from typing import TYPE_CHECKING  # pragma: no cover

import pytest  # pragma: no cover

if TYPE_CHECKING:  # pragma: no cover
    from rdetoolkit.types import InputPaths, InvoiceData, OutputContext, RdeConfig


@pytest.fixture  # pragma: no cover
def rde_paths(tmp_path: Path) -> InputPaths:  # pragma: no cover
    """Return an isolated minimal ``InputPaths`` tree."""
    from rdetoolkit.testing.builders import make_input_paths  # noqa: PLC0415

    return make_input_paths(tmp_path)


@pytest.fixture  # pragma: no cover
def rde_out(tmp_path: Path) -> OutputContext:  # pragma: no cover
    """Return an isolated ``OutputContext`` with all directories created."""
    from rdetoolkit.testing.builders import make_output_context  # noqa: PLC0415

    return make_output_context(tmp_path / "out")


@pytest.fixture  # pragma: no cover
def rde_config() -> RdeConfig:  # pragma: no cover
    """Return the default strict v2 configuration."""
    from rdetoolkit.types import RdeConfig  # noqa: PLC0415

    return RdeConfig()


@pytest.fixture  # pragma: no cover
def rde_invoice() -> InvoiceData:  # pragma: no cover
    """Return minimal non-empty invoice data."""
    from rdetoolkit.testing.builders import make_invoice  # noqa: PLC0415

    return make_invoice()
