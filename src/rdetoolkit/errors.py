from __future__ import annotations

import contextlib
import logging
import os
import sys
import traceback
from collections.abc import Generator
from functools import wraps
from typing import Any, Callable

from rdetoolkit.exceptions import StructuredError
from rdetoolkit.rde2util import StorageDir


def catch_exception_with_message(
    *,
    error_message: str | None = None,
    error_code: int | None = None,
    eobj: Any | None = None,
    verbose: bool = False,
) -> Callable:
    """A decorator that catches exceptions and re-raises a StructuredError with a customized message and error code.

    This decorator catches exceptions thrown within the decorated function.
    If a StructuredError is raised, it re-raises it with the specified error message, error code, and optional additional error object.
    For other exceptions, it re-raises them as standard Exceptions. The verbosity level of the error message can be controlled via the verbose parameter.

    Args:
        error_message (Optional[str]): Customized message to be used in case of an error. Defaults to None.
        error_code (Optional[int]): Error code to be used in case of an error. Defaults to None.
        eobj (Optional[Any]): Additional object to include in the error. Defaults to None.
        verbose (bool): If set to True, provides detailed error messages. Defaults to False.

    Returns:
        Callable: A function decorator that provides customized error handling on exception occurrence.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> None:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                _emsg = e.emsg if hasattr(e, "emsg") else error_message
                _ecode = e.ecode if hasattr(e, "ecode") else error_code
                _eobj = e.eobj if hasattr(e, "eobj") else eobj
                raise handle_exception(e, error_message=_emsg, error_code=_ecode, eobj=_eobj, verbose=verbose) from e

        return wrapper

    return decorator


@contextlib.contextmanager
def skip_exception_context(exception_type: type[Exception], logger: logging.Logger | None = None, enabled: bool = False) -> Generator[dict[str, str | None], None, None]:
    """Context manager to skip exceptions and log them.

    Args:
        exception_type (type[Exception]): The type of exception to skip.
        logger (logging.Logger | None): The logger to use for logging. Defaults to None.
        enabled (bool): Whether to enable the context manager. Defaults to False.

    Yields:
        dict[str, object | None]: Yields None if no exception occurs, otherwise yields a tuple containing the error code, error message, and stack trace.

    Example:
        ```python
        with skip_exception_context(ValueError, logger=logger, enabled=True) as error_info:
            raise ValueError("Test error")
        if error_info["code"]:
            print(f"Code: {error_info['code']}, Message: {error_info['message']}")
            print(f"Stack Trace: {error_info['stacktrace']}")
        ```
    """
    error_info: dict[str, str | None] = {
        "code": None,
        "message": None,
        "stacktrace": None,
    }
    try:
        yield error_info
    except exception_type as exc:
        if enabled:
            if logger:
                msg = f"Skipped exception: {exc}"
                logger.warning(msg)
            error_info["code"] = getattr(exc, 'ecode', "999")
            error_info["message"] = f"Error: {exc}"
            error_info["stacktrace"] = traceback.format_exc()
        else:
            raise exc


def format_simplified_traceback(tb_list: list[traceback.FrameSummary]) -> str:
    """Formats a simplified version of the traceback information.

    This function takes a list of traceback frame summaries and constructs a formatted string representing the call stack.
    The formatted string includes indentation and node characters to indicate the call path,
    highlighting the file, line number, and function name. The final line of the traceback is marked with a fire emoji.

    Args:
        tb_list (list[traceback.FrameSummary]): A list of traceback frame summaries to format.

    Returns:
        str: A formatted string representing the simplified traceback information.
    """
    formatted_traceback = ""
    indent = "  "
    node_char = "└─"
    last_index = len(tb_list) - 1
    fire_mark = "\U0001F525"
    for index, tb in enumerate(tb_list):
        prefix = (indent * 2 * index) + node_char if index != 0 else indent
        formatted_traceback += f"{prefix} File: {tb.filename}, Line: {tb.lineno} in {tb.name}()\n"

        if index == last_index:
            final_prefix = (indent * 2 * (index + 1)) + node_char
            formatted_traceback += f"{final_prefix}> L{tb.lineno}: {tb.line} {fire_mark}"

    return formatted_traceback


def handle_exception(
    e: Exception,
    error_message: str | None = None,
    error_code: int | None = None,
    eobj: Any | None = None,
    verbose: bool = False,
) -> StructuredError:
    """Handles exceptions and formats them into a StructuredError with optional custom message, error code, and additional object.

    This function captures the exception type and traceback, then formats a simplified version of the traceback.
    It constructs a custom error message, optionally including the full original traceback if verbose mode is enabled.
    The function returns a StructuredError containing the error message, error code, optional additional object,
    and simplified traceback information.

    Args:
        e (Exception): The exception to handle.
        error_message (Optional[str]): Customized message to be used in case of an error. Defaults to the exception message.
        error_code (Optional[int]): Error code to be used in case of an error. Defaults to 1.
        eobj (Optional[Any]): Additional object to include in the error. Defaults to None.
        verbose (bool): If set to True, includes the original traceback in the error message. Defaults to False.

    Returns:
        StructuredError: A structured error object containing the error message, error code, additional object,
        and simplified traceback information.
    """
    _message = f"Error: {error_message}" if error_message else f"Error: {str(e)}"
    _code = error_code if error_code else 1

    exc_type, _, exc_traceback = sys.exc_info()
    exc_type_name = exc_type.__name__ if exc_type else "UnknownException"
    tb_list = traceback.extract_tb(exc_traceback)

    combined_tb = tb_list

    # Get information from chained exceptions if they exist
    # If __cause__ or __context__ exists, include the original exception's traceback
    if hasattr(e, '__cause__') and e.__cause__ is not None:
        # Get the original exception's traceback and place it at the beginning
        original_tb = traceback.extract_tb(e.__cause__.__traceback__)
        _tb_list = original_tb + tb_list
        combined_tb = traceback.StackSummary.from_list(_tb_list)
    elif hasattr(e, '__context__') and e.__context__ is not None:
        # Get the context exception's traceback and place it at the beginning
        context_tb = traceback.extract_tb(e.__context__.__traceback__)
        _tb_list = context_tb + tb_list
        combined_tb = traceback.StackSummary.from_list(_tb_list)

    simplifed_traceback: str = format_simplified_traceback(combined_tb)
    error_messages = (
        "\nTraceback (simplified message):\n",
        f"Call Path:\n{simplifed_traceback}\n",
        f"\nException Type: {exc_type_name}\n",
        _message,
    )

    if verbose:
        original_traceback = traceback.format_exc()
        error_msg = f"{original_traceback}\n\n{'=' * 60}\nCustom Traceback (simplified and more readable):\n{'=' * 60}\n"
        sys.stderr.write(error_msg)

    return StructuredError(emsg=_message, ecode=_code, eobj=eobj, traceback_info="".join(error_messages))


def handle_and_exit_on_structured_error(e: StructuredError, logger: logging.Logger) -> None:
    """Catch StructuredError and write to log file.

    Args:
        e (StructuredError): StructuredError instance
        logger (logging.Logger): Logger instance
    """
    sys.stderr.write((e.traceback_info or "") + "\n")
    write_job_errorlog_file(e.ecode, e.emsg)
    logger.exception(e.emsg)
    sys.exit(1)


def handle_generic_error(e: Exception, logger: logging.Logger) -> None:
    """Catch generic error and write to log file.

    Args:
        e (Exception): Exception instance
        logger (logging.Logger): Logger instance
    """
    structured_error = handle_exception(e, verbose=True)
    sys.stderr.write((structured_error.traceback_info or "") + "\n")
    write_job_errorlog_file(999, "Error: Please check the logs and code, then try again.")
    logger.exception(str(e))
    sys.exit(1)


def write_job_errorlog_file(code: int, message: str, *, filename: str = "job.failed") -> None:
    """Write the error log to a file.

    This function writes the given error code and message to a specified file.
    The file will be saved in a directory determined by `StorageDir.get_datadir(False)`.

    Args:
        code (int): The error code to be written to the log file.
        message (str): The error message to be written to the log file.
        filename (str, optional): The name of the file to which the error log will be written.
            Defaults to "job.failed".

    Example:
        ```python
        write_job_errorlog_file(404, 'Not Found', filename='error.log')
        ```
    """
    with open(
        os.path.join(StorageDir.get_datadir(False), filename),
        "w",
        encoding="utf_8",
    ) as f:
        f.write(f"ErrorCode={code}\n")
        f.write(f"ErrorMessage={message}\n")
