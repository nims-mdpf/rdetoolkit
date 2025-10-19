import pandas as pd
from pathlib import Path
from typing import Any, Protocol

__all__ = ['CSVParser', 'CSVParserProtocol']

class CSVParserProtocol(Protocol):
    def parse(self, csv_path: Path) -> pd.DataFrame: ...

class CSVParser:
    DEFAULT_MODE: str
    @staticmethod
    def parse(csv_path: str | Path) -> tuple[pd.DataFrame, dict[str, Any]]: ...
