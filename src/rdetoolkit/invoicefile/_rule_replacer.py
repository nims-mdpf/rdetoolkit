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

from rdetoolkit.exceptions import StructuredError
from rdetoolkit.fileops import readf_json, writef_json


class RuleBasedReplacer:
    """A class for changing the rules of data naming.

    This class is used to manage and apply file name mapping rules. It reads rules from a JSON format
    rule file, sets rules, and performs file name transformations and replacements based on those rules.

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
        """Function to convert file mapping rules into a JSON format.

        This function takes string mappings separated by dots ('.') and converts them into a dictionary format, making it easier to handle within a target JsonObject.

        Args:
            replacements (Mapping[str, Any]): The object containing mapping rules (read-only).
            source_json_obj (MutableMapping[str, Any] | None): Objects of key and value to which you want to apply the rule (performs nested assignments).
            mapping_rules (Mapping[str, str] | None, optional): Rules for mapping key and value (read-only). Defaults to None.

        Returns:
            dict[str, Any]: dictionary type data after conversion

        Example:
            # rule.json
            rule = {
                "filename_mapping": {
                    "invoice.basic.dataName": "${filename}",
                    "invoice.sample.names": ["${somedataname}"],
                }
            }
            replacer = RuleBasedReplacer('rules.json')
            replacements = {
                '${filename}': 'example.txt',
                '${somedataname}': ['some data']
            }
            result = replacer.apply_rules(replacement_rule, save_file_path, mapping_rules = rule)
            print(result)
        """
        # [TODO] Correction of type definitions in version 0.1.6
        if mapping_rules is None:
            mapping_rules = self.rules
        if source_json_obj is None:
            source_json_obj = {}

        for key, value in self.rules.items():
            keys = key.split(".")
            replace_value = replacements.get(value, "")
            current_obj: MutableMapping[str, Any] = source_json_obj
            for k in keys[:-1]:
                # search for the desired key in the dictionary from "xxx.xxx.xxx" ...
                if k not in current_obj:
                    current_obj[k] = {}
                current_obj = current_obj[k]
            current_obj[keys[-1]] = replace_value

        self.last_apply_result = dict(source_json_obj)

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
