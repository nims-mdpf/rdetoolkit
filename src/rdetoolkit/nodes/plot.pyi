from pathlib import Path
from collections.abc import Sequence
from matplotlib.figure import Figure

import pandas as pd

from rdetoolkit.types import OutputContext, OutputKind

LinePair = tuple[str, str] | tuple[str, str, str]

def plot_lines(df: pd.DataFrame, out: OutputContext, filename: str, *, x: str | None = None, y: str | Sequence[str] | None = None, pairs: Sequence[LinePair] | None = None, labels: Sequence[str] | None = None, title: str | None = None, xlabel: str | None = None, ylabel: str | None = None, yscale: str = "linear", legend: bool = True, grid: bool = False, label_fontsize: float | str | None = None, figsize: tuple[float, float] | None = None, dpi: float = 150, bbox_inches: str | None = "tight", pad_inches: float | None = None, kind: OutputKind = "main_image") -> Path: ...
def save_figure(fig: Figure, out: OutputContext, filename: str, *, kind: OutputKind = "main_image", dpi: float = 150, bbox_inches: str | None = "tight", pad_inches: float | None = None) -> Path: ...
def plot_scatter(df: pd.DataFrame, out: OutputContext, filename: str, x: str, y: str) -> Path: ...
