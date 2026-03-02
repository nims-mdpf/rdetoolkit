"""Tests for agent-guide CLI command."""

import re
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from rdetoolkit.cli.app import app

runner = CliRunner()


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_escape.sub("", text)


class TestAgentGuideCLISuccess:
    """Test successful agent-guide command execution."""

    def test_agent_guide_default_shows_summary__tc_ep_001(self):
        """Test: agent-guide without flags shows summary guide.

        TC-EP-001: Normal case with default arguments.
        """
        # Given: CLI app
        # When: Running agent-guide command
        result = runner.invoke(app, ["agent-guide"])

        # Then: Should succeed
        assert result.exit_code == 0, f"Command failed: {result.stdout}"

        # And: Should display summary content
        assert len(result.stdout) > 0
        assert 1000 < len(result.stdout) < 4000, f"Summary output size {len(result.stdout)} bytes out of expected range"

        # And: Should contain expected content
        assert "rdetoolkit" in result.stdout.lower()

    def test_agent_guide_detailed_shows_full_guide__tc_ep_002(self):
        """Test: agent-guide --detailed shows detailed guide.

        TC-EP-002: Normal case with --detailed flag.
        """
        # Given: CLI app
        # When: Running with --detailed flag
        result = runner.invoke(app, ["agent-guide", "--detailed"])

        # Then: Should succeed
        assert result.exit_code == 0, f"Command failed: {result.stdout}"

        # And: Should display detailed content
        assert len(result.stdout) > 0
        assert 4000 < len(result.stdout) < 8000, f"Detailed output size {len(result.stdout)} bytes out of expected range"

        # And: Should be longer than summary
        summary_result = runner.invoke(app, ["agent-guide"])
        assert len(result.stdout) > len(summary_result.stdout)

    def test_agent_guide_help_shows_usage__tc_ep_003(self):
        """Test: agent-guide --help shows usage information.

        TC-EP-003: Help text display.
        """
        # Given: CLI app
        # When: Running with --help flag
        result = runner.invoke(app, ["agent-guide", "--help"])

        # Then: Should succeed
        assert result.exit_code == 0

        # And: Should display help text (strip ANSI codes for CI compatibility)
        output = strip_ansi(result.stdout)
        assert "Display agent guide for AI coding assistants" in output
        assert "--detailed" in output
        assert "advanced patterns" in output.lower()


class TestAgentGuideCLIFailures:
    """Test agent-guide command error cases."""

    def test_agent_guide_missing_file_exits_with_error__tc_ep_004(self):
        """Test: agent-guide exits with error when guide file missing.

        TC-EP-004: File system error - file not found.
        """
        # Given: Mock get_guide to raise FileNotFoundError
        with patch("rdetoolkit._agent.get_guide") as mock_get_guide:
            mock_get_guide.side_effect = FileNotFoundError("Guide file not found: /path/to/guide.md")

            # When: Running command
            result = runner.invoke(app, ["agent-guide"])

            # Then: Should exit with error code
            assert result.exit_code == 1

            # And: Should display error message
            assert "Error: Guide file not found" in result.stderr

    def test_agent_guide_unreadable_file_exits_with_error__tc_ep_005(self):
        """Test: agent-guide exits with error when file cannot be read.

        TC-EP-005: I/O error - file read failure.
        """
        # Given: Mock get_guide to raise OSError
        with patch("rdetoolkit._agent.get_guide") as mock_get_guide:
            mock_get_guide.side_effect = OSError("Permission denied: /path/to/guide.md")

            # When: Running command
            result = runner.invoke(app, ["agent-guide"])

            # Then: Should exit with error code
            assert result.exit_code == 1

            # And: Should display error message
            assert "Error: Failed to read guide file" in result.stderr

    def test_agent_guide_invalid_flag_exits_with_error__tc_ep_006(self):
        """Test: agent-guide with invalid flag shows error.

        TC-EP-006: Invalid command-line argument.
        """
        # Given: CLI app
        # When: Running with invalid flag
        result = runner.invoke(app, ["agent-guide", "--invalid-flag"])

        # Then: Should exit with error code (Typer returns 2 for bad arguments)
        assert result.exit_code != 0

        # And: Should display error message (Typer outputs to stderr for invalid arguments)
        assert "Error" in result.stderr or "error" in result.stderr.lower() or "No such option" in result.stderr


class TestAgentGuideCLIBoundaries:
    """Test boundary conditions for CLI command."""

    def test_agent_guide_empty_output_succeeds__tc_bv_001(self):
        """Test: agent-guide handles empty guide content.

        TC-BV-001: Edge case - empty file content.
        """
        # Given: Mock get_guide to return empty string
        with patch("rdetoolkit._agent.get_guide") as mock_get_guide:
            mock_get_guide.return_value = ""

            # When: Running command
            result = runner.invoke(app, ["agent-guide"])

            # Then: Should succeed (empty output is valid)
            assert result.exit_code == 0
            assert result.stdout in {"\n", ""}

    def test_agent_guide_large_output_succeeds__tc_bv_002(self):
        """Test: agent-guide handles very large guide content.

        TC-BV-002: Edge case - large file content.
        """
        # Given: Mock get_guide to return large content
        large_content = "# Guide\n" + ("Content line\n" * 5000)
        with patch("rdetoolkit._agent.get_guide") as mock_get_guide:
            mock_get_guide.return_value = large_content

            # When: Running command
            result = runner.invoke(app, ["agent-guide"])

            # Then: Should succeed and output full content
            assert result.exit_code == 0
            assert len(result.stdout) >= len(large_content)

    def test_agent_guide_output_to_stdout__tc_bv_003(self):
        """Test: agent-guide outputs to stdout, not stderr.

        TC-BV-003: Output stream validation.
        """
        # Given: CLI app
        # When: Running command with CliRunner (captures streams)
        result = runner.invoke(app, ["agent-guide"])

        # Then: Output should be in stdout
        assert result.exit_code == 0
        assert len(result.stdout) > 0
        # Success output should go to stdout
        assert "rdetoolkit" in result.stdout.lower()

    def test_agent_guide_errors_to_stderr__tc_bv_004(self):
        """Test: agent-guide errors go to stderr, not stdout.

        TC-BV-004: Error stream validation.
        """
        # Given: Mock get_guide to raise error
        with patch("rdetoolkit._agent.get_guide") as mock_get_guide:
            mock_get_guide.side_effect = FileNotFoundError("Test error")

            # When: Running command
            result = runner.invoke(app, ["agent-guide"])

            # Then: Should exit with error
            assert result.exit_code == 1
            # Error message should be in stderr
            assert "Error: Guide file not found" in result.stderr


class TestAgentGuideCLIIntegration:
    """Integration tests for agent-guide command."""

    def test_agent_guide_via_python_module__tc_int_001(self):
        """Test: agent-guide accessible via python -m rdetoolkit.

        TC-INT-001: Python module invocation.
        """
        # Given: Package installed
        # When: Running via python -m
        result = subprocess.run(
            ["python", "-m", "rdetoolkit", "agent-guide"],
            capture_output=True,
            text=True,
            check=False,
        )

        # Then: Should succeed
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert len(result.stdout) > 0
        assert "rdetoolkit" in result.stdout.lower()

    def test_agent_guide_detailed_via_python_module__tc_int_002(self):
        """Test: agent-guide --detailed via python -m rdetoolkit.

        TC-INT-002: Python module invocation with --detailed.
        """
        # Given: Package installed
        # When: Running via python -m with --detailed
        result = subprocess.run(
            ["python", "-m", "rdetoolkit", "agent-guide", "--detailed"],
            capture_output=True,
            text=True,
            check=False,
        )

        # Then: Should succeed
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert len(result.stdout) > 0

        # And: Should be longer than summary
        summary_result = subprocess.run(
            ["python", "-m", "rdetoolkit", "agent-guide"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert len(result.stdout) > len(summary_result.stdout)

    def test_agent_guide_output_redirectable__tc_int_003(self):
        """Test: agent-guide output can be redirected to file.

        TC-INT-003: Output redirection capability.
        """
        # Given: Package installed and temp file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as tmp:
            tmp_path = tmp.name

        try:
            # When: Running command with output redirection
            result = subprocess.run(
                ["python", "-m", "rdetoolkit", "agent-guide"],
                capture_output=True,
                text=True,
                check=False,
            )

            # And: Writing to file
            Path(tmp_path).write_text(result.stdout, encoding="utf-8")

            # Then: File should contain guide content
            content = Path(tmp_path).read_text(encoding="utf-8")
            assert len(content) > 0
            assert "rdetoolkit" in content.lower()

        finally:
            # Cleanup
            Path(tmp_path).unlink(missing_ok=True)

    def test_agent_guide_in_command_list__tc_int_004(self):
        """Test: agent-guide appears in rdetoolkit command list.

        TC-INT-004: Command discoverability.
        """
        # Given: Package installed
        # When: Running rdetoolkit --help
        result = subprocess.run(
            ["python", "-m", "rdetoolkit", "--help"],
            capture_output=True,
            text=True,
            check=False,
        )

        # Then: Should list agent-guide command
        assert result.returncode == 0
        assert "agent-guide" in result.stdout


class TestAgentGuideCLIContract:
    """Test CLI command contract and behavior."""

    def test_agent_guide_consistent_output__tc_contract_001(self):
        """Test: Multiple calls return consistent output.

        TC-CONTRACT-001: Output consistency verification.
        """
        # Given: CLI app
        # When: Running command multiple times
        result1 = runner.invoke(app, ["agent-guide"])
        result2 = runner.invoke(app, ["agent-guide"])

        # Then: Output should be consistent
        assert result1.exit_code == result2.exit_code
        assert result1.stdout == result2.stdout

    def test_agent_guide_both_modes_in_same_session__tc_contract_002(self):
        """Test: Summary and detailed can be called in same session.

        TC-CONTRACT-002: Multi-mode session support.
        """
        # Given: CLI app
        # When: Running both modes
        summary = runner.invoke(app, ["agent-guide"])
        detailed = runner.invoke(app, ["agent-guide", "--detailed"])

        # Then: Both should succeed
        assert summary.exit_code == 0
        assert detailed.exit_code == 0

        # And: Outputs should differ
        assert summary.stdout != detailed.stdout
        assert len(detailed.stdout) > len(summary.stdout)
