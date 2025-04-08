from __future__ import annotations

from pydantic import BaseModel


class CodeSnippet(BaseModel):
    file_path: str
    snippet: str
    description: str | None = None


class ReportItem(BaseModel):
    exec_date: str
    dockerfile_path: str
    requirements_path: str
    include_dirs: list[str]
    code_security_scan_results: list[CodeSnippet]
    code_ext_requests_scan_results: list[CodeSnippet]
