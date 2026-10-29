"""Path-only output layout resolution for common domain services."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rdetoolkit.domain.service_errors import internal_error


@dataclass(frozen=True, slots=True)
class OutputLayout:
    """Canonical output directories for one tile."""

    struct: Path
    meta: Path
    main_image: Path
    other_image: Path
    thumbnail: Path
    attachment: Path
    nonshared_raw: Path
    raw: Path
    invoice: Path
    logs: Path


class OutputLayoutResolver:
    """Resolve output paths without creating directories."""

    def resolve(self, base_dir: Path, index: int) -> OutputLayout:
        """Resolve the v1-compatible layout for a tile index.

        Args:
            base_dir: Data output root.
            index: Non-negative tile index.

        Returns:
            Immutable output layout.

        Raises:
            RdeInternalError: If the tile index is negative.
        """
        if index < 0:
            raise internal_error(5001, f"Tile index must be non-negative: {index}")
        root = base_dir if index == 0 else base_dir / "divided" / f"{index:04d}"
        return OutputLayout(
            struct=root / "structured",
            meta=root / "meta",
            main_image=root / "main_image",
            other_image=root / "other_image",
            thumbnail=root / "thumbnail",
            attachment=root / "attachment",
            nonshared_raw=root / "nonshared_raw",
            raw=root / "raw",
            invoice=root / "invoice",
            logs=root / "logs",
        )
