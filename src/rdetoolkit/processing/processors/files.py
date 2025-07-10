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


class SmartTableFileCopier(Processor):
    """Copies raw files for SmartTable mode, excluding generated CSV files."""

    def __init__(self) -> None:
        self.smarttable_suffix_length = 4

    def process(self, context: ProcessingContext) -> None:
        """Copy files based on configuration settings, excluding SmartTable CSV files.

        This method handles file copying operations according to the system configuration.
        It processes raw file copying and non-shared raw file copying based on the
        respective configuration flags.

        Args:
            context (ProcessingContext): The processing context containing source paths,
                configuration settings, and other processing information.

        Returns:
            None

        Note:
            SmartTable CSV files are excluded from the copying process.
        """
        if context.srcpaths.config.system.save_raw:
            self._copy_to_raw(context)

        if context.srcpaths.config.system.save_nonshared_raw:
            self._copy_to_nonshared_raw(context)

    def _copy_to_raw(self, context: ProcessingContext) -> None:
        """Copy files to raw directory, excluding SmartTable generated CSVs."""
        filtered_files = self._filter_smarttable_csvs(context.resource_paths.rawfiles)
        filtered_files = self._filter_smarttable_original_file(context, filtered_files)
        self._copy_files(context.resource_paths.raw, filtered_files)

    def _copy_to_nonshared_raw(self, context: ProcessingContext) -> None:
        """Copy files to nonshared_raw directory, excluding SmartTable generated CSVs."""
        filtered_files = self._filter_smarttable_csvs(context.resource_paths.rawfiles)
        filtered_files = self._filter_smarttable_original_file(context, filtered_files)
        self._copy_files(context.resource_paths.nonshared_raw, filtered_files)

    def _filter_smarttable_csvs(self, source_files: tuple[Path, ...]) -> tuple[Path, ...]:
        """Filter out SmartTable generated CSV files from the copy list.

        SmartTable generated CSV files have specific naming patterns:
        - Start with 'f' followed by original smarttable filename
        - Located in temp directory
        - Have .csv extension

        Args:
            source_files: Original list of files to copy

        Returns:
            Filtered list of files excluding SmartTable generated CSVs
        """
        filtered = []
        for file_path in source_files:
            # Check if this is a SmartTable generated CSV file
            if self._is_smarttable_generated_csv(file_path):
                logger.debug(f"Skipping SmartTable generated CSV: {file_path}")
                continue
            filtered.append(file_path)

        return tuple(filtered)

    def _filter_smarttable_original_file(self, context: ProcessingContext, source_files: tuple[Path, ...]) -> tuple[Path, ...]:
        """Filter original SmartTable file based on configuration.

        If save_table_file is False, remove original SmartTable files from the copy list.

        Args:
            context: Processing context containing configuration
            source_files: Original list of files to copy

        Returns:
            Filtered list of files
        """
        if not context.is_smarttable_mode:
            return source_files

        save_table_file = False
        if (context.srcpaths.config.smarttable and hasattr(context.srcpaths.config.smarttable, 'save_table_file')):
            save_table_file = context.srcpaths.config.smarttable.save_table_file

        if save_table_file:
            return source_files

        filtered = []
        for file_path in source_files:
            if not self._is_original_smarttable_file(file_path):
                filtered.append(file_path)
            else:
                logger.debug(f"Skipping original SmartTable file (save_table_file=False): {file_path}")

        return tuple(filtered)

    def _is_original_smarttable_file(self, file_path: Path) -> bool:
        """Check if the file is an original SmartTable file.

        Args:
            file_path: Path to check

        Returns:
            True if this is an original SmartTable file in inputdata directory
        """
        if 'inputdata' not in file_path.parts:
            return False

        if not file_path.name.startswith('smarttable_'):
            return False

        supported_extensions = ['.xlsx', '.csv', '.tsv']
        return file_path.suffix.lower() in supported_extensions

    def _is_smarttable_generated_csv(self, file_path: Path) -> bool:
        """Check if the file is a SmartTable generated CSV file.

        Args:
            file_path: Path to check

        Returns:
            True if this is a SmartTable generated CSV file
        """
        if file_path.suffix.lower() != '.csv':
            return False

        if 'temp' not in file_path.parts:
            return False

        filename = file_path.name
        if not filename.startswith('fsmarttable_'):
            return False

        name_without_ext = filename[:-4]
        parts = name_without_ext.split('_')

        # Must have at least 3 parts: ['fsmarttable', 'filename', 'number']
        min_parts = 3
        if len(parts) < min_parts:
            return False

        # Last part must be numeric (4-digit number like 0000, 0001, etc.)
        last_part = parts[-1]
        return last_part.isdigit() and len(last_part) == self.smarttable_suffix_length

    def _copy_files(self, dest_dir: Path, source_files: tuple[Path, ...]) -> None:
        """Copy files to destination directory."""
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
