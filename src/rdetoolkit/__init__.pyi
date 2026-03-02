from .impl import *
from .interfaces import *
from . import errors as errors, exceptions as exceptions, img2thumb as img2thumb, invoicefile as invoicefile, modeproc as modeproc, rde2util as rde2util, rdelogger as rdelogger, workflows as workflows
from .models import config as config, invoice_schema as invoice_schema, metadata as metadata, rde2types as rde2types
from rdetoolkit.core import resize_image_aspect_ratio as resize_image_aspect_ratio

__version__: str
__all__: list[str]

def get_agent_guide(detailed: bool = False) -> str:
    """Return the agent guide as a string.

    Args:
        detailed: If True, return the detailed guide (~5KB).
                  If False (default), return the summary (~2KB).

    Returns:
        Markdown-formatted guide string.
    """
    ...
