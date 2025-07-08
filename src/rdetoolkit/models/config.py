from __future__ import annotations

from pydantic import BaseModel, Field


class SystemSettings(BaseModel):
    """SystemSettings is a configuration model for the RDEtoolkit system settings.

    Attributes:
        extended_mode (str | None): The mode to run the RDEtoolkit in. Options include 'rdeformat' and 'MultiDataTile'. Default is None.
        save_raw (bool): Indicates whether to automatically save raw data to the raw directory. Default is False.
        save_nonshared_raw (bool): Indicates whether to save nonshared raw data. If True, non-shared raw data will be saved. Default is True.
        save_thumbnail_image (bool): Indicates whether to automatically save the main image to the thumbnail directory. Default is False.
        magic_variable (bool): A feature where specifying '${filename}' as the data name results in the filename being transcribed as the data name. Default is False.
    """

    extended_mode: str | None = Field(default=None, description="The mode to run the RDEtoolkit in. select: rdeformat, MultiDataTile")
    save_raw: bool = Field(default=False, description="Auto Save raw data to the raw directory")
    save_nonshared_raw: bool = Field(default=True, description="Specifies whether to save nonshared raw data. If True, non-shared raw data will be saved.")
    save_thumbnail_image: bool = Field(default=False, description="Auto Save main image to the thumbnail directory")
    magic_variable: bool = Field(
        default=False,
        description="The feature where specifying '${filename}' as the data name results in the filename being transcribed as the data name.",
    )


class MultiDataTileSettings(BaseModel):
    ignore_errors: bool = Field(default=False, description="If true, errors encountered during processing will be ignored, and the process will continue without stopping.")


# class ExcelInvoiceSettings(BaseModel):
#     ignore_errors: bool = Field(default=False, description="If true, errors encountered during ExcelInvoice processing will be ignored, and the process will continue without stopping.")


class Config(BaseModel, extra="allow"):
    """The configuration class used in RDEToolKit.

    Attributes:
        system (SystemSettings): System related settings.
        multidata_tile (MultiDataTileSettings | None): MultiDataTile related settings.
        excel_invoice (ExcelInvoiceSettings | None): ExcelInvoice related settings.
    """
    system: SystemSettings = Field(default_factory=SystemSettings, description="System related settings")
    multidata_tile: MultiDataTileSettings | None = Field(default_factory=MultiDataTileSettings, description="MultiDataTile related settings")
    # excel_invoice: ExcelInvoiceSettings | None = Field(default_factory=ExcelInvoiceSettings, description="ExcelInvoice related settings")
