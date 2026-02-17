"""Test suite for _agent.get_guide() function.

Test coverage based on EP/BV analysis:

Equivalence Partitioning:
- TC-EP-001: detailed=False (default) - Returns AGENTS.md
- TC-EP-002: detailed=True - Returns guide.md
- TC-EP-003: Guide file missing - Raises FileNotFoundError
- TC-EP-004: Guide file unreadable - Raises OSError

Boundary Values:
- TC-BV-001: Empty guide file - Returns empty string
- TC-BV-002: Large guide file - Returns full content
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from rdetoolkit._agent import get_guide


class TestGetGuideFunctional:
    """Functional tests for get_guide() API."""

    def test_get_guide_summary_default(self) -> None:
        """TC-EP-001: Default call returns AGENTS.md content.

        Given: No parameters (detailed defaults to False)
        When: Calling get_guide()
        Then: Returns AGENTS.md content as string
        """
        result = get_guide()
        assert isinstance(result, str)
        assert len(result) > 0
        assert "AGENTS.md" in result or "Summary Guide" in result

    def test_get_guide_summary_explicit(self) -> None:
        """TC-EP-001b: Explicit detailed=False returns AGENTS.md.

        Given: detailed=False explicitly
        When: Calling get_guide(detailed=False)
        Then: Returns AGENTS.md content as string
        """
        result = get_guide(detailed=False)
        assert isinstance(result, str)
        assert len(result) > 0
        assert "AGENTS.md" in result or "Summary Guide" in result

    def test_get_guide_detailed(self) -> None:
        """TC-EP-002: detailed=True returns guide.md content.

        Given: detailed=True
        When: Calling get_guide(detailed=True)
        Then: Returns guide.md content as string
        """
        result = get_guide(detailed=True)
        assert isinstance(result, str)
        assert len(result) > 0
        assert "guide.md" in result or "Detailed Guide" in result


class TestGetGuideEdgeCases:
    """Edge case tests for get_guide() API."""

    def test_guide_file_missing(self, tmp_path: Path) -> None:
        """TC-EP-003: Raises FileNotFoundError when guide file missing.

        Given: Guide file does not exist
        When: Calling get_guide()
        Then: Raises FileNotFoundError with descriptive message
        """
        # Create a temporary module file to mock __file__
        agent_dir = tmp_path / "_agent"
        agent_dir.mkdir()
        init_file = agent_dir / "__init__.py"
        init_file.write_text("")

        # Don't create AGENTS.md - it should be missing
        with patch("rdetoolkit._agent.Path") as mock_path_class:
            # Create a mock instance that will be returned by Path(__file__)
            mock_instance = Mock()
            mock_instance.parent = agent_dir
            mock_path_class.return_value = mock_instance

            with pytest.raises(FileNotFoundError, match="Guide file not found"):
                get_guide()

    def test_guide_file_read_error(self) -> None:
        """TC-EP-004: Raises OSError when guide file is unreadable.

        Given: Guide file exists but cannot be read (permission error)
        When: Calling get_guide()
        Then: Raises OSError with descriptive message
        """
        with patch("rdetoolkit._agent.Path") as mock_path:
            # Mock exists() to return True
            mock_guide_path = Mock(spec=["exists", "read_text"])
            mock_guide_path.exists.return_value = True
            # Mock read_text() to raise PermissionError (subclass of OSError)
            mock_guide_path.read_text.side_effect = PermissionError("Permission denied")

            mock_path.return_value.parent.__truediv__ = Mock(return_value=mock_guide_path)

            with pytest.raises(OSError, match="Failed to read guide file"):
                get_guide()

    def test_empty_guide_file(self, tmp_path: Path) -> None:
        """TC-BV-001: Empty guide file returns empty string.

        Given: Guide file exists but is empty (0 bytes)
        When: Calling get_guide()
        Then: Returns empty string without error
        """
        # Create empty guide file
        agent_dir = tmp_path / "_agent"
        agent_dir.mkdir()
        guide_file = agent_dir / "AGENTS.md"
        guide_file.write_text("", encoding="utf-8")

        with patch("rdetoolkit._agent.Path") as mock_path_class:
            # Create a mock instance that will be returned by Path(__file__)
            mock_instance = Mock()
            mock_instance.parent = agent_dir
            mock_path_class.return_value = mock_instance

            result = get_guide()
            assert result == ""

    def test_large_guide_file(self) -> None:
        """TC-BV-002: Large guide file returns full content.

        Given: Guide file is very large (>100KB)
        When: Calling get_guide()
        Then: Returns full content without truncation
        """
        # Create large content (>100KB)
        large_content = "# Large Guide\n" + ("Line content\n" * 10000)
        assert len(large_content) > 100000  # Verify it's actually large

        with patch("rdetoolkit._agent.Path") as mock_path:
            mock_guide_path = Mock()
            mock_guide_path.exists.return_value = True
            mock_guide_path.read_text.return_value = large_content
            mock_path.return_value.parent.__truediv__ = lambda self, other: mock_guide_path

            result = get_guide()
            assert result == large_content
            assert len(result) > 100000


class TestGetGuideEncoding:
    """UTF-8 encoding tests for get_guide() API."""

    def test_utf8_encoding(self) -> None:
        """Verify UTF-8 encoding is used for reading guide files.

        Given: Guide file with UTF-8 content
        When: Calling get_guide()
        Then: Content is read with UTF-8 encoding
        """
        utf8_content = "# Agent Guide\n日本語コンテンツ\nEmoji: 🚀"

        with patch("rdetoolkit._agent.Path") as mock_path:
            mock_guide_path = Mock()
            mock_guide_path.exists.return_value = True
            mock_guide_path.read_text.return_value = utf8_content
            mock_path.return_value.parent.__truediv__ = lambda self, other: mock_guide_path

            result = get_guide()
            assert "日本語コンテンツ" in result
            assert "🚀" in result


class TestGetGuideFileSelection:
    """File selection logic tests for get_guide() API."""

    def test_selects_agents_md_by_default(self) -> None:
        """Verify AGENTS.md is selected when detailed=False.

        Given: detailed=False (default)
        When: Calling get_guide()
        Then: AGENTS.md file is selected and read
        """
        with patch("rdetoolkit._agent.Path") as mock_path:
            mock_guide_path = Mock()
            mock_guide_path.exists.return_value = True
            mock_guide_path.read_text.return_value = "AGENTS.md content"

            # Track which file was requested
            requested_file = None

            def track_file(self, other):
                nonlocal requested_file
                requested_file = other
                return mock_guide_path

            mock_path.return_value.parent.__truediv__ = track_file

            get_guide(detailed=False)
            assert requested_file == "AGENTS.md"

    def test_selects_guide_md_when_detailed(self) -> None:
        """Verify guide.md is selected when detailed=True.

        Given: detailed=True
        When: Calling get_guide()
        Then: guide.md file is selected and read
        """
        with patch("rdetoolkit._agent.Path") as mock_path:
            mock_guide_path = Mock()
            mock_guide_path.exists.return_value = True
            mock_guide_path.read_text.return_value = "guide.md content"

            # Track which file was requested
            requested_file = None

            def track_file(self, other):
                nonlocal requested_file
                requested_file = other
                return mock_guide_path

            mock_path.return_value.parent.__truediv__ = track_file

            get_guide(detailed=True)
            assert requested_file == "guide.md"


class TestGetGuideSpecialCharacters:
    """Special character handling tests for get_guide() API."""

    def test_special_characters_in_content(self) -> None:
        """TC-BV-003: Verify special characters are properly handled.

        Given: Guide file with various special characters
        When: Calling get_guide()
        Then: All special characters are preserved correctly
        """
        special_content = """# Guide with Special Chars
        Symbols: @#$%^&*()_+-={}[]|\\:;"'<>,.?/~`
        Math: ∀∃∈∉⊂⊃∩∪∫∑∏√∞
        Arrows: ←→↑↓⇐⇒⇑⇓
        """

        with patch("rdetoolkit._agent.Path") as mock_path:
            mock_guide_path = Mock()
            mock_guide_path.exists.return_value = True
            mock_guide_path.read_text.return_value = special_content
            mock_path.return_value.parent.__truediv__ = lambda self, other: mock_guide_path

            result = get_guide()
            assert "@#$%^&*()" in result
            assert "∀∃∈∉" in result
            assert "←→↑↓" in result


class TestGetGuideContentQuality:
    """Content quality and structure tests for guide files."""

    def test_summary_guide_is_non_empty(self) -> None:
        """Verify summary guide contains substantive content.

        Given: get_guide() function
        When: Calling without detailed parameter
        Then: Returns non-empty, substantive content
        """
        result = get_guide()
        assert len(result) > 100  # Should be substantial
        assert result.strip()  # Should not be only whitespace

    def test_detailed_guide_is_longer_than_summary(self) -> None:
        """Verify detailed guide has more content than summary.

        Given: get_guide() function
        When: Comparing summary and detailed versions
        Then: Detailed version is longer
        """
        summary = get_guide(detailed=False)
        detailed = get_guide(detailed=True)
        assert len(detailed) > len(summary)

    def test_guides_are_different_content(self) -> None:
        """Verify summary and detailed guides have different content.

        Given: get_guide() function
        When: Retrieving both versions
        Then: Content is different (not just length)
        """
        summary = get_guide(detailed=False)
        detailed = get_guide(detailed=True)
        assert summary != detailed

    def test_guide_contains_markdown_formatting(self) -> None:
        """Verify guide content uses Markdown formatting.

        Given: get_guide() function
        When: Retrieving guide content
        Then: Contains Markdown elements (headers, lists, code blocks)
        """
        result = get_guide()
        # Should contain at least headers
        assert "#" in result or "##" in result


class TestGetGuideIntegration:
    """Integration tests for get_guide functionality."""

    def test_package_level_import_and_call(self) -> None:
        """Test: get_agent_guide accessible from package level.

        Given: rdetoolkit package
        When: Accessing via package level get_agent_guide()
        Then: Works identically to direct import
        """
        import rdetoolkit

        # When: Accessing via package
        result = rdetoolkit.get_agent_guide()

        # Then: Should work identically to direct import
        expected = get_guide()
        assert result == expected

    def test_both_guides_accessible_in_same_session(self) -> None:
        """Test: Both guide versions can be retrieved in same session.

        Given: get_guide() function
        When: Retrieving both versions in sequence
        Then: Both work correctly and are different
        """
        # When: Retrieving both versions
        summary = get_guide()
        detailed = get_guide(detailed=True)

        # Then: Both should work and be different
        assert summary != detailed
        assert len(detailed) > len(summary)

        # And: Calling again should return same content (idempotent)
        assert get_guide() == summary
        assert get_guide(detailed=True) == detailed


class TestGetGuideAPIContract:
    """API contract and signature tests."""

    def test_function_signature_has_detailed_parameter(self) -> None:
        """Verify get_guide() has correct function signature.

        Given: get_guide function
        When: Inspecting signature
        Then: Has detailed parameter with default False
        """
        import inspect

        sig = inspect.signature(get_guide)
        assert "detailed" in sig.parameters
        assert sig.parameters["detailed"].default is False

    def test_accepts_keyword_argument(self) -> None:
        """Verify get_guide() accepts detailed as keyword argument.

        Given: get_guide function
        When: Calling with keyword argument
        Then: Works without error
        """
        result = get_guide(detailed=False)
        assert isinstance(result, str)

    def test_accepts_positional_argument(self) -> None:
        """Verify get_guide() accepts detailed as positional argument.

        Given: get_guide function
        When: Calling with positional argument
        Then: Works without error
        """
        result = get_guide(True)
        assert isinstance(result, str)
        # Detailed guide should be longer
        assert len(result) > len(get_guide(False))
