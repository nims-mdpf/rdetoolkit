"""Comprehensive behavioral tests for Pipeline and Processor classes."""

import pytest
from unittest.mock import patch, MagicMock

from rdetoolkit.models.result import WorkflowExecutionStatus
from rdetoolkit.processing.pipeline import Pipeline, Processor
from tests.fixtures.processing.mock_processors import (
    MockSuccessProcessor,
    MockFailureProcessor,
    MockConditionalProcessor,
    MockFileProcessor,
    MockValidationProcessor,
)


class TestProcessor:
    """Test cases for Processor abstract base class."""

    def test_processor_is_abstract(self):
        """Test that Processor cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            Processor()

    def test_processor_subclass_must_implement_process(self):
        """Test that Processor subclasses must implement process method."""

        class IncompleteProcessor(Processor):
            pass

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteProcessor()

    def test_processor_get_name_default_behavior(self):
        """Test default get_name implementation returns class name."""
        processor = MockSuccessProcessor()
        assert processor.get_name() == "MockSuccessProcessor"

    def test_processor_get_name_custom_implementation(self):
        """Test that processors can override get_name method."""
        processor = MockSuccessProcessor(name="CustomProcessorName")
        assert processor.get_name() == "CustomProcessorName"

    def test_processor_inheritance_behavior(self):
        """Test that processors properly inherit from Processor."""
        processor = MockSuccessProcessor()
        assert isinstance(processor, Processor)
        assert hasattr(processor, 'process')
        assert hasattr(processor, 'get_name')


class TestPipeline:
    """Comprehensive behavioral tests for Pipeline class."""

    def test_pipeline_creation_and_initial_state(self):
        """Test Pipeline creation and its initial state."""
        pipeline = Pipeline()

        # Verify initial state
        assert pipeline.get_processor_count() == 0
        assert pipeline.get_processor_names() == []
        assert isinstance(pipeline._processors, list)

    def test_pipeline_processor_management(self):
        """Test adding and managing processors in pipeline."""
        pipeline = Pipeline()
        processor1 = MockSuccessProcessor(name="Processor1")
        processor2 = MockSuccessProcessor(name="Processor2")
        processor3 = MockSuccessProcessor(name="Processor3")

        # Test fluent interface (method chaining)
        result = pipeline.add(processor1).add(processor2).add(processor3)

        # Verify method chaining returns self
        assert result is pipeline

        # Verify processors are properly tracked
        assert pipeline.get_processor_count() == 3
        assert pipeline.get_processor_names() == ["Processor1", "Processor2", "Processor3"]

    def test_pipeline_execution_happy_path(self, basic_processing_context):
        """Test successful pipeline execution with multiple processors."""
        pipeline = Pipeline()
        processor1 = MockSuccessProcessor(name="DataLoader")
        processor2 = MockFileProcessor(name="FileProcessor")
        processor3 = MockValidationProcessor(name="Validator")

        pipeline.add(processor1).add(processor2).add(processor3)

        result = pipeline.execute(basic_processing_context)

        # Verify all processors were executed
        assert processor1.executed
        assert processor2.executed
        assert processor3.executed

        # Verify execution result
        assert isinstance(result, WorkflowExecutionStatus)
        assert result.status == "success"
        assert result.run_id == basic_processing_context.index
        assert result.mode == basic_processing_context.mode_name
        assert result.error_code is None
        assert result.error_message is None
        assert result.stacktrace is None

    def test_pipeline_execution_with_context_sharing(self, basic_processing_context):
        """Test that all processors receive the same context instance."""
        pipeline = Pipeline()
        processor1 = MockSuccessProcessor(name="First")
        processor2 = MockSuccessProcessor(name="Second")
        processor3 = MockSuccessProcessor(name="Third")

        pipeline.add(processor1).add(processor2).add(processor3)
        pipeline.execute(basic_processing_context)

        # Verify all processors received the same context instance
        assert processor1.context_received is basic_processing_context
        assert processor2.context_received is basic_processing_context
        assert processor3.context_received is basic_processing_context

    def test_pipeline_execution_order_enforcement(self, basic_processing_context):
        """Test that processors are executed in the exact order they were added."""
        pipeline = Pipeline()

        # Use logging processors to track execution order
        execution_tracker = []

        def create_ordered_processor(order_num):
            class OrderedProcessor(Processor):
                def __init__(self, order):
                    self.order = order

                def process(self, context):
                    execution_tracker.append(self.order)

                def get_name(self):
                    return f"OrderedProcessor{self.order}"

            return OrderedProcessor(order_num)

        # Add processors in specific order
        for i in range(5):
            pipeline.add(create_ordered_processor(i))

        pipeline.execute(basic_processing_context)

        # Verify execution order
        assert execution_tracker == [0, 1, 2, 3, 4]

    def test_pipeline_failure_handling_and_early_termination(self, basic_processing_context):
        """Test pipeline behavior when a processor fails."""
        pipeline = Pipeline()
        processor1 = MockSuccessProcessor(name="BeforeFailure")
        processor2 = MockFailureProcessor(error_message="Critical failure", name="FailingProcessor")
        processor3 = MockSuccessProcessor(name="AfterFailure")

        pipeline.add(processor1).add(processor2).add(processor3)

        result = pipeline.execute(basic_processing_context)

        # Verify execution stopped at failure
        assert processor1.executed
        assert processor2.executed
        assert not processor3.executed  # Should not execute after failure

        # Verify error result
        assert isinstance(result, WorkflowExecutionStatus)
        assert result.status == "failed"
        assert result.error_code == 1
        assert "Critical failure" in result.error_message
        assert result.stacktrace is not None
        assert "RuntimeError" in result.stacktrace

    def test_pipeline_conditional_processing_behavior(self, basic_processing_context):
        """Test pipeline with conditional processors based on context."""
        pipeline = Pipeline()

        # Processor that fails if context has specific mode
        fail_condition = lambda ctx: ctx.mode_name == "test_mode"
        conditional_processor = MockConditionalProcessor(
            fail_condition_func=fail_condition,
            name="ConditionalProcessor"
        )

        success_processor = MockSuccessProcessor(name="AlwaysSuccess")

        pipeline.add(success_processor).add(conditional_processor)

        result = pipeline.execute(basic_processing_context)

        # Should fail because context mode_name is "test_mode"
        assert success_processor.executed
        assert conditional_processor.executed
        assert result.status == "failed"
        assert "Conditional failure" in result.error_message

    def test_pipeline_file_processing_behavior(self, basic_processing_context):
        """Test pipeline processing with file-related operations."""
        pipeline = Pipeline()
        file_processor = MockFileProcessor(name="FileHandler")

        pipeline.add(file_processor)
        pipeline.execute(basic_processing_context)

        # Verify file processor processed the raw files
        assert file_processor.executed
        assert len(file_processor.files_processed) == len(basic_processing_context.resource_paths.rawfiles)

        # Verify it processed the actual file paths
        expected_files = [str(f) for f in basic_processing_context.resource_paths.rawfiles]
        assert file_processor.files_processed == expected_files

    def test_pipeline_validation_workflow(self, basic_processing_context):
        """Test a realistic validation workflow."""
        pipeline = Pipeline()

        # Create a validation chain
        pre_validator = MockValidationProcessor(validation_result=True, name="PreValidator")
        main_processor = MockSuccessProcessor(name="MainProcessor")
        post_validator = MockValidationProcessor(validation_result=True, name="PostValidator")

        pipeline.add(pre_validator).add(main_processor).add(post_validator)

        result = pipeline.execute(basic_processing_context)

        # Verify all executed successfully
        assert pre_validator.executed
        assert main_processor.executed
        assert post_validator.executed
        assert result.status == "success"

    def test_pipeline_validation_failure_workflow(self, basic_processing_context):
        """Test validation workflow with validation failure."""
        pipeline = Pipeline()

        pre_validator = MockValidationProcessor(validation_result=True, name="PreValidator")
        failing_validator = MockValidationProcessor(validation_result=False, name="FailingValidator")
        main_processor = MockSuccessProcessor(name="MainProcessor")

        pipeline.add(pre_validator).add(failing_validator).add(main_processor)

        result = pipeline.execute(basic_processing_context)

        # Verify execution stopped at validation failure
        assert pre_validator.executed
        assert failing_validator.executed
        assert not main_processor.executed
        assert result.status == "failed"
        assert "Validation failed" in result.error_message

    def test_pipeline_empty_execution_behavior(self, basic_processing_context):
        """Test execution of empty pipeline."""
        pipeline = Pipeline()

        result = pipeline.execute(basic_processing_context)

        # Empty pipeline should succeed
        assert result.status == "success"
        assert result.run_id == basic_processing_context.index
        assert result.mode == basic_processing_context.mode_name

    @patch('rdetoolkit.processing.pipeline.logger')
    def test_pipeline_logging_behavior(self, mock_logger, basic_processing_context):
        """Test that pipeline logs execution properly."""
        pipeline = Pipeline()
        processor = MockSuccessProcessor(name="TestProcessor")

        pipeline.add(processor)
        pipeline.execute(basic_processing_context)

        # Verify logging calls
        mock_logger.info.assert_called_with(f"Starting pipeline execution for mode: {basic_processing_context.mode_name}")
        mock_logger.debug.assert_any_call("Executing processor: TestProcessor")
        mock_logger.debug.assert_any_call("Processor TestProcessor completed successfully")

    @patch('rdetoolkit.processing.pipeline.logger')
    def test_pipeline_error_logging_behavior(self, mock_logger, basic_processing_context):
        """Test that pipeline logs errors properly."""
        pipeline = Pipeline()
        processor = MockFailureProcessor(error_message="Test error", name="FailingProcessor")

        pipeline.add(processor)
        result = pipeline.execute(basic_processing_context)

        # Verify error logging
        mock_logger.error.assert_any_call("Processor FailingProcessor failed: Test error")
        mock_logger.error.assert_any_call("Pipeline execution failed: Test error")
        assert result.status == "failed"

    def test_pipeline_success_status_with_invoice_title(self, basic_processing_context):
        """Test success status creation with invoice title extraction."""
        pipeline = Pipeline()
        processor = MockSuccessProcessor()

        pipeline.add(processor)

        # Mock invoice file to not exist so we use default title
        result = pipeline.execute(basic_processing_context)

        assert result.status == "success"
        assert f"{basic_processing_context.mode_name} Mode Process" in result.title
        assert result.target == basic_processing_context.basedir

    @patch('rdetoolkit.processing.pipeline.InvoiceFile')
    def test_pipeline_success_status_with_custom_invoice_title(self, mock_invoice_file, basic_processing_context):
        """Test success status with custom title from invoice file."""
        pipeline = Pipeline()
        processor = MockSuccessProcessor()

        # Mock invoice file with custom data name
        mock_invoice = MagicMock()
        mock_invoice.invoice_obj = {"basic": {"dataName": "test_mode Mode Process"}}
        mock_invoice_file.return_value = mock_invoice

        pipeline.add(processor)

        result = pipeline.execute(basic_processing_context)

        assert result.status == "success"
        assert result.title == "test_mode Mode Process"

    @patch('rdetoolkit.processing.pipeline.InvoiceFile')
    @patch('rdetoolkit.processing.pipeline.logger')
    def test_pipeline_invoice_reading_error_handling(self, mock_logger, mock_invoice_file, isolated_processing_context):
        """Test error handling when invoice file reading fails."""
        pipeline = Pipeline()
        processor = MockSuccessProcessor()

        # Create the invoice file so it exists (in isolated temp directory)
        invoice_path = isolated_processing_context.invoice_dst_filepath
        invoice_path.write_text('{"basic": {"dataName": "test"}}')

        # Mock invoice file reading to raise an exception
        mock_invoice_file.side_effect = Exception("Invoice read error")

        pipeline.add(processor)

        result = pipeline.execute(isolated_processing_context)

        # Should still succeed but use default title and log warning
        assert result.status == "success"
        assert f"{isolated_processing_context.mode_name} Mode Process" in result.title
        mock_logger.warning.assert_called_once()

    @pytest.mark.parametrize("mode_name,expected_pattern", [
        ("rdeformat", "rdeformat Mode Process"),
        ("MultiDataTile", "MultiDataTile Mode Process"),
        ("Excelinvoice", "Excelinvoice Mode Process"),
        ("invoice", "invoice Mode Process"),
        ("custom_mode", "custom_mode Mode Process"),
    ])
    def test_pipeline_title_generation_for_different_modes(self, basic_processing_context, mode_name, expected_pattern):
        """Test title generation for various processing modes."""
        pipeline = Pipeline()
        processor = MockSuccessProcessor()

        # Update context mode
        basic_processing_context.mode_name = mode_name

        pipeline.add(processor)

        result = pipeline.execute(basic_processing_context)

        assert result.status == "success"
        assert expected_pattern in result.title
        assert result.mode == mode_name

    def test_pipeline_complex_workflow_simulation(self, basic_processing_context):
        """Test a complex, realistic processing workflow."""
        pipeline = Pipeline()

        # Simulate a complete processing workflow
        file_loader = MockFileProcessor(name="FileLoader")
        pre_validator = MockValidationProcessor(validation_result=True, name="PreValidation")
        data_processor = MockSuccessProcessor(name="DataProcessor")
        post_validator = MockValidationProcessor(validation_result=True, name="PostValidation")
        finalizer = MockSuccessProcessor(name="Finalizer")

        pipeline.add(file_loader).add(pre_validator).add(data_processor).add(post_validator).add(finalizer)

        result = pipeline.execute(basic_processing_context)

        # Verify complete workflow execution
        assert file_loader.executed
        assert pre_validator.executed
        assert data_processor.executed
        assert post_validator.executed
        assert finalizer.executed

        # Verify files were processed
        assert len(file_loader.files_processed) > 0

        # Verify successful completion
        assert result.status == "success"
        assert result.error_code is None

    def test_pipeline_state_isolation_between_executions(self, basic_processing_context):
        """Test that pipeline executions don't interfere with each other."""
        pipeline = Pipeline()
        processor1 = MockSuccessProcessor(name="Processor1")
        processor2 = MockSuccessProcessor(name="Processor2")

        pipeline.add(processor1).add(processor2)

        # First execution
        result1 = pipeline.execute(basic_processing_context)

        # Reset processor states
        processor1.executed = False
        processor2.executed = False

        # Second execution
        result2 = pipeline.execute(basic_processing_context)

        # Both executions should succeed independently
        assert result1.status == "success"
        assert result2.status == "success"
        assert result1.run_id == result2.run_id  # Same context

        # Processors should have been executed in both runs
        assert processor1.executed
        assert processor2.executed

    def test_pipeline_with_none_context(self):
        """Test pipeline behavior with None context."""
        pipeline = Pipeline()
        processor = MockSuccessProcessor()
        pipeline.add(processor)

        with pytest.raises(AttributeError):
            pipeline.execute(None)

    def test_pipeline_processor_count_edge_cases(self):
        """Test processor count in various states."""
        pipeline = Pipeline()

        # Empty pipeline
        assert pipeline.get_processor_count() == 0
        assert pipeline.get_processor_names() == []

        # Add single processor
        processor = MockSuccessProcessor()
        pipeline.add(processor)
        assert pipeline.get_processor_count() == 1
        assert len(pipeline.get_processor_names()) == 1

        # Add same processor multiple times
        pipeline.add(processor).add(processor)
        assert pipeline.get_processor_count() == 3  # Same instance added 3 times

    def test_pipeline_processor_with_none_name(self):
        """Test processor that returns None for get_name."""
        class NoneNameProcessor(Processor):
            def process(self, context):
                # Process with no-op
                pass

            def get_name(self):
                return None

        pipeline = Pipeline()
        processor = NoneNameProcessor()
        pipeline.add(processor)

        names = pipeline.get_processor_names()
        assert None in names

    def test_pipeline_large_processor_chain(self, basic_processing_context):
        """Test pipeline with large number of processors."""
        pipeline = Pipeline()

        # Add 100 processors
        processors = []
        for i in range(100):
            processor = MockSuccessProcessor(name=f"Processor{i}")
            processors.append(processor)
            pipeline.add(processor)

        assert pipeline.get_processor_count() == 100

        result = pipeline.execute(basic_processing_context)

        # Verify all processors executed
        for processor in processors:
            assert processor.executed

        assert result.status == "success"

    def test_pipeline_processor_exception_types(self, basic_processing_context):
        """Test pipeline handling of different exception types."""
        test_cases = [
            (ValueError, "Value error occurred"),
            (RuntimeError, "Runtime error occurred"),
            (FileNotFoundError, "File not found"),
            (PermissionError, "Permission denied"),
            (KeyError, "Key not found"),
        ]

        for exception_type, error_message in test_cases:
            pipeline = Pipeline()

            class CustomExceptionProcessor(Processor):
                def process(self, context):
                    # Raise specific exception for testing
                    raise exception_type(error_message)

                def get_name(self):
                    return f"{exception_type.__name__}Processor"

            processor = CustomExceptionProcessor()
            pipeline.add(processor)

            result = pipeline.execute(basic_processing_context)

            assert result.status == "failed"
            assert error_message in result.error_message
            assert exception_type.__name__ in result.stacktrace

    def test_pipeline_context_modification_isolation(self, basic_processing_context):
        """Test that processors can modify context without affecting others."""
        pipeline = Pipeline()

        class ContextModifyingProcessor(Processor):
            def __init__(self, attribute_name, value):
                self.attribute_name = attribute_name
                self.value = value
                self.original_value = None

            def process(self, context):
                # Store original value
                self.original_value = getattr(context, self.attribute_name, None)
                # Modify context
                setattr(context, self.attribute_name, self.value)

            def get_name(self):
                return f"ContextModifier_{self.attribute_name}"

        modifier1 = ContextModifyingProcessor("test_attr1", "value1")
        modifier2 = ContextModifyingProcessor("test_attr2", "value2")
        checker = MockSuccessProcessor(name="Checker")

        pipeline.add(modifier1).add(modifier2).add(checker)

        result = pipeline.execute(basic_processing_context)

        # Verify modifications persisted
        assert hasattr(basic_processing_context, "test_attr1")
        assert hasattr(basic_processing_context, "test_attr2")
        assert basic_processing_context.test_attr1 == "value1"
        assert basic_processing_context.test_attr2 == "value2"

        assert result.status == "success"
