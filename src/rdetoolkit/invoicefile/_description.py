"""Description field update utilities.

This module provides functions for updating invoice description fields
based on metadata and feature values extracted from datasets.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rdetoolkit.fileops import writef_json
from rdetoolkit.invoicefile._helpers import _ensure_chardet

if TYPE_CHECKING:
    from rdetoolkit.models.rde2types import RdeOutputResourcePath


def backup_invoice_json_files(excel_invoice_file: Path | None, mode: str | None) -> Path:
    """Backs up invoice files and retrieves paths based on the mode specified in the input.

    For excelinvoice and rdeformat modes, it backs up invoice.json as the original file in the temp directory in MultiDataTile mode.
    For other modes, it treats the files in the invoice directory as the original files.
    After backing up, it returns the file paths for invoice_org.json and invoice.schema.json.

    Args:
        excel_invoice_file (Optional[Path]): File path for excelinvoice mode
        mode (str): mode flags

    Returns:
        tuple[Path, Path]: File paths for invoice.json and invoice.schema.json
    """
    if mode is None:
        mode = ""
    from rdetoolkit.rde2util import StorageDir

    invoice_org_filepath = StorageDir.get_specific_outputdir(False, "invoice").joinpath("invoice.json")
    if (excel_invoice_file is not None) or (mode is not None and mode.lower() in ["rdeformat", "multidatatile"]):
        invoice_org_filepath = StorageDir.get_specific_outputdir(True, "temp").joinpath("invoice_org.json")
        shutil.copy(StorageDir.get_specific_outputdir(False, "invoice").joinpath("invoice.json"), invoice_org_filepath)
    # elif mode is not None and mode.lower() in ["rdeformat", "multidatatile"]:
    #     invoice_org_filepath = StorageDir.get_specific_outputdir(True, "temp").joinpath("invoice_org.json")
    #     shutil.copy(StorageDir.get_specific_outputdir(False, "invoice").joinpath("invoice.json"), invoice_org_filepath)

    return invoice_org_filepath


def __collect_values_from_variable(key: str, metadata_json_obj: Mapping[str, Any]) -> list[Any]:
    """Collect all values for a given key from variable array.

    This function iterates through the variable array in metadata.json
    and collects all values associated with the specified key.

    Args:
        key (str): The key to search for in the variable array
        metadata_json_obj (Mapping[str, Any]): Metadata object containing constant/variable sections

    Returns:
        list[Any]: List of values found in variable array. Returns empty list if:
            - 'variable' key doesn't exist
            - variable array is empty
            - specified key is not found in any variable array element

    Example:
        >>> metadata = {
        ...     "constant": {},
        ...     "variable": [
        ...         {"chemical_name": {"value": "A"}},
        ...         {"chemical_name": {"value": "B"}}
        ...     ]
        ... }
        >>> __collect_values_from_variable("chemical_name", metadata)
        ['A', 'B']
    """
    if not metadata_json_obj.get("variable"):
        return []

    values = []
    for var_item in metadata_json_obj["variable"]:
        if key in var_item and "value" in var_item[key]:
            values.append(var_item[key]["value"])

    return values


def __serch_key_from_constant_variable_obj(key: str, metadata_json_obj: Mapping[str, Any]) -> dict | None:
    if key in metadata_json_obj["constant"]:
        return metadata_json_obj["constant"]
    if metadata_json_obj.get("variable"):
        _variable = metadata_json_obj["variable"]
        if len(_variable) > 0:
            return metadata_json_obj["variable"][0]
        return None
    return None


def __format_description_entry(name_ja: str, header_value: Any, unit: str | None = None) -> str:
    r"""Format a description entry with optional unit.

    This function formats metadata entries for the invoice description field.
    It handles both constant values (single) and variable array values (formatted as [A,B,C]).
    When a unit is provided, it is appended to the name in parentheses.

    Args:
        name_ja (str): Japanese name of the metadata field from metadata-def.json.
        header_value (Any): Value to be included in the description. Can be a single value
            or an array-formatted string like "[A,B,C]" for variable array values.
        unit (str | None): Optional unit string from metadata-def.json. Defaults to None.

    Returns:
        str: Formatted description entry string with newline prefix.
            Format: "\n{name_ja}({unit}):{value}" if unit exists,
            otherwise "\n{name_ja}:{value}".

    Example:
        >>> __format_description_entry("温度", 25, "°C")
        '\n温度(°C):25'
        >>> __format_description_entry("化学名", "[A,B,C]", "V")
        '\n化学名(V):[A,B,C]'
        >>> __format_description_entry("化学名", "[A,B]")
        '\n化学名:[A,B]'
    """
    if unit:
        return f"\n{name_ja}({unit}):{header_value}"
    return f"\n{name_ja}:{header_value}"


def update_description_with_features(
    rde_resource: RdeOutputResourcePath,
    dst_invoice_json: Path,
    metadata_def_json: Path,
) -> None:
    """Writes the provided features to the description field RDE.

    This function takes a dictionary of features and formats them to be written
    into the description field(to invoice.json)

    Args:
        rde_resource (RdeOutputResourcePath): Path object containing resource paths needed for RDE processing.
        dst_invoice_json (Path): Path to the invoice.json file where the features will be written.
        metadata_def_json (Path): Path to the metadata list JSON file, which may include definitions or schema information.

    Returns:
        None: The function does not return a value but writes the features to the invoice.json file in the description field.
    """
    from rdetoolkit.invoicefile._invoice import _assign_invoice_val

    chardet = _ensure_chardet()
    with open(dst_invoice_json, "rb") as dst_invoice:
        enc_dst_invoice_data = dst_invoice.read()
    enc = chardet.detect(enc_dst_invoice_data)["encoding"]
    with open(dst_invoice_json, encoding=enc) as f:
        invoice_obj = json.load(f)

    with open(rde_resource.invoice_schema_json, "rb") as rde_resource_invoice_schema:
        enc_rde_invoice_schema_data = rde_resource_invoice_schema.read()
    enc = chardet.detect(enc_rde_invoice_schema_data)["encoding"]
    with open(rde_resource.invoice_schema_json, encoding=enc) as f:
        invoice_schema_obj = json.load(f)

    with open(metadata_def_json, "rb") as metadata_def_json_f:
        enc_rde_invoice_schema_data = metadata_def_json_f.read()
    enc = chardet.detect(enc_rde_invoice_schema_data)["encoding"]
    with open(metadata_def_json, encoding=enc) as f:
        metadata_def_obj = json.load(f)

    with open(rde_resource.meta.joinpath("metadata.json"), encoding=enc) as f:
        metadata_json_obj = json.load(f)

    description = invoice_obj["basic"]["description"] if invoice_obj["basic"]["description"] else ""
    feature_added = False
    for key, value in metadata_def_obj.items():
        if not value.get("_feature"):
            continue

        metadata_details = value
        name_ja = metadata_details["name"]["ja"]
        unit = metadata_details.get("unit")
        header_value = None

        if key in metadata_json_obj["constant"]:
            header_entry = metadata_json_obj["constant"][key]
            header_value = header_entry["value"]
        else:
            variable_values = __collect_values_from_variable(key, metadata_json_obj)
            if variable_values:
                header_value = variable_values[0] if len(variable_values) == 1 else f"[{','.join(str(v) for v in variable_values)}]"

        if header_value is not None:
            description += __format_description_entry(name_ja, header_value, unit)
            feature_added = True

    # Only trim leading newline if feature was actually added
    if feature_added and description.startswith("\n"):
        description = description[1:]

    _assign_invoice_val(invoice_obj, "basic", "description", description, invoice_schema_obj)
    writef_json(dst_invoice_json, invoice_obj)
