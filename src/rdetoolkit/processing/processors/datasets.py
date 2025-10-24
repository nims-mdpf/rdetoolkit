"""Dataset processing processor."""

from __future__ import annotations

import inspect

from rdetoolkit.models.rde2types import DatasetCallback
from rdetoolkit.processing.context import ProcessingContext
from rdetoolkit.processing.pipeline import Processor
from rdetoolkit.rdelogger import get_logger

logger = get_logger(__name__, file_path="data/logs/rdesys.log")


class DatasetRunner(Processor):
    """Executes custom dataset processing functions."""

    def process(self, context: ProcessingContext) -> None:
        """Run custom dataset processing function if provided."""
        if context.datasets_function is None:
            logger.debug("No dataset processing function provided, skipping")
            return

        try:
            logger.debug("Executing custom dataset processing function")
            self._invoke_callback(context)
            logger.debug("Custom dataset processing completed successfully")
        except Exception as e:
            logger.error(f"Custom dataset processing failed: {str(e)}")
            raise

    # ------------------------------------------------------------------
    def _invoke_callback(self, context: ProcessingContext) -> None:
        """Call the user callback with an appropriate signature."""
        callback = context.datasets_function
        if callback is None:
            return

        dataset_paths = context.dataset_paths
        srcpaths, resource_paths = dataset_paths.as_legacy_args()

        _signature = _expects_legacy_signature(callback)
        if _signature is True:
            callback(srcpaths, resource_paths)
            return
        if _signature is False:
            callback(dataset_paths)
            return

        # Ambiguous callable – attempt new signature first with guarded fallback.
        try:
            callback(dataset_paths)
        except TypeError as error:
            if _looks_like_arity_mismatch(error):
                callback(srcpaths, resource_paths)
            else:
                raise


LEGACY_ARG_COUNT = 2


def _expects_legacy_signature(callback: DatasetCallback) -> bool | None:
    """Infer whether the callback expects two legacy positional arguments."""
    try:
        signature = inspect.signature(callback)
    except (TypeError, ValueError):
        return None

    params = list(signature.parameters.values())
    positional = [
        param
        for param in params
        if param.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
    ]

    if any(param.kind == inspect.Parameter.VAR_POSITIONAL for param in params):
        return None

    if len(positional) >= LEGACY_ARG_COUNT:
        return True

    if len(positional) == 1:
        return False

    return None


def _looks_like_arity_mismatch(error: TypeError) -> bool:
    """Return True when the TypeError appears to be caused by wrong arity."""
    message = str(error)
    keywords = (
        "required positional argument",
        "positional arguments but",
        "missing 1 required positional argument",
        "positional argument but",
    )
    return any(keyword in message for keyword in keywords)
