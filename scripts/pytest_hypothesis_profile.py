"""Pytest plugin that loads the Hypothesis profile before any test module.

Usage (from the repository root):
    HYPOTHESIS_PROFILE=ci python -m pytest -p scripts.pytest_hypothesis_profile PATHS

The profiles are registered and ``HYPOTHESIS_PROFILE`` is loaded only by
``tests/property/conftest.py``, which pytest imports only when it collects
``tests/property``. A CI shard that selects other paths would otherwise run its
properties with Hypothesis's default settings instead of the complete suite's.
Importing that conftest here keeps it the single definition of the profiles.
"""

from __future__ import annotations

import tests.property.conftest  # noqa: F401  (registers the profiles and loads HYPOTHESIS_PROFILE)
