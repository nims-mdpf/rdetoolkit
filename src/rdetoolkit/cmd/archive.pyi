import pathlib
from _typeshed import Incomplete
from rdetoolkit.artifact.report import TemplateMarkdownReportGenerator as TemplateMarkdownReportGenerator, get_scanner as get_scanner
from rdetoolkit.impl.compressed_controller import get_artifact_archiver as get_artifact_archiver
from rdetoolkit.models.reports import CodeSnippet as CodeSnippet, ReportItem as ReportItem

class CreateArtifactCommand:
    MARK_SUCCESS: str
    MARK_WARNING: str
    MARK_ERROR: str
    MARK_INFO: str
    MARK_SCAN: str
    MARK_ARCHIVE: str
    source_dir: Incomplete
    output_archive_path: Incomplete
    exclude_patterns: Incomplete
    template_report_generator: Incomplete
    def __init__(self, source_dir: pathlib.Path, *, output_archive_path: pathlib.Path | None = None, exclude_patterns: list[str] | None = None) -> None: ...
    def invoke(self) -> None: ...
