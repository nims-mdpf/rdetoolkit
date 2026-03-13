"""V2 core package — @node, @flow, DAG, Compiler, Executor.

This package also re-exports the Rust extension functions/classes
that were previously available as ``rdetoolkit.core`` (the .so module)
for backward compatibility with v1.x code.
"""

from rdetoolkit._core import (  # noqa: F401
    DirectoryOps,
    ManagedDirectory,
    detect_encoding,
    read_file_with_encoding,
    resize_image_aspect_ratio,
)
