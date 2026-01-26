"""Tests for Python 3.9 deprecation warning (Issue #360).

Test Design:
- TC-EP-001: Python 3.9 environment shows warning
- TC-EP-002: Python 3.10+ environment shows no warning
- TC-EP-003: Warning appears only once per session
- TC-BV-001: Boundary test for Python 3.9.x
- TC-BV-002: Boundary test for Python 3.10.0
"""
import sys
import warnings
import pytest


def test_py39_deprecation_warning_on_py39__tc_ep_001(monkeypatch):
    """Test that DeprecationWarning is raised on Python 3.9.

    TC-EP-001: Equivalence partition for Python < 3.10
    """
    # Given: Python 3.9 environment
    monkeypatch.setattr(sys, "version_info", (3, 9, 0))

    # When: Importing rdetoolkit
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        # Force reimport to trigger warning
        if "rdetoolkit" in sys.modules:
            del sys.modules["rdetoolkit"]

        import rdetoolkit  # noqa: F401

        # Then: DeprecationWarning is raised
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "Python 3.9 support is deprecated" in str(w[0].message)
        assert "rdetoolkit v2.0" in str(w[0].message)
        assert "Python 3.10 or later" in str(w[0].message)


def test_no_warning_on_py310_plus__tc_ep_002(monkeypatch):
    """Test that no warning is raised on Python 3.10+.

    TC-EP-002: Equivalence partition for Python >= 3.10
    """
    # Given: Python 3.10+ environment
    monkeypatch.setattr(sys, "version_info", (3, 10, 0))

    # When: Importing rdetoolkit
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        # Force reimport
        if "rdetoolkit" in sys.modules:
            del sys.modules["rdetoolkit"]

        import rdetoolkit  # noqa: F401

        # Then: No DeprecationWarning is raised
        deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(deprecation_warnings) == 0


def test_warning_appears_once_per_session__tc_ep_003(monkeypatch):
    """Test that warning appears only once in a single session.

    TC-EP-003: Warning frequency control
    """
    # Given: Python 3.9 environment
    monkeypatch.setattr(sys, "version_info", (3, 9, 0))

    # When: Importing rdetoolkit multiple times
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        # First import
        if "rdetoolkit" in sys.modules:
            del sys.modules["rdetoolkit"]
        import rdetoolkit  # noqa: F401, F811

        first_warning_count = len(w)

        # Second import (module already loaded)
        import rdetoolkit  # noqa: F401, F811

        # Then: Warning appears only once
        assert len(w) == first_warning_count


@pytest.mark.parametrize(
    "version_info,should_warn,test_id",
    [
        ((3, 9, 0), True, "TC-BV-001"),    # Exact lower boundary
        ((3, 9, 18), True, "TC-BV-001"),   # Python 3.9.18 (latest 3.9)
        ((3, 10, 0), False, "TC-BV-002"),  # Exact upper boundary
        ((3, 11, 0), False, "TC-BV-002"),  # Python 3.11
        ((3, 12, 0), False, "TC-BV-002"),  # Python 3.12
    ],
)
def test_version_boundary_behavior(monkeypatch, version_info, should_warn, test_id):
    """Test warning behavior at version boundaries.

    Parametrized test covering:
    - TC-BV-001: Python 3.9.x should warn
    - TC-BV-002: Python 3.10+ should not warn
    """
    # Given: Specific Python version
    monkeypatch.setattr(sys, "version_info", version_info)

    # When: Importing rdetoolkit
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        if "rdetoolkit" in sys.modules:
            del sys.modules["rdetoolkit"]

        import rdetoolkit  # noqa: F401

        # Then: Warning behavior matches expectation
        deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        if should_warn:
            assert len(deprecation_warnings) == 1, f"{test_id}: Expected warning for Python {version_info}"
        else:
            assert len(deprecation_warnings) == 0, f"{test_id}: Expected no warning for Python {version_info}"
