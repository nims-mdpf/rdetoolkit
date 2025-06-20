"""Thumbnail generation processor."""

from __future__ import annotations

from rdetoolkit import img2thumb
from rdetoolkit.processing.context import ProcessingContext
from rdetoolkit.processing.pipeline import Processor
from rdetoolkit.rdelogger import get_logger

logger = get_logger(__name__, file_path="data/logs/rdesys.log")


class ThumbnailGenerator(Processor):
    """Generates thumbnail images from source images."""

    def process(self, context: ProcessingContext) -> None:
        """Generate thumbnails if enabled."""
        if not context.srcpaths.config.system.save_thumbnail_image:
            logger.debug("Thumbnail generation disabled, skipping")
            return

        try:
            img2thumb.copy_images_to_thumbnail(
                context.resource_paths.thumbnail,
                context.resource_paths.main_image,
            )
            logger.debug("Thumbnail generation completed successfully")
        except Exception as e:
            logger.warning(f"Thumbnail generation failed: {str(e)}")
            # Don't raise the exception as thumbnail generation is not critical
