from __future__ import annotations

import re


def sanitize_filename(name: str) -> str:
    """Sanitize a filename by replacing invalid characters with underscores.

    Args:
        name: The filename to sanitize.

    Returns:
        Sanitized filename with invalid characters replaced by underscores.

    Example:
        >>> sanitize_filename('data:file<name>')
        'data_file_name_'
    """
    return re.sub(r'[\\/*?:"<>|]', "_", name)


def titleize(text: str) -> str:
    """Convert a string to a title case (each word capitalized).

    Similar to CakePHP's humanize function:
    - Replaces underscores with spaces
    - Capitalizes first letter of each word
    - Ensures the first character of the entire string is capitalized

    Args:
        text: The text to convert (e.g., 'cycle_count', 'specific_sample')

    Returns:
        Titleized text (e.g., 'Cycle Count', 'Specific Sample')

    Example:
        >>> titleize('api_token')
        'Api Token'
        >>> titleize('charge (mA)')
        'Charge (Ma)'
    Note:
        return text.replace("_", " ").title()
    """
    if not text:
        return text

    words = text.replace("_", " ").split()
    result = " ".join(word.capitalize() for word in words)

    # Ensure the first character is capitalized (handles cases like "charge (mA)")
    if result and result[0].islower():
        result = result[0].upper() + result[1:]

    return result


def to_snake_case(text: str) -> str:
    """Convert human readable format back to lower_snake_case.

    Reverse of humanize function:
    - Converts spaces to underscores
    - Converts to lowercase

    Args:
        text: The text to convert (e.g., 'Cycle Number', 'Specific Capacity')

    Returns:
        Snake case text (e.g., 'cycle_number', 'specific_capacity')

    Example:
        >>> to_snake_case('Battery Voltage')
        'battery_voltage'
    """
    if not text:
        return text
    return text.replace(" ", "_").lower()


def _split_unit(text: str) -> tuple[str, str | None]:
    """Remove a trailing parenthesized unit if present."""
    _text = text.strip()
    if not _text or _text[-1] != ')':
        return _text, None

    depth = 0
    for i in range(len(_text) - 1, -1, -1):
        ch = _text[i]
        if ch == ')':
            depth += 1
        elif ch == '(':
            depth -= 1
            if depth == 0:
                unit = _text[i + 1 : -1]
                return _text[:i].rstrip(), unit or None
    return _text, None


def _split_series(text: str) -> tuple[str | None, str]:
    """Split off a series name using only colons that are outside parentheses."""
    _text = text.strip()
    depth = 0
    for i, ch in enumerate(_text):
        if ch == '(':
            depth += 1
        elif ch == ')':
            if depth > 0:
                depth -= 1
        elif ch == ':' and depth == 0:
            series = _text[:i].rstrip()
            label = _text[i + 1 :].lstrip()
            return (series or None), label
    return None, _text


def parse_header(header: str) -> tuple[str | None, str, str | None]:
    """Parse header into series name, label name, and unit.

    Expected formats:
    - "series_name: label_name (unit)" → (series, label, unit)
    - "label_name (unit)" → (None, label, unit)
    - "label_name" → (None, label, None)

    Label names in lower_snake_case are automatically humanized.

    Args:
        header: The header string to parse.

    Returns:
        Tuple of (series_name, label_name, unit).
        - series_name: Optional series identifier
        - label_name: The measurement name (humanized if snake_case)
        - unit: Optional unit of measurement

    Example:
        >>> parse_header('1cyc: capacity_calculated (mAh)')
        ('1cyc', 'Capacity Calculated', 'mAh')
        >>> parse_header('voltage (V)')
        (None, 'Voltage', 'V')
        >>> parse_header('cycle_number')
        (None, 'Cycle Number', None)
    """
    header = header.strip()
    if not header:
        return None, "", None

    label_raw, unit = _split_unit(header)
    series, label = _split_series(label_raw)

    if series and ("_" in series or series[0].islower()):
        series = titleize(series)
    if label and ("_" in label or label[0].islower()):
        label = titleize(label)

    return series, label, unit
