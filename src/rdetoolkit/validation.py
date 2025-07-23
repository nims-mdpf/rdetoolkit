from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker, validate
from jsonschema import ValidationError as SchemaValidationError
from pydantic import ValidationError

from rdetoolkit.exceptions import InvoiceSchemaValidationError, MetadataValidationError
from rdetoolkit.fileops import readf_json
from rdetoolkit.models.invoice_schema import InvoiceSchemaJson
from rdetoolkit.models.metadata import MetadataItem


class MetadataValidator:
    def __init__(self) -> None:
        self.schema = MetadataItem

    def validate(self, *, path: str | Path | None = None, json_obj: dict[str, Any] | None = None) -> dict[str, Any]:
        """Validates the provided JSON data against the MetadataItem schema.

        Args:
            path (Union[str, Path], optional): The path to the JSON file to be validated. Defaults to None.
            json_obj (dict[str, Any], optional): The JSON object to be validated. Defaults to None.

        Returns:
            dict[str, Any]: The validated JSON data.

        Raises:
            ValueError: If neither 'path' nor 'json_obj' is provided.
            ValueError: If both 'path' and 'json_obj' are provided.
            ValueError: If an unexpected error occurs.

        """
        if path is None and json_obj is None:
            emsg = "At least one of 'path' or 'json_obj' must be provided"
            raise ValueError(emsg)
        if path is not None and json_obj is not None:
            emsg = "Both 'path' and 'json_obj' cannot be provided at the same time"
            raise ValueError(emsg)

        if path is not None:
            __data = readf_json(path)
        elif json_obj is not None:
            __data = json_obj
        else:
            emsg = "Unexpected validation error"
            raise ValueError(emsg)

        MetadataItem(**__data)
        return __data


def metadata_validate(path: str | Path) -> None:
    """Validate metadata.json file.

    This function validates the metadata definition file specified by the given path.
    It checks if the file exists and then uses a validator to validate the file against a schema.

    Args:
        path (Union[str, Path]): The path to the metadata definition file.

    Raises:
        FileNotFoundError: If the schema and path do not exist.
        MetadataValidationError: If there is an error in validating the metadata definition file.
    """
    if isinstance(path, str):
        path = Path(path)

    if not path.exists():
        emsg = f"The schema and path do not exist: {path.name}"
        raise FileNotFoundError(emsg)

    validator = MetadataValidator()
    try:
        validator.validate(path=path)
    except ValidationError as validation_error:
        emsg = "Validation Errors in metadata.json. Please correct the following fields\n"
        for idx, error in enumerate(validation_error.errors(), start=1):
            emsg += f"{idx}. Field: {'.'.join([str(e) for e in error['loc']])}\n"
            emsg += f"   Type: {error['type']}\n"
            emsg += f"   Context: {error['msg']}\n"
        raise MetadataValidationError(emsg) from validation_error


class InvoiceValidator:
    pre_basic_info_schema = os.path.join(os.path.dirname(__file__), "static", "invoice_basic_and_sample.schema_.json")

    def __init__(self, schema_path: str | Path):
        self.schema_path = schema_path
        self.schema = self.__pre_validate()
        self.__temporarily_modify_json_schema()

    def validate(self, *, path: str | Path | None = None, obj: dict[str, Any] | None = None) -> dict[str, Any]:
        """Validate the provided JSON data against the schema.

        Args:
            path (Optional[Union[str, Path]]): The path to the JSON file to validate.
            obj (Optional[dict[str, Any]]): The JSON object to validate.

        Raises:
            ValueError: If neither 'path' nor 'obj' is provided.
            ValueError: If both 'path' and 'obj' are provided.

        Returns:
            None
        """
        data = self.__get_data(path, obj)

        # Remove None values from the data
        # Although invoice.schema.json does not allow None, the invoice.json generated from the system is written in a format that allows None. Therefore, as a temporary measure, we remove the None values from invoice.json.
        _data = self._remove_none_values(data)
        if isinstance(data, dict):
            data = cast(dict[str, Any], _data)
        else:
            # In RDE, the top of invoice.json never returns as an array.
            emsg = "Expected a dictionary, but got a different type."
            raise ValueError(emsg)

        basic_info = readf_json(self.pre_basic_info_schema)
        # with open(self.pre_basic_info_schema, encoding="utf-8") as f:
        #     basic_info = json.load(f)
        try:
            validate(instance=data, schema=basic_info)
        except SchemaValidationError as schema_error:
            emsg = "Error in validating system standard field.\nPlease correct the following fields in invoice.json\n"
            emsg += f"Field: {'.'.join(list(map(str, schema_error.path)))}\n"
            emsg += f"Type: {schema_error.validator}\n"
            emsg += f"Context: {schema_error.message}\n"
            raise InvoiceSchemaValidationError(emsg) from schema_error

        validator = Draft202012Validator(self.schema, format_checker=FormatChecker())
        errors = sorted(validator.iter_errors(data), key=lambda e: e.path)

        # Custom validation: Check if invoice.json contains only required fields
        required_fields_errors = self._validate_required_fields_only(data)
        if required_fields_errors:
            errors.extend(required_fields_errors)

        emsg = "Error in validating invoice.json:\n"
        for idx, error in enumerate(errors, start=1):
            emsg += f"{idx}. Field: {'.'.join(list(map(str, error.path)))}\n"
            emsg += f"   Type: {error.validator}\n"
            emsg += f"   Context: {error.message}\n"
        if errors:
            raise InvoiceSchemaValidationError(emsg)

        return data

    def __get_data(self, path: str | Path | None, obj: dict[str, Any] | None) -> dict[str, Any]:
        if path is None and obj is None:
            emsg = "At least one of 'path' or 'obj' must be provided"
            raise ValueError(emsg)
        if path is not None and obj is not None:
            emsg = "Both 'path' and 'obj' cannot be provided at the same time"
            raise ValueError(emsg)

        if path is not None:
            return readf_json(path)
        if obj is not None:
            return obj
        emsg = "Unexpected error"
        raise ValueError(emsg)

    def __pre_validate(self) -> dict[str, Any]:
        __path = Path(self.schema_path) if isinstance(self.schema_path, str) else self.schema_path

        if __path.suffix != ".json":
            emsg = "The schema file must be a json file"
            raise ValueError(emsg)

        data = readf_json(__path)

        if __path.name == "invoice.schema.json":
            try:
                # _data, line_map = load_json_with_line_numbers(data)
                InvoiceSchemaJson(**data)
            except ValidationError as validation_error:
                emsg = "Validation Errors in invoice.schema.json. Please correct the following fields\n"
                for idx, error in enumerate(validation_error.errors(), start=1):
                    emsg += f"{idx}. Field: {'.'.join([str(e) for e in error['loc']])}\n"
                    emsg += f"   Type: {error['type']}\n"
                    emsg += f"   Context: {error['msg']}\n"
                raise InvoiceSchemaValidationError(emsg) from validation_error
            except ValueError as value_error:
                emsg = "Error in schema validation"
                raise InvoiceSchemaValidationError(emsg) from value_error
            return data

        return data

    def __temporarily_modify_json_schema(self) -> dict[str, Any] | None:
        """Temporarily modifies the structure of the schema to validate invoice.json using invoice.schema.json.

        This method modifies the 'generalAttributes' and 'specificAttributes' sections of the schema by replacing
        the 'items' with a new dictionary that has 'oneOf' as the key and the original 'items' as the value.
        This allows the schema to validate invoice.json using invoice.schema.json.

        Note:
            - The modifications are temporary and only affect the current instance of the schema.
            - If the 'sample' property does not exist in the schema, the method returns the original schema without any modifications.
        """
        if not self.schema.get("properties", {}).get("sample", {}):
            return self.schema

        __generalattr_item = self.schema.get("properties", {}).get("sample", {}).get("properties", {}).get("generalAttributes")
        if __generalattr_item:
            __ref = self.schema["properties"]["sample"]["properties"]["generalAttributes"]
            __temp_generalattr_item = copy.deepcopy(__ref)
            __ref["prefixItems"] = __temp_generalattr_item["items"]
            del __ref["items"]
            # __ref["items"][rule_keyword] = __temp_generalattr_item["items"]

        __specificattr_item = self.schema.get("properties", {}).get("sample", {}).get("properties", {}).get("specificAttributes")
        if __specificattr_item:
            __ref = self.schema["properties"]["sample"]["properties"]["specificAttributes"]
            __temp_specificattr_item = copy.deepcopy(__ref)
            __ref["prefixItems"] = __temp_specificattr_item["items"]
            del __ref["items"]
            # __ref["items"][rule_keyword] = __temp_specificattr_item["items"]

        return None

    def _remove_none_values(self, data: dict | list | Any) -> dict | list | Any:
        """Recursively removes key/value pairs from dictionaries and elements from lists where the value is None.

        Args:
            data (Union[dict, list, Any]): The input data which can be a dictionary, list, or any other type.

        Returns:
            Union[dict, list, Any]: The cleaned data with None values removed.

        Examples:
            >>> remove_none_values({"a": 1, "b": None, "c": 3})
            {'a': 1, 'c': 3}

            >>> remove_none_values([1, None, 3, {"a": None, "b": 2}])
            [1, 3, {'b': 2}]

            >>> remove_none_values({"a": [None, 2, None], "b": None, "c": [1, 2, 3]})
            {'a': [2], 'c': [1, 2, 3]}
        """
        if isinstance(data, dict):
            return {k: self._remove_none_values(v) for k, v in data.items() if v is not None}
        if isinstance(data, list):
            return [self._remove_none_values(item) for item in data if item is not None]

        return data

    def _validate_required_fields_only(self, data: dict[str, Any]) -> list:
        """Validate that invoice.json contains only fields listed in schema's required array.

        Args:
            data: The invoice data to validate

        Returns:
            List of validation errors for fields not in required array
        """
        errors = []

        # Get required fields from schema
        required_fields = set(self.schema.get("required", []))

        # Always allow system-required fields
        system_required = {"basic", "datasetId"}
        required_fields.update(system_required)

        # Check top-level fields in invoice data
        for field_name in data:
            if field_name not in required_fields:
                # Create a mock validation error for consistency with JSONSchema errors
                error = ValidationError(
                    message=f"Field '{field_name}' is not allowed. Only required fields {sorted(required_fields)} are permitted in invoice.json",
                    path=[field_name],
                    validator='required_fields_only',
                )
                errors.append(error)

        return errors


def invoice_validate(path: str | Path, schema: str | Path) -> None:
    """invoice.json validation function.

    Args:
        path (Union[str, Path]): invoice.json file path
        schema (Union[str, Path]): invoice.schema.json file path

    Raises:
        FileNotFoundError: If the provided schema file does not exist.
        FileNotFoundError: If the provided invoice.json file does not exist.
        InvoiceSchemaValidationError: If the invoice.json file fails to validate against the schema.
    """
    if isinstance(schema, str):
        schema = Path(schema)
    if isinstance(path, str):
        path = Path(path)

    if not schema.exists():
        emsg = f"The schema and path do not exist: {schema.name}"
        raise FileNotFoundError(emsg)
    if not path.exists():
        emsg = f"The schema and path do not exist: {path.name}"
        raise FileNotFoundError(emsg)

    validator = InvoiceValidator(schema)
    try:
        validator.validate(path=path)
    except ValidationError as validation_error:
        raise InvoiceSchemaValidationError from validation_error
