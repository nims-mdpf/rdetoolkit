"""Pipeline architecture for processing operations."""

from __future__ import annotations

from abc import ABC, abstractmethod

from rdetoolkit.invoicefile import InvoiceFile
from rdetoolkit.models.result import WorkflowExecutionStatus
from rdetoolkit.processing.context import ProcessingContext
from rdetoolkit.rdelogger import get_logger
from rdetoolkit.exceptions import SkipRemainingProcessorsError

logger = get_logger(__name__, file_path="data/logs/rdesys.log")


class Processor(ABC):
    """Abstract base class for processing operations.

    Each processor represents a single step in the processing pipeline.
    Processors should be stateless and idempotent when possible.
    """

    @abstractmethod
    def process(self, context: ProcessingContext) -> None:
        """Execute the processing operation.

        Args:
            context: The processing context containing all necessary information

        Raises:
            Any exceptions that occur during processing should be allowed to propagate
            unless the processor is designed to handle specific error conditions.
        """
        ...

    def get_name(self) -> str:
        """Get the name of this processor for logging purposes."""
        return self.__class__.__name__


class Pipeline:
    """Pipeline for executing a sequence of processing operations.

    The pipeline executes processors in the order they were added,
    passing the same context to each processor.
    """

    def __init__(self) -> None:
        """Initialize an empty pipeline."""
        self._processors: list[Processor] = []

    def add(self, processor: Processor) -> Pipeline:
        """Add a processor to the pipeline.

        Args:
            processor: The processor to add

        Returns:
            Self for method chaining
        """
        self._processors.append(processor)
        return self

    def execute(self, context: ProcessingContext) -> WorkflowExecutionStatus:
        """Execute all processors in the pipeline.

        Args:
            context: The processing context

        Returns:
            WorkflowExecutionStatus indicating success or failure

        Raises:
            Any exceptions from processors will propagate unless handled
        """
        logger.info(f"Starting pipeline execution for mode: {context.mode_name}")

        try:
            for processor in self._processors:
                processor_name = processor.get_name()
                logger.debug(f"Executing processor: {processor_name}")

                try:
                    processor.process(context)
                    logger.debug(f"Processor {processor_name} completed successfully")
                except SkipRemainingProcessorsError as e:
                    logger.info(f"Processor {processor_name} requested to skip remaining processors: {str(e)}")
                    break  # Exit the for loop, skipping remaining processors
                except Exception as e:
                    logger.error(f"Processor {processor_name} failed: {str(e)}")
                    raise

            # Create success status
            return self._create_success_status(context)

        except Exception as e:
            logger.error(f"Pipeline execution failed: {str(e)}")
            return self._create_error_status(context, e)

    def _create_success_status(self, context: ProcessingContext) -> WorkflowExecutionStatus:
        """Create a success status result."""
        # Try to get title from invoice if available
        title = f"{context.mode_name} Mode Process"
        try:
            if context.invoice_dst_filepath.exists():
                invoice = InvoiceFile(context.invoice_dst_filepath)
                title = invoice.invoice_obj.get("basic", {}).get("dataName", title)
        except Exception:
            # If we can't read the invoice, use the default title
            logger.warning(f"Failed to read invoice file at {context.invoice_dst_filepath}, using default title")

        return WorkflowExecutionStatus(
            run_id=context.index,
            title=title,
            status="success",
            mode=context.mode_name,
            error_code=None,
            error_message=None,
            target=context.basedir,
            stacktrace=None,
        )

    def _create_error_status(self, context: ProcessingContext, error: Exception) -> WorkflowExecutionStatus:
        """Create an error status result."""
        import traceback

        return WorkflowExecutionStatus(
            run_id=context.index,
            title=f"{context.mode_name} Mode Process (Failed)",
            status="failed",
            mode=context.mode_name,
            error_code=1,
            error_message=str(error),
            target=context.basedir,
            stacktrace=traceback.format_exc(),
            exception_object=error,
        )

    def get_processor_count(self) -> int:
        """Get the number of processors in this pipeline."""
        return len(self._processors)

    def get_processor_names(self) -> list[str]:
        """Get the names of all processors in this pipeline."""
        return [processor.get_name() for processor in self._processors]
