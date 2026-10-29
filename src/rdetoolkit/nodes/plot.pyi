from pathlib import Path

import pandas as pd

from rdetoolkit.types import OutputContext

def plot_lines(df: pd.DataFrame, out: OutputContext, filename: str) -> Path: ...
def plot_scatter(df: pd.DataFrame, out: OutputContext, filename: str, x: str, y: str) -> Path: ...
