import contextlib
import logging
import traceback
from collections.abc import Callable as Callable, Generator
from rdetoolkit.exceptions import StructuredError as StructuredError
from rdetoolkit.models.config import Config as Config
from typing import Any, Any as _Any

def catch_exception_with_message(*, error_message: str | None = None, error_code: int | None = None, eobj: Any | None = None, verbose: bool = False) -> Callable: ...
@contextlib.contextmanager
def skip_exception_context(exception_type: type[Exception], logger: logging.Logger | None = None, enabled: bool = False) -> Generator[dict[str, str | None], None, None]: ...
def format_simplified_traceback(tb_list: list[traceback.FrameSummary]) -> str: ...
def handle_exception(e: Exception, error_message: str | None = None, error_code: int | None = None, eobj: Any | None = None, verbose: bool = False, config: Config | None = None) -> StructuredError: ...
def handle_and_exit_on_structured_error(e: StructuredError, logger: logging.Logger, config: Config | None = None) -> None: ...
def handle_generic_error(e: Exception, logger: logging.Logger, config: Config | None = None) -> None: ...
def write_job_errorlog_file(code: int, message: str, *, filename: str = 'job.failed') -> None: ...

class RdeError(Exception):
    code: int | str
    name: str
    message: str
    detail: dict[str, _Any] | None
    def __init__(self, *, code: int | str, message: str, name: str | None = None, detail: dict[str, _Any] | None = None) -> None: ...
    def to_dict(self) -> dict[str, _Any]: ...

class RdeExecutionError(RdeError):
    call_id: str | None
    def __init__(
        self,
        *,
        code: int | str,
        message: str,
        name: str | None = None,
        detail: dict[str, _Any] | None = None,
        call_id: str | None = None,
    ) -> None: ...
class RdeConfigError(RdeError): ...

class ErrorDef:
    name: str
    message_template: str
    remediation: str
    retired: bool
    def __init__(self, name: str, message_template: str, remediation: str, retired: bool = False) -> None: ...

class WarningDef:
    name: str
    message_template: str
    def __init__(self, name: str, message_template: str) -> None: ...

ERROR_CATALOG: dict[int, ErrorDef]
WARNING_CATALOG: dict[int, WarningDef]

class RdeRegistryError(RdeError): ...
class RdeValidationError(RdeError): ...
class RdeInternalError(RdeError): ...

from rdetoolkit.config import get_traceback_settings_from_env as get_traceback_settings_from_env
from rdetoolkit.rde2util import StorageDir as StorageDir
from rdetoolkit.traceback.formatter import CompactTraceFormatter as CompactTraceFormatter

class ProcessingError(RdeExecutionError):
    code: int
    name: str
    message: str
    remediation: str
    def __init__(self, message: str, *, remediation: str | None = None) -> None: ...
    def to_dict(self) -> dict[str, _Any]: ...

def _catch_exception_with_message(*, error_message: str | None = None, error_code: int | None = None, eobj: Any | None = None, verbose: bool = False) -> Callable: ...
