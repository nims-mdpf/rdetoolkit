from pathlib import Path
from rdetoolkit.impl.input_controller import ExcelInvoiceChecker as ExcelInvoiceChecker, InvoiceChecker as InvoiceChecker, MultiFileChecker as MultiFileChecker, RDEFormatChecker as RDEFormatChecker, SmartTableChecker as SmartTableChecker
from rdetoolkit.interfaces.filechecker import IInputFileChecker as IInputFileChecker
from rdetoolkit.models.config import Config as Config
from rdetoolkit.models.rde2types import RdeInputDirPaths as RdeInputDirPaths

def selected_input_checker(src_paths: RdeInputDirPaths, unpacked_dir_path: Path, mode: str | None, config: Config | None = None) -> IInputFileChecker: ...
