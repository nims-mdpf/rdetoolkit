import pandas as pd
from pathlib import Path

class TransposeParser:
    def parse(self, csv_path: Path) -> pd.DataFrame: ...
