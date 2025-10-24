import pandas as pd
from pathlib import Path

class NoHeaderParser:
    def parse(self, csv_path: Path) -> pd.DataFrame: ...
