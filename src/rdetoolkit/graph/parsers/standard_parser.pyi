import pandas as pd
from pathlib import Path

class StandardParser:
    def parse(self, csv_path: Path) -> pd.DataFrame: ...
