from _typeshed import Incomplete
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal

class PlotMode(str, Enum):
    OVERLAY = 'overlay'
    INDIVIDUAL = 'individual'
    DUAL_AXIS = 'dual_axis'

class CSVFormat(str, Enum):
    META_BLOCK = 'meta_block'
    SINGLE_HEADER = 'single_header'
    NO_HEADER = 'no_header'

class Direction(str, Enum):
    CHARGE = 'Charge'
    DISCHARGE = 'Discharge'
    REST = 'Rest'

@dataclass
class AxisConfig:
    label: str
    unit: str | None = ...
    scale: Literal['linear', 'log'] = ...
    grid: bool = ...
    invert: bool = ...
    lim: tuple[float, float] | None = ...

@dataclass
class LegendConfig:
    max_items: int | None = ...
    info: str | None = ...
    loc: str | int | Literal['best'] | None = ...

@dataclass
class DirectionConfig:
    column: str | None = ...
    filters: list[Direction | str] = field(default_factory=list)
    colors: dict[Direction | str, str] = field(default_factory=Incomplete)
    use_custom_colors: bool = ...

@dataclass
class RenderResult:
    figure: Any
    filename: str
    format: str

@dataclass
class OutputConfig:
    main_image_dir: Path | None = ...
    no_individual: bool = ...
    return_fig: bool = ...
    formats: list[str] = field(default_factory=Incomplete)
    base_name: str | None = ...

@dataclass
class PlotConfig:
    mode: PlotMode = ...
    title: str | None = ...
    x_axis: AxisConfig = field(default_factory=Incomplete)
    y_axis: AxisConfig = field(default_factory=Incomplete)
    y2_axis: AxisConfig | None = ...
    legend: LegendConfig = field(default_factory=LegendConfig)
    direction: DirectionConfig = field(default_factory=DirectionConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    humanize: bool = ...
    csv_format: CSVFormat = ...
    x_col: int | str | list[int | str] | None = ...
    y_cols: list[int | str] | None = ...
    direction_cols: list[int | str | None] | None = ...

@dataclass
class CSVMetadata:
    dimension: str
    headers: list[str]
    additional: dict[str, str] = field(default_factory=dict)

@dataclass
class ParsedData:
    data: object
    metadata: CSVMetadata | None
    x_col: str
    y_cols: list[str]
    series_col: str | None = ...
    direction_col: str | None = ...
