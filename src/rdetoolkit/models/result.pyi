from _typeshed import Incomplete as Incomplete
from collections.abc import Iterator
from pydantic import BaseModel

class WorkflowExecutionStatus(BaseModel):
    run_id: str
    title: str
    status: str
    mode: str
    error_code: int | None
    error_message: str | None
    target: str | None
    stacktrace: str | None
    exception_object: Exception | None
    @classmethod
    def format_run_id(cls, v: str) -> str: ...

class WorkflowExecutionResults(BaseModel):
    statuses: list[WorkflowExecutionStatus]

class WorkflowResultManager:
    statuses: Incomplete
    def __init__(self) -> None: ...
    def add(self, run_id: str, title: str, status: str, mode: str, error_code: int | None = None, error_message: str | None = None, target: str | None = None, stacktrace: str | None = None) -> None: ...
    def add_status(self, status: WorkflowExecutionStatus) -> None: ...
    def __iter__(self) -> Iterator[WorkflowExecutionStatus]: ...
    def __len__(self) -> int: ...
    def __getitem__(self, index: int) -> WorkflowExecutionStatus: ...
    def to_json(self) -> str: ...
