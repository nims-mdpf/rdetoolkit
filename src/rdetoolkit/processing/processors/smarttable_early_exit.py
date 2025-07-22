"""SmartTable early exit processor for terminating pipeline when processing original table files."""

from pathlib import Path
import shutil

from rdetoolkit.exceptions import SkipRemainingProcessorsError
from rdetoolkit.processing.context import ProcessingContext
from rdetoolkit.processing.pipeline import Processor
from rdetoolkit.processing.processors.validation import MetadataValidator, InvoiceValidator
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

        For original SmartTable files, this processor:
        1. Copies the file to appropriate directories (if save_table_file is enabled)
        2. Performs validation of invoice.json and metadata.json
        3. Terminates the pipeline early to avoid unnecessary processing

        Args:
            context: Processing context containing rawfiles and other information

        Raises:
            SkipRemainingProcessorsError: When the current entry contains an original SmartTable file
                                         after validation is completed
        """
        if not context.is_smarttable_mode:
            return

        for file_path in context.resource_paths.rawfiles:
            if self._is_original_smarttable_file(file_path):
                logger.info(f"Original SmartTable file detected: {file_path}")

                # Copy SmartTable file if save_table_file is enabled
                if self._should_save_table_file(context):
                    self._copy_smarttable_file(context, file_path)

                # Always validate files for SmartTable entries
                try:
                    self._validate_files(context)
                    logger.info("SmartTable validation completed successfully")
                except Exception as e:
                    logger.error(f"SmartTable validation failed: {str(e)}")
                    raise

                # Skip remaining processors after validation
                logger.info("Skipping remaining processors for SmartTable file entry")
                msg = "SmartTable file processing and validation completed"
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

    def _should_save_table_file(self, context: ProcessingContext) -> bool:
        """Check if save_table_file is enabled in the configuration.

        Args:
            context: Processing context

        Returns:
            True if save_table_file is enabled, False otherwise
        """
        if (context.srcpaths.config.smarttable and
                hasattr(context.srcpaths.config.smarttable, 'save_table_file')):
            return context.srcpaths.config.smarttable.save_table_file
        return False

    def _validate_files(self, context: ProcessingContext) -> None:
        """Validate invoice.json and metadata.json files.

        This method ensures that both invoice.json and metadata.json are validated
        against their respective schemas, regardless of the save_table_file setting.

        Args:
            context: Processing context containing file paths

        Raises:
            Exception: If validation fails for either file
        """
        logger.debug("Starting SmartTable file validation")

        # Validate metadata.json if it exists
        try:
            metadata_validator = MetadataValidator()
            metadata_validator.process(context)
            logger.debug("Metadata validation completed successfully")
        except Exception as e:
            logger.error(f"Metadata validation failed: {str(e)}")
            raise

        # Validate invoice.json against schema
        try:
            invoice_validator = InvoiceValidator()
            invoice_validator.process(context)
            logger.debug("Invoice validation completed successfully")
        except Exception as e:
            logger.error(f"Invoice validation failed: {str(e)}")
            raise

        logger.debug("All SmartTable validation completed successfully")
