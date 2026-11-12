# Type surface of the lazily-resolved top-level API. Every name here mirrors an
# entry of ``_LAZY_ATTRS`` / ``_LAZY_MODULES`` in ``__init__.py``; the literal
# ``__all__`` below must equal the runtime one (tests/v2/api/test_top_level_api_637.py).
from rdetoolkit import (
    errors as errors,
    exceptions as exceptions,
    img2thumb as img2thumb,
    invoicefile as invoicefile,
    models as models,
    rde2util as rde2util,
    rdelogger as rdelogger,
    storage as storage,
    traceback as traceback,
    workflows as workflows,
)
from rdetoolkit.core import (
    DirectoryOps as DirectoryOps,
    ManagedDirectory as ManagedDirectory,
    detect_encoding as detect_encoding,
    resize_image_aspect_ratio as resize_image_aspect_ratio,
)
from rdetoolkit.core.flow import flow as flow
from rdetoolkit.core.node import node as node
from rdetoolkit.models import (
    config as config,
    invoice as invoice,
    invoice_schema as invoice_schema,
    metadata as metadata,
    rde2types as rde2types,
)
from rdetoolkit.nodes import as_node as as_node
from rdetoolkit.result import (
    Failure as Failure,
    Result as Result,
    Success as Success,
    try_result as try_result,
)

__version__: str

__all__ = [
    "__version__",
    "DirectoryOps",
    "ManagedDirectory",
    "detect_encoding",
    "resize_image_aspect_ratio",
    "Result",
    "Success",
    "Failure",
    "try_result",
    "errors",
    "exceptions",
    "get_agent_guide",
    "img2thumb",
    "invoicefile",
    "rde2util",
    "rdelogger",
    "workflows",
    "storage",
    "traceback",
    "config",
    "invoice",
    "invoice_schema",
    "metadata",
    "rde2types",
    "models",
    "node",
    "flow",
    "as_node",
]

def get_agent_guide(detailed: bool = False) -> str:
    """Return the agent guide as a string.

    Kept for v1 compatibility only; slated for removal by RDE-005 (#644).

    Args:
        detailed: If True, return the detailed guide (~5KB).
                  If False (default), return the summary (~2KB).

    Returns:
        Markdown-formatted guide string.
    """
    ...
