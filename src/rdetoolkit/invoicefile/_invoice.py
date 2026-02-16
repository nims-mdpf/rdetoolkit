"""JSON invoice file handling.

This module provides the InvoiceFile class for reading, validating,
and overwriting RDE invoice JSON files.
"""

from __future__ import annotations

import copy
import json
import os
import shutil
from collections.abc import Mapping, MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rdetoolkit.exceptions import StructuredError
from rdetoolkit.fileops import readf_json, writef_json

if TYPE_CHECKING:
    from rdetoolkit.models.rde2types import RdeFsPath

from rdetoolkit.invoicefile._helpers import _ensure_chardet


def _assign_invoice_val(invoiceobj: MutableMapping[str, Any], key1: str, key2: str, valobj: Any, invoiceschema_obj: Mapping[str, Any]) -> None:
    """When the destination key, which is the first key 'keys1', is 'custom', valobj is cast according to the invoiceschema_obj. In all other cases, valobj is assigned without changing its type.

    Args:
        invoiceobj (MutableMapping[str, Any]): The invoice object to mutate (performs assignments).
        key1 (str): The first-level key (e.g., 'basic', 'custom').
        key2 (str): The second-level key within key1.
        valobj (Any): The value to assign.
        invoiceschema_obj (Mapping[str, Any]): The invoice schema for type casting (read-only).
    """
    if key1 == "custom":
        from rdetoolkit import rde2util

        dct_schema = invoiceschema_obj["properties"][key1]["properties"][key2]
        try:
            invoiceobj[key1][key2] = rde2util.castval(valobj, dct_schema["type"], dct_schema.get("format"))
        except StructuredError as struct_err:
            emsg = f"ERROR: failed to cast invoice value for key [{key1}][{key2}]"
            raise StructuredError(emsg) from struct_err
    else:
        invoiceobj[key1][key2] = valobj


def overwrite_invoicefile_for_dpfterm(
    invoiceobj: dict[str, Any],
    invoice_dst_filepath: RdeFsPath,
    invoiceschema_filepath: RdeFsPath,
    invoice_info: Mapping[str, Any],
) -> None:
    """A function to overwrite DPF metadata into an invoice file.

    Args:
        invoiceobj (dict[str, Any]): The object of invoice.json.
        invoice_dst_filepath (RdeFsPath): The file path for the destination invoice.json.
        invoiceschema_filepath (RdeFsPath): The file path of invoice.schema.json.
        invoice_info (Mapping[str, Any]): Information about the invoice file.
    """
    chardet = _ensure_chardet()
    with open(invoiceschema_filepath, "rb") as f:
        data = f.read()
    enc = chardet.detect(data)["encoding"]
    with open(invoiceschema_filepath, encoding=enc) as f:
        invoiceschema_obj = json.load(f)
    for k, v in invoice_info.items():
        _assign_invoice_val(invoiceobj, "custom", k, v, invoiceschema_obj)
    with open(invoice_dst_filepath, "w", encoding=enc) as fout:
        json.dump(invoiceobj, fout, indent=4, ensure_ascii=False)


class InvoiceFile:
    """Represents an invoice file and provides utilities to read and overwrite it.

    Attributes:
        invoice_path (Path): Path to the invoice file.
        schema_path (Path | None): Optional path to the invoice schema file used for validation.
        invoice_obj (dict): Dictionary representation of the invoice JSON file.

    Args:
        invoice_path (Path): The path to the invoice file.
        schema_path (Path | None): Optional path to the invoice schema for validation when overwriting.

    Raises:
        ValueError: If `invoice_obj` is not a dictionary.

    Example:
        # Usage
        invoice = InvoiceFile(Path("invoice.json"), schema_path=Path("invoice.schema.json"))
        invoice.invoice_obj["basic"]["dataName"] = "new_data_name"
        invoice.overwrite(Path("invoice_new.json"))
        invoice.invoice_obj["basic"]["dataName"] = "updated"
        invoice.overwrite(schema_path=Path("invoice.schema.json"))
    """

    def __init__(self, invoice_path: Path, *, schema_path: Path | None = None):
        self.invoice_path = Path(invoice_path)
        self.schema_path = Path(schema_path) if schema_path is not None else None
        self._invoice_obj = self.read()

    @property
    def invoice_obj(self) -> dict[str, Any]:
        """Gets the invoice object."""
        return self._invoice_obj

    @invoice_obj.setter
    def invoice_obj(self, value: dict[str, Any]) -> None:
        """Sets the invoice object."""
        if not isinstance(value, dict):
            emsg = "invoice_obj must be a dictionary"
            raise ValueError(emsg)
        self._invoice_obj = value

    def __getitem__(self, key: str) -> Any:
        return self._invoice_obj[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._invoice_obj[key] = value

    def __delitem__(self, key: str) -> None:
        del self._invoice_obj[key]

    def read(self, *, target_path: Path | None = None) -> dict:
        """Reads the content of the invoice file and returns it as a dictionary.

        Args:
            target_path (Optional[Path], optional): Path to the target invoice file. If not provided,
                uses the path from `self.invoice_path`. Defaults to None.

        Returns:
            dict: Dictionary representation of the invoice JSON file.
        """
        if target_path is None:
            target_path = self.invoice_path

        self.invoice_obj = readf_json(target_path)
        return self.invoice_obj

    def overwrite(
        self,
        dst_file_path: Path | None = None,
        *,
        src_obj: dict[str, Any] | Path | str | None = None,
        schema_path: Path | None = None,
    ) -> None:
        """Persist invoice data to disk.

        Args:
            dst_file_path: Destination file path. Defaults to `self.invoice_path` when omitted.
            src_obj: Source invoice data. Accepts a dict to overwrite with explicit data or a path to a JSON file.
                Defaults to the current `invoice_obj`.
            schema_path: Optional path to `invoice.schema.json` for validation. Falls back to the instance level
                `schema_path` when provided at construction time.

        Raises:
            TypeError: If `src_obj` is not a dict or path-like object.
            InvoiceSchemaValidationError: When validation fails against the provided schema.
            StructuredError: If writing the file fails.

        Note:
            When `dst_file_path` targets the instance's own `invoice_path`, the in-memory `invoice_obj` is updated with
            the sanitized data after a successful write to keep state in sync. Writing to a different destination leaves
            the instance state untouched.
        """
        destination = Path(dst_file_path) if dst_file_path is not None else self.invoice_path
        validator_schema = Path(schema_path) if schema_path is not None else self.schema_path

        if src_obj is None:
            candidate: dict[str, Any] = copy.deepcopy(self.invoice_obj)
        elif isinstance(src_obj, dict):
            candidate = copy.deepcopy(src_obj)
        elif isinstance(src_obj, (str, Path)):
            candidate = readf_json(Path(src_obj))
        else:
            emsg = "src_obj must be either a dict or a path-like object"
            raise TypeError(emsg)

        sanitized = self._sanitize_invoice_data(candidate, validator_schema)
        should_update_instance = destination == self.invoice_path
        os.makedirs(destination.parent, exist_ok=True)
        writef_json(destination, sanitized)

        if should_update_instance:
            self.invoice_obj = sanitized

    def _sanitize_invoice_data(self, candidate: dict[str, Any], schema_path: Path | None) -> dict[str, Any]:
        """Validate and normalise invoice data prior to persisting."""
        if schema_path is not None:
            from rdetoolkit.validation import InvoiceValidator

            validator = InvoiceValidator(schema_path)
            return validator.validate(obj=candidate)
        return candidate

    @classmethod
    def copy_original_invoice(cls, src_file_path: Path, dst_file_path: Path) -> None:
        """Copies the original invoice file from the source file path to the destination file path.

        Args:
            src_file_path (Path): The source file path of the original invoice file.
            dst_file_path (Path): The destination file path where the original invoice file will be copied to.

        Raises:
            StructuredError: If the source file path does not exist.

        Returns:
            None
        """
        if not os.path.exists(src_file_path):
            emsg = f"File Not Found: {src_file_path}"
            raise StructuredError(emsg)
        if src_file_path != dst_file_path:
            shutil.copy(str(src_file_path), str(dst_file_path))
