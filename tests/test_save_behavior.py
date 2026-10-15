"""Tests for save_raw and save_nonshared_raw parameter behavior.

This module tests the behavior of save_raw and save_nonshared_raw parameters
in different combinations and processing modes.
"""

import tempfile
from pathlib import Path

import pytest

from rdetoolkit.models.config import Config, SystemSettings


class TestSaveParameterDefaults:
    """Test default values of save parameters."""

    def test_default_save_raw_is_false(self):
        """Test that save_raw defaults to False."""
        system_settings = SystemSettings()
        assert system_settings.save_raw is False

    def test_default_save_nonshared_raw_is_true(self):
        """Test that save_nonshared_raw defaults to True."""
        system_settings = SystemSettings()
        assert system_settings.save_nonshared_raw is True

    def test_config_default_values(self):
        """Test that Config uses correct default values."""
        config = Config()
        assert config.system.save_raw is False
        assert config.system.save_nonshared_raw is True


class TestSaveParameterCombinations:
    """Test all combinations of save_raw and save_nonshared_raw parameters."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def sample_files(self, temp_dir):
        """Create sample files for testing."""
        files = []
        for i in range(3):
            file_path = temp_dir / f"sample_{i}.txt"
            file_path.write_text(f"Sample content {i}")
            files.append(file_path)
        return tuple(files)


    def test_save_raw_true_save_nonshared_raw_true(self, temp_dir):
        """Test save_raw=True, save_nonshared_raw=True combination."""
        system_settings = SystemSettings(save_raw=True, save_nonshared_raw=True)
        config = Config(system=system_settings)

        # Verify the configuration
        assert config.system.save_raw is True
        assert config.system.save_nonshared_raw is True

    def test_save_raw_true_save_nonshared_raw_false(self, temp_dir):
        """Test save_raw=True, save_nonshared_raw=False combination."""
        system_settings = SystemSettings(save_raw=True, save_nonshared_raw=False)
        config = Config(system=system_settings)

        # Verify the configuration
        assert config.system.save_raw is True
        assert config.system.save_nonshared_raw is False

    def test_save_raw_false_save_nonshared_raw_true(self, temp_dir):
        """Test save_raw=False, save_nonshared_raw=True combination."""
        system_settings = SystemSettings(save_raw=False, save_nonshared_raw=True)
        config = Config(system=system_settings)

        # Verify the configuration
        assert config.system.save_raw is False
        assert config.system.save_nonshared_raw is True

    def test_save_raw_false_save_nonshared_raw_false(self, temp_dir):
        """Test save_raw=False, save_nonshared_raw=False combination."""
        system_settings = SystemSettings(save_raw=False, save_nonshared_raw=False)
        config = Config(system=system_settings)

        # Verify the configuration - both can be False
        assert config.system.save_raw is False
        assert config.system.save_nonshared_raw is False


class TestEdgeCases:
    """Test edge cases and error conditions."""


    def test_config_validation_allows_both_false(self):
        """Test that configuration validation allows both parameters to be False."""
        # This should not raise any validation errors
        system_settings = SystemSettings(save_raw=False, save_nonshared_raw=False)
        config = Config(system=system_settings)

        # Validate the model (this would raise ValidationError if validation failed)
        assert config.model_validate(config.model_dump())

        assert config.system.save_raw is False
        assert config.system.save_nonshared_raw is False
