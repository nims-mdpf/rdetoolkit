from __future__ import annotations

import os
import warnings
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypedDict, Union

from rdetoolkit.models.config import Config, MultiDataTileSettings, SystemSettings

ZipFilesPathList = Sequence[Path]
UnZipFilesPathList = Sequence[Path]
ExcelInvoicePathList = Sequence[Path]
OtherFilesPathList = Sequence[Path]
PathTuple = tuple[Path, ...]
InputFilesGroup = tuple[ZipFilesPathList, ExcelInvoicePathList, OtherFilesPathList]
RawFiles = Sequence[PathTuple]
MetaType = dict[str, Union[str, int, float, list, bool]]
RepeatedMetaType = dict[str, list[Union[str, int, float, list, bool]]]
MetaItem = dict[str, Union[str, int, float, list, bool]]
RdeFsPath = Union[str, Path]


@dataclass
class RdeFormatFlags:  # pragma: no cover
    """Class for managing flags used in RDE.

    This class has two private attributes: _is_rdeformat_enabled and _is_multifile_enabled.
    These attributes are set in the __post_init__ method, depending on the existence of certain files.
    Additionally, properties and setters are used to get and modify the values of these attributes.
    However, it is not allowed for both attributes to be True simultaneously.

    Warning:
        Currently, this class is not used because the `data/tasksupport/rdeformat.txt` and `data/tasksupport/multifile.txt` files are not used. It is scheduled to be deleted in the next update.

    Attributes:
        _is_rdeformat_enabled (bool): Flag indicating whether RDE format is enabled
        _is_multifile_enabled (bool): Flag indicating whether multi-file support is enabled
    """

    _is_rdeformat_enabled: bool = False
    _is_multifile_enabled: bool = False

    def __init__(self) -> None:
        warnings.warn("The RdeFormatFlags class is scheduled to be deleted in the next update.", FutureWarning, stacklevel=2)

    def __post_init__(self) -> None:
        """Method called after object initialization.

        This method checks for the existence of files named rdeformat.txt and multifile.txt in the data/tasksupport directory,
        and sets the values of _is_rdeformat_enabled and _is_multifile_enabled accordingly.
        """
        self.is_rdeformat_enabled = os.path.exists("data/tasksupport/rdeformat.txt")
        self.is_multifile_enabled = os.path.exists("data/tasksupport/multifile.txt")

    @property
    def is_rdeformat_enabled(self) -> bool:
        """Property returning whether the RDE format is enabled.

        Returns:
            bool: Whether the RDE format is enabled
        """
        return self._is_rdeformat_enabled

    @is_rdeformat_enabled.setter
    def is_rdeformat_enabled(self, value: bool) -> None:
        """Setter to change the enabled state of the RDE format.

        Args:
            value (bool): Whether to enable the RDE format

        Raises:
            ValueError: If both flags are set to True
        """
        if value and self.is_multifile_enabled:
            emsg = "both flags cannot be True"
            raise ValueError(emsg)
        self._is_rdeformat_enabled = value

    @property
    def is_multifile_enabled(self) -> bool:
        """Property returning whether multi-file support is enabled.

        Returns:
            bool: Whether multi-file support is enabled
        """
        return self._is_multifile_enabled

    @is_multifile_enabled.setter
    def is_multifile_enabled(self, value: bool) -> None:
        """Setter to change the enabled state of multi-file support.

        Args:
            value (bool): Whether to enable multi-file support

        Raises:
            ValueError: If both flags are set to True
        """
        if value and self.is_rdeformat_enabled:
            emsg = "both flags cannot be True"
            raise ValueError(emsg)
        self._is_multifile_enabled = value


def create_default_config() -> Config:
    """Creates and returns a default configuration object.

    Returns:
        Config: A default configuration object.
    """
    return Config(system=SystemSettings(extended_mode=None, save_raw=True, save_thumbnail_image=False, magic_variable=False), multidata_tile=MultiDataTileSettings(ignore_errors=False))


@dataclass
class RdeInputDirPaths:
    """A data class that holds folder paths used for input in the RDE.

    It manages the folder paths for input data necessary for the RDE.

    Attributes:
        inputdata (Path): Path to the folder where input data is stored.
        invoice (Path): Path to the folder where invoice.json is stored.
        tasksupport (Path): Path to the folder where task support data is stored.
        config (Config): The configuration object.

    Properties:
        default_csv (Path): Provides the path to the `default_value.csv` file. If `tasksupport` is specified, it uses the path under it; otherwise,
        it uses the default path under `data/tasksupport`.
    """

    inputdata: Path
    invoice: Path
    tasksupport: Path
    config: Config = field(default_factory=create_default_config)

    @property
    def default_csv(self) -> Path:
        """Returns the path to the 'default_value.csv' file.

        If `tasksupport` is set, this path is used.
        If not set, the default path under 'data/tasksupport' is used.

        Returns:
            Path: Path to the 'default_value.csv' file.
        """
        tasksupport = self.tasksupport if self.tasksupport else Path("data", "tasksupport")
        return tasksupport.joinpath("default_value.csv")


@dataclass
class RdeOutputResourcePath:
    """A data class that holds folder paths used as output destinations for RDE.

    It maintains the paths for various files used in the structuring process.

    Attributes:
        raw (Path): Path where raw data is stored.
        nonshared_raw (Path): Path where nonshared raw data is stored.
        rawfiles (tuple[Path, ...]): Holds a tuple of input file paths, such as those unzipped, for a single tile of data.
        struct (Path): Path for storing structured data.
        main_image (Path): Path for storing the main image file.
        other_image (Path): Path for storing other image files.
        meta (Path): Path for storing metadata files.
        thumbnail (Path): Path for storing thumbnail image files.
        logs (Path): Path for storing log files.
        invoice (Path): Path for storing invoice files.
        invoice_schema_json (Path): Path for the invoice.schema.json file.
        invoice_org (Path): Path for storing the backup of invoice.json.
        temp (Optional[Path]): Path for storing temporary files.
        invoice_patch (Optional[Path]): Path for storing modified invoice files.
        attachment (Optional[Path]): Path for storing attachment files.
    """

    raw: Path
    nonshared_raw: Path
    rawfiles: tuple[Path, ...]
    struct: Path
    main_image: Path
    other_image: Path
    meta: Path
    thumbnail: Path
    logs: Path
    invoice: Path
    invoice_schema_json: Path
    invoice_org: Path
    temp: Path | None = None
    invoice_patch: Path | None = None
    attachment: Path | None = None


class Name(TypedDict):
    """Represents a name structure as a Typed Dictionary.

    This class is designed to hold names in different languages, specifically Japanese and English.

    Attributes:
        ja (str): The name in Japanese.
        en (str): The name in English.
    """

    ja: str
    en: str


class Schema(TypedDict, total=False):
    """Represents a schema definition as a Typed Dictionary.

    This class is used to define the structure of a schema with optional keys.
    It extends TypedDict with `total=False` to allow partial dictionaries.

    Attributes:
        type (str): The type of the schema.
        format (str): The format of the schema.
    """

    type: str
    format: str


class MetadataDefJson(TypedDict):
    """Defines the metadata structure for a JSON object as a Typed Dictionary.

    This class specifies the required structure of metadata, including various fields
    that describe characteristics and properties of the data.

    Attributes:
        name (Name): The name associated with the metadata.
        schema (Schema): The schema of the metadata.
        unit (str): The unit of measurement.
        description (str): A description of the metadata.
        uri (str): The URI associated with the metadata.
        originalName (str): The original name of the metadata.
        originalType (str): The original type of the metadata.
        mode (str): The mode associated with the metadata.
        order (str): The order of the metadata.
        valiable (int): A variable associated with the metadata.
        _feature (bool): A private attribute indicating a feature.
        action (str): An action associated with the metadata.
    """

    name: Name
    schema: Schema
    unit: str
    description: str
    uri: str
    originalName: str
    originalType: str
    mode: str
    order: str
    valiable: int
    _feature: bool
    action: str


@dataclass
class ValueUnitPair:
    """Dataclass representing a pair of value and unit.

    This class is used to store and manage a value along with its associated unit.
    It uses the features of dataclass for simplified data handling.

    Attributes:
        value (str): The value part of the pair.
        unit (str): The unit associated with the value.
    """

    value: str
    unit: str
