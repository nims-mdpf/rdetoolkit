"""Tests for ProcessingContext."""

from pathlib import Path

import pytest

from rdetoolkit.processing.context import ProcessingContext


class TestProcessingContext:
    """Test cases for ProcessingContext."""

    def test_context_creation(self, basic_processing_context):
        """Test basic ProcessingContext creation."""
        context = basic_processing_context

        assert context.index == "0001"
        assert context.mode_name == "test_mode"
        assert context.datasets_function is not None
        assert context.excel_file is None

    def test_context_creation_with_excel_file(self, excel_processing_context):
        """Test ProcessingContext creation with Excel file."""
        context = excel_processing_context

        assert context.excel_file == Path("data/inputdata/test_excel_invoice.xlsx")
        assert context.mode_name == "Excelinvoice"

    def test_basedir_property(self, basic_processing_context):
        """Test basedir property calculation."""
        context = basic_processing_context

        # Should return parent directory of first rawfile
        expected_basedir = str(Path("data/inputdata"))
        assert context.basedir == expected_basedir

    def test_basedir_property_no_rawfiles(self, processing_context_no_rawfiles):
        """Test basedir property when no rawfiles exist."""
        context = processing_context_no_rawfiles

        # Should return empty string when no rawfiles
        assert context.basedir == ""

    def test_invoice_dst_filepath_property(self, basic_processing_context):
        """Test invoice_dst_filepath property."""
        context = basic_processing_context

        expected_path = Path("data/invoice/invoice.json")
        assert context.invoice_dst_filepath == expected_path

    def test_schema_path_property(self, basic_processing_context):
        """Test schema_path property."""
        context = basic_processing_context

        expected_path = Path("data/tasksupport/invoice.schema.json")
        assert context.schema_path == expected_path

    def test_metadata_def_path_property(self, basic_processing_context):
        """Test metadata_def_path property."""
        context = basic_processing_context

        expected_path = Path("data/tasksupport/metadata-def.json")
        assert context.metadata_def_path == expected_path

    def test_metadata_path_property(self, basic_processing_context):
        """Test metadata_path property."""
        context = basic_processing_context

        expected_path = Path("data/meta/metadata.json")
        assert context.metadata_path == expected_path

    def test_dataset_paths_property(self, basic_processing_context):
        """The dataset_paths property should expose unified paths."""
        context = basic_processing_context

        dataset_paths = context.dataset_paths
        assert dataset_paths.input_paths is context.srcpaths
        assert dataset_paths.output_paths is context.resource_paths
        assert dataset_paths.inputdata == context.srcpaths.inputdata
        assert dataset_paths.raw == context.resource_paths.raw
        assert dataset_paths.invoice_org == context.resource_paths.invoice_org
        assert dataset_paths.invoice == context.resource_paths.invoice
        assert dataset_paths.metadata_def_json == context.srcpaths.tasksupport.joinpath("metadata-def.json")

    def test_context_immutability(self, basic_processing_context):
        """Test that context properties are properly accessible."""
        context = basic_processing_context

        # Test that all properties are accessible
        assert hasattr(context, 'index')
        assert hasattr(context, 'srcpaths')
        assert hasattr(context, 'resource_paths')
        assert hasattr(context, 'datasets_function')
        assert hasattr(context, 'mode_name')
        assert hasattr(context, 'excel_file')

    @pytest.mark.parametrize("mode_name,expected", [
        ("rdeformat", "rdeformat"),
        ("MultiDataTile", "MultiDataTile"),
        ("Excelinvoice", "Excelinvoice"),
        ("invoice", "invoice"),
    ])
    def test_different_mode_names(self, rde_input_paths, rde_output_paths, mock_datasets_function, mode_name, expected):
        """Test ProcessingContext with different mode names."""
        context = ProcessingContext(
            index="0001",
            srcpaths=rde_input_paths,
            resource_paths=rde_output_paths,
            datasets_function=mock_datasets_function,
            mode_name=mode_name
        )

        assert context.mode_name == expected

    def test_context_with_none_datasets_function(self, rde_input_paths, rde_output_paths):
        """Test ProcessingContext with None datasets function."""
        context = ProcessingContext(
            index="0001",
            srcpaths=rde_input_paths,
            resource_paths=rde_output_paths,
            datasets_function=None,
            mode_name="test_mode"
        )

        assert context.datasets_function is None

    def test_context_string_representation(self, basic_processing_context):
        """Test that context can be represented as string (for debugging)."""
        context = basic_processing_context

        # Should not raise an exception
        str_repr = str(context)
        assert "ProcessingContext" in str_repr
        assert context.mode_name in str_repr
