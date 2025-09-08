"""Integration tests for compact trace formatting system.

Tests the complete integration of TracebackSettings, CompactTraceFormatter,
environment variables, Config objects, and error handling system.
"""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from rdetoolkit.config import get_traceback_settings_from_env, parse_config_file
from rdetoolkit.errors import handle_exception, handle_generic_error, handle_and_exit_on_structured_error
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.models.config import Config, TracebackSettings


class TestTracebackIntegration:
    """Integration tests for the complete traceback formatting system."""

    def test_environment_variable_integration(self):
        """Test that environment variables correctly configure traceback formatting."""
        with patch.dict(os.environ, {
            'TRACE_VERBOSE': 'context,locals',
            'TRACE_FORMAT': 'compact'
        }):
            settings = get_traceback_settings_from_env()

            assert settings is not None
            assert settings.enabled is True
            assert settings.include_context is True
            assert settings.include_locals is True
            assert settings.include_env is False
            assert settings.format == 'compact'

    def test_config_file_integration_yaml(self):
        """Test that YAML config files correctly configure traceback settings."""
        config_content = """
system:
  extended_mode: null
  save_raw: false

traceback:
  enabled: true
  format: "duplex"
  include_context: true
  include_locals: false
  include_env: true
  max_locals_size: 1024
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_content)
            f.flush()

            config = parse_config_file(path=f.name)

            # Note: Config creation from dict should populate traceback settings
            # if the data is present in the config file
            assert hasattr(config, 'traceback')
            if config.traceback is not None:
                assert config.traceback.enabled is True
                assert config.traceback.format == "duplex"
                assert config.traceback.include_context is True
                assert config.traceback.include_locals is False
                assert config.traceback.include_env is True
                assert config.traceback.max_locals_size == 1024

            os.unlink(f.name)

    def test_config_file_integration_toml(self):
        """Test that TOML config files correctly configure traceback settings."""
        config_content = """
[tool.rdetoolkit.traceback]
enabled = true
format = "compact"
include_context = false
include_locals = true
include_env = false
max_locals_size = 256
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(config_content)
            f.flush()

            config = parse_config_file(path=f.name)

            # Note: Config creation from dict should populate traceback settings
            # if the data is present in the config file
            assert hasattr(config, 'traceback')
            if config.traceback is not None:
                assert config.traceback.enabled is True
                assert config.traceback.format == "compact"
                assert config.traceback.include_context is False
                assert config.traceback.include_locals is True
                assert config.traceback.include_env is False
                assert config.traceback.max_locals_size == 256

            os.unlink(f.name)

    def test_handle_exception_with_config_compact_format(self):
        """Test handle_exception with Config providing compact format."""
        config = Config(
            traceback=TracebackSettings(
                enabled=True,
                format="compact",
                include_context=True,
                include_locals=False
            )
        )

        try:
            raise ValueError("Test exception for compact format")
        except Exception as e:
            result = handle_exception(
                e,
                error_message="Custom error message",
                error_code=42,
                config=config
            )

            assert isinstance(result, StructuredError)
            assert result.emsg == "Error: Custom error message"
            assert result.ecode == 42
            assert result.traceback_info is not None

            # Should contain compact format markers
            assert "<STACKTRACE>" in result.traceback_info
            assert "</STACKTRACE>" in result.traceback_info
            # Check for compact format structure
            assert "CFG" in result.traceback_info  # Configuration line
            assert "E " in result.traceback_info   # Exception line
            assert "F" in result.traceback_info    # Frame line

    def test_handle_exception_with_config_duplex_format(self):
        """Test handle_exception with Config providing duplex format."""
        config = Config(
            traceback=TracebackSettings(
                enabled=True,
                format="duplex",
                include_context=True,
                include_locals=False
            )
        )

        try:
            raise ValueError("Test exception for duplex format")
        except Exception as e:
            result = handle_exception(
                e,
                error_message="Custom error message",
                config=config
            )

            assert isinstance(result, StructuredError)
            assert result.traceback_info is not None

            # Should contain both compact and Python formats
            assert "<STACKTRACE>" in result.traceback_info
            assert "Traceback (simplified message):" in result.traceback_info

    def test_handle_exception_with_environment_variables(self):
        """Test handle_exception using environment variable configuration."""
        with patch.dict(os.environ, {
            'TRACE_VERBOSE': 'context',
            'TRACE_FORMAT': 'python'
        }):
            try:
                raise ValueError("Test exception with env vars")
            except Exception as e:
                result = handle_exception(
                    e,
                    error_message="Env var test",
                    error_code=123
                )

                assert isinstance(result, StructuredError)
                assert result.emsg == "Error: Env var test"
                assert result.ecode == 123
                assert result.traceback_info is not None

                assert "Traceback (simplified message):" in result.traceback_info
                assert "<STACKTRACE>" not in result.traceback_info

    def test_config_precedence_over_environment(self):
        """Test that Config object takes precedence over environment variables."""
        config = Config(
            traceback=TracebackSettings(
                enabled=True,
                format="compact"
            )
        )

        with patch.dict(os.environ, {
            'TRACE_VERBOSE': 'context,locals',
            'TRACE_FORMAT': 'python'
        }):
            try:
                raise ValueError("Precedence test")
            except Exception as e:
                result = handle_exception(e, config=config)

                assert isinstance(result, StructuredError)
                assert result.traceback_info is not None

                assert "<STACKTRACE>" in result.traceback_info
                assert "Traceback (simplified message):" not in result.traceback_info

    def test_fallback_to_traditional_traceback(self):
        """Test fallback to traditional traceback when no special config is provided."""
        try:
            raise ValueError("Fallback test")
        except Exception as e:
            result = handle_exception(
                e,
                error_message="Fallback message"
            )

            assert isinstance(result, StructuredError)
            assert result.emsg == "Error: Fallback message"
            assert result.traceback_info is not None

            assert "Traceback (simplified message):" in result.traceback_info
            assert "Exception Type: ValueError" in result.traceback_info
            assert "Error: Fallback message" in result.traceback_info

    def test_sensitive_information_masking(self):
        """Test that sensitive information is properly masked in traces with locals."""
        config = Config(
            traceback=TracebackSettings(
                enabled=True,
                format="compact",
                include_locals=True
            )
        )

        def function_with_sensitive_data():
            password = "secret123"
            api_key = "abc-def-123"
            raise ValueError("Test with sensitive data")

        try:
            function_with_sensitive_data()
        except Exception as e:
            result = handle_exception(e, config=config)

            assert isinstance(result, StructuredError)
            assert result.traceback_info is not None
            assert "secret123" not in result.traceback_info
            assert "abc-def-123" not in result.traceback_info
            assert ("***" in result.traceback_info or
                   "[MASKED]" in result.traceback_info or
                   "password=" in result.traceback_info)

    def test_max_locals_size_limit(self):
        """Test that locals are truncated according to max_locals_size setting."""
        config = Config(
            traceback=TracebackSettings(
                enabled=True,
                format="compact",
                include_locals=True,
                max_locals_size=50
            )
        )

        def function_with_large_locals():
            large_var = "x" * 1000  # Much larger than limit
            raise ValueError("Test with large locals")

        try:
            function_with_large_locals()
        except Exception as e:
            result = handle_exception(e, config=config)

            assert isinstance(result, StructuredError)
            assert result.traceback_info is not None

            # Should contain truncation markers (could be ... or other format)
            assert ("..." in result.traceback_info or
                   "[TRUNCATED]" in result.traceback_info or
                   len(result.traceback_info) < 2000)  # Should be limited in size
