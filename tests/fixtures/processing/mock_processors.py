"""Mock processors for testing."""

from __future__ import annotations

from rdetoolkit.processing.context import ProcessingContext
from rdetoolkit.processing.pipeline import Processor


class MockSuccessProcessor(Processor):
    """A processor that always succeeds."""

    def __init__(self, name: str = "MockSuccessProcessor"):
        self.name = name
        self.executed = False
        self.context_received = None

    def process(self, context: ProcessingContext) -> None:
        """Execute the mock processing operation."""
        self.executed = True
        self.context_received = context

    def get_name(self) -> str:
        """Get the name of this processor."""
        return self.name


class MockFailureProcessor(Processor):
    """A processor that always fails."""

    def __init__(self, error_message: str = "Mock processor failure", name: str = "MockFailureProcessor"):
        self.error_message = error_message
        self.name = name
        self.executed = False

    def process(self, context: ProcessingContext) -> None:
        """Execute the mock processing operation that fails."""
        self.executed = True
        raise RuntimeError(self.error_message)

    def get_name(self) -> str:
        """Get the name of this processor."""
        return self.name


class MockLoggingProcessor(Processor):
    """A processor that logs its execution."""

    def __init__(self, name: str = "MockLoggingProcessor"):
        self.name = name
        self.execution_log = []

    def process(self, context: ProcessingContext) -> None:
        """Execute the mock processing operation with logging."""
        self.execution_log.append({
            "processor": self.name,
            "context_index": context.index,
            "mode_name": context.mode_name,
            "rawfiles_count": len(context.resource_paths.rawfiles)
        })

    def get_name(self) -> str:
        """Get the name of this processor."""
        return self.name


class MockConditionalProcessor(Processor):
    """A processor that succeeds or fails based on context conditions."""

    def __init__(self, fail_condition_func=None, name: str = "MockConditionalProcessor"):
        self.fail_condition_func = fail_condition_func or (lambda ctx: False)
        self.name = name
        self.executed = False

    def process(self, context: ProcessingContext) -> None:
        """Execute the mock processing operation conditionally."""
        self.executed = True
        if self.fail_condition_func(context):
            raise RuntimeError(f"Conditional failure in {self.name}")

    def get_name(self) -> str:
        """Get the name of this processor."""
        return self.name


class MockFileProcessor(Processor):
    """A processor that simulates file operations."""

    def __init__(self, name: str = "MockFileProcessor"):
        self.name = name
        self.files_processed = []
        self.executed = False

    def process(self, context: ProcessingContext) -> None:
        """Execute mock file processing."""
        self.executed = True
        for rawfile in context.resource_paths.rawfiles:
            self.files_processed.append(str(rawfile))

    def get_name(self) -> str:
        """Get the name of this processor."""
        return self.name


class MockValidationProcessor(Processor):
    """A processor that simulates validation operations."""

    def __init__(self, validation_result: bool = True, name: str = "MockValidationProcessor"):
        self.validation_result = validation_result
        self.name = name
        self.executed = False

    def process(self, context: ProcessingContext) -> None:
        """Execute mock validation."""
        self.executed = True
        if not self.validation_result:
            raise ValueError(f"Validation failed in {self.name}")

    def get_name(self) -> str:
        """Get the name of this processor."""
        return self.name
