"""Path-based artifact services shared by all execution modes."""

from __future__ import annotations

import shutil
from pathlib import Path

from rdetoolkit import img2thumb
from rdetoolkit.domain.service_errors import execution_error
from rdetoolkit.types import RdeConfig


class RawArtifactService:
    """Copy raw inputs according to canonical configuration."""

    def copy(
        self,
        source_files: tuple[Path, ...],
        *,
        raw_dir: Path,
        nonshared_raw_dir: Path,
        config: RdeConfig,
        smarttable: bool = False,
        data_root: Path | None = None,
    ) -> None:
        """Copy configured raw artifacts using explicit destination paths.

        Args:
            source_files: Input files or directories to copy.
            raw_dir: Shared raw destination.
            nonshared_raw_dir: Non-shared raw destination.
            config: Canonical run configuration.
            smarttable: Whether SmartTable filtering rules apply.
            data_root: Unused. The generic service copies every selected input
                into the two raw directories, so it never classifies by path
                component and needs no reference point (ruling #7).
        """
        _ = data_root
        selected = self._selected_files(source_files, config=config, smarttable=smarttable)
        if config.system.save_raw:
            self._copy_files(selected, raw_dir)
        if config.system.save_nonshared_raw:
            self._copy_files(selected, nonshared_raw_dir)

    @staticmethod
    def _selected_files(
        source_files: tuple[Path, ...],
        *,
        config: RdeConfig,
        smarttable: bool,
    ) -> tuple[Path, ...]:
        ordered = tuple(sorted(source_files))
        if not smarttable:
            return ordered
        selected = tuple(path for path in ordered if not _is_generated_smarttable_row(path))
        if config.smarttable.save_table_file:
            return selected
        return tuple(path for path in selected if not _is_original_smarttable_file(path))

    @staticmethod
    def _copy_files(source_files: tuple[Path, ...], destination: Path) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        for source in source_files:
            target = destination / source.name
            try:
                if source.is_file():
                    shutil.copy2(source, target)
                elif source.is_dir():
                    shutil.copytree(source, target, dirs_exist_ok=True)
            except Exception as exc:
                message = f"Failed to copy {source} --> {target}"
                raise execution_error(3001, message) from exc


class ImageArtifactService:
    """Generate optional image artifacts while retaining v1 failure tolerance."""

    def generate(
        self,
        *,
        main_image_dir: Path,
        thumbnail_dir: Path,
        config: RdeConfig,
    ) -> None:
        """Generate thumbnails when configured, suppressing converter failures.

        Args:
            main_image_dir: Directory containing main images.
            thumbnail_dir: Thumbnail destination directory.
            config: Canonical run configuration.
        """
        if not config.system.save_thumbnail_image:
            return
        try:
            img2thumb.copy_images_to_thumbnail(thumbnail_dir, main_image_dir)
        except Exception:  # noqa: BLE001
            return


def _is_generated_smarttable_row(path: Path) -> bool:
    return path.name.startswith("fsmarttable_") and path.suffix.lower() == ".csv"


def _is_original_smarttable_file(path: Path) -> bool:
    return (
        "inputdata" in path.parts
        and path.name.startswith("smarttable_")
        and path.suffix.lower() in {".csv", ".tsv", ".xlsx"}
    )
