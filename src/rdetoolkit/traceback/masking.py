from __future__ import annotations

import re
from typing import Any


class SecretsSanitizer:
    """Masks sensitive information in traceback data.

    This class provides functionality to detect and mask sensitive
    information like passwords, tokens, and API keys in variable names
    and values.
    """
    default_patterns = [
        r'(?i)password',
        r'(?i)passwd',
        r'(?i)pwd',
        r'(?i)token',
        r'(?i)secret',
        r'(?i)apikey',
        r'(?i)api_key',
        r'(?i)auth',
        r'(?i)session',
        r'(?i)cookie',
        r'(?i)cred',
        r'(?i)credential',
        r'(?i)private_key',
        r'(?i)priv_key',
        r'(?i)access_key',
    ]

    mask_string: str = "***"

    def __init__(self, custom_patterns: list[str] | None = None):
        self.patterns = self.default_patterns.copy()
        if custom_patterns:
            self.patterns.extend(custom_patterns)
        self.compiled_patterns = [re.compile(pattern) for pattern in self.patterns]

    def check_mask(self, variable_name: str) -> bool:
        """Check if a variable name should be masked.

        Args:
            variable_name (str): The name of the variable to check.

        Returns:
            bool: True if the variable name should be masked, False otherwise.

        """
        return any(pattern.search(variable_name) for pattern in self.compiled_patterns)

    def mask_value(self, variable_name: str, value: Any) -> str:
        """Mask a value if the variable name indicates sensitive data.

        Args:
            variable_name (str): The name of the variable to mask.
            value (Any): The value to mask.

        Returns:
            str: The masked value.

        """
        if self.check_mask(variable_name):
            return self.mask_string
        try:
            return repr(value)
        except Exception:
            try:
                return str(value)
            except Exception:
                return "<unprintable>"

    def mask_dict(self, data: dict[str, Any]) -> dict[str, str]:
        """Mask all sensitive values in a dictionary.

        Args:
            data (dict[str, Any]): Dictionary of variable names to values.

        Returns:
            dict[str, str]: Dictionary of variable names to masked values.

        Raises:
            TypeError: If the input is not a dictionary.

        """
        masked: dict[str, Any] = {}
        for key, value in data.items():
            if self.check_mask(key):
                masked[key] = self.mask_string
            elif isinstance(value, str):
                masked[key] = repr(value)
            else:
                masked[key] = value
        return masked

    def truncate_value(self, value: str, max_size: int) -> str:
        """Truncate a string value to fit within max_size.

        Args:
            value (str): The string value to truncate.
            max_size (int): The maximum size of the truncated string.

        Returns:
            str: The truncated string value.

        """
        if max_size <= 0:
            return '...'

        encoded = value.encode('utf-8', errors='replace')
        if len(encoded) <= max_size:
            return value

        ellipsis = b'...'
        if max_size <= len(ellipsis):
            return "..."

        target_size = max_size - len(ellipsis)

        left, right = 0, len(value)
        result = ""
        while left <= right:
            mid = (left + right) // 2
            cand = value[:mid]
            if len(cand.encode("utf-8", errors="replace")) <= target_size:
                left = mid + 1
            else:
                right = mid - 1
        return result + "..."

    def process_locals(self, frame_locals: dict[str, Any], max_size: int = 50) -> dict[str, str]:
        """Process frame locals with masking and truncation.

        Args:
            frame_locals (dict[str, Any]): Dictionary of variable names to values.
            max_size: Maximum size for each value in UTF-8 bytes.

        Returns:
            dict[str, str]: Dictionary of variable names to truncated string values.

        """
        result = {}
        for name, value in frame_locals.items():
            if name.startswith('__') and name.endswith('__'):
                continue

            value_str = self.mask_value(name, value)

            if value_str != self.mask_string:
                value_str = self.truncate_value(value_str, max_size)

            result[name] = value_str
        return result
