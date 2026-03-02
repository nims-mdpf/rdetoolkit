"""Test package-level exports for agent guide.

This module tests that get_agent_guide() is properly exported at the package level
and accessible through rdetoolkit.get_agent_guide().
"""

import sys

import rdetoolkit


class TestPackageExports:
    """Test package-level exports for agent guide."""

    def test_get_agent_guide_exported(self) -> None:
        """Test: get_agent_guide is accessible at package level."""
        # Given: Package imported
        # When: Accessing get_agent_guide
        # Then: Function should be accessible
        assert hasattr(rdetoolkit, "get_agent_guide")
        assert callable(rdetoolkit.get_agent_guide)

    def test_get_agent_guide_default_returns_summary(self) -> None:
        """Test: get_agent_guide() returns summary guide."""
        # Given: Package imported
        # When: Calling with default arguments
        result = rdetoolkit.get_agent_guide()

        # Then: Should return non-empty string
        assert isinstance(result, str)
        assert len(result) > 0
        # Should be summary (smaller size)
        assert 1000 < len(result) < 4000  # ~1-3 KB

    def test_get_agent_guide_detailed_returns_full_guide(self) -> None:
        """Test: get_agent_guide(detailed=True) returns detailed guide."""
        # Given: Package imported
        # When: Calling with detailed=True
        result = rdetoolkit.get_agent_guide(detailed=True)

        # Then: Should return non-empty string
        assert isinstance(result, str)
        assert len(result) > 0
        # Should be detailed (larger size)
        assert 4000 < len(result) < 8000  # ~4-6 KB

    def test_get_agent_guide_in_all(self) -> None:
        """Test: get_agent_guide is listed in __all__."""
        # Given: Package imported
        # When: Checking __all__
        # Then: get_agent_guide should be listed
        assert "get_agent_guide" in rdetoolkit.__all__

    def test_get_agent_guide_in_dir(self) -> None:
        """Test: get_agent_guide is discoverable via dir()."""
        # Given: Package imported
        # When: Checking dir()
        # Then: get_agent_guide should be listed
        assert "get_agent_guide" in dir(rdetoolkit)

    def test_lazy_loading(self) -> None:
        """Test: get_agent_guide is lazily loaded."""
        # Given: Package imported
        # Record whether _agent is already loaded
        was_loaded = "rdetoolkit._agent" in sys.modules

        # When: Accessing function through __getattr__
        func = rdetoolkit.get_agent_guide

        # Then: Function should be callable
        assert callable(func)
        # And: Function should be accessible
        assert func is rdetoolkit.get_agent_guide

        # If module wasn't loaded before, it should be now
        if not was_loaded:
            assert "rdetoolkit._agent" in sys.modules
