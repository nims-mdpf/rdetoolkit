"""SmartTable early exit processor for terminating pipeline when processing original table files."""

from pathlib import Path
import shutil

from rdetoolkit.exceptions import SkipRemainingProcessorsError
from rdetoolkit.processing.context import ProcessingContext
from rdetoolkit.processing.pipeline import Processor
from rdetoolkit.rdelogger import get_logger

logger = get_logger(__name__, file_path="data/logs/rdesys.log")


class SmartTableEarlyExitProcessor(Processor):
    """Processor that terminates pipeline early when processing original SmartTable files.

    This processor checks if the current rawfiles entry contains an original SmartTable file
    (located in data/inputdata/) and terminates the pipeline early if save_table_file is enabled.
    This prevents unnecessary processing for the SmartTable file entry while allowing normal
    processing to continue when save_table_file is disabled or when processing CSV files.
    """

    def process(self, context: ProcessingContext) -> None:
        """Check if processing should be terminated early and copy SmartTable file if needed.

        Args:
            context: Processing context containing rawfiles and other information

        Raises:
            SkipRemainingProcessorsError: When the current entry contains an original SmartTable file
                                   and save_table_file is enabled
        """
        if not context.is_smarttable_mode:
            return

        # Check if save_table_file is enabled
        save_table_file = False
        if (context.srcpaths.config.smarttable and
                hasattr(context.srcpaths.config.smarttable, 'save_table_file')):
            save_table_file = context.srcpaths.config.smarttable.save_table_file

        if not save_table_file:
            return

        for file_path in context.resource_paths.rawfiles:
            if self._is_original_smarttable_file(file_path):
                logger.info(f"Original SmartTable file detected: {file_path}")
                self._copy_smarttable_file(context, file_path)

                # Skip remaining processors
                logger.info("Skipping remaining processors for SmartTable file entry")
                msg = "SmartTable file processing completed"
                raise SkipRemainingProcessorsError(msg)

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

    def _copy_smarttable_file(self, context: ProcessingContext, file_path: Path) -> None:
        """Copy SmartTable file to raw/nonshared_raw directories based on configuration.

        Args:
            context: Processing context
            file_path: Path to the SmartTable file to copy
        """
        # Check which directories to save to based on system configuration
        if context.srcpaths.config.system.save_raw and context.resource_paths.raw:
            dest_path = context.resource_paths.raw / file_path.name
            self._copy_file(file_path, dest_path)
            logger.info(f"Copied SmartTable file to raw: {dest_path}")

        if context.srcpaths.config.system.save_nonshared_raw and context.resource_paths.nonshared_raw:
            dest_path = context.resource_paths.nonshared_raw / file_path.name
            self._copy_file(file_path, dest_path)
            logger.info(f"Copied SmartTable file to nonshared_raw: {dest_path}")

    def _copy_file(self, source: Path, destination: Path) -> None:
        """Copy a file to the destination, creating directories if needed.

        Args:
            source: Source file path
            destination: Destination file path
        """
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        logger.debug(f"File copied: {source} -> {destination}")
