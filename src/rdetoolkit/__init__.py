__version__ = "1.4.3"

from rdetoolkit.core import DirectoryOps, ManagedDirectory, detect_encoding, resize_image_aspect_ratio
from rdetoolkit.result import Result, Success, Failure, try_result

from . import errors, exceptions, img2thumb, invoicefile, modeproc, rde2util, rdelogger, workflows
from .impl import *
from .interfaces import *
from .models import config, invoice, invoice_schema, metadata, rde2types

__all__ = [
    # Version
    "__version__",
    # Core utilities
    "DirectoryOps",
    "ManagedDirectory",
    "detect_encoding",
    "resize_image_aspect_ratio",
    # Result types for explicit error handling
    "Result",
    "Success",
    "Failure",
    "try_result",
    # Submodules
    "errors",
    "exceptions",
    "img2thumb",
    "invoicefile",
    "modeproc",
    "rde2util",
    "rdelogger",
    "workflows",
    "config",
    "invoice",
    "invoice_schema",
    "metadata",
    "rde2types",
]
