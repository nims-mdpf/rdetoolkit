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
