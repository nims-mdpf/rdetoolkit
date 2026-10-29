"""Path resolution helpers for v2 domain workflows."""

from __future__ import annotations

from pathlib import Path

from rdetoolkit.domain.output import create_output_context
from rdetoolkit.types import InputPaths, OutputContext


def resolve_input_paths(input_root: str | Path) -> InputPaths:
    """Resolve standard RDE input paths below a root directory.

    Args:
        input_root: Directory containing ``inputdata``, ``invoice``, and
            ``tasksupport`` children.

    Returns:
        Input path bundle.

    Raises:
        FileNotFoundError: If ``input_root`` does not exist.
        NotADirectoryError: If ``input_root`` is not a directory.
    """
    root = Path(input_root)
    if not root.exists():
        msg = f"Input root does not exist: {root}"
        raise FileNotFoundError(msg)
    if not root.is_dir():
        msg = f"Input root is not a directory: {root}"
        raise NotADirectoryError(msg)
    return InputPaths(
        inputdata=root / "inputdata",
        invoice=root / "invoice",
        tasksupport=root / "tasksupport",
    )


def resolve_output_paths(output_root: str | Path, *, create: bool = True) -> OutputContext:
    """Resolve standard RDE output paths below a root directory.

    Args:
        output_root: Root directory for output resources.
        create: Whether to create the output directories.

    Returns:
        Output context with standard child paths.
    """
    return create_output_context(output_root, create=create)
