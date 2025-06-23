"""Unit tests for thumbnail generation processor."""

import pytest
from unittest.mock import patch, MagicMock

from rdetoolkit.processing.processors.thumbnails import ThumbnailGenerator
from rdetoolkit.processing.context import ProcessingContext


class TestThumbnailGenerator:
    """Test cases for ThumbnailGenerator processor."""

    def test_get_name(self):
        """Test processor name."""
        processor = ThumbnailGenerator()
        assert processor.get_name() == "ThumbnailGenerator"

    def test_process_thumbnail_generation_disabled(self, processing_context_disabled_features):
        """Test ThumbnailGenerator when thumbnail generation is disabled."""
        processor = ThumbnailGenerator()
        context = processing_context_disabled_features
        
        # Verify that save_thumbnail_image is disabled
        assert not context.srcpaths.config.system.save_thumbnail_image
        
        with patch('rdetoolkit.processing.processors.thumbnails.img2thumb.copy_images_to_thumbnail') as mock_copy:
            processor.process(context)
            # Should not call copy_images_to_thumbnail when disabled
            mock_copy.assert_not_called()

    @patch('rdetoolkit.processing.processors.thumbnails.img2thumb.copy_images_to_thumbnail')
    def test_process_thumbnail_generation_enabled_success(self, mock_copy, basic_processing_context):
        """Test successful thumbnail generation when enabled."""
        processor = ThumbnailGenerator()
        context = basic_processing_context
        context.srcpaths.config.system.save_thumbnail_image = True
        
        processor.process(context)
        
        # Verify that copy_images_to_thumbnail was called with correct arguments
        mock_copy.assert_called_once_with(
            context.resource_paths.thumbnail,
            context.resource_paths.main_image,
        )

    @patch('rdetoolkit.processing.processors.thumbnails.img2thumb.copy_images_to_thumbnail')
    def test_process_thumbnail_generation_with_exception(self, mock_copy, basic_processing_context):
        """Test thumbnail generation handles exceptions gracefully."""
        processor = ThumbnailGenerator()
        context = basic_processing_context
        context.srcpaths.config.system.save_thumbnail_image = True
        
        # Mock an exception from copy_images_to_thumbnail
        mock_copy.side_effect = Exception("Test error")
        
        # Should not raise the exception (thumbnail generation is not critical)
        processor.process(context)
        
        # Verify that copy_images_to_thumbnail was called
        mock_copy.assert_called_once_with(
            context.resource_paths.thumbnail,
            context.resource_paths.main_image,
        )

    @patch('rdetoolkit.processing.processors.thumbnails.img2thumb.copy_images_to_thumbnail')
    @patch('rdetoolkit.processing.processors.thumbnails.logger')
    def test_process_logs_debug_messages_success(self, mock_logger, mock_copy, basic_processing_context):
        """Test that appropriate debug messages are logged on success."""
        processor = ThumbnailGenerator()
        context = basic_processing_context
        context.srcpaths.config.system.save_thumbnail_image = True
        
        processor.process(context)
        
        # Verify that debug success message was logged
        mock_logger.debug.assert_called_with("Thumbnail generation completed successfully")

    @patch('rdetoolkit.processing.processors.thumbnails.img2thumb.copy_images_to_thumbnail')
    @patch('rdetoolkit.processing.processors.thumbnails.logger')
    def test_process_logs_debug_messages_disabled(self, mock_logger, mock_copy, processing_context_disabled_features):
        """Test that appropriate debug messages are logged when disabled."""
        processor = ThumbnailGenerator()
        context = processing_context_disabled_features
        
        processor.process(context)
        
        # Verify that debug disabled message was logged
        mock_logger.debug.assert_called_with("Thumbnail generation disabled, skipping")
        # Should not call copy_images_to_thumbnail
        mock_copy.assert_not_called()

    @patch('rdetoolkit.processing.processors.thumbnails.img2thumb.copy_images_to_thumbnail')
    @patch('rdetoolkit.processing.processors.thumbnails.logger')
    def test_process_logs_warning_on_exception(self, mock_logger, mock_copy, basic_processing_context):
        """Test that warning is logged when exception occurs."""
        processor = ThumbnailGenerator()
        context = basic_processing_context
        context.srcpaths.config.system.save_thumbnail_image = True
        
        # Mock an exception
        error_message = "Test thumbnail error"
        mock_copy.side_effect = Exception(error_message)
        
        processor.process(context)
        
        # Verify that warning message was logged
        mock_logger.warning.assert_called_with(f"Thumbnail generation failed: {error_message}")