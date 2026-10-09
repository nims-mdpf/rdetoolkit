"""Unit tests for AxisConfig dataclass fields.

Covers the ``tick_format`` and ``scilimits`` fields added in Phase 2
(Issue #483) of csv2graph tick label readability improvements.
"""

from __future__ import annotations

import pytest

from rdetoolkit.graph.models import AxisConfig


class TestAxisConfigDefaults:
    """Test default values for tick_format and scilimits fields."""

    def test_default_tick_format_is_auto(self):
        """Default tick_format is 'auto'."""
        # Given/When: AxisConfig created with only required field
        config = AxisConfig(label="X")

        # Then: tick_format defaults to "auto"
        assert config.tick_format == "auto"

    def test_default_scilimits_is_minus3_4(self):
        """Default scilimits is (-3, 4)."""
        # Given/When: AxisConfig created with only required field
        config = AxisConfig(label="X")

        # Then: scilimits defaults to (-3, 4)
        assert config.scilimits == (-3, 4)


class TestAxisConfigTickFormatExplicit:
    """Test explicit tick_format value assignment."""

    @pytest.mark.parametrize(
        "tick_format",
        ["auto", "plain", "sci", "eng"],
    )
    def test_tick_format_is_preserved(self, tick_format):
        """Explicitly specified tick_format value is preserved as-is."""
        # Given/When: AxisConfig created with explicit tick_format
        config = AxisConfig(label="Y", tick_format=tick_format)

        # Then: value is stored unchanged
        assert config.tick_format == tick_format


class TestAxisConfigScilimitsCustom:
    """Test custom scilimits tuple assignment."""

    def test_custom_scilimits_is_preserved(self):
        """Custom scilimits tuple is preserved as-is."""
        # Given/When: AxisConfig created with custom scilimits
        config = AxisConfig(label="Y", scilimits=(-2, 3))

        # Then: value is stored unchanged
        assert config.scilimits == (-2, 3)


class TestAxisConfigFieldCoexistence:
    """Regression test: new fields coexist with existing fields."""

    def test_new_fields_do_not_interfere_with_existing_fields(self):
        """tick_format/scilimits coexist with unit, lim and other fields."""
        # Given/When: AxisConfig created with existing + new fields together
        config = AxisConfig(
            label="Voltage",
            unit="V",
            scale="linear",
            grid=False,
            invert=True,
            lim=(0.0, 10.0),
            tick_format="sci",
            scilimits=(-2, 2),
        )

        # Then: all fields hold their specified values without interference
        assert config.label == "Voltage"
        assert config.unit == "V"
        assert config.scale == "linear"
        assert config.grid is False
        assert config.invert is True
        assert config.lim == (0.0, 10.0)
        assert config.tick_format == "sci"
        assert config.scilimits == (-2, 2)
