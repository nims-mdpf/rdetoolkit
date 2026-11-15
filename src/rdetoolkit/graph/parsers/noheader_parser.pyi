import pandas as pd
from pathlib import Path

class NoHeaderParser:
    encoding: str | None
    delimiter: str | None
    def __init__(self, *, encoding: str | None = None, delimiter: str | None = None) -> None: ...
    def parse(self, csv_path: Path) -> pd.DataFrame: ...
