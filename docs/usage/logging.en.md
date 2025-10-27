# Logging with `get_logger`

## About This Guide

This page explains how to persist logs from your RDEToolKit workflows by using `rdetoolkit.rdelogger.get_logger`. It focuses on initialization, output patterns, and operational tips so you can trace progress and troubleshoot issues in RDE-structured processing.

## Behavior of `get_logger`

- **Name (`name`)**: Identifier for the logger. Pass `__name__` to keep one logger per module.
- **Log level (`level`)**: Defaults to `logging.DEBUG`, but you can set `INFO`, `WARNING`, and other levels as needed.
- **Destination (`file_path`)**: Accepts an `RdeFsPath` or a string path. When provided, `LazyFileHandler` creates parent directories and the log file only when the first log record arrives.
- **Handler deduplication**: Repeated calls with the same `name` and `file_path` do not register duplicate handlers, preventing duplicated log lines and file handles.
- **When `file_path` is omitted**: The function returns a logger without handlers. Configure handlers separately with `logging.basicConfig()` or custom logging setup to emit records elsewhere.

The default log format is `%(asctime)s - [%(name)s](%(levelname)s) - %(message)s`, which keeps timestamps, module names, and severities visible at a glance.

## 1. Minimal file logging

The example below writes messages at level INFO or higher to `data/logs/structured_process.log`.

```python
from pathlib import Path
import logging

from rdetoolkit.rdelogger import get_logger
from rdetoolkit.models.rde2types import RdeFsPath

log_path = RdeFsPath(Path("data/logs/structured_process.log"))
logger = get_logger(__name__, file_path=log_path, level=logging.INFO)

logger.info("Structured processing started")
logger.warning("Input files are missing")
```

When this code runs, `LazyFileHandler` creates `data/logs/structured_process.log` on the first write and appends entries similar to:

```
2024-06-14 10:21:35,147 - [my_module](INFO) - Structured processing started
2024-06-14 10:21:35,148 - [my_module](WARNING) - Input files are missing
```

## 2. Sharing a logger per module

If a module emits logs repeatedly, initialize the logger at module scope. The pattern below fits naturally in RDEToolKit workflows.

```python
# modules/dataset.py
from rdetoolkit.rdelogger import get_logger

logger = get_logger(__name__, file_path="data/logs/dataset.log")


def run(context: dict) -> int:
    logger.debug("Structured processing will start")
    try:
        # ... (main logic)
        logger.info("Structured processing completed")
        return 0
    except Exception:
        logger.exception("Structured processing failed")
        raise
```

- `logger.exception()` appends the stack trace automatically, which speeds up root cause analysis.
- Thanks to `LazyFileHandler`, `data/logs/dataset.log` is created only when the first record arrives.

## 3. Choosing log levels

| Level            | Typical usage                                            |
| ---------------- | -------------------------------------------------------- |
| `DEBUG`          | Detailed diagnostics. Turn on during development/testing.|
| `INFO`           | Expected progress and checkpoints.                        |
| `WARNING`        | Recoverable problems that require attention.             |
| `ERROR`          | Serious issues that may block progress; consider retries.|
| `CRITICAL`       | Outages that demand immediate action.                    |

- In production, start with `INFO` or `WARNING` and switch to `DEBUG` only when deeper investigation is required.
- `get_logger` honors existing handler configuration. Add standard logging handlers (for example `RotatingFileHandler`) if you need rotation or forwarding to external services.

## 4. Writing to stdout

Omitting `file_path` returns a logger with no handlers. To use the console instead, configure a handler beforehand and reuse the same logger.

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = get_logger(__name__)

logger.info("Logging to stdout")
```

This approach plays nicely with applications that already define their own logging configuration.

## 5. Frequently asked questions

**Q. Will repeated initialization cause duplicate log lines?**  
A. No. `get_logger` checks for an existing `LazyFileHandler` targeting the same file before adding a new one.

**Q. What if the target directory does not exist yet?**  
A. `LazyFileHandler` creates the directory tree and log file during the first write.

**Q. How should I construct an `RdeFsPath`?**  
A. Wrap a `Path` or string. RDEToolKit uses `RdeFsPath` to keep path handling consistent across the project.

---

By adopting `get_logger`, you can chronologically track RDE-structured workflows and streamline troubleshooting and auditing. Standardize how each module initializes its logger, then adjust levels and handlers to fit your operational requirements.
