import polars as pl
from _typeshed import Incomplete as Incomplete
from dataclasses import dataclass
from pathlib import Path
from pydantic import BaseModel
from rdetoolkit.models.invoice_schema import GeneralAttribute as GeneralAttribute, SpecificAttribute as SpecificAttribute
from typing import Any, Literal

class HeaderRow1(BaseModel):
    A1: str

class HeaderRow2(BaseModel):
    A2: str
    D2_G2: list[str]
    H2_M2: list[str]

class HeaderRow3(BaseModel):
    A3: str
    B3: str
    C3: str
    D3: str
    E3: str
    F3: str
    G3: str
    H3: str
    I3: str
    J3: str
    K3: str
    L3: str
    M3: str

class HeaderRow4(BaseModel):
    A4: str
    B4: str
    C4: str
    D4: str
    E4: str
    F4: str
    G4: str
    H4: str
    I4: str
    J4: str
    K4: str
    L4: str
    M4: str

class FixedHeaders(BaseModel):
    row1: HeaderRow1
    row2: HeaderRow2
    row3: HeaderRow3
    row4: HeaderRow4
    def to_template_dataframe(self) -> pl.DataFrame: ...

@dataclass
class TemplateConfig:
    schema_path: str | Path
    general_term_path: str | Path
    specific_term_path: str | Path
    inputfile_mode: Literal['file', 'folder'] = ...
    def __init__(self, schema_path, general_term_path, specific_term_path, inputfile_mode=...) -> None: ...

class BaseTermRegistry:
    base_schema: Incomplete

class GeneralTermRegistry(BaseTermRegistry):
    df: Incomplete
    def __init__(self, csv_path: str) -> None: ...
    def search(self, column: str, value: str, out_cols: list[str]) -> list[dict[str, Any]]: ...
    def by_term_id(self, term_id: str) -> list[dict[str, Any]]: ...
    def by_ja(self, ja_text: str) -> list[dict[str, Any]]: ...
    def by_en(self, en_text: str) -> list[dict[str, Any]]: ...

class SpecificTermRegistry(BaseTermRegistry):
    df: Incomplete
    def __init__(self, csv_path: str) -> None: ...
    def search(self, columns: list[str], values: list[str], out_cols: list[str]) -> list[dict[str, Any]]: ...
    def by_term_and_class_id(self, term_id: str, sample_class_id: str) -> list[dict[str, Any]]: ...
    def by_key_name(self, key_name: list[str]) -> list[dict[str, Any]]: ...
    def by_ja(self, ja_text: list[str]) -> list[dict[str, Any]]: ...
    def by_en(self, en_text: list[str]) -> list[dict[str, Any]]: ...

@dataclass
class GeneralAttributeConfig:
    type: str
    registry: GeneralTermRegistry
    prefix: str
    attributes: GeneralAttribute | None
    requires_class_id: Literal[False]
    def __init__(self, type, registry, prefix, attributes, requires_class_id) -> None: ...

@dataclass
class SpecificAttributeConfig:
    type: str
    registry: SpecificTermRegistry
    prefix: str
    attributes: SpecificAttribute | None
    requires_class_id: Literal[True]
    def __init__(self, type, registry, prefix, attributes, requires_class_id) -> None: ...
