"""Recognize the Runner's run interruption inside library failure tolerance."""

from __future__ import annotations

from rdetoolkit.errors import RdeExecutionError

#: ``RunInterrupted``: raised by the Runner's SIGTERM handler while a run is in
#: progress. This is the only predicate for it. It lives in the shared kernel
#: (Layer 0, beside ``errors``) because the event log (Layer 0), ``core`` and
#: ``templates`` (Layer 1), ``domain`` (Layer 2) and the Runner (Layer 3) all
#: tolerate failures that must not swallow it, and each layer may depend only
#: on the layers below it (Design §1).
_RUN_INTERRUPTED_CODE = 3004


def is_run_interrupted(exc: BaseException) -> bool:
    """Return whether ``exc`` is the catalogued run interruption (3004).

    Optional, best-effort work (thumbnails, description transfer, repr
    capture, annotation resolution, stderr notices) tolerates its own
    failures, but the interruption is not such a failure: it is the run being
    stopped, so every tolerant ``except`` must let it through (review rc1 F01).

    Args:
        exc: Exception caught by a failure-tolerant block.

    Returns:
        ``True`` only for an ``RdeExecutionError`` carrying code 3004.
    """
    return isinstance(exc, RdeExecutionError) and exc.code == _RUN_INTERRUPTED_CODE
