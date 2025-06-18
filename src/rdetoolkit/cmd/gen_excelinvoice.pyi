import pathlib
from _typeshed import Incomplete as Incomplete
from typing import Literal

logger: Incomplete

class GenerateExcelInvoiceCommand:
    invoice_schema_file: Incomplete
    output_path: Incomplete
    mode: Incomplete
    def __init__(self, invoice_schema_file: pathlib.Path, output_path: pathlib.Path, mode: Literal['file', 'folder']) -> None: ...
    def invoke(self) -> None: ...
