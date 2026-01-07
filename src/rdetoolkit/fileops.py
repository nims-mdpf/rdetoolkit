from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from rdetoolkit.exceptions import StructuredError

@lru_cache(maxsize=1)
def _get_logger() -> Any:
    from rdetoolkit.rdelogger import get_logger

    return get_logger(__name__)


def detect_encoding(path: str) -> str:
    """Detect file encoding using the core implementation.

    Args:
        path: Path to the target file.

    Returns:
        Detected encoding name.
    """
    from rdetoolkit.core import detect_encoding as _detect_encoding

    return _detect_encoding(path)


def readf_json(path: str | Path) -> dict[str, Any]:  # pragma: no cover
    """A function that reads a JSON file and returns the JSON object.

    Args:
        path (str | Path): The path to the JSON file.

    Returns:
        dict[str, Any]: The parsed json object.

    Raises:
        StructuredError: If an error occurs while processing the file.
    """
    _path = str(path) if isinstance(path, Path) else path
    try:
        enc = detect_encoding(_path)
        normalize_enc = enc.lower().replace("-", "_") if enc else "utf_8"
        with open(_path, encoding=normalize_enc) as f:
            return json.load(f)
    except Exception as e:
        emsg = f"An error occurred while processing the file: {str(e)}"
        _get_logger().error(emsg)
        raise StructuredError(emsg) from e


def writef_json(path: str | Path, obj: dict[str, Any], *, enc: str = "utf_8") -> dict[str, Any]:
    """Writes an content to a JSON file.

    Args:
        path (str | Path): Path to the destination JSON file.
        obj (dict[str, Any]): Invoice object to be serialized and written.
        enc (str): Encoding to use when writing the file. Defaults to "utf_8".

    Returns:
        dict[str, Any]: The parsed json object.
    """
    with open(path, "w", encoding=enc) as f:
        json.dump(obj, f, indent=4, ensure_ascii=False)
    return obj
