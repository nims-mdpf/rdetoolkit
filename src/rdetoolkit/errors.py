from __future__ import annotations

import contextlib
import logging
import os
import sys
import traceback
from collections.abc import Generator
from functools import wraps
from typing import TYPE_CHECKING, Any
from collections.abc import Callable

from rdetoolkit.exceptions import StructuredError

if TYPE_CHECKING:
    from rdetoolkit.models.config import Config


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


def _generate_python_traceback(e: Exception, verbose: bool = False, custom_error_message: str | None = None) -> str:
    """Generate Python-style traceback.

    Args:
        e: The exception.
        verbose: Whether to include full traceback.
        custom_error_message: Custom error message to use instead of exception message.

    Returns:
        Formatted traceback string.
    """
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
    error_messages = [
        "\nTraceback (simplified message):\n",
        f"Call Path:\n{simplifed_traceback}\n",
        f"\nException Type: {exc_type_name}\n",
        f"Error: {custom_error_message or str(e)}",
    ]

    if verbose:
        original_traceback = traceback.format_exc()
        error_msg = f"{original_traceback}\n\n{'=' * 60}\nCustom Traceback (simplified and more readable):\n{'=' * 60}\n"
        sys.stderr.write(error_msg)

    return "".join(error_messages)


def handle_exception(
    e: Exception,
    error_message: str | None = None,
    error_code: int | None = None,
    eobj: Any | None = None,
    verbose: bool = False,
    config: Config | None = None,
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
        config (Config | None): Optional configuration object whose ``traceback`` attribute (``TracebackSettings``)
                    determines how traceback text is produced when ``e.traceback_info`` is missing.
                    If None, traceback settings are resolved from environment variables (fallback behavior).

    Returns:
        StructuredError: A structured error object containing the error message, error code, additional object,
        and simplified traceback information.
    """
    _message = f"Error: {error_message}" if error_message else f"Error: {str(e)}"
    _code = error_code if error_code else 1

    from rdetoolkit.config import get_traceback_settings_from_env
    from rdetoolkit.traceback.formatter import CompactTraceFormatter

    traceback_settings = config.traceback if (config and config.traceback) else get_traceback_settings_from_env()

    if traceback_settings and traceback_settings.enabled:
        formatter = CompactTraceFormatter(traceback_settings)
        compact_trace = formatter.format(e)

        if traceback_settings.format == "compact":
            traceback_info = compact_trace
        elif traceback_settings.format == "python":
            traceback_info = _generate_python_traceback(e, verbose, error_message)
        else:
            traceback_info = f"{compact_trace}\n{_generate_python_traceback(e, verbose, error_message)}"

        return StructuredError(emsg=_message, ecode=_code, eobj=eobj,
                                traceback_info=traceback_info)
    # Always generate traceback for backward compatibility
    traceback_info = _generate_python_traceback(e, verbose, error_message)
    return StructuredError(emsg=_message, ecode=_code, eobj=eobj, traceback_info=traceback_info)


def handle_and_exit_on_structured_error(e: StructuredError, logger: logging.Logger, config: Config | None = None) -> None:
    """Catch StructuredError and write to log file.

    Args:
        e (StructuredError): StructuredError instance
        logger (logging.Logger): Logger instance
        config (Config | None): Optional configuration object whose ``traceback`` attribute (``TracebackSettings``)
                   determines how traceback text is produced when ``e.traceback_info`` is missing.
                   If None, traceback settings are resolved from environment variables (fallback behavior)
    """
    if e.traceback_info is not None:
        sys.stderr.write(e.traceback_info + "\n")
    else:
        structured_error = handle_exception(e, verbose=True, config=config)
        sys.stderr.write((structured_error.traceback_info or "") + "\n")

    write_job_errorlog_file(e.ecode, e.emsg)
    logger.exception(e.emsg)
    sys.exit(1)


def handle_generic_error(e: Exception, logger: logging.Logger, config: Config | None = None) -> None:
    """Catch a generic (non-StructuredError) exception, emit a formatted traceback, log it, and exit.

    This helper:
        1. Formats the exception into a structured traceback (compact or python style depending on settings).
        2. Writes the formatted traceback to stderr.
        3. Writes a generic job error file with a fixed error code (999) to assist external supervisors.
        4. Logs the exception (including stack trace) via the provided logger.
        5. Exits the process with status code 1.

    Args:
        e (Exception): The caught exception instance.
        logger (logging.Logger): Logger used to record the exception (`logger.exception` is invoked so a stack trace is included).
        config (Config | None): Optional configuration object. If provided and it contains traceback settings,
            those settings control whether a compact traceback, a standard Python traceback, or both are generated.
            If omitted, traceback settings are resolved from the environment (see `get_traceback_settings_from_env`).

    Side Effects:
        - Writes structured traceback text to stderr.
        - Creates/overwrites an error marker file via `write_job_errorlog_file` (default filename: job.failed) with code=999.
        - Emits an ERROR-level log entry with stack trace.
        - Terminates the interpreter with `sys.exit(1)`.

    Returns:
        None. (The function does not return; it terminates the process.)

    """
    structured_error = handle_exception(e, verbose=True, config=config)
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
    from rdetoolkit.rde2util import StorageDir

    _write_job_failed_marker(os.path.join(StorageDir.get_datadir(False), filename), code, message)


def _write_job_failed_marker(path: str | os.PathLike[str], code: int, message: str) -> None:
    """Write the RDE job-failure marker to an explicit destination.

    The format is exactly two newline-terminated UTF-8 lines,
    ``ErrorCode=<code>`` and ``ErrorMessage=<message>``. The text-mode
    ``open`` call is v1's own, so the bytes (including newline translation)
    match what ``write_job_errorlog_file`` has always produced. Callers own
    the destination: the v2 finalizer passes ``<data_root>/job.failed``, and
    the v1 wrapper passes its legacy ``StorageDir`` location.

    Args:
        path: Marker file to create or overwrite; its parent must exist.
        code: Integer error code.
        message: Error message text.
    """
    with open(path, "w", encoding="utf_8") as f:
        f.write(f"ErrorCode={code}\n")
        f.write(f"ErrorMessage={message}\n")


# ---------------------------------------------------------------------------
# v2 Error Hierarchy (Design §9.2)
# ---------------------------------------------------------------------------
# The pre-GA draft taxonomy (string ``ErrorCode`` E001-E025, ``RdeGraphError``,
# ``RdeCompileError``, ``RdeIOError``, ``UnconnectedInputError`` and the
# ``E_CYCLE``-style constants) belonged to the retired Trace/Compile design and
# was removed before GA (issue #646). It never shipped in a v1 release. Those
# identifiers must never be reintroduced with a new meaning.

from typing import Any as _Any


class RdeError(Exception):
    """Base exception for rdetoolkit v2.

    The canonical form carries an int ``code`` from ``ERROR_CATALOG`` and its
    stable ``name``. A string ``code`` is still accepted at runtime (pre-GA
    tolerance); its display name then defaults to the code itself.

    Args:
        code: Catalogued int error code (e.g. ``3001``).
        message: Human-readable error description.
        name: Stable error name. Defaults to the catalog name for a catalogued
            int code, ``E{code}`` for an uncatalogued int code, or the code
            itself for a string code.
        detail: Optional structured context about the error.

    Attributes:
        code: The error code as passed.
        name: The resolved stable error name.
        message: Human-readable error description.
        detail: Optional structured context, or None.
    """

    code: int | str
    name: str
    message: str
    detail: dict[str, _Any] | None

    def __init__(
        self,
        *,
        code: int | str,
        message: str,
        name: str | None = None,
        detail: dict[str, _Any] | None = None,
    ) -> None:
        error_name = _coerce_error_name(code, name)
        self.code = code
        self.name = error_name
        self.message = message
        self.detail = detail
        super().__init__(f"[{error_name}] {message}")

    def to_dict(self) -> dict[str, _Any]:
        """Serialize the error to a dictionary.

        Returns:
            Dictionary with ``code``, ``name`` and ``message``, plus ``detail``
            when it is not None.
        """
        error_dict: dict[str, _Any] = {"code": self.code, "name": self.name, "message": self.message}
        if self.detail is not None:
            error_dict["detail"] = self.detail
        return error_dict


class RdeExecutionError(RdeError):
    """Execution error for v2 3xxx codes.

    Preserves the Python ``__cause__`` chain when raised with ``from``.

    Args:
        code: Catalogued int error code (e.g. ``3001``).
        message: Human-readable error description.
        name: Stable error name; see ``RdeError``.
        detail: Optional structured context about the error.
        call_id: Call-log identifier of the failing node call, if any.

    Attributes:
        call_id: Call-log identifier of the failing node call, or None.
    """

    call_id: str | None

    def __init__(
        self,
        *,
        code: int | str,
        message: str,
        name: str | None = None,
        detail: dict[str, _Any] | None = None,
        call_id: str | None = None,
    ) -> None:
        self.call_id = call_id
        super().__init__(code=code, name=name, message=message, detail=detail)


class RdeConfigError(RdeError):
    """Configuration or usage error for v2 1xxx codes."""


def _coerce_error_name(code: int | str, name: str | None) -> str:
    if name is not None:
        return name
    if isinstance(code, int):
        catalog_entry = ERROR_CATALOG.get(code)
        if catalog_entry is not None:
            return catalog_entry.name
        return f"E{code}"
    return code


# ---------------------------------------------------------------------------
# v2 Unified Error Catalog (Design §9, append-only A1 additions)
# ---------------------------------------------------------------------------

from dataclasses import dataclass as _dataclass

def get_traceback_settings_from_env() -> _Any:
    """Return traceback settings resolved from environment variables.

    Returns:
        Traceback settings from `rdetoolkit.config.get_traceback_settings_from_env`.
    """
    from rdetoolkit.config import get_traceback_settings_from_env as _get_traceback_settings_from_env

    return _get_traceback_settings_from_env()


class CompactTraceFormatter:
    """Lazy compatibility proxy for the compact traceback formatter.

    Importing the real formatter requires optional runtime dependencies. This
    proxy keeps the restored `rdetoolkit.errors` export importable and forwards
    construction to the real formatter when used.
    """

    def __new__(cls, *args: _Any, **kwargs: _Any) -> _Any:
        """Create the real compact traceback formatter.

        Args:
            *args: Positional arguments forwarded to the real formatter.
            **kwargs: Keyword arguments forwarded to the real formatter.

        Returns:
            A `rdetoolkit.traceback.formatter.CompactTraceFormatter` instance.
        """
        from rdetoolkit.traceback.formatter import CompactTraceFormatter as _CompactTraceFormatter

        return _CompactTraceFormatter(*args, **kwargs)


class _StorageDirProxyMeta(type):
    def __getattr__(cls, name: str) -> _Any:
        from rdetoolkit.rde2util import StorageDir as _StorageDir

        return getattr(_StorageDir, name)


class _StorageDirProxy(metaclass=_StorageDirProxyMeta):
    """Lazy compatibility proxy for `rdetoolkit.rde2util.StorageDir`."""


globals()["StorageDir"] = _StorageDirProxy


@_dataclass(frozen=True)
class ErrorDef:
    """Single catalog entry for a v2 error code.

    Args:
        name: Human-readable stable error name.
        message_template: Message template used by callers when formatting errors.
        remediation: Researcher-facing guidance on how to fix the error (R9:
            required, never empty; rendered in error messages and generated docs).
        retired: True when the number is permanently retired (R1). Retired
            numbers must never be reused for a different meaning.
    """

    name: str
    message_template: str
    remediation: str
    retired: bool = False


@_dataclass(frozen=True)
class WarningDef:
    """Single catalog entry for a v2 warning code.

    Args:
        name: Human-readable stable warning name.
        message_template: Message template used by callers when formatting warnings.
    """

    name: str
    message_template: str


ERROR_CATALOG: dict[int, ErrorDef] = {
    1001: ErrorDef(
        name="RunArgumentUsageError",
        message_template="Specify exactly one of flow or custom_dataset_function.",
        remediation="Call run() with exactly one entry point: run(flow=...) for v2 pipelines or run(custom_dataset_function=...) for v1 workflows.",
    ),
    1002: ErrorDef(
        name="ConfigLoadFailed",
        message_template="Failed to load RDE configuration: {reason}",
        remediation="Fix the reported issue in rdeconfig.yaml (or [tool.rdetoolkit] in pyproject.toml). Unknown keys are rejected: check for typos and remove settings this version does not support.",
    ),
    2001: ErrorDef(
        name="DuplicateNodeId",
        message_template="Duplicate node id registered: {node_id}",
        remediation="Rename one of the functions or move it to another module (the node id is '{module}.{qualname}'), or pass an explicit id via @node(id=...).",
    ),
    2002: ErrorDef(
        name="ReservedParamMismatch",
        message_template="Reserved flow parameter has an incompatible type: {param_name}",
        remediation="Retired by design revision R1: DI is type-based and parameter names are advisory only, so a name mismatch is no longer an error. This number must not be reused.",
        retired=True,
    ),
    2003: ErrorDef(
        name="UnresolvableFlowParam",
        message_template="Could not resolve flow parameter: {param_name}",
        remediation="Annotate the parameter with one of the reserved types (InputPaths, OutputContext, RdeConfig, InvoiceData, IterationInfo) or give it a default value.",
    ),
    3001: ErrorDef(
        name="NodeExecutionFailed",
        message_template="Node execution failed for call {call_id}: {reason}",
        remediation="Inspect the chained original exception (__cause__) and the call-log entry for the failing call; fix the node implementation or its inputs. Nodes are plain functions - reproduce directly with pytest.",
    ),
    3002: ErrorDef(
        name="NodeTypeMismatch",
        message_template="Node argument type mismatch for {node_id}.{param_name}",
        remediation="Pass a value matching the node's type annotation, or adjust the annotation. Set execution.type_check to 'off' or 'warn' if strict checking is not desired.",
    ),
    3003: ErrorDef(
        name="UndecoratedNodeCall",
        message_template="Undecorated callable cannot be recorded as a node: {callable_name}",
        remediation="Decorate the callable with @node, or call it as a plain helper (plain calls work but are not recorded in the call log).",
    ),
    4001: ErrorDef(
        name="InvoiceSchemaInvalid",
        message_template="Invoice schema validation failed: {reason}",
        remediation="Fix invoice.schema.json (or the generated invoice.json) so it validates; the reported reason names the failing keyword and path.",
    ),
    4002: ErrorDef(
        name="MetadataDefinitionInvalid",
        message_template="Metadata definition validation failed: {reason}",
        remediation="Fix metadata-def.json to satisfy the metadata definition schema; the reported reason names the offending field.",
    ),
    4003: ErrorDef(
        name="RequiredArtifactMissing",
        message_template="Required output artifact is missing: {path}",
        remediation="Ensure the flow writes the artifact before finalize (use the save nodes in rdetoolkit.nodes); check that the reported path is produced in the expected output directory.",
    ),
    5001: ErrorDef(
        name="InternalInvariantViolation",
        message_template="Internal rdetoolkit invariant failed: {reason}",
        remediation="This is a bug in rdetoolkit, not in user code. Please report it together with the run report and the stack trace.",
    ),
    2006: ErrorDef(
        name="DuplicateReservedTypeAnnotation",
        message_template="Reserved type {type_name} is annotated on more than one flow parameter: {param_names}",
        remediation="A flow signature may declare each reserved type at most once; merge the duplicated parameters into one.",
    ),
    2005: ErrorDef(
        name="UnstableNodeId",
        message_template="Node id is unstable because it is derived from a local function qualname: {node_id}",
        remediation="Move the node function to module scope or pass a stable explicit id via @node(id=...).",
    ),
    # --- Template errors (R6): catalog reserved here; raised from Phase F ---
    2101: ErrorDef(
        name="TemplateSlotMissing",
        message_template="Template slot is not implemented: {slot_name}",
        remediation="Implement the required slot method declared by the template; 'rdetoolkit nodes lint' lists missing slots.",
    ),
    2102: ErrorDef(
        name="TemplateSlotSignatureMismatch",
        message_template="Template slot signature mismatch: {slot_name}",
        remediation="Match the slot's declared signature (parameter names and type annotations); see 'rdetoolkit templates describe <name>'.",
    ),
    2103: ErrorDef(
        name="TemplateFinalOverride",
        message_template="Template skeleton method must not be overridden: {method_name}",
        remediation="Implement only the declared slots and hooks; if you need a different pipeline shape, write a plain @flow instead.",
    ),
    2104: ErrorDef(
        name="TemplateDeepInheritance",
        message_template="Template subclass must not be inherited further: {class_name}",
        remediation="Inherit directly from the provider's template class (one level only); compose behavior via slots/hooks or a plain @flow.",
    ),
    2105: ErrorDef(
        name="TemplateCtorNotDefault",
        message_template="Template class must be constructible with no arguments: {class_name}",
        remediation="Remove required __init__ parameters; receive parameters via config.custom instead.",
    ),
    # --- rdetoolkit-nb marker/slot errors (band reservation only, name/message
    #     drafted by the Phase D dispatch decomposition from
    #     local/develop/v2/editor/05_計画評価_20260707.md §2.1/2.5/2.6 - not yet a
    #     ratified nb design; correct via retired=True + new number if wrong,
    #     never edit in place): raised from a future nb session, not Phase D ---
    2201: ErrorDef(
        name="MarkerFormatInvalid",
        message_template="Notebook marker line does not match the canonical `# rde:` format: {line}",
        remediation="Insert a single space after 'rde:' (e.g. '# rde: slot=read'); if the line is not meant to be a marker, remove the 'rde:' prefix.",
    ),
    2208: ErrorDef(
        name="RequiredSlotMissing",
        message_template="Notebook does not implement required slot: {slot_name}",
        remediation="Add a cell marked '# rde: slot={slot_name}' implementing the required slot.",
    ),
    2211: ErrorDef(
        name="NotebookUnreadable",
        message_template="Notebook file could not be read: {reason}",
        remediation="Open the notebook in Jupyter and re-save it; notebooks below nbformat 4 are not supported.",
    ),
    2212: ErrorDef(
        name="NoMarkersFound",
        message_template="No `# rde:` markers were found in the notebook",
        remediation="Add at least one '# rde: slot=<name>' marker cell, or check for a typo in the marker prefix.",
    ),
    # E2201-E2299 reserved for rdetoolkit-nb (see local/develop/v2/editor/05_計画評価_20260707.md §2.5);
    # allocate further codes only when the nb design session defines them.
}

WARNING_CATALOG: dict[int, WarningDef] = {
    1001: WarningDef(
        name="ModeOverriddenByFileDetection",
        message_template="Configured mode was overridden by input file detection: {mode}",
    ),
    1002: WarningDef(
        name="EventsLogTruncated",
        message_template="events log truncated at the size cap; node-level events are no longer recorded for this run",
    ),
    1101: WarningDef(
        name="TemplateSelfStateUsage",
        message_template="Template slot or hook uses hidden self state: {qualified_name}.{attribute_name}",
    ),
}

ERROR_CATALOG[3004] = ErrorDef(
    name="RunInterrupted",
    message_template="The run was interrupted by an external termination signal.",
    remediation=(
        "Review partial results in data/logs/iterations/, then rerun the workflow "
        "to complete the interrupted processing."
    ),
)


class RdeRegistryError(RdeError):
    """Registration or declaration error for v2 2xxx codes."""


class RdeValidationError(RdeError):
    """Validation error for v2 4xxx codes."""


class RdeInternalError(RdeError):
    """Internal rdetoolkit error for v2 5xxx codes."""


ERROR_CATALOG[3005] = ErrorDef(
    name="ArtifactPublicationFailed",
    message_template="Publishing tile artifacts failed after the flow completed: {reason}",
    remediation=(
        "The flow itself succeeded; the failure is in the rdetoolkit output stage. "
        "Check free space and write permissions for the data/ output directories "
        "(raw, nonshared_raw, thumbnail, structured, invoice), then rerun."
    ),
)


ERROR_CATALOG[3006] = ErrorDef(
    name="InvoiceArtifactFailed",
    message_template="Applying the configured invoice artifact steps failed: {reason}",
    remediation=(
        "The flow itself succeeded; the failure is in the rdetoolkit invoice output stage "
        "(structured copy, magic variable, or description update). Check that "
        "data/invoice/invoice.json and the tasksupport schema are readable and consistent "
        "with the enabled system.* settings, then rerun."
    ),
)


ERROR_CATALOG[4004] = ErrorDef(
    name="EmptyExcelInvoice",
    message_template="The Excel invoice has no data rows.",
    remediation="Add at least one data row to the Excel invoice, then rerun.",
)


ERROR_CATALOG[1003] = ErrorDef(
    name="InvalidTestInputPath",
    message_template="Test input file must name a file inside inputdata: {path}",
    remediation=(
        "Pass relative file names to make_input_paths(files=...). Avoid absolute paths, "
        "directories, parent paths escaping inputdata, and symlinks pointing outside the input tree."
    ),
)


ERROR_CATALOG[1004] = ErrorDef(
    name="InvalidMetadataMatchMode",
    message_template="Unsupported metadata source matching mode: {mode}",
    remediation="Pass match='key', match='original_name' or match='both' to build_meta().",
)
