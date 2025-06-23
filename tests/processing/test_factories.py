"""Tests for PipelineFactory and related classes."""

import pytest

from rdetoolkit.processing.factories import (
    PipelineFactory,
    ProcessingMode,
    RDEFormatPipelineBuilder,
    MultiFilePipelineBuilder,
    ExcelInvoicePipelineBuilder,
    InvoicePipelineBuilder,
)
from rdetoolkit.processing.pipeline import Pipeline


class TestProcessingMode:
    """Test cases for ProcessingMode enum."""

    def test_processing_mode_values(self):
        """Test that ProcessingMode has correct values."""
        assert ProcessingMode.RDEFORMAT.value == "rdeformat"
        assert ProcessingMode.MULTIDATATILE.value == "multidatatile"
        assert ProcessingMode.EXCELINVOICE.value == "excelinvoice"
        assert ProcessingMode.INVOICE.value == "invoice"

    def test_processing_mode_from_string(self):
        """Test creating ProcessingMode from string."""
        assert ProcessingMode("rdeformat") == ProcessingMode.RDEFORMAT
        assert ProcessingMode("multidatatile") == ProcessingMode.MULTIDATATILE
        assert ProcessingMode("excelinvoice") == ProcessingMode.EXCELINVOICE
        assert ProcessingMode("invoice") == ProcessingMode.INVOICE


class TestPipelineBuilders:
    """Test cases for individual pipeline builders."""

    def test_rdeformat_builder(self):
        """Test RDEFormatPipelineBuilder."""
        builder = RDEFormatPipelineBuilder()
        pipeline = builder.build()

        assert isinstance(pipeline, Pipeline)
        assert pipeline.get_processor_count() == 7

        expected_processors = [
            "StandardInvoiceInitializer",
            "RDEFormatFileCopier",
            "DatasetRunner",
            "ThumbnailGenerator",
            "DescriptionUpdater",
            "MetadataValidator",
            "InvoiceValidator"
        ]

        actual_processors = pipeline.get_processor_names()
        assert actual_processors == expected_processors

    def test_multifile_builder(self):
        """Test MultiFilePipelineBuilder."""
        builder = MultiFilePipelineBuilder()
        pipeline = builder.build()

        assert isinstance(pipeline, Pipeline)
        assert pipeline.get_processor_count() == 8

        expected_processors = [
            "StandardInvoiceInitializer",
            "FileCopier",
            "DatasetRunner",
            "VariableApplier",
            "ThumbnailGenerator",
            "DescriptionUpdater",
            "MetadataValidator",
            "InvoiceValidator"
        ]

        actual_processors = pipeline.get_processor_names()
        assert actual_processors == expected_processors

    def test_excel_invoice_builder(self):
        """Test ExcelInvoicePipelineBuilder."""
        builder = ExcelInvoicePipelineBuilder()
        pipeline = builder.build()

        assert isinstance(pipeline, Pipeline)
        assert pipeline.get_processor_count() == 8

        expected_processors = [
            "ExcelInvoiceInitializer",
            "FileCopier",
            "DatasetRunner",
            "VariableApplier",
            "ThumbnailGenerator",
            "DescriptionUpdater",
            "MetadataValidator",
            "InvoiceValidator"
        ]

        actual_processors = pipeline.get_processor_names()
        assert actual_processors == expected_processors

    def test_invoice_builder(self):
        """Test InvoicePipelineBuilder."""
        builder = InvoicePipelineBuilder()
        pipeline = builder.build()

        assert isinstance(pipeline, Pipeline)
        assert pipeline.get_processor_count() == 7

        expected_processors = [
            "FileCopier",
            "DatasetRunner",
            "ThumbnailGenerator",
            "VariableApplier",
            "DescriptionUpdater",
            "MetadataValidator",
            "InvoiceValidator"
        ]

        actual_processors = pipeline.get_processor_names()
        assert actual_processors == expected_processors


class TestPipelineFactory:
    """Test cases for PipelineFactory."""

    def test_create_pipeline_with_enum(self):
        """Test creating pipelines using ProcessingMode enum."""
        rde_pipeline = PipelineFactory.create_pipeline(ProcessingMode.RDEFORMAT)
        multi_pipeline = PipelineFactory.create_pipeline(ProcessingMode.MULTIDATATILE)
        excel_pipeline = PipelineFactory.create_pipeline(ProcessingMode.EXCELINVOICE)
        invoice_pipeline = PipelineFactory.create_pipeline(ProcessingMode.INVOICE)

        assert isinstance(rde_pipeline, Pipeline)
        assert isinstance(multi_pipeline, Pipeline)
        assert isinstance(excel_pipeline, Pipeline)
        assert isinstance(invoice_pipeline, Pipeline)

    def test_create_pipeline_with_string(self):
        """Test creating pipelines using string mode names."""
        rde_pipeline = PipelineFactory.create_pipeline("rdeformat")
        multi_pipeline = PipelineFactory.create_pipeline("multidatatile")
        excel_pipeline = PipelineFactory.create_pipeline("excelinvoice")
        invoice_pipeline = PipelineFactory.create_pipeline("invoice")

        assert isinstance(rde_pipeline, Pipeline)
        assert isinstance(multi_pipeline, Pipeline)
        assert isinstance(excel_pipeline, Pipeline)
        assert isinstance(invoice_pipeline, Pipeline)

    def test_create_pipeline_case_insensitive(self):
        """Test that pipeline creation is case insensitive."""
        pipeline1 = PipelineFactory.create_pipeline("RDEFORMAT")
        pipeline2 = PipelineFactory.create_pipeline("RdeFormat")
        pipeline3 = PipelineFactory.create_pipeline("rdeformat")

        assert all(isinstance(p, Pipeline) for p in [pipeline1, pipeline2, pipeline3])
        assert all(p.get_processor_count() == 7 for p in [pipeline1, pipeline2, pipeline3])

    def test_create_pipeline_unsupported_mode(self):
        """Test error handling for unsupported modes."""
        with pytest.raises(ValueError, match="Unsupported mode"):
            PipelineFactory.create_pipeline("unknown_mode")

    def test_get_supported_modes(self):
        """Test getting supported modes."""
        modes = PipelineFactory.get_supported_modes()
        expected_modes = ["rdeformat", "multidatatile", "excelinvoice", "invoice", "smarttableinvoice"]

        assert modes == expected_modes
        assert isinstance(modes, list)

    # Backward compatibility tests
    def test_create_rdeformat_pipeline(self):
        """Test creation of RDEFormat pipeline (backward compatibility)."""
        pipeline = PipelineFactory.create_rdeformat_pipeline()

        assert isinstance(pipeline, Pipeline)
        assert pipeline.get_processor_count() == 7

        expected_processors = [
            "StandardInvoiceInitializer",
            "RDEFormatFileCopier",
            "DatasetRunner",
            "ThumbnailGenerator",
            "DescriptionUpdater",
            "MetadataValidator",
            "InvoiceValidator"
        ]

        actual_processors = pipeline.get_processor_names()
        assert actual_processors == expected_processors

    def test_create_multifile_pipeline(self):
        """Test creation of MultiFile pipeline."""
        pipeline = PipelineFactory.create_multifile_pipeline()

        assert isinstance(pipeline, Pipeline)
        assert pipeline.get_processor_count() == 8

        expected_processors = [
            "StandardInvoiceInitializer",
            "FileCopier",
            "DatasetRunner",
            "VariableApplier",
            "ThumbnailGenerator",
            "DescriptionUpdater",
            "MetadataValidator",
            "InvoiceValidator"
        ]

        actual_processors = pipeline.get_processor_names()
        assert actual_processors == expected_processors

    def test_create_excel_pipeline(self):
        """Test creation of ExcelInvoice pipeline."""
        pipeline = PipelineFactory.create_excel_pipeline()

        assert isinstance(pipeline, Pipeline)
        assert pipeline.get_processor_count() == 8

        expected_processors = [
            "ExcelInvoiceInitializer",
            "FileCopier",
            "DatasetRunner",
            "VariableApplier",
            "ThumbnailGenerator",
            "DescriptionUpdater",
            "MetadataValidator",
            "InvoiceValidator"
        ]

        actual_processors = pipeline.get_processor_names()
        assert actual_processors == expected_processors

    def test_create_invoice_pipeline(self):
        """Test creation of Invoice pipeline."""
        pipeline = PipelineFactory.create_invoice_pipeline()

        assert isinstance(pipeline, Pipeline)
        assert pipeline.get_processor_count() == 7

        expected_processors = [
            "FileCopier",
            "DatasetRunner",
            "ThumbnailGenerator",
            "VariableApplier",
            "DescriptionUpdater",
            "MetadataValidator",
            "InvoiceValidator"
        ]

        actual_processors = pipeline.get_processor_names()
        assert actual_processors == expected_processors

    def test_pipeline_processor_order_rdeformat(self):
        """Test that RDEFormat pipeline has correct processor order."""
        pipeline = PipelineFactory.create_rdeformat_pipeline()
        processors = pipeline.get_processor_names()

        # Check specific ordering requirements
        invoice_idx = processors.index("StandardInvoiceInitializer")
        file_copier_idx = processors.index("RDEFormatFileCopier")
        dataset_idx = processors.index("DatasetRunner")
        thumbnail_idx = processors.index("ThumbnailGenerator")
        description_idx = processors.index("DescriptionUpdater")
        metadata_val_idx = processors.index("MetadataValidator")
        invoice_val_idx = processors.index("InvoiceValidator")

        # Invoice handling should come first
        assert invoice_idx == 0

        # File copying should come before dataset processing
        assert file_copier_idx < dataset_idx

        # Validation should come last
        assert metadata_val_idx > description_idx
        assert invoice_val_idx > description_idx
        assert invoice_val_idx == len(processors) - 1  # Last processor

    def test_pipeline_processor_order_multifile(self):
        """Test that MultiFile pipeline has correct processor order."""
        pipeline = PipelineFactory.create_multifile_pipeline()
        processors = pipeline.get_processor_names()

        # Check specific ordering requirements
        invoice_idx = processors.index("StandardInvoiceInitializer")
        file_copier_idx = processors.index("FileCopier")
        dataset_idx = processors.index("DatasetRunner")
        variable_idx = processors.index("VariableApplier")
        thumbnail_idx = processors.index("ThumbnailGenerator")
        description_idx = processors.index("DescriptionUpdater")
        metadata_val_idx = processors.index("MetadataValidator")
        invoice_val_idx = processors.index("InvoiceValidator")

        # Invoice handling should come first
        assert invoice_idx == 0

        # File copying should come before dataset processing
        assert file_copier_idx < dataset_idx

        # Variable application should come after dataset processing
        assert variable_idx > dataset_idx

        # Validation should come last
        assert metadata_val_idx > description_idx
        assert invoice_val_idx > description_idx
        assert invoice_val_idx == len(processors) - 1  # Last processor

    def test_pipeline_processor_order_excel(self):
        """Test that ExcelInvoice pipeline has correct processor order."""
        pipeline = PipelineFactory.create_excel_pipeline()
        processors = pipeline.get_processor_names()

        # Check specific ordering requirements
        excel_invoice_idx = processors.index("ExcelInvoiceInitializer")
        file_copier_idx = processors.index("FileCopier")
        dataset_idx = processors.index("DatasetRunner")
        variable_idx = processors.index("VariableApplier")
        thumbnail_idx = processors.index("ThumbnailGenerator")
        description_idx = processors.index("DescriptionUpdater")
        metadata_val_idx = processors.index("MetadataValidator")
        invoice_val_idx = processors.index("InvoiceValidator")

        # Excel invoice handling should come first
        assert excel_invoice_idx == 0

        # File copying should come before dataset processing
        assert file_copier_idx < dataset_idx

        # Variable application should come after dataset processing
        assert variable_idx > dataset_idx

        # Validation should come last
        assert metadata_val_idx > description_idx
        assert invoice_val_idx > description_idx
        assert invoice_val_idx == len(processors) - 1  # Last processor

    def test_pipeline_processor_order_invoice(self):
        """Test that Invoice pipeline has correct processor order."""
        pipeline = PipelineFactory.create_invoice_pipeline()
        processors = pipeline.get_processor_names()

        # Check specific ordering requirements
        file_copier_idx = processors.index("FileCopier")
        dataset_idx = processors.index("DatasetRunner")
        thumbnail_idx = processors.index("ThumbnailGenerator")
        variable_idx = processors.index("VariableApplier")
        description_idx = processors.index("DescriptionUpdater")
        metadata_val_idx = processors.index("MetadataValidator")
        invoice_val_idx = processors.index("InvoiceValidator")

        # File copying should come first
        assert file_copier_idx == 0

        # Dataset processing should come after file copying
        assert dataset_idx > file_copier_idx

        # Variable application should come after thumbnail generation
        assert variable_idx > thumbnail_idx

        # Validation should come last
        assert metadata_val_idx > description_idx
        assert invoice_val_idx > description_idx
        assert invoice_val_idx == len(processors) - 1  # Last processor

    def test_pipeline_processor_types(self):
        """Test that pipelines contain the correct processor types."""
        # Test RDEFormat pipeline
        rde_pipeline = PipelineFactory.create_rdeformat_pipeline()
        rde_processors = rde_pipeline.get_processor_names()
        assert "RDEFormatFileCopier" in rde_processors
        assert "FileCopier" not in rde_processors
        assert "ExcelInvoiceInitializer" not in rde_processors

        # Test MultiFile pipeline
        multi_pipeline = PipelineFactory.create_multifile_pipeline()
        multi_processors = multi_pipeline.get_processor_names()
        assert "FileCopier" in multi_processors
        assert "RDEFormatFileCopier" not in multi_processors
        assert "ExcelInvoiceInitializer" not in multi_processors
        assert "VariableApplier" in multi_processors

        # Test Excel pipeline
        excel_pipeline = PipelineFactory.create_excel_pipeline()
        excel_processors = excel_pipeline.get_processor_names()
        assert "ExcelInvoiceInitializer" in excel_processors
        assert "StandardInvoiceInitializer" not in excel_processors
        assert "FileCopier" in excel_processors
        assert "VariableApplier" in excel_processors

        # Test Invoice pipeline
        invoice_pipeline = PipelineFactory.create_invoice_pipeline()
        invoice_processors = invoice_pipeline.get_processor_names()
        assert "FileCopier" in invoice_processors
        assert "StandardInvoiceInitializer" not in invoice_processors
        assert "ExcelInvoiceInitializer" not in invoice_processors
        assert "VariableApplier" in invoice_processors

    def test_factory_methods_return_new_instances(self):
        """Test that factory methods return new pipeline instances."""
        pipeline1 = PipelineFactory.create_rdeformat_pipeline()
        pipeline2 = PipelineFactory.create_rdeformat_pipeline()

        # Should be different instances
        assert pipeline1 is not pipeline2

        # But should have the same configuration
        assert pipeline1.get_processor_count() == pipeline2.get_processor_count()
        assert pipeline1.get_processor_names() == pipeline2.get_processor_names()

    @pytest.mark.parametrize("factory_method,expected_count", [
        ("create_rdeformat_pipeline", 7),
        ("create_multifile_pipeline", 8),
        ("create_excel_pipeline", 8),
        ("create_invoice_pipeline", 7),
    ])
    def test_pipeline_processor_counts(self, factory_method, expected_count):
        """Test that pipelines have the expected number of processors."""
        factory = PipelineFactory()
        method = getattr(factory, factory_method)
        pipeline = method()

        assert pipeline.get_processor_count() == expected_count

    def test_all_pipelines_end_with_validation(self):
        """Test that all pipelines end with validation processors."""
        pipelines = [
            PipelineFactory.create_rdeformat_pipeline(),
            PipelineFactory.create_multifile_pipeline(),
            PipelineFactory.create_excel_pipeline(),
            PipelineFactory.create_invoice_pipeline(),
        ]

        for pipeline in pipelines:
            processors = pipeline.get_processor_names()
            # All pipelines should end with MetadataValidator and InvoiceValidator
            assert processors[-2] == "MetadataValidator"
            assert processors[-1] == "InvoiceValidator"
