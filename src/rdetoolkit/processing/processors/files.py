"""File operations processors with Rust integration."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from rdetoolkit.processing.context import ProcessingContext
from rdetoolkit.processing.pipeline import Processor
from rdetoolkit.rdelogger import get_logger

logger = get_logger(__name__, file_path="data/logs/rdesys.log")


class FileCopier(Processor):
    """Copies raw files to designated directories with Rust optimization."""

    def process(self, context: ProcessingContext) -> None:
        """Copy files based on configuration settings."""
        if context.srcpaths.config.system.save_raw:
            self._copy_to_raw(context)

        if context.srcpaths.config.system.save_nonshared_raw:
            self._copy_to_nonshared_raw(context)

    def _copy_to_raw(self, context: ProcessingContext) -> None:
        """Copy files to raw directory."""
        self._copy_files(context.resource_paths.raw, context.resource_paths.rawfiles)

    def _copy_to_nonshared_raw(self, context: ProcessingContext) -> None:
        """Copy files to nonshared_raw directory."""
        self._copy_files(context.resource_paths.nonshared_raw, context.resource_paths.rawfiles)

    def _copy_files(self, dest_dir: Path, source_files: tuple[Path, ...]) -> None:
        """Python fallback for file copying."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        for source_path in source_files:
            dest_path = dest_dir / source_path.name

            try:
                if source_path.is_file():
                    shutil.copy2(source_path, dest_path)
                    logger.debug(f"Copied file: {source_path} -> {dest_path}")
                elif source_path.is_dir():
                    shutil.copytree(source_path, dest_path, dirs_exist_ok=True)
                    logger.debug(f"Copied directory: {source_path} -> {dest_path}")
                else:
                    logger.warning(f"Skipping unknown path type: {source_path}")
            except Exception as e:
                err_msg = f"Failed to copy {source_path} --> {dest_path}"
                logger.error(f"Failed to copy {source_path}: {e}")
                raise RuntimeError(err_msg) from e


class RDEFormatFileCopier(Processor):
    """Copies files by directory structure for RDEFormat mode."""

    def process(self, context: ProcessingContext) -> None:
        """Copy files based on their directory structure.

        Python fallback for directory structure copying.

        """
        directories = {
            "raw": context.resource_paths.raw,
            "main_image": context.resource_paths.main_image,
            "other_image": context.resource_paths.other_image,
            "meta": context.resource_paths.meta,
            "structured": context.resource_paths.struct,
            "logs": context.resource_paths.logs,
            "nonshared_raw": context.resource_paths.nonshared_raw,
        }

        for f in context.resource_paths.rawfiles:
            for dir_name, directory in directories.items():
                if dir_name in f.parts:
                    try:
                        shutil.copy(f, os.path.join(str(directory), f.name))
                    except Exception as e:
                        err_msg = f"Error: Failed to copy {f} to {directory}"
                        logger.error(f"Failed to copy {f} to {directory}: {e}")
                        raise RuntimeError(err_msg) from e
                    break
