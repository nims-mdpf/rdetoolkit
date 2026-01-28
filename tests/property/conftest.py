"""Pytest configuration for property-based tests.

This module configures Hypothesis settings for property-based testing,
including profiles for CI and local development.
"""

import os

import pytest

try:
    from hypothesis import Verbosity, settings

    HYPOTHESIS_AVAILABLE = True

    # CI profile: Reduced examples for faster execution
    settings.register_profile(
        "ci",
        max_examples=50,
        verbosity=Verbosity.verbose,
        deadline=5000,  # 5 seconds per test
    )

    # Dev profile: More examples for thorough local testing
    settings.register_profile(
        "dev",
        max_examples=100,
        verbosity=Verbosity.normal,
        deadline=None,
    )

    # Load profile based on environment variable
    profile = os.environ.get("HYPOTHESIS_PROFILE", "dev")
    settings.load_profile(profile)

except ImportError:
    HYPOTHESIS_AVAILABLE = False


def pytest_collection_modifyitems(config, items):
    """Skip property tests if hypothesis is not available."""
    if not HYPOTHESIS_AVAILABLE:
        skip_hypothesis = pytest.mark.skip(reason="hypothesis not installed")
        for item in items:
            if "property" in item.keywords:
                item.add_marker(skip_hypothesis)
