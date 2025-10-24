import os
from unittest.mock import patch

from rdetoolkit.config import get_traceback_settings_from_env
from rdetoolkit.errors import handle_exception
from rdetoolkit.models.config import Config, TracebackSettings


class TestTracebackOffSettings:
    """Test various ways to disable traceback formatting."""

    def test_default_behavior_off(self):
        """Test that by default, traceback formatting is off."""
        # No environment variables set
        with patch.dict(os.environ, {}, clear=True):
            settings = get_traceback_settings_from_env()
            assert settings is None
        default_settings = TracebackSettings()
        assert default_settings.enabled is False

    def test_empty_trace_verbose_off(self):
        """Test that empty TRACE_VERBOSE disables traceback."""
        with patch.dict(os.environ, {'TRACE_VERBOSE': ''}):
            settings = get_traceback_settings_from_env()
            assert settings is None

    def test_explicit_off_values(self):
        """Test that explicit 'off' values disable traceback."""
        off_values = ['off', 'false', 'disable', 'disabled', 'OFF', 'False', 'DISABLE']

        for off_value in off_values:
            with patch.dict(os.environ, {'TRACE_VERBOSE': off_value}):
                settings = get_traceback_settings_from_env()
                assert settings is not None
                assert settings.enabled is False

    def test_handle_exception_with_disabled_traceback(self):
        """Test that handle_exception respects disabled traceback settings."""
        config = Config(
            traceback=TracebackSettings(enabled=False)
        )

        try:
            raise ValueError("Test error")
        except Exception as e:
            result = handle_exception(e, config=config)
            assert result.traceback_info is not None
            assert "<STACKTRACE>" not in result.traceback_info
            assert "Traceback (simplified message):" in result.traceback_info

    def test_handle_exception_with_env_disabled(self):
        """Test that handle_exception respects environment disabled settings."""
        with patch.dict(os.environ, {'TRACE_VERBOSE': 'off'}):
            try:
                raise ValueError("Test error")
            except Exception as e:
                result = handle_exception(e, config=None)
                assert result.traceback_info is not None
                assert "<STACKTRACE>" not in result.traceback_info
                assert "Traceback (simplified message):" in result.traceback_info

    def test_handle_exception_no_config_no_env(self):
        """Test that handle_exception with no config or env uses traditional traceback."""
        with patch.dict(os.environ, {}, clear=True):
            try:
                raise ValueError("Test error")
            except Exception as e:
                result = handle_exception(e, config=None)

                assert result.traceback_info is not None
                assert "<STACKTRACE>" not in result.traceback_info
                assert "Traceback (simplified message):" in result.traceback_info

    def test_config_overrides_env_disable(self):
        """Test that explicit config overrides environment disable."""
        with patch.dict(os.environ, {'TRACE_VERBOSE': 'off'}):
            config = Config(
                traceback=TracebackSettings(enabled=True, format="compact")
            )

            try:
                raise ValueError("Test error")
            except Exception as e:
                result = handle_exception(e, config=config)

                assert result.traceback_info is not None
                assert "<STACKTRACE>" in result.traceback_info
