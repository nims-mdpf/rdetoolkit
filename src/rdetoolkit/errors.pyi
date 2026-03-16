import contextlib
import enum
import logging
import traceback
from _typeshed import Incomplete
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

class ErrorCode(enum.Enum):
    E001 = 'E001'
    E002 = 'E002'
    E003 = 'E003'
    E004 = 'E004'
    E005 = 'E005'
    E006 = 'E006'
    E007 = 'E007'
    E008 = 'E008'
    E009 = 'E009'
    E010 = 'E010'
    E011 = 'E011'
    E012 = 'E012'
    E013 = 'E013'
    E014 = 'E014'
    E015 = 'E015'
    E016 = 'E016'
    E017 = 'E017'
    E018 = 'E018'
    E019 = 'E019'
    E020 = 'E020'
    E021 = 'E021'
    E022 = 'E022'
    E023 = 'E023'
    E024 = 'E024'
    E025 = 'E025'

class RdeError(Exception):
    code: Incomplete
    message: Incomplete
    detail: Incomplete
    def __init__(self, *, code: str, message: str, detail: dict[str, _Any] | None = None) -> None: ...
    def to_dict(self) -> dict[str, _Any]: ...

class RdeGraphError(RdeError): ...
class RdeCompileError(RdeError): ...
class RdeExecutionError(RdeError): ...
class RdeConfigError(RdeError): ...
class RdeIOError(RdeError): ...

class UnconnectedInputError(RdeExecutionError):
    node_id: str
    param_name: str
    def __init__(self, node_id: str, param_name: str) -> None: ...
