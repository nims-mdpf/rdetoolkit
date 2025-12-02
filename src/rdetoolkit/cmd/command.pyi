import click
from _typeshed import Incomplete as Incomplete
from pathlib import Path
from rdetoolkit import __version__ as __version__
from rdetoolkit.cmd.default import INVOICE_JSON as INVOICE_JSON, PROPERTIES
from rdetoolkit.models.invoice_schema import InvoiceSchemaJson as InvoiceSchemaJson, Properties as Properties
from rdetoolkit.rdelogger import get_logger as get_logger
from typing import Any

logger: Incomplete

class Command(click.Command):
    def __init__(self, name: str, **attrs: Any) -> None: ...

class InitTemplateError(Exception): ...

class InitTemplateConfig:
    entry_point: Path | None
    modules: Path | None
    tasksupport: Path | None
    inputdata: Path | None
    other: list[Path] | None
    def has_templates(self) -> bool: ...

class InitTemplateLoader:
    SUPPORTED_FILENAMES: Incomplete
    template_path: Path
    def __init__(self, template_path: Path) -> None: ...
    def load(self) -> InitTemplateConfig: ...

class InitCommand:
    default_dirs: Incomplete
    template_path: Path | None
    def __init__(self, template_path: Path | None = ..., cli_template_config: InitTemplateConfig | None = ...) -> None: ...
    def invoke(self) -> None: ...

class VersionCommand:
    def invoke(self) -> None: ...

class DockerfileGenerator:
    path: Incomplete
    def __init__(self, path: str | Path = 'Dockerfile') -> None: ...
    def generate(self) -> list[str]: ...

class RequirementsTxtGenerator:
    path: Incomplete
    def __init__(self, path: str | Path = 'requirements.txt') -> None: ...
    def generate(self) -> list[str]: ...

class InvoiceSchemaJsonGenerator:
    path: Incomplete
    def __init__(self, path: str | Path = 'invoice.schema.json') -> None: ...
    def generate(self) -> dict[str, Any]: ...

class MetadataDefJsonGenerator:
    path: Incomplete
    def __init__(self, path: str | Path = 'metadata-def.json') -> None: ...
    def generate(self) -> dict[str, Any]: ...

class InvoiceJsonGenerator:
    path: Incomplete
    def __init__(self, path: str | Path = 'invoice.json') -> None: ...
    def generate(self) -> dict[str, Any]: ...

class MainScriptGenerator:
    path: Incomplete
    def __init__(self, path: str | Path) -> None: ...
    def generate(self) -> list[str]: ...
