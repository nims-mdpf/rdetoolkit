"""Pytest configuration for property-based tests.

This module configures Hypothesis settings for property-based testing,
including profiles for CI and local development.
"""

import os

from hypothesis import Verbosity, settings

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
