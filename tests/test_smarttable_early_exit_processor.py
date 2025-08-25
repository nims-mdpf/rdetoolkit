"""Test SmartTableEarlyExitProcessor functionality."""

from pathlib import Path
from unittest.mock import Mock, patch
import pytest
import tempfile
import os
import json

from rdetoolkit.processing.processors.smarttable_early_exit import SmartTableEarlyExitProcessor
from rdetoolkit.exceptions import SkipRemainingProcessorsError


class TestSmartTableEarlyExitProcessor:
    """Test suite for SmartTableEarlyExitProcessor functionality."""

    def test_process_not_smarttable_mode(self):
        """Test processing when not in SmartTable mode."""
        processor = SmartTableEarlyExitProcessor()

        # Create mock context
        mock_context = Mock()
        mock_context.is_smarttable_mode = False
        mock_context.resource_paths.rawfiles = (
            Path("/data/inputdata/smarttable_test.xlsx"),
            Path("/data/temp/file.csv"),
        )

        # Should not raise exception when not in SmartTable mode
        processor.process(mock_context)

    @patch('rdetoolkit.processing.processors.smarttable_early_exit.MetadataValidator')
    @patch('rdetoolkit.processing.processors.smarttable_early_exit.InvoiceValidator')
    def test_process_with_original_smarttable_file_save_enabled(self, mock_invoice_validator, mock_meta_validator):
        """Test processing when rawfiles contains original SmartTable file and save_table_file is enabled."""
        processor = SmartTableEarlyExitProcessor()

        # Create mock context with save_table_file enabled
        mock_context = Mock()
        mock_context.is_smarttable_mode = True
        mock_context.resource_paths.rawfiles = (
            Path("/data/inputdata/smarttable_test.xlsx"),
        )
        mock_context.srcpaths.config.smarttable = Mock()
        mock_context.srcpaths.config.smarttable.save_table_file = True

        # Create actual temporary invoice file
        with tempfile.TemporaryDirectory() as temp_dir:
            invoice_path = Path(temp_dir) / "invoice.json"
            initial_invoice_data = {
                "basic": {
                    "dataName": "original_data_name",
                    "description": "Test description"
                },
                "custom": {}
            }
            
            # Write initial invoice file
            import json
            with open(invoice_path, 'w', encoding='utf-8') as f:
                json.dump(initial_invoice_data, f, ensure_ascii=False, indent=2)
            
            mock_context.invoice_dst_filepath = invoice_path

            # Mock system settings to avoid copying during test
            mock_context.srcpaths.config.system.save_raw = False
            mock_context.srcpaths.config.system.save_nonshared_raw = False

            # Mock validators
            mock_meta_validator.return_value.process.return_value = None
            mock_invoice_validator.return_value.process.return_value = None

            # Should raise SkipRemainingProcessorsError when original SmartTable file is found
            with pytest.raises(SkipRemainingProcessorsError) as exc_info:
                processor.process(mock_context)

            # Verify dataName was updated in the actual file
            with open(invoice_path, 'r', encoding='utf-8') as f:
                updated_invoice = json.load(f)
            
            assert updated_invoice['basic']['dataName'] == 'smarttable_test.xlsx'
            assert updated_invoice['basic']['description'] == "Test description"  # Other fields preserved

            # Verify validators were called
            mock_meta_validator.return_value.process.assert_called_once_with(mock_context)
            mock_invoice_validator.return_value.process.assert_called_once_with(mock_context)

            assert "SmartTable file processing and validation completed" in str(exc_info.value)

    @patch('rdetoolkit.processing.processors.smarttable_early_exit.MetadataValidator')
    @patch('rdetoolkit.processing.processors.smarttable_early_exit.InvoiceValidator')
    def test_process_with_original_smarttable_file_save_disabled(self, mock_invoice_validator, mock_meta_validator):
        """Test processing when rawfiles contains original SmartTable file but save_table_file is disabled."""
        processor = SmartTableEarlyExitProcessor()

        # Create mock context with save_table_file disabled
        mock_context = Mock()
        mock_context.is_smarttable_mode = True
        mock_context.resource_paths.rawfiles = (
            Path("/data/inputdata/smarttable_test.xlsx"),
        )
        mock_context.srcpaths.config.smarttable = Mock()
        mock_context.srcpaths.config.smarttable.save_table_file = False

        # Mock validators
        mock_meta_validator.return_value.process.return_value = None
        mock_invoice_validator.return_value.process.return_value = None

        # Should still raise SkipRemainingProcessorsError even when save_table_file is False (validation still runs)
        with pytest.raises(SkipRemainingProcessorsError):
            processor.process(mock_context)
        
        # Verify validators were called
        mock_meta_validator.return_value.process.assert_called_once_with(mock_context)
        mock_invoice_validator.return_value.process.assert_called_once_with(mock_context)

    def test_process_with_csv_files_only(self):
        """Test processing when rawfiles contains only CSV files."""
        processor = SmartTableEarlyExitProcessor()

        # Create mock context
        mock_context = Mock()
        mock_context.is_smarttable_mode = True
        mock_context.resource_paths.rawfiles = (
            Path("/data/temp/fsmarttable_test_0000.csv"),
            Path("/data/temp/extracted_file.txt"),
        )

        # Should not raise exception when no original SmartTable file
        processor.process(mock_context)

    @patch('rdetoolkit.processing.processors.smarttable_early_exit.MetadataValidator')
    @patch('rdetoolkit.processing.processors.smarttable_early_exit.InvoiceValidator')
    def test_process_with_multiple_files_including_smarttable(self, mock_invoice_validator, mock_meta_validator):
        """Test processing with multiple files including SmartTable file."""
        processor = SmartTableEarlyExitProcessor()

        # Create mock context with save_table_file enabled
        mock_context = Mock()
        mock_context.is_smarttable_mode = True
        mock_context.resource_paths.rawfiles = (
            Path("/data/inputdata/smarttable_experiment.csv"),
            Path("/data/temp/fsmarttable_test_0000.csv"),
            Path("/data/temp/other_file.txt"),
        )
        mock_context.srcpaths.config.smarttable = Mock()
        mock_context.srcpaths.config.smarttable.save_table_file = True

        # Create actual temporary invoice file
        with tempfile.TemporaryDirectory() as temp_dir:
            invoice_path = Path(temp_dir) / "invoice.json"
            initial_invoice_data = {
                "basic": {
                    "dataName": "original_data_name",
                    "description": "Test description"
                },
                "custom": {}
            }
            
            # Write initial invoice file
            import json
            with open(invoice_path, 'w', encoding='utf-8') as f:
                json.dump(initial_invoice_data, f, ensure_ascii=False, indent=2)
            
            mock_context.invoice_dst_filepath = invoice_path

            # Mock system settings to avoid copying during test
            mock_context.srcpaths.config.system.save_raw = False
            mock_context.srcpaths.config.system.save_nonshared_raw = False

            # Mock validators
            mock_meta_validator.return_value.process.return_value = None
            mock_invoice_validator.return_value.process.return_value = None

            # Should raise SkipRemainingProcessorsError when original SmartTable file is found
            with pytest.raises(SkipRemainingProcessorsError) as exc_info:
                processor.process(mock_context)

            # Verify dataName was updated with first SmartTable file
            with open(invoice_path, 'r', encoding='utf-8') as f:
                updated_invoice = json.load(f)
            
            assert updated_invoice['basic']['dataName'] == 'smarttable_experiment.csv'

        # Verify validators were called
        mock_meta_validator.return_value.process.assert_called_once_with(mock_context)
        mock_invoice_validator.return_value.process.assert_called_once_with(mock_context)

        assert "SmartTable file processing and validation completed" in str(exc_info.value)

    def test_is_original_smarttable_file_true_cases(self):
        """Test identification of original SmartTable files."""
        processor = SmartTableEarlyExitProcessor()

        # Test valid SmartTable files
        true_cases = [
            Path("/data/inputdata/smarttable_test.xlsx"),
            Path("/data/inputdata/smarttable_experiment.csv"),
            Path("/project/data/inputdata/smarttable_data.tsv"),
            Path("/path/to/inputdata/smarttable_sample.XLSX"),  # Case insensitive
        ]

        for test_path in true_cases:
            assert processor._is_original_smarttable_file(test_path) is True

    def test_is_original_smarttable_file_false_cases(self):
        """Test identification of non-SmartTable files."""
        processor = SmartTableEarlyExitProcessor()

        # Test invalid cases
        false_cases = [
            Path("/data/temp/fsmarttable_test_0000.csv"),  # Generated CSV
            Path("/data/raw/smarttable_test.xlsx"),  # Not in inputdata
            Path("/data/inputdata/table_test.xlsx"),  # No smarttable_ prefix
            Path("/data/inputdata/smarttable_test.txt"),  # Unsupported extension
            Path("/data/inputdata/other_file.csv"),  # No smarttable_ prefix
            Path("/data/output/smarttable_test.xlsx"),  # Not in inputdata
        ]

        for test_path in false_cases:
            assert processor._is_original_smarttable_file(test_path) is False

    def test_is_original_smarttable_file_edge_cases(self):
        """Test edge cases for SmartTable file identification."""
        processor = SmartTableEarlyExitProcessor()

        # Test edge cases
        edge_cases = [
            (Path("/data/inputdata/smarttable_.xlsx"), True),  # Empty name part
            (Path("/data/inputdata/smarttable_a.csv"), True),  # Single char name
            (Path("/inputdata/smarttable_test.xlsx"), True),  # Root inputdata
            (Path("/data/inputdata/nested/smarttable_test.xlsx"), True),  # Nested under inputdata
        ]

        for test_path, expected in edge_cases:
            assert processor._is_original_smarttable_file(test_path) is expected

    @patch('rdetoolkit.processing.processors.smarttable_early_exit.MetadataValidator')
    @patch('rdetoolkit.processing.processors.smarttable_early_exit.InvoiceValidator')
    def test_process_with_tsv_file(self, mock_invoice_validator, mock_meta_validator):
        """Test processing with TSV SmartTable file."""
        processor = SmartTableEarlyExitProcessor()

        # Create mock context with save_table_file enabled
        mock_context = Mock()
        mock_context.is_smarttable_mode = True
        mock_context.resource_paths.rawfiles = (
            Path("/data/inputdata/smarttable_data.tsv"),
        )
        mock_context.srcpaths.config.smarttable = Mock()
        mock_context.srcpaths.config.smarttable.save_table_file = True

        # Create actual temporary invoice file
        with tempfile.TemporaryDirectory() as temp_dir:
            invoice_path = Path(temp_dir) / "invoice.json"
            initial_invoice_data = {
                "basic": {
                    "dataName": "original_data_name",
                    "description": "Test description"
                },
                "custom": {}
            }
            
            # Write initial invoice file
            import json
            with open(invoice_path, 'w', encoding='utf-8') as f:
                json.dump(initial_invoice_data, f, ensure_ascii=False, indent=2)
            
            mock_context.invoice_dst_filepath = invoice_path

            # Mock system settings to avoid copying during test
            mock_context.srcpaths.config.system.save_raw = False
            mock_context.srcpaths.config.system.save_nonshared_raw = False

            # Mock validators
            mock_meta_validator.return_value.process.return_value = None
            mock_invoice_validator.return_value.process.return_value = None

            # Should raise SkipRemainingProcessorsError for TSV files too
            with pytest.raises(SkipRemainingProcessorsError):
                processor.process(mock_context)

            # Verify dataName was updated
            with open(invoice_path, 'r', encoding='utf-8') as f:
                updated_invoice = json.load(f)
            
            assert updated_invoice['basic']['dataName'] == 'smarttable_data.tsv'

        # Verify validators were called
        mock_meta_validator.return_value.process.assert_called_once_with(mock_context)
        mock_invoice_validator.return_value.process.assert_called_once_with(mock_context)

    def test_process_with_empty_rawfiles(self):
        """Test processing with empty rawfiles."""
        processor = SmartTableEarlyExitProcessor()

        # Create mock context
        mock_context = Mock()
        mock_context.is_smarttable_mode = True
        mock_context.resource_paths.rawfiles = ()

        # Should not raise exception when rawfiles is empty
        processor.process(mock_context)

    def test_case_insensitive_extension_matching(self):
        """Test that extensions are matched case-insensitively."""
        processor = SmartTableEarlyExitProcessor()

        test_cases = [
            Path("/data/inputdata/smarttable_test.XLSX"),
            Path("/data/inputdata/smarttable_test.Csv"),
            Path("/data/inputdata/smarttable_test.TSV"),
            Path("/data/inputdata/smarttable_test.xlsx"),
            Path("/data/inputdata/smarttable_test.csv"),
            Path("/data/inputdata/smarttable_test.tsv"),
        ]

        for test_path in test_cases:
            assert processor._is_original_smarttable_file(test_path) is True

    @patch('rdetoolkit.processing.processors.smarttable_early_exit.MetadataValidator')
    @patch('rdetoolkit.processing.processors.smarttable_early_exit.InvoiceValidator')
    def test_process_with_smarttable_config_none(self, mock_invoice_validator, mock_meta_validator):
        """Test processing when smarttable config is None."""
        processor = SmartTableEarlyExitProcessor()

        # Create mock context with smarttable config as None
        mock_context = Mock()
        mock_context.is_smarttable_mode = True
        mock_context.resource_paths.rawfiles = (
            Path("/data/inputdata/smarttable_test.xlsx"),
        )
        mock_context.srcpaths.config.smarttable = None

        # Mock validators
        mock_meta_validator.return_value.process.return_value = None
        mock_invoice_validator.return_value.process.return_value = None

        # Should still raise SkipRemainingProcessorsError (validation still runs regardless of config)
        with pytest.raises(SkipRemainingProcessorsError):
            processor.process(mock_context)
        
        # Verify validators were called
        mock_meta_validator.return_value.process.assert_called_once_with(mock_context)
        mock_invoice_validator.return_value.process.assert_called_once_with(mock_context)

    @patch('rdetoolkit.processing.processors.smarttable_early_exit.MetadataValidator')
    @patch('rdetoolkit.processing.processors.smarttable_early_exit.InvoiceValidator')
    def test_process_with_smarttable_config_missing_save_table_file(self, mock_invoice_validator, mock_meta_validator):
        """Test processing when smarttable config exists but save_table_file attribute is missing."""
        processor = SmartTableEarlyExitProcessor()

        # Create mock context with smarttable config that doesn't have save_table_file
        mock_context = Mock()
        mock_context.is_smarttable_mode = True
        mock_context.resource_paths.rawfiles = (
            Path("/data/inputdata/smarttable_test.xlsx"),
        )
        # Create a mock that doesn't have save_table_file attribute
        mock_smarttable = Mock(spec=[])  # Empty spec means no attributes
        mock_context.srcpaths.config.smarttable = mock_smarttable

        # Mock validators
        mock_meta_validator.return_value.process.return_value = None
        mock_invoice_validator.return_value.process.return_value = None

        # Should still raise SkipRemainingProcessorsError (validation still runs regardless of save_table_file)
        with pytest.raises(SkipRemainingProcessorsError):
            processor.process(mock_context)
        
        # Verify validators were called
        mock_meta_validator.return_value.process.assert_called_once_with(mock_context)
        mock_invoice_validator.return_value.process.assert_called_once_with(mock_context)

    def test_should_save_table_file_true(self):
        """Test _should_save_table_file returns True when save_table_file is enabled."""
        processor = SmartTableEarlyExitProcessor()
        
        mock_context = Mock()
        mock_context.srcpaths.config.smarttable = Mock()
        mock_context.srcpaths.config.smarttable.save_table_file = True
        
        assert processor._should_save_table_file(mock_context) is True

    def test_should_save_table_file_false(self):
        """Test _should_save_table_file returns False when save_table_file is disabled."""
        processor = SmartTableEarlyExitProcessor()
        
        mock_context = Mock()
        mock_context.srcpaths.config.smarttable = Mock()
        mock_context.srcpaths.config.smarttable.save_table_file = False
        
        assert processor._should_save_table_file(mock_context) is False

    def test_should_save_table_file_no_config(self):
        """Test _should_save_table_file returns False when smarttable config is None."""
        processor = SmartTableEarlyExitProcessor()
        
        mock_context = Mock()
        mock_context.srcpaths.config.smarttable = None
        
        assert processor._should_save_table_file(mock_context) is False

    def test_should_save_table_file_no_attribute(self):
        """Test _should_save_table_file returns False when save_table_file attribute is missing."""
        processor = SmartTableEarlyExitProcessor()
        
        mock_context = Mock()
        mock_smarttable = Mock(spec=[])  # Empty spec means no attributes
        mock_context.srcpaths.config.smarttable = mock_smarttable
        
        assert processor._should_save_table_file(mock_context) is False

    @patch('rdetoolkit.processing.processors.smarttable_early_exit.MetadataValidator')
    @patch('rdetoolkit.processing.processors.smarttable_early_exit.InvoiceValidator')
    def test_validate_files_success(self, mock_invoice_validator, mock_meta_validator):
        """Test _validate_files calls both validators successfully."""
        processor = SmartTableEarlyExitProcessor()
        
        mock_context = Mock()
        
        # Mock validators
        mock_meta_validator.return_value.process.return_value = None
        mock_invoice_validator.return_value.process.return_value = None
        
        # Should not raise any exception
        processor._validate_files(mock_context)
        
        # Verify both validators were called
        mock_meta_validator.return_value.process.assert_called_once_with(mock_context)
        mock_invoice_validator.return_value.process.assert_called_once_with(mock_context)

    @patch('rdetoolkit.processing.processors.smarttable_early_exit.MetadataValidator')
    def test_validate_files_metadata_error(self, mock_meta_validator):
        """Test _validate_files propagates metadata validation errors."""
        processor = SmartTableEarlyExitProcessor()
        
        mock_context = Mock()
        
        # Mock metadata validator to raise exception
        mock_meta_validator.return_value.process.side_effect = Exception("Metadata validation failed")
        
        # Should propagate the exception
        with pytest.raises(Exception, match="Metadata validation failed"):
            processor._validate_files(mock_context)
        
        # Verify metadata validator was called
        mock_meta_validator.return_value.process.assert_called_once_with(mock_context)

    @patch('rdetoolkit.processing.processors.smarttable_early_exit.MetadataValidator')
    @patch('rdetoolkit.processing.processors.smarttable_early_exit.InvoiceValidator')
    def test_validate_files_invoice_error(self, mock_invoice_validator, mock_meta_validator):
        """Test _validate_files propagates invoice validation errors."""
        processor = SmartTableEarlyExitProcessor()
        
        mock_context = Mock()
        
        # Mock validators
        mock_meta_validator.return_value.process.return_value = None
        mock_invoice_validator.return_value.process.side_effect = Exception("Invoice validation failed")
        
        # Should propagate the exception
        with pytest.raises(Exception, match="Invoice validation failed"):
            processor._validate_files(mock_context)
        
        # Verify both validators were called (metadata succeeds, invoice fails)
        mock_meta_validator.return_value.process.assert_called_once_with(mock_context)
        mock_invoice_validator.return_value.process.assert_called_once_with(mock_context)

    @patch('rdetoolkit.processing.processors.smarttable_early_exit.MetadataValidator')
    @patch('rdetoolkit.processing.processors.smarttable_early_exit.InvoiceValidator')
    def test_process_validation_error_propagation(self, mock_invoice_validator, mock_meta_validator):
        """Test that validation errors are properly propagated from process method."""
        processor = SmartTableEarlyExitProcessor()
        
        mock_context = Mock()
        mock_context.is_smarttable_mode = True
        mock_context.resource_paths.rawfiles = (
            Path("/data/inputdata/smarttable_test.xlsx"),
        )
        mock_context.srcpaths.config.smarttable = Mock()
        mock_context.srcpaths.config.smarttable.save_table_file = True
        mock_context.srcpaths.config.system.save_raw = False
        mock_context.srcpaths.config.system.save_nonshared_raw = False
        
        # Create actual temporary invoice file
        with tempfile.TemporaryDirectory() as temp_dir:
            invoice_path = Path(temp_dir) / "invoice.json"
            initial_invoice_data = {
                "basic": {
                    "dataName": "original_data_name",
                    "description": "Test description"
                },
                "custom": {}
            }
            
            # Write initial invoice file
            import json
            with open(invoice_path, 'w', encoding='utf-8') as f:
                json.dump(initial_invoice_data, f, ensure_ascii=False, indent=2)
            
            mock_context.invoice_dst_filepath = invoice_path
            
            # Mock validators
            mock_meta_validator.return_value.process.return_value = None
            mock_invoice_validator.return_value.process.side_effect = Exception("Invoice validation failed")
            
            # Should propagate the validation exception (not raise SkipRemainingProcessorsError)
            with pytest.raises(Exception, match="Invoice validation failed"):
                processor.process(mock_context)