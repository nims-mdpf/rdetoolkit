"""Rule-based filename mapping and replacement.

This module provides classes and functions for applying rule-based
transformations to filenames in invoice files.
"""

from __future__ import annotations

import copy
import json
import os
from collections.abc import Mapping, MutableMapping
from pathlib import Path
from typing import Any

from rdetoolkit.errors import ERROR_CATALOG, RdeValidationError
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.fileops import readf_json, writef_json


class RuleBasedReplacer:
    """A class for changing the rules of data naming.

    This compatibility API applies explicit dotted-path assignments. It is
    separate from magic-variable interpolation and does not parse templates.

    Attributes:
        rules (dict[str, str]): Dictionary holding the mapping rules.
        last_apply_result (dict[str, Any]): The result of the last applied rules.

    Args:
        rule_file_path (Optional[Union[str, Path]]): Path to the rule file. If specified, rules are loaded from this path.
    """

    def __init__(self, *, rule_file_path: str | Path | None = None):
        self.rules: dict[str, str] = {}
        self.last_apply_result: dict[str, Any] = {}

        if isinstance(rule_file_path, str):
            rule_file_path = Path(rule_file_path)
        if rule_file_path and rule_file_path.exists():
            self.load_rules(rule_file_path)

    def load_rules(self, filepath: str | Path) -> None:
        """Function to read file mapping rules.

        The file containing the mapping rules must be in JSON format.

        Args:
            filepath (Union[str, Path]): The file path of the JSON file containing the mapping rules.

        Raises:
            StructuredError: An exception is raised if the file extension is not json.
        """
        if isinstance(filepath, str):
            filepath = Path(filepath)
        if filepath.suffix != ".json":
            emsg = f"Error. File format/extension is not correct: {filepath}"
            raise StructuredError(emsg)

        data = readf_json(filepath)
        self.rules = data.get("filename_mapping", {})

    def get_apply_rules_obj(
        self,
        replacements: Mapping[str, Any],
        source_json_obj: MutableMapping[str, Any] | None,
        *,
        mapping_rules: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        """Apply dotted-path rules to a mutable JSON object.

        An explicit ``mapping_rules`` replaces ``self.rules``, including when
        it is empty. Missing replacement keys produce an empty string for v1
        compatibility. Missing object ancestors are created. Empty path
        segments, scalar ancestors, and overlapping parent/child destinations
        fail before any source assignment is published.

        Successful calls mutate ``source_json_obj`` as in v1. Replacement
        values are copied, so later source edits cannot change ``replacements``.
        Failed calls preserve both the source and ``last_apply_result``.

        Args:
            replacements: Read-only placeholder-to-value mapping.
            source_json_obj: Object to update, or None to create an object.
            mapping_rules: Read-only destination-to-placeholder mapping.
                None selects the stored rules.

        Returns:
            Updated object, also stored in ``last_apply_result``.

        Raises:
            RdeValidationError: If a destination path is malformed or conflicts
                with the source structure or another rule (4008).
        """
        rules = self.rules if mapping_rules is None else mapping_rules
        _validate_rule_paths(rules)
        result = copy.deepcopy(dict(source_json_obj)) if source_json_obj is not None else {}
        assignments = [(path, copy.deepcopy(replacements.get(placeholder, ""))) for path, placeholder in rules.items()]
        for path, value in assignments:
            _assign_rule(result, path, value)
        if source_json_obj is not None:
            for path, value in assignments:
                _assign_rule(source_json_obj, path, value)
            result = dict(source_json_obj)
        self.last_apply_result = dict(result)
        return self.last_apply_result

    def set_rule(self, path: str, variable: str) -> None:
        """Sets a new rule.

        Args:
            path (str): The path to the target location for replacement.
            variable (str): The rule after replacement.

        Example:
            replacer = RuleBasedReplacer()
            replacer.set_rule('invoice.basic.dataName', 'filename')
            replacer.set_rule('invoice.sample.name', 'dataname')
            print(replacer.rules)
        """
        self.rules[path] = variable

    def write_rule(self, replacements_rule: dict[str, Any], save_file_path: str | Path) -> str:
        """Function to write file mapping rules to a target JSON file.

        Writes the set mapping rules (in JSON format) to the target file

        Args:
            replacements_rule (dict[str, str]): The object containing mapping rules.
            save_file_path (Union[str, Path]): The file path for saving.

        Raises:
            StructuredError: An exception error occurs if the extension of the save path is not .json.
            StructuredError: An exception error occurs if values cannot be written to the json.

        Returns:
            str: The result of writing to the target JSON.
        """
        contents: str = ""

        if isinstance(save_file_path, str):
            save_file_path = Path(save_file_path)

        if save_file_path.suffix != ".json":
            emsg = f"Extension error. Incorrect extension: {save_file_path}"
            raise StructuredError(emsg)

        if save_file_path.exists():
            exists_contents = readf_json(save_file_path)
            _ = self.get_apply_rules_obj(replacements_rule, exists_contents)
            data_to_write = copy.deepcopy(exists_contents)
        else:
            new_contents: dict[str, Any] = {}
            _ = self.get_apply_rules_obj(replacements_rule, new_contents)
            data_to_write = copy.deepcopy(new_contents)

        try:
            writef_json(save_file_path, data_to_write)
            contents = json.dumps({"filename_mapping": self.rules})
        except json.JSONDecodeError as json_err:
            emsg = "Error. No write was performed on the target json"
            raise StructuredError(emsg) from json_err

        return contents


def _validate_rule_paths(rules: Mapping[str, str]) -> None:
    for path in rules:
        segments = path.split(".")
        if any(not segment for segment in segments):
            raise _mapping_rule_error(path, "path segments must not be empty")
        for index in range(1, len(segments)):
            if ".".join(segments[:index]) in rules:
                raise _mapping_rule_error(path, "parent and child destinations overlap")


def _assign_rule(result: MutableMapping[str, Any], path: str, value: Any) -> None:
    segments = path.split(".")
    current = result
    for segment in segments[:-1]:
        if segment not in current:
            current[segment] = {}
        child = current[segment]
        if not isinstance(child, MutableMapping):
            raise _mapping_rule_error(path, "an ancestor is not a JSON object")
        current = child
    current[segments[-1]] = value


def _mapping_rule_error(path: str, reason: str) -> RdeValidationError:
    definition = ERROR_CATALOG[4008]
    return RdeValidationError(
        code=4008,
        name=definition.name,
        message=f"Invalid mapping destination {path!r}: {reason}. Remediation: {definition.remediation}",
    )


def apply_default_filename_mapping_rule(replacement_rule: dict[str, Any], save_file_path: str | Path) -> dict[str, Any]:
    """Applies a default filename mapping rule based on the basename of the save file path.

    This function creates an instance of RuleBasedReplacer and applies a default mapping rule. If the basename
    of the save file path is 'invoice', it sets a specific rule for 'basic.dataName'. After setting the rule,
    it writes the mapping rule to the specified file path and returns the result of the last applied rules.

    Args:
        replacement_rule (dict[str, Any]): The replacement rules to be applied.
        save_file_path (Union[str, Path]): The file path where the replacement rules are saved.

    Returns:
        dict[str, Any]: The result of the last applied replacement rules.

    The function assumes the existence of certain structures in the replacement rules and file paths, and it
    specifically checks for a basename of 'invoice' to apply a predefined rule.
    """
    if isinstance(save_file_path, str):
        basename = os.path.splitext(os.path.basename(save_file_path))[0]
    elif isinstance(save_file_path, Path):
        basename = save_file_path.stem

    replacer = RuleBasedReplacer()
    if basename == "invoice":
        replacer.set_rule("basic.dataName", "${filename}")
    replacer.write_rule(replacement_rule, save_file_path)

    return replacer.last_apply_result
