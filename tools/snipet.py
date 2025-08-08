from __future__ import annotations

import base64
import json
import re
from typing import Optional


def _best_encoding(text_bytes: bytes) -> str:
    """Attempt to decode bytes using the best available encoding."""
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return text_bytes.decode(enc)
        except UnicodeDecodeError:
            continue
    return text_bytes.decode("utf-8", errors="ignore")


def _detect_language_from_name(name: str) -> str:
    """Detect programming language from file extension."""
    extension_map = {
        ".py": "python",
        ".md": "markdown",
        ".markdown": "markdown",
        ".yml": "yaml",
        ".yaml": "yaml",
        ".json": "json",
        ".toml": "toml",
        ".sh": "bash",
        ".bash": "bash",
    }

    name_lower = name.lower()
    for ext, lang in extension_map.items():
        if name_lower.endswith(ext):
            return lang
    return "text"


def _extract_terms(question: str, symbols: Optional[list[str]]) -> list[str]:
    """Extract search terms from question and symbols."""
    # ASCII identifiers (snake_case/camelCase/module.path etc.)
    ascii_terms = [t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_\.]*", question)]
    # Japanese (hiragana, katakana, kanji) identifiers
    cjk_terms = re.findall(r"[ぁ-んァ-ン一-龥ー]{2,}", question)
    # Symbols passed from upstream nodes (function/class name candidates)
    sym_terms = [s for s in (symbols or []) if isinstance(s, str)]

    # Remove duplicates while preserving order
    seen = set()
    terms = []
    for term in ascii_terms + cjk_terms + sym_terms:
        term_lower = term.lower() if isinstance(term, str) else str(term).lower()
        if term_lower and term_lower not in seen:
            terms.append(term_lower)
            seen.add(term_lower)
    return terms


def _find_symbol_line_py(lines: list[str], candidates: list[str]) -> Optional[int]:
    """Find line number of Python def/class definition matching candidates."""
    if not candidates:
        return None

    names = "|".join(map(re.escape, candidates))
    try:
        pattern = re.compile(rf"^\s*(def|class)\s+({names})\b")
    except re.error:
        return None

    for i, line in enumerate(lines):
        if pattern.search(line):
            return i
    return None


def _find_heading_line_md(lines: list[str], candidates: list[str]) -> Optional[int]:
    """Find line number of Markdown heading matching candidates."""
    if not candidates:
        return None

    names = "|".join(map(re.escape, candidates))
    try:
        pattern = re.compile(rf"^\s{{0,3}}#{1,3}\s*({names})\b", re.IGNORECASE)
    except re.error:
        return None

    for i, line in enumerate(lines):
        if pattern.search(line):
            return i
    return None


def _find_keyword_line(lines: list[str], terms: list[str]) -> Optional[int]:
    """Find line number containing any of the search terms."""
    if not terms:
        return None

    ascii_terms = [t for t in terms if re.match(r"^[a-z0-9_\.]+$", t)]
    other_terms = [t for t in terms if t not in ascii_terms]

    ascii_pattern = None
    if ascii_terms:
        ascii_pattern = re.compile(rf"\b({'|'.join(map(re.escape, ascii_terms))})\b", re.IGNORECASE)

    for i, line in enumerate(lines):
        line_lower = line.lower()
        if ascii_pattern and ascii_pattern.search(line_lower):
            return i
        if other_terms and any(term in line_lower for term in other_terms):
            return i
    return None


def _slice_window(total_lines: int, location: int, pre: int = 60, post: int = 90) -> tuple[int, int]:
    """Calculate window boundaries around a target location."""
    start = max(0, location - pre)
    end = min(total_lines, location + post)
    return start, end


def _format_snippet(lines: list[str], start: int, end: int, max_chars: int = 8000) -> tuple[str, int, int]:
    """Format code snippet with line numbers, truncating if too long."""
    def render(start_idx: int, end_idx: int) -> str:
        return "\n".join(f"{i+1:>5}: {lines[i]}" for i in range(start_idx, end_idx))

    current_start, current_end = start, end
    snippet = render(current_start, current_end)

    while len(snippet) > max_chars and current_end - current_start > 20:
        current_start += 5
        current_end -= 5
        snippet = render(current_start, current_end)

    return snippet, current_start, current_end


def main(gh_json: str, question: str, symbols: list[str] | None) -> dict:
    """Extract a code snippet from GitHub contents API JSON data.

    Takes a JSON string from GitHub contents API (CodeReader.body) and extracts
    the section most relevant to the question and symbols with line numbers.

    Returns: {"file_path", "snippet", "start_line", "end_line", "language", "matched_by"}
    """
    # Parse JSON
    try:
        data = json.loads(gh_json) if isinstance(gh_json, str) else gh_json
    except (json.JSONDecodeError, TypeError):
        return {"file_path": "", "snippet": "", "start_line": 0, "end_line": 0, "language": "text", "matched_by": "error"}

    path = data.get("path") or data.get("name") or ""
    language = _detect_language_from_name(path)
    content_b64 = (data.get("content") or "").replace("\n", "")

    # Decode Base64 to string
    try:
        raw_bytes = base64.b64decode(content_b64, validate=True) if content_b64 else b""
    except (base64.binascii.Error, ValueError):
        raw_bytes = base64.b64decode(content_b64.encode("utf-8", "ignore")) if content_b64 else b""

    text = _best_encoding(raw_bytes) if raw_bytes else ""
    lines = text.splitlines()
    total_lines = len(lines)

    # Extract search terms (question + symbols)
    terms = _extract_terms(question or "", symbols)

    # Find target location
    location, matched_by = None, "head"

    if language == "python":
        # Python: prioritize def/class definitions
        python_identifiers = [t for t in terms if re.match(r"^[a-z_][a-z0-9_]*$", t)]
        location = _find_symbol_line_py(lines, python_identifiers)
        if location is not None:
            matched_by = "symbol"
    elif language == "markdown":
        location = _find_heading_line_md(lines, terms)
        if location is not None:
            matched_by = "heading"

    if location is None:
        location = _find_keyword_line(lines, terms)
        if location is not None:
            matched_by = "keyword"

    if location is None:
        location, matched_by = 0, "head"

    # Extract snippet
    start, end = _slice_window(total_lines, location, pre=60, post=90)
    snippet, actual_start, actual_end = _format_snippet(lines, start, end, max_chars=8000)

    return {
        "file_path": path,
        "snippet": snippet,
        "start_line": actual_start + 1,
        "end_line": actual_end,
        "language": language,
        "matched_by": matched_by,
    }
