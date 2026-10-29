from pathlib import Path

import pandas as pd

from rdetoolkit.types import OutputContext

def save_csv(df: pd.DataFrame, out: OutputContext, filename: str) -> Path: ...
def save_json(content: object, out: OutputContext, filename: str) -> Path: ...
