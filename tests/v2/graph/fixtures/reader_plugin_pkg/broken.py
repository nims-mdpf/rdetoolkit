"""A reader plugin module whose optional dependency is missing: importing it fails."""

from __future__ import annotations

import importlib

importlib.import_module("rdetoolkit_vendor_sdk_that_is_not_installed")
