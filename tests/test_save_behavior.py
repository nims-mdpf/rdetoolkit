"""Tests for save_raw and save_nonshared_raw parameter behavior.

This module tests the behavior of save_raw and save_nonshared_raw parameters
in different combinations and processing modes.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from rdetoolkit.modeproc import copy_input_to_rawfile
from rdetoolkit.models.config import Config, SystemSettings
from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath


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

    def test_copy_input_to_rawfile_creates_directory(self, temp_dir, sample_files):
        """Test that copy_input_to_rawfile creates directory if it doesn't exist."""
        raw_dir = temp_dir / "nonexistent_dir" / "raw"
        assert not raw_dir.exists()

        copy_input_to_rawfile(raw_dir, sample_files)

        assert raw_dir.exists()
        assert raw_dir.is_dir()
        for sample_file in sample_files:
            copied_file = raw_dir / sample_file.name
            assert copied_file.exists()
            assert copied_file.read_text() == sample_file.read_text()

    def test_copy_input_to_rawfile_existing_directory(self, temp_dir, sample_files):
        """Test that copy_input_to_rawfile works with existing directory."""
        raw_dir = temp_dir / "existing_dir"
        raw_dir.mkdir(parents=True, exist_ok=True)

        copy_input_to_rawfile(raw_dir, sample_files)

        for sample_file in sample_files:
            copied_file = raw_dir / sample_file.name
            assert copied_file.exists()
            assert copied_file.read_text() == sample_file.read_text()

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


class TestProcessingModeBehavior:
    """Test save parameter behavior in different processing modes with Pipeline pattern."""

    @pytest.fixture
    def mock_paths(self):
        """Create mock paths for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create sample files
            sample_file = temp_path / "sample.txt"
            sample_file.write_text("Sample content")

            # Mock input paths
            input_paths = Mock(spec=RdeInputDirPaths)
            input_paths.tasksupport = temp_path / "tasksupport"
            input_paths.tasksupport.mkdir(exist_ok=True)

            # Create invoice schema
            (input_paths.tasksupport / "invoice.schema.json").write_text('{"type": "object"}')

            # Mock output paths
            output_paths = Mock(spec=RdeOutputResourcePath)
            output_paths.raw = temp_path / "raw"
            output_paths.nonshared_raw = temp_path / "nonshared_raw"
            output_paths.rawfiles = (sample_file,)
            output_paths.invoice = temp_path / "invoice"
            output_paths.invoice.mkdir(exist_ok=True)
            output_paths.invoice_org = temp_path / "invoice_org.json"
            output_paths.invoice_org.write_text('{"basic": {"dataName": "test"}}')
            output_paths.thumbnail = temp_path / "thumbnail"
            output_paths.main_image = temp_path / "main_image"
            output_paths.meta = temp_path / "meta"
            output_paths.invoice_schema_json = input_paths.tasksupport / "invoice.schema.json"

            yield input_paths, output_paths

    def test_copy_input_with_save_raw_true_save_nonshared_raw_false(self, mock_paths):
        """Test copy behavior with save_raw=True, save_nonshared_raw=False."""
        input_paths, output_paths = mock_paths

        system_settings = SystemSettings(save_raw=True, save_nonshared_raw=False)
        config = Config(system=system_settings)
        input_paths.config = config

        # Simulate the copy behavior based on config
        if config.system.save_raw:
            copy_input_to_rawfile(output_paths.raw, output_paths.rawfiles)

        if config.system.save_nonshared_raw:
            copy_input_to_rawfile(output_paths.nonshared_raw, output_paths.rawfiles)

        # Check that raw directory was created and files copied
        assert output_paths.raw.exists()
        assert (output_paths.raw / "sample.txt").exists()

        # Check that nonshared_raw directory was NOT created
        assert not output_paths.nonshared_raw.exists()

    def test_copy_input_with_save_raw_false_save_nonshared_raw_true(self, mock_paths):
        """Test copy behavior with save_raw=False, save_nonshared_raw=True."""
        input_paths, output_paths = mock_paths

        system_settings = SystemSettings(save_raw=False, save_nonshared_raw=True)
        config = Config(system=system_settings)
        input_paths.config = config

        # Simulate the copy behavior based on config
        if config.system.save_raw:
            copy_input_to_rawfile(output_paths.raw, output_paths.rawfiles)

        if config.system.save_nonshared_raw:
            copy_input_to_rawfile(output_paths.nonshared_raw, output_paths.rawfiles)

        # Check that raw directory was NOT created
        assert not output_paths.raw.exists()

        # Check that nonshared_raw directory was created and files copied
        assert output_paths.nonshared_raw.exists()
        assert (output_paths.nonshared_raw / "sample.txt").exists()

    def test_copy_input_with_save_raw_false_save_nonshared_raw_false(self, mock_paths):
        """Test copy behavior with both save parameters False."""
        input_paths, output_paths = mock_paths

        system_settings = SystemSettings(save_raw=False, save_nonshared_raw=False)
        config = Config(system=system_settings)
        input_paths.config = config

        # Simulate the copy behavior based on config
        if config.system.save_raw:
            copy_input_to_rawfile(output_paths.raw, output_paths.rawfiles)

        if config.system.save_nonshared_raw:
            copy_input_to_rawfile(output_paths.nonshared_raw, output_paths.rawfiles)

        # Check that neither directory was created
        assert not output_paths.raw.exists()
        assert not output_paths.nonshared_raw.exists()

    def test_copy_input_with_both_true(self, mock_paths):
        """Test copy behavior with both save parameters True."""
        input_paths, output_paths = mock_paths

        system_settings = SystemSettings(save_raw=True, save_nonshared_raw=True)
        config = Config(system=system_settings)
        input_paths.config = config

        # Simulate the copy behavior based on config
        if config.system.save_raw:
            copy_input_to_rawfile(output_paths.raw, output_paths.rawfiles)

        if config.system.save_nonshared_raw:
            copy_input_to_rawfile(output_paths.nonshared_raw, output_paths.rawfiles)

        # Check that both directories were created
        assert output_paths.raw.exists()
        assert output_paths.nonshared_raw.exists()
        assert (output_paths.raw / "sample.txt").exists()
        assert (output_paths.nonshared_raw / "sample.txt").exists()


class TestPipelineIntegration:
    """Test integration with Pipeline pattern."""

    @patch('rdetoolkit.modeproc.PipelineFactory')
    def test_multifile_mode_uses_pipeline(self, mock_factory):
        """Test that multifile_mode_process uses PipelineFactory."""
        from rdetoolkit.modeproc import multifile_mode_process

        # Setup mocks
        mock_pipeline = MagicMock()
        mock_pipeline.execute.return_value = Mock(status="success")
        mock_factory.create_multifile_pipeline.return_value = mock_pipeline

        # Create mock inputs
        input_paths = Mock(spec=RdeInputDirPaths)
        output_paths = Mock(spec=RdeOutputResourcePath)

        # Call the function
        result = multifile_mode_process("0001", input_paths, output_paths)

        # Verify pipeline was created and executed
        mock_factory.create_multifile_pipeline.assert_called_once()
        mock_pipeline.execute.assert_called_once()
        assert result.status == "success"


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_copy_input_to_rawfile_empty_files(self):
        """Test copy_input_to_rawfile with empty file list."""
        with tempfile.TemporaryDirectory() as temp_dir:
            raw_dir = Path(temp_dir) / "raw"

            copy_input_to_rawfile(raw_dir, ())

            # Directory should be created even with no files
            assert raw_dir.exists()
            assert raw_dir.is_dir()

    def test_copy_input_to_rawfile_nested_directory(self):
        """Test copy_input_to_rawfile with deeply nested directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create a sample file
            sample_file = temp_path / "sample.txt"
            sample_file.write_text("Sample content")

            # Create deeply nested target directory
            raw_dir = temp_path / "level1" / "level2" / "level3" / "raw"

            copy_input_to_rawfile(raw_dir, (sample_file,))

            assert raw_dir.exists()
            assert (raw_dir / "sample.txt").exists()

    def test_config_validation_allows_both_false(self):
        """Test that configuration validation allows both parameters to be False."""
        # This should not raise any validation errors
        system_settings = SystemSettings(save_raw=False, save_nonshared_raw=False)
        config = Config(system=system_settings)

        # Validate the model (this would raise ValidationError if validation failed)
        assert config.model_validate(config.model_dump())

        assert config.system.save_raw is False
        assert config.system.save_nonshared_raw is False
