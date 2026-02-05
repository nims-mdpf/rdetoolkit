from __future__ import annotations

import sys

# Enforce Python 3.10+ requirement (Issue #351)
if sys.version_info < (3, 10):  # noqa: UP036
    msg = (
        "Python 3.10 or higher is required. "
        "Python 3.9 support was removed in rdetoolkit 1.6.0. "
        "Please use rdetoolkit 1.5.x or upgrade Python."
    )
    raise RuntimeError(msg)

from importlib import import_module
from typing import Any

__version__ = "1.6.0"

_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    "DirectoryOps": ("rdetoolkit.core", "DirectoryOps"),
    "ManagedDirectory": ("rdetoolkit.core", "ManagedDirectory"),
    "detect_encoding": ("rdetoolkit.core", "detect_encoding"),
    "resize_image_aspect_ratio": ("rdetoolkit.core", "resize_image_aspect_ratio"),
    # Result types for explicit error handling
    "Result": ("rdetoolkit.result", "Result"),
    "Success": ("rdetoolkit.result", "Success"),
    "Failure": ("rdetoolkit.result", "Failure"),
    "try_result": ("rdetoolkit.result", "try_result"),
}

_LAZY_MODULES: dict[str, str] = {
    "errors": "rdetoolkit.errors",
    "exceptions": "rdetoolkit.exceptions",
    "img2thumb": "rdetoolkit.img2thumb",
    "invoicefile": "rdetoolkit.invoicefile",
    "modeproc": "rdetoolkit.modeproc",
    "rde2util": "rdetoolkit.rde2util",
    "rdelogger": "rdetoolkit.rdelogger",
    "workflows": "rdetoolkit.workflows",
    "processing": "rdetoolkit.processing",
    "storage": "rdetoolkit.storage",
    "traceback": "rdetoolkit.traceback",
    "config": "rdetoolkit.models.config",
    "invoice": "rdetoolkit.models.invoice",
    "invoice_schema": "rdetoolkit.models.invoice_schema",
    "metadata": "rdetoolkit.models.metadata",
    "rde2types": "rdetoolkit.models.rde2types",
    "impl": "rdetoolkit.impl",
    "interfaces": "rdetoolkit.interfaces",
    "models": "rdetoolkit.models",
}

__all__ = [
    "__version__",
    "DirectoryOps",
    "ManagedDirectory",
    "detect_encoding",
    "resize_image_aspect_ratio",
    # Result types for explicit error handling
    "Result",
    "Success",
    "Failure",
    "try_result",
    "errors",
    "exceptions",
    "img2thumb",
    "invoicefile",
    "modeproc",
    "rde2util",
    "rdelogger",
    "workflows",
    "processing",
    "storage",
    "traceback",
    "config",
    "invoice",
    "invoice_schema",
    "metadata",
    "rde2types",
    "impl",
    "interfaces",
    "models",
]


def __getattr__(name: str) -> Any:
    if name in _LAZY_ATTRS:
        module_name, attr_name = _LAZY_ATTRS[name]
        module = import_module(module_name)
        value = getattr(module, attr_name)
        globals()[name] = value
        return value
    if name in _LAZY_MODULES:
        module = import_module(_LAZY_MODULES[name])
        globals()[name] = module
        return module

    for module_name in ("rdetoolkit.impl", "rdetoolkit.interfaces"):
        module = import_module(module_name)
        if hasattr(module, name):
            value = getattr(module, name)
            globals()[name] = value
            return value

    emsg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(emsg)


def __dir__() -> list[str]:
    return sorted(set(__all__) | set(globals()))
