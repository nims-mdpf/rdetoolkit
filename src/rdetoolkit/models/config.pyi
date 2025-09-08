from pydantic import BaseModel

class SystemSettings(BaseModel):
    extended_mode: str | None
    save_raw: bool
    save_nonshared_raw: bool
    save_thumbnail_image: bool
    magic_variable: bool
    @classmethod
    def validate_extended_mode(cls, v: str | None) -> str | None: ...

class MultiDataTileSettings(BaseModel):
    ignore_errors: bool

class SmartTableSettings(BaseModel):
    save_table_file: bool

class TracebackSettings(BaseModel):
    enabled: bool
    format: str
    include_context: bool
    include_locals: bool
    include_env: bool
    max_locals_size: int
    sensitive_patterns: list[str]
    @classmethod
    def validate_format(cls, v: str) -> str: ...
    @classmethod
    def validate_max_locals_size(cls, v: int) -> int: ...

class Config(BaseModel, extra='allow'):
    system: SystemSettings
    multidata_tile: MultiDataTileSettings | None
    smarttable: SmartTableSettings | None
    traceback: TracebackSettings | None
