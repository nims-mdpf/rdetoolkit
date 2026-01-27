from __future__ import annotations

from typing import Any


class StructuredError(Exception):
    """A custom exception class providing structured error information.

    This class extends the standard Exception class to include additional information
    such as an error message, an error code, an error object, and traceback information.
    This allows for a more detailed representation of errors.

    Args:
        emsg (str): The error message.
        ecode (int): The error code. Defaults to 1.
        eobj (any): An additional error object. This can be an object of any type to provide more context to the error.
        traceback_info (str, optional): Additional traceback information. Defaults to None.
    """

    def __init__(self, emsg: str = "", ecode: int = 1, eobj: Any | None = None, traceback_info: str | None = None) -> None:
        super().__init__(emsg)
        self.emsg = emsg
        self.ecode = ecode
        self.eobj = eobj
        self.traceback_info = traceback_info


class SkipRemainingProcessorsError(Exception):
    """Exception to signal that remaining processors in the pipeline should be skipped.

    This exception is used for flow control in the pipeline, allowing a processor
    to indicate that all subsequent processors should be skipped for the current
    processing context.
    """
    def __init__(self, emsg: str = "", ecode: int = 101, eobj: Any | None = None, traceback_info: str | None = None) -> None:
        emsg = f"SmartTable Error: {emsg}" if emsg else "SmartTable Error"
        super().__init__(emsg)
        self.emsg = emsg
        self.ecode = ecode
        self.eobj = eobj
        self.traceback_info = traceback_info


class InvoiceModeError(Exception):
    """Exception raised for errors related to invoice mode.

    Attributes:
        emsg (str): Error message describing the exception.
        ecode (int): Error code associated with the exception. Default is 100.
        eobj (Any | None): Optional object related to the exception. Default is None.
        traceback_info (str | None): Optional traceback information. Default is None.

    Args:
        emsg (str): Error message describing the exception.
        ecode (int): Error code associated with the exception. Default is 100.
        eobj (Any | None): Optional object related to the exception. Default is None.
        traceback_info (str | None): Optional traceback information. Default is None.
    """
    def __init__(self, emsg: str = "", ecode: int = 100, eobj: Any | None = None, traceback_info: str | None = None) -> None:
        emsg = f"InvoiceMode Error: {emsg}" if emsg else "InvoiceMode Error"
        super().__init__(emsg)
        self.emsg = emsg
        self.ecode = ecode
        self.eobj = eobj
        self.traceback_info = traceback_info


class ExcelInvoiceModeError(Exception):
    """Exception raised for errors related to Excelinvoice mode.

    Attributes:
        emsg (str): Error message describing the exception.
        ecode (int): Error code associated with the exception. Default is 101.
        eobj (Any | None): Optional object related to the exception. Default is None.
        traceback_info (str | None): Optional traceback information. Default is None.

    Args:
        emsg (str): Error message describing the exception.
        ecode (int): Error code associated with the exception. Default is 102.
        eobj (Any | None): Optional object related to the exception. Default is None.
        traceback_info (str | None): Optional traceback information. Default is None.
    """
    def __init__(self, emsg: str = "", ecode: int = 101, eobj: Any | None = None, traceback_info: str | None = None) -> None:
        emsg = f"ExcelInvoiceMode Error: {emsg}" if emsg else "ExcelInvoiceMode Error"
        super().__init__(emsg)
        self.emsg = emsg
        self.ecode = ecode
        self.eobj = eobj
        self.traceback_info = traceback_info


class MultiDataTileModeError(Exception):
    """Exception raised for errors in MultiData tile mode operations.

    Attributes:
        emsg (str): Error message describing the exception.
        ecode (int): Error code associated with the exception. Default is 102.
        eobj (Any | None): Optional object related to the error. Default is None.
        traceback_info (str | None): Optional traceback information. Default is None.

    Args:
        emsg (str): Error message describing the exception.
        ecode (int): Error code associated with the exception. Default is 101.
        eobj (Any | None): Optional object related to the error. Default is None.
        traceback_info (str | None): Optional traceback information. Default is None.
    """

    def __init__(self, emsg: str = "", ecode: int = 102, eobj: Any | None = None, traceback_info: str | None = None) -> None:
        emsg = f"MultiDataTileMode Error: {emsg}" if emsg else "MultiDataTileMode Error"
        super().__init__(emsg)
        self.emsg = emsg
        self.ecode = ecode
        self.eobj = eobj
        self.traceback_info = traceback_info


class RdeFormatModeError(Exception):
    """Exception raised for errors in the RDE format mode.

    Attributes:
        emsg (str): Error message describing the exception.
        ecode (int): Error code associated with the exception. Default is 103.
        eobj (Any | None): Optional object related to the error. Default is None.
        traceback_info (str | None): Optional traceback information. Default is None.

    Args:
        emsg (str): Error message describing the exception.
        ecode (int): Error code associated with the exception. Default is 103.
        eobj (Any | None): Optional object related to the error. Default is None.
        traceback_info (str | None): Optional traceback information. Default is None.
    """
    def __init__(self, emsg: str = "", ecode: int = 103, eobj: Any | None = None, traceback_info: str | None = None) -> None:
        emsg = f"RdeFormatMode Error: {emsg}" if emsg else "RdeFormatMode Error"
        super().__init__(emsg)
        self.emsg = emsg
        self.ecode = ecode
        self.eobj = eobj
        self.traceback_info = traceback_info


class InvoiceSchemaValidationError(Exception):
    """Raised when a validation error occurs."""

    def __init__(self, message: str = "Validation error") -> None:
        self.message = message
        super().__init__(self.message)


class MetadataValidationError(Exception):
    """Raised when a validation error occurs."""

    def __init__(self, message: str = "Validation error") -> None:
        self.message = message
        super().__init__(self.message)


class DataRetrievalError(Exception):
    """Raised when an error occurs during data retrieval."""

    def __init__(self, message: str = "Data retrieval error") -> None:
        self.message = message
        super().__init__(self.message)


class NoResultsFoundError(Exception):
    """Raised when no results are found."""

    def __init__(self, message: str = "No results found") -> None:
        self.message = message
        super().__init__(self.message)


class InvalidSearchParametersError(Exception):
    """Raised when an invalid search term is used."""

    def __init__(self, message: str = "Invalid search term") -> None:
        self.message = message
        super().__init__(self.message)


class ConfigError(Exception):
    """Exception raised for configuration file loading errors.

    This exception provides structured, informative error messages for configuration
    file failures, including file paths, error types, line/column information for
    parse errors, and documentation links.

    Attributes:
        message: The error message describing what went wrong.
        file_path: Path to the configuration file that failed to load.
        error_type: Type of error (e.g., 'file_not_found', 'parse_error', 'validation_error').
        line_number: Line number where error occurred (for parse errors).
        column_number: Column number where error occurred (for parse errors).
        field_name: Field name that failed validation (for validation errors).
        doc_url: Documentation URL for help and troubleshooting.

    Examples:
        File not found error:
        >>> raise ConfigError(
        ...     "Configuration file not found",
        ...     file_path="config.yaml",
        ...     error_type="file_not_found"
        ... )

        Parse error with line information:
        >>> raise ConfigError(
        ...     "Invalid YAML syntax: expected <block end>",
        ...     file_path="config.yaml",
        ...     error_type="parse_error",
        ...     line_number=10,
        ...     column_number=5
        ... )

        Validation error with field information:
        >>> raise ConfigError(
        ...     "Invalid value for field",
        ...     file_path="config.yaml",
        ...     error_type="validation_error",
        ...     field_name="system.extended_mode"
        ... )
    """

    def __init__(
        self,
        message: str,
        *,
        file_path: str | None = None,
        error_type: str = "unknown",
        line_number: int | None = None,
        column_number: int | None = None,
        field_name: str | None = None,
        doc_url: str = "https://nims-mdpf.github.io/rdetoolkit/usage/config/config/",
    ) -> None:
        """Initialize ConfigError with detailed information.

        Args:
            message: The error message describing what went wrong.
            file_path: Path to the configuration file that failed.
            error_type: Type of error (e.g., 'file_not_found', 'parse_error', 'validation_error').
            line_number: Line number where error occurred (for parse errors).
            column_number: Column number where error occurred (for parse errors).
            field_name: Field name that failed validation (for validation errors).
            doc_url: Documentation URL for help and troubleshooting.
        """
        self.message = message
        self.file_path = file_path
        self.error_type = error_type
        self.line_number = line_number
        self.column_number = column_number
        self.field_name = field_name
        self.doc_url = doc_url

        # Build comprehensive error message
        parts = []
        if file_path:
            parts.append(f"Configuration file: '{file_path}'")

        parts.append(message)

        if line_number is not None:
            location = f"line {line_number}"
            if column_number is not None:
                location += f", column {column_number}"
            parts.append(f"Location: {location}")

        if field_name:
            parts.append(f"Field: {field_name}")

        parts.append(f"See: {doc_url}")

        full_message = "\n".join(parts)
        super().__init__(full_message)
