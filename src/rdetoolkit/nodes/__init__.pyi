from collections.abc import Callable
from typing import Any

from rdetoolkit.nodes.image import copy_raw as copy_raw, make_thumbnail as make_thumbnail, save_main_image as save_main_image, to_jpeg as to_jpeg, to_png as to_png
from rdetoolkit.nodes.io import read_csv_with_header as read_csv_with_header, read_excel as read_excel, read_text as read_text, unzip_inputs as unzip_inputs
from rdetoolkit.nodes.meta import parse_invoice_meta as parse_invoice_meta, save_meta as save_meta
from rdetoolkit.nodes.plot import plot_lines as plot_lines, plot_scatter as plot_scatter
from rdetoolkit.nodes.structured import save_csv as save_csv, save_json as save_json

def as_node(instance: Any, *, method: str, id: str | None = None) -> Callable[..., Any]: ...

__all__: list[str]
