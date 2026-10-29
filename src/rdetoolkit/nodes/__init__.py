"""Canonical builtin nodes and migration adapter for rdetoolkit v2."""

from collections.abc import Callable
from typing import Any, cast

from rdetoolkit.core.node import node
from rdetoolkit.nodes.image import copy_raw, make_thumbnail, save_main_image, to_jpeg, to_png
from rdetoolkit.nodes.io import read_csv_with_header, read_excel, read_text, unzip_inputs
from rdetoolkit.nodes.meta import parse_invoice_meta, save_meta
from rdetoolkit.nodes.plot import plot_lines, plot_scatter
from rdetoolkit.nodes.structured import save_csv, save_json


def as_node(instance: Any, *, method: str, id: str | None = None) -> Callable[..., Any]:  # noqa: A002
    """Adapt a bound method from a class-based asset into an ordinary node.

    This migration helper uses the same decorator and registry path as every
    user-defined node. It grants no special registration or execution
    behavior.

    Args:
        instance: Object that owns the method.
        method: Name of the method to adapt.
        id: Optional explicit node id. Defaults to ``module.Class.method``.

    Returns:
        The registered node callable wrapping the bound method.

    Raises:
        AttributeError: If the named method does not exist.
        TypeError: If the named attribute is not callable.
    """
    target = getattr(instance, method)
    if not callable(target):
        msg = f"{type(instance).__qualname__}.{method} is not callable"
        raise TypeError(msg)
    default_id = f"{type(instance).__module__}.{type(instance).__qualname__}.{method}"
    decorator = node(id=id or default_id)
    return decorator(cast(Callable[..., Any], target))

__all__ = [
    "read_text",
    "read_csv_with_header",
    "read_excel",
    "unzip_inputs",
    "save_csv",
    "save_json",
    "parse_invoice_meta",
    "save_meta",
    "to_png",
    "to_jpeg",
    "make_thumbnail",
    "save_main_image",
    "copy_raw",
    "plot_lines",
    "plot_scatter",
    "as_node",
]
