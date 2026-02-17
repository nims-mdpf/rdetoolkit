"""Agent guide module for AI coding assistants.

This module provides documentation for AI coding agents (Claude Code, GitHub Copilot, etc.)
to effectively use rdetoolkit without requiring users to write detailed instruction files.
"""

from __future__ import annotations

from pathlib import Path


def get_guide(detailed: bool = False) -> str:
    """Return the agent guide as a string.

    Provides hierarchical documentation access with token-efficient design:
    - Summary guide (~2KB, ~1500-2000 tokens): Quick reference for common tasks
    - Detailed guide (~5KB, ~3000-4000 tokens): Comprehensive reference with advanced patterns

    Args:
        detailed: If True, return the detailed guide (~5KB).
                  If False (default), return the summary (~2KB).

    Returns:
        Markdown-formatted guide string.

    Raises:
        FileNotFoundError: If the guide file cannot be found in the package.
        OSError: If there are file read errors.

    Examples:
        >>> guide = get_guide()  # Get summary guide
        >>> guide = get_guide(detailed=True)  # Get detailed guide
    """
    guide_dir = Path(__file__).parent
    guide_file = "guide.md" if detailed else "AGENTS.md"
    guide_path = guide_dir / guide_file

    if not guide_path.exists():
        msg = f"Guide file not found: {guide_path}"
        raise FileNotFoundError(msg)

    try:
        return guide_path.read_text(encoding="utf-8")
    except OSError as e:
        msg = f"Failed to read guide file: {guide_path}"
        raise OSError(msg) from e


__all__ = ["get_guide"]
