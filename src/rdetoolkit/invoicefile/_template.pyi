import pandas as pd
from _typeshed import Incomplete
from collections.abc import Mapping
from typing import Protocol, TypeAlias
from rdetoolkit.models.invoice import (
    FixedHeaders,
    GeneralAttributeConfig,
    SpecificAttributeConfig,
    TemplateConfig,
)

AttributeConfig: TypeAlias = GeneralAttributeConfig | SpecificAttributeConfig

class TemplateGenerator(Protocol):
    def generate(self, config: TemplateConfig) -> pd.DataFrame: ...

class ExcelInvoiceTemplateGenerator:
    GENERAL_PREFIX: str
    SPECIFIC_PREFIX: str
    CUSTOM_PREFIX: str
    fixed_header: Incomplete
    def __init__(self, fixed_header: FixedHeaders) -> None: ...
    def generate(self, config: TemplateConfig) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]: ...
    def save(self, dataframes: Mapping[str, pd.DataFrame], save_path: str) -> None: ...
