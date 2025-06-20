import pathlib
from _typeshed import Incomplete as Incomplete

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
