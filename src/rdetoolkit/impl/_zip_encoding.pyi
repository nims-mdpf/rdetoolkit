import logging
import zipfile
from pathlib import Path
from typing import Final

logger: logging.Logger
LANG_ENC_FLAG: Final[int]
FALLBACK_ENCODING: Final[str]
PREFERRED_ENCODING: Final[str]

def resolve_filename(zip_info: zipfile.ZipInfo) -> str: ...
def extract_zip_with_encoding(zip_path: Path | str, extract_path: Path | str) -> None: ...
