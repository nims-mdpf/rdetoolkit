import logging
import logging.handlers
import os
import pathlib
import shutil
from collections.abc import Generator
from unittest import mock

import pytest

from rdetoolkit.rdelogger import get_logger, CustomLog, log_decorator, LazyFileHandler


def test_custom_log():
    custom_log = CustomLog('test')

    logger = custom_log.get_logger()

    # # Confirm that the logger was correctly obtained
    assert logger is not None
    # Confirm that the logger name is correct
    assert logger.name == 'test'
    # Confirm that the logger has a handler
    assert len(logger.handlers) > 0


def test_log_decorator(caplog):
    logger_mock = mock.Mock(spec=CustomLog)
    logger_mock.get_logger.return_value = mock.Mock()

    with mock.patch('rdetoolkit.rdelogger.CustomLog', return_value=logger_mock):
        @log_decorator()
        def test_func():
            return "Hello, World!"

        result = test_func()

        assert result == "Hello, World!"

        calls = [
            mock.call.info('test_func       --> Start'),
            mock.call.info('test_func       <-- End'),
        ]
        logger_mock.get_logger.return_value.assert_has_calls(calls)


def test_get_logger_with_filepath():
    """Test that FileStreamHandler and StreamHandler logging work correctly."""
    name = "test_logger_with_file"
    test_dir = os.path.join(os.getcwd(), "tests", "logs")
    filepath = os.path.join(test_dir, "test.log")
    logger = get_logger(name, file_path=filepath)
    assert logger.name == name
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], LazyFileHandler)

    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)


@pytest.fixture
def tmp_path():
    yield pathlib.Path("tmp_tests")

    if os.path.exists("tmp_tests"):
        shutil.rmtree("tmp_tests")


def test_get_logger_without_file():
    """Test logger creation without file path"""
    logger = get_logger("test_logger")

    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_logger"
    assert logger.level == logging.DEBUG
    assert len(logger.handlers) == 0


def test_get_logger_with_file(tmp_path):
    """Test logger creation with file path"""
    log_file = tmp_path / "test.log"
    logger = get_logger("test_logger", file_path=log_file)

    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_logger"
    assert logger.level == logging.DEBUG
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], LazyFileHandler)

    # Test log writing
    test_message = "Test debug message"
    logger.debug(test_message)

    assert log_file.exists()
    content = log_file.read_text()
    assert test_message in content
    assert "[test_logger](DEBUG)" in content


def test_get_logger_creates_directory(tmp_path):
    """Test logger creates directory structure if not exists"""
    log_dir = tmp_path / "logs" / "subdir"
    log_file = log_dir / "test.log"

    assert not log_dir.exists()

    logger = get_logger("test_logger", file_path=log_file)
    logger.debug("Test message")

    assert log_dir.exists()
    assert log_file.exists()


def test_get_logger_formatter():
    """Test logger formatter"""
    logger = get_logger("test_logger")

    assert logger.handlers == []
    for handler in logger.handlers:
        formatter = handler.formatter
        assert formatter._fmt == "%(asctime)s - [%(name)s](%(levelname)s) - %(message)s"


def test_get_logger_level(tmp_path):
    """Test logger level"""
    log_file = tmp_path / "test.log"
    logger = get_logger("test_logger", level=logging.INFO, file_path=log_file)

    assert logger.level == logging.INFO
    assert len(logger.handlers) > 0
    assert logger.handlers[0].level == logging.INFO


@pytest.fixture(autouse=True)
def cleanup_logger():
    """Clear logger handlers before and after each test"""
    logger = logging.getLogger("test_logger")
    logger.handlers.clear()

    yield

    # テスト後のクリーンアップ
    logger.handlers.clear()


@pytest.fixture
def temp_log_file() -> Generator[str, None, None]:
    """Fixture that provides a temporary log file path.

    Args:
        tmp_path: Pytest temporary directory

    Yields:
        str: The path to a temporary log file.
    """
    tmp_path = pathlib.Path(__file__).parent / "logs"
    log_path = tmp_path / "test_logs" / "test.log"
    yield str(log_path)

    if log_path.exists():
        log_path.unlink()
    if log_path.parent.exists():
        log_path.parent.rmdir()


class TestLazyFileHandler:
    def test_init(self, temp_log_file: str) -> None:
        handler = LazyFileHandler(temp_log_file)

        assert handler.filename == temp_log_file
        assert handler.mode == "a"
        assert handler.encoding == "utf-8"
        assert handler._handler is None
        assert not os.path.exists(temp_log_file)

    def test_emit_creates_file(self, temp_log_file: str) -> None:
        handler = LazyFileHandler(temp_log_file)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        handler.emit(record)
        assert handler._handler is not None

    def test_multiple_emit_calls(self, temp_log_file: str) -> None:
        """Test that multiple calls to emit reuse the same handler"""
        handler = LazyFileHandler(temp_log_file)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        handler.emit(record)
        first_handler = handler._handler
        handler.emit(record)
        assert handler._handler is first_handler

    def test_costom_mode_and_encoding(self, temp_log_file) -> None:
        """Test that a non-existent directory is automatically created"""
        deep_path = pathlib.Path("tests", "deep", "nested", "dir", "test.log")
        handler = LazyFileHandler(str(deep_path))
        record = logging.LogRecord(
            name="test_logger",
            level=logging.DEBUG,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        handler.emit(record)

        assert deep_path.exists()
        assert deep_path.parent.exists()

    def test_formatter_and_level_propagation(self, temp_log_file: str) -> None:
        """Test that the formatter and log level propagate correctly"""
        handler = LazyFileHandler(temp_log_file)
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        handler.setLevel(logging.WARNING)

        record = logging.LogRecord(
            name="test_logger",
            level=logging.WARNING,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        handler.emit(record)

        assert handler._handler is not None
        assert handler._handler.formatter == formatter
        assert handler._handler.level == logging.WARNING
