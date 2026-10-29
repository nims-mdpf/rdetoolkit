"""Structural input validation for common Runner planning."""

from __future__ import annotations

from pathlib import Path

from rdetoolkit.domain.service_errors import validation_error
from rdetoolkit.types import InputPaths


class InputValidator:
    """Validate the required RDE input directory structure."""

    def validate(self, root: Path) -> InputPaths:
        """Validate and resolve required input directories.

        Args:
            root: Data root containing inputdata, invoice, and tasksupport.

        Returns:
            Validated explicit input paths.

        Raises:
            RdeValidationError: If a required directory is missing.
        """
        required = tuple(root / name for name in ("inputdata", "invoice", "tasksupport"))
        for path in required:
            if not path.is_dir():
                raise validation_error(4003, f"Required input directory does not exist: {path}")
        return InputPaths(inputdata=required[0], invoice=required[1], tasksupport=required[2])
