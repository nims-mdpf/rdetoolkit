from __future__ import annotations

from collections.abc import Iterator

from pydantic import BaseModel, Field, field_validator, ConfigDict


class WorkflowExecutionStatus(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    run_id: str
    title: str
    status: str
    mode: str
    error_code: int | None = Field(default=None)
    error_message: str | None = Field(default=None)
    target: str | None
    stacktrace: str | None = Field(default=None)
    exception_object: Exception | None = Field(default=None, exclude=True)  # Store original exception, excluded from JSON serialization

    @field_validator("run_id")
    @classmethod
    def format_run_id(cls, v: str) -> str:  # noqa: D102
        return f"{int(v):04d}"


class WorkflowExecutionResults(BaseModel):
    statuses: list[WorkflowExecutionStatus]


class WorkflowResultManager:

    def __init__(self) -> None:
        self.statuses = WorkflowExecutionResults(statuses=[])

    def add(self, run_id: str, title: str, status: str, mode: str, error_code: int | None = None, error_message: str | None = None, target: str | None = None, stacktrace: str | None = None, exception_object: Exception | None = None) -> None:
        """Adds a new workflow execution status to the statuses list.

        Args:
            run_id (int): The unique identifier for the run.
            title (str): The title of the workflow execution.
            status (str): The current status of the workflow execution.
            mode (str): Process Mode.
            error_code (int, optional): The error code associated with the workflow execution, if any. Defaults to None.
            error_message (str, optional): The error message associated with the workflow execution, if any. Defaults to None.
            target (str, optional): target directory path, if any. Defaults to None.
            stacktrace (str, optional): The stack trace of the error, if any. Defaults to None.
            exception_object (Exception, optional): The original exception object, if any. Defaults to None.

        Returns:
            None

        """
        execution_status = WorkflowExecutionStatus(
            run_id=run_id,
            title=title,
            status=status,
            mode=mode,
            error_code=error_code,
            error_message=error_message,
            target=target,
            stacktrace=stacktrace,
            exception_object=exception_object,
        )
        self.statuses.statuses.append(execution_status)

    def add_status(self, status: WorkflowExecutionStatus) -> None:
        """Adds an existing WorkflowExecutionStatus object to the statuses list.

        Args:
            status (WorkflowExecutionStatus): The WorkflowExecutionStatus object to add.

        Returns:
            None
        """
        self.statuses.statuses.append(status)

    def __iter__(self) -> Iterator[WorkflowExecutionStatus]:
        return iter(self.statuses.statuses)

    def __len__(self) -> int:
        return len(self.statuses.statuses)

    def __getitem__(self, index: int) -> WorkflowExecutionStatus:
        return self.statuses.statuses[index]

    def __repr__(self) -> str:
        return f"WorkflowResultManager({self.statuses})"

    def to_json(self) -> str:
        """Return the JSON representation of the workflow execution results."""
        return self.statuses.model_dump_json(indent=2)
