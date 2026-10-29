from pathlib import Path

import pandas as pd
from typing_extensions import Protocol

from rdetoolkit.types import InputPaths, InvoiceData, Metadata, OutputContext

class FileReader(Protocol):
    def read(self, paths: InputPaths) -> tuple[Metadata, pd.DataFrame]: ...

class MetadataExtractor(Protocol):
    def extract(self, df: pd.DataFrame, invoice: InvoiceData) -> Metadata: ...

class DataProcessor(Protocol):
    def process(self, df: pd.DataFrame, meta: Metadata) -> pd.DataFrame: ...

class ResultWriter(Protocol):
    def write(self, df: pd.DataFrame, meta: Metadata, out: OutputContext) -> None: ...

class Visualizer(Protocol):
    def visualize(self, df: pd.DataFrame, out: OutputContext) -> list[Path]: ...

__all__: list[str]
