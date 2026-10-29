"""Deterministic input enumeration for future unified mode adapters."""

from __future__ import annotations

from pathlib import Path

from rdetoolkit.domain.service_errors import validation_error


class IterationFactory:
    """Enumerate candidate inputs deterministically."""

    def files(self, directory: Path, *, pattern: str = "*") -> tuple[Path, ...]:
        """Return matching sibling paths in stable order.

        Args:
            directory: Directory to enumerate.
            pattern: Glob pattern applied below the directory.

        Returns:
            Sorted matching paths.

        Raises:
            RdeValidationError: If the directory does not exist.
        """
        if not directory.is_dir():
            raise validation_error(4003, f"Input directory does not exist: {directory}")
        return tuple(sorted(directory.glob(pattern)))
