import logging
import traceback
import pytest
from rdetoolkit.exceptions import StructuredError, InvoiceModeError, ExcelInvoiceModeError, MultiDataTileModeError, RdeFormatModeError
from rdetoolkit.errors import skip_exception_context, format_simplified_traceback, handle_exception, catch_exception_with_message, handle_and_exit_on_structured_error
from unittest.mock import Mock, patch
from rdetoolkit.models.config import Config, TracebackSettings


def test_structured_error_initialization():
    """Test the initialization of the StructuredError class.

    This test verifies that the StructuredError class correctly initializes its properties
    with the provided arguments.

    Steps:
    1. Define the custom error message, error code, error object, and traceback information.
    2. Create an instance of StructuredError with these arguments.
    3. Assert that the instance properties match the provided arguments.
    4. Verify that the string representation of the instance is the error message.
    """
    error_message = "This is an error message"
    error_code = 404
    error_object = {"key": "value"}
    traceback_info = "Traceback (most recent call last): ..."

    # StructuredErrorインスタンスを作成
    error = StructuredError(emsg=error_message, ecode=error_code, eobj=error_object, traceback_info=traceback_info)

    # プロパティの確認
    assert error.emsg == error_message
    assert error.ecode == error_code
    assert error.eobj == error_object
    assert error.traceback_info == traceback_info
    assert str(error) == error_message


def test_structured_error_default_initialization():
    """Test the default initialization of the StructuredError class.

    This test verifies that the StructuredError class correctly initializes its properties
    with default values when no arguments are provided.

    Steps:
    1. Create an instance of StructuredError with no arguments.
    2. Assert that the instance properties match the expected default values.
    3. Verify that the string representation of the instance is an empty string.
    """
    # デフォルト値でStructuredErrorインスタンスを作成
    error = StructuredError()

    # デフォルトプロパティの確認
    assert error.emsg == ""
    assert error.ecode == 1
    assert error.eobj is None
    assert error.traceback_info is None
    assert str(error) == ""


def test_format_simplified_traceback():
    """Test the format_simplified_traceback function.

    This test verifies that the format_simplified_traceback function correctly formats
    a list of traceback.FrameSummary objects into a readable string representation.

    Steps:
    1. Create a list of dummy traceback.FrameSummary objects.
    2. Define the expected output string.
    3. Assert that the function's output matches the expected output.
    """
    line_number = (10, 20, 30)
    tb_list = [
        traceback.FrameSummary("file1.py", line_number[0], "function1", line="line1"),
        traceback.FrameSummary("file2.py", line_number[1], "function2", line="line2"),
        traceback.FrameSummary("file3.py", line_number[2], "function3", line="line3"),
    ]
    expected_output = (
        "   File: file1.py, Line: 10 in function1()\n"
        "    └─ File: file2.py, Line: 20 in function2()\n"
        "        └─ File: file3.py, Line: 30 in function3()\n"
        "            └─> L30: line3 \U0001F525"
    )
    assert format_simplified_traceback(tb_list) == expected_output


def test_catch_exception_with_message_verbose(capfd):
    """Test catch_exception_with_message with verbose output.

    This test verifies that the decorator correctly catches an exception and writes the original
    traceback to standard error when verbose is set to True.

    Steps:
    1. Define a function that raises a ValueError with a specific message.
    2. Decorate the function with catch_exception_with_message, setting verbose=True.
    3. Call the decorated function and capture the standard error output.
    4. Verify that the captured standard error output contains:
        - "Traceback (most recent call last):"
        - "ValueError: An error occurred"
        - "Custom Traceback (simplified and more readable):"
    5. Verify that the StructuredError object returned by the decorator has the following properties:
        - emsg: "Error: An error occurred"
        - ecode: 1
        - eobj: None
        - traceback_info contains:
            - "Traceback (simplified message):"
            - "Exception Type: ValueError"
            - "Error: An error occurred"
    """

    @catch_exception_with_message(verbose=True)
    def func_that_raises():
        raise ValueError("An error occurred")

    with pytest.raises(StructuredError) as excinfo:
        func_that_raises()

    captured = capfd.readouterr()
    assert "Traceback (most recent call last):" in captured.err
    assert "ValueError: An error occurred" in captured.err
    assert "Custom Traceback (simplified and more readable):" in captured.err

    structured_error = excinfo.value
    assert structured_error.emsg == "Error: An error occurred"
    assert structured_error.ecode == 1
    assert structured_error.eobj is None
    assert "Traceback (simplified message):" in structured_error.traceback_info
    assert "Exception Type: ValueError" in structured_error.traceback_info
    assert "Error: An error occurred" in structured_error.traceback_info


def test_catch_exception_with_message_custom_eobj():
    """Test catch_exception_with_message with a custom error object.

    This test verifies that the decorator correctly catches an exception and re-raises
    a StructuredError with a custom error object.

    Steps:
    1. Define a custom error object.
    2. Define a function that raises a ValueError with a specific message.
    3. Decorate the function with catch_exception_with_message, passing the custom error object.
    4. Call the decorated function and verify that a StructuredError is raised.
    5. Verify that the StructuredError object returned by the decorator has the following properties:
        - emsg: "Error: An error occurred"
        - ecode: 1
        - eobj: {"key": "value"}
        - traceback_info contains:
            - "Traceback (simplified message):"
            - "Exception Type: ValueError"
            - "Error: An error occurred"
    """
    custom_eobj = {"key": "value"}

    @catch_exception_with_message(eobj=custom_eobj)
    def func_that_raises():
        raise ValueError("An error occurred")

    with pytest.raises(StructuredError) as excinfo:
        func_that_raises()

    structured_error = excinfo.value
    assert structured_error.emsg == "Error: An error occurred"
    assert structured_error.ecode == 1
    assert structured_error.eobj == custom_eobj
    assert "Traceback (simplified message):" in structured_error.traceback_info
    assert "Exception Type: ValueError" in structured_error.traceback_info
    assert "Error: An error occurred" in structured_error.traceback_info


def test_catch_exception_with_message_custom_code():
    """Test catch_exception_with_message with a custom error code.

    This test verifies that the decorator correctly catches an exception and re-raises
    a StructuredError with a custom error code.

    Steps:
    1. Define a custom error code.
    2. Define a function that raises a ValueError with a specific message.
    3. Decorate the function with catch_exception_with_message, passing the custom error code.
    4. Call the decorated function and verify that a StructuredError is raised.
    5. Verify that the StructuredError object returned by the decorator has the following properties:
        - emsg: "Error: An error occurred"
        - ecode: 500
        - eobj: None
        - traceback_info contains:
            - "Traceback (simplified message):"
            - "Exception Type: ValueError"
            - "Error: An error occurred"
    """
    custom_code = 500

    @catch_exception_with_message(error_code=custom_code)
    def func_that_raises():
        raise ValueError("An error occurred")

    with pytest.raises(StructuredError) as excinfo:
        func_that_raises()

    structured_error = excinfo.value
    assert structured_error.emsg == "Error: An error occurred"
    assert structured_error.ecode == custom_code
    assert structured_error.eobj is None
    assert "Traceback (simplified message):" in structured_error.traceback_info
    assert "Exception Type: ValueError" in structured_error.traceback_info
    assert "Error: An error occurred" in structured_error.traceback_info


def test_catch_exception_with_message_custom_message():
    """Test catch_exception_with_message with a custom error message.

    This test verifies that the decorator correctly catches an exception and re-raises
    a StructuredError with a custom error message.

    Steps:
    1. Define a custom error message.
    2. Define a function that raises a ValueError with a specific message.
    3. Decorate the function with catch_exception_with_message, passing the custom error message.
    4. Call the decorated function and verify that a StructuredError is raised.
    5. Verify that the StructuredError object returned by the decorator has the following properties:
        - emsg: "Error: This is a custom error message"
        - ecode: 1
        - eobj: None
        - traceback_info contains:
            - "Traceback (simplified message):"
            - "Exception Type: ValueError"
            - "Error: This is a custom error message"
    """
    custom_message = "This is a custom error message"

    @catch_exception_with_message(error_message=custom_message)
    def func_that_raises():
        raise ValueError("An error occurred")

    with pytest.raises(StructuredError) as excinfo:
        func_that_raises()

    structured_error = excinfo.value
    assert structured_error.emsg == f"Error: {custom_message}"
    assert structured_error.ecode == 1
    assert structured_error.eobj is None
    assert "Traceback (simplified message):" in structured_error.traceback_info
    assert "Exception Type: ValueError" in structured_error.traceback_info
    assert f"Error: {custom_message}" in structured_error.traceback_info


def test_catch_exception_with_message_default():
    """Test catch_exception_with_message with default parameters.

    This test verifies that the decorator correctly catches an exception and re-raises
    a StructuredError with the default error message and error code.

    Steps:
    1. Define a function that raises a ValueError with a specific message.
    2. Decorate the function with catch_exception_with_message using default parameters.
    3. Call the decorated function and verify that a StructuredError is raised.
    4. Verify that the StructuredError object returned by the decorator has the following properties:
        - emsg: "Error: An error occurred"
        - ecode: 1
        - eobj: None
        - traceback_info contains:
            - "Traceback (simplified message):"
            - "Exception Type: ValueError"
            - "Error: An error occurred"
    """

    @catch_exception_with_message()
    def func_that_raises():
        raise ValueError("An error occurred")

    with pytest.raises(StructuredError) as excinfo:
        func_that_raises()

    structured_error = excinfo.value
    assert structured_error.emsg == "Error: An error occurred"
    assert structured_error.ecode == 1
    assert structured_error.eobj is None
    assert "Traceback (simplified message):" in structured_error.traceback_info
    assert "Exception Type: ValueError" in structured_error.traceback_info
    assert "Error: An error occurred" in structured_error.traceback_info


def test_catch_exception_with_message_exception():
    """Test the handle_exception function.

    This test verifies that the handle_exception function correctly handles exceptions,
    and returns a StructuredError object with the appropriate error message and traceback information.

    Steps:
    1. Define a function that raises a ValueError.
    2. Decorate the function with the catch_exception_with_message decorator.
    3. Call the decorated function and assert that a StructuredError is raised.
    4. Verify the properties of the StructuredError object.
    """

    @catch_exception_with_message(verbose=False)
    def func_that_raises():
        raise ValueError("An error occurred")

    with pytest.raises(StructuredError) as excinfo:
        func_that_raises()

    e = excinfo.value
    assert e.emsg == "Error: An error occurred"
    assert "Traceback (simplified message):" in e.traceback_info
    assert "Exception Type: ValueError" in e.traceback_info
    assert "Error: An error occurred" in e.traceback_info


def test_handle_exception_default():
    """Test handle_exception with default parameters.

    This test verifies that the handle_exception function correctly handles an exception
    and returns a StructuredError with the default error message and error code.

    Steps:
    1. Raise a ValueError with a specific message.
    2. Catch the exception and pass it to handle_exception.
    3. Verify that the StructuredError object returned by handle_exception has the following properties:
        - emsg: "Error: This is a ValueError"
        - ecode: 1
        - eobj: None
        - traceback_info contains:
            - "Traceback (simplified message):"
            - "Exception Type: ValueError"
            - "Error: This is a ValueError"
    """
    try:
        raise ValueError("This is a ValueError")
    except Exception as e:
        structured_error = handle_exception(e)

    assert structured_error.emsg == "Error: This is a ValueError"
    assert structured_error.ecode == 1
    assert structured_error.eobj is None
    assert "Traceback (simplified message):" in structured_error.traceback_info
    assert "Exception Type: ValueError" in structured_error.traceback_info
    assert "Error: This is a ValueError" in structured_error.traceback_info


def test_handle_exception_custom_message():
    """Test handle_exception with a custom error message.

    This test verifies that the handle_exception function correctly handles an exception
    and returns a StructuredError with a custom error message.

    Steps:
    1. Define a custom error message.
    2. Raise a ValueError with a specific message.
    3. Catch the exception and pass it to handle_exception along with the custom error message.
    4. Verify that the StructuredError object returned by handle_exception has the following properties:
        - emsg: "Error: This is a custom error message"
        - ecode: 1
        - eobj: None
        - traceback_info contains:
            - "Traceback (simplified message):"
            - "Exception Type: ValueError"
            - "Error: This is a custom error message"
    """
    custom_message = "This is a custom error message"
    try:
        raise ValueError("This is a ValueError")
    except Exception as e:
        structured_error = handle_exception(e, error_message=custom_message)

    assert structured_error.emsg == f"Error: {custom_message}"
    assert structured_error.ecode == 1
    assert structured_error.eobj is None
    assert "Traceback (simplified message):" in structured_error.traceback_info
    assert "Exception Type: ValueError" in structured_error.traceback_info
    assert f"Error: {custom_message}" in structured_error.traceback_info


def test_handle_exception_custom_code():
    """Test handle_exception with a custom error code.

    This test verifies that the handle_exception function correctly handles an exception
    and returns a StructuredError with a custom error code.

    Steps:
    1. Define a custom error code.
    2. Raise a ValueError with a specific message.
    3. Catch the exception and pass it to handle_exception along with the custom error code.
    4. Verify that the StructuredError object returned by handle_exception has the following properties:
        - emsg: "Error: An error occurred"
        - ecode: 500
        - eobj: None
        - traceback_info contains:
            - "Traceback (simplified message):"
            - "Exception Type: ValueError"
            - "Error: An error occurred"
    """
    custom_code = 500
    try:
        raise ValueError("An error occurred")
    except Exception as e:
        structured_error = handle_exception(e, error_code=custom_code)

    assert structured_error.emsg == "Error: An error occurred"
    assert structured_error.ecode == custom_code
    assert structured_error.eobj is None
    assert "Traceback (simplified message):" in structured_error.traceback_info
    assert "Exception Type: ValueError" in structured_error.traceback_info
    assert "Error: An error occurred" in structured_error.traceback_info


def test_handle_exception_custom_eobj():
    """Test handle_exception with a custom error object.

    This test verifies that the handle_exception function correctly handles an exception
    and returns a StructuredError with a custom error object.

    Steps:
    1. Define a custom error object.
    2. Raise a ValueError with a specific message.
    3. Catch the exception and pass it to handle_exception along with the custom error object.
    4. Verify that the StructuredError object returned by handle_exception has the following properties:
        - emsg: "Error: An error occurred"
        - ecode: 1
        - eobj: {"key": "value"}
        - traceback_info contains:
            - "Traceback (simplified message):"
            - "Exception Type: ValueError"
            - "Error: An error occurred"
    """
    custom_eobj = {"key": "value"}
    try:
        raise ValueError("An error occurred")
    except Exception as e:
        structured_error = handle_exception(e, eobj=custom_eobj)

    assert structured_error.emsg == "Error: An error occurred"
    assert structured_error.ecode == 1
    assert structured_error.eobj == custom_eobj
    assert "Traceback (simplified message):" in structured_error.traceback_info
    assert "Exception Type: ValueError" in structured_error.traceback_info
    assert "Error: An error occurred" in structured_error.traceback_info


def test_handle_exception_verbose(capfd):
    """Test handle_exception with verbose output.

    This test verifies that the handle_exception function correctly handles an exception
    and writes the original traceback to standard error when verbose is set to True.

    Steps:
    1. Raise a ValueError with a specific message.
    2. Catch the exception and pass it to handle_exception with verbose=True.
    3. Capture the standard error output.
    4. Verify that the captured standard error output contains:
        - "Traceback (most recent call last):"
        - "ValueError: An error occurred"
        - "Custom Traceback (simplified and more readable):"
    5. Verify that the StructuredError object returned by handle_exception has the following properties:
        - emsg: "Error: An error occurred"
        - ecode: 1
        - eobj: None
        - traceback_info contains:
            - "Traceback (simplified message):"
            - "Exception Type: ValueError"
            - "Error: An error occurred"
    """
    try:
        raise ValueError("An error occurred")
    except Exception as e:
        structured_error = handle_exception(e, verbose=True)

    captured = capfd.readouterr()
    assert "Traceback (most recent call last):" in captured.err
    assert "ValueError: An error occurred" in captured.err
    assert "Custom Traceback (simplified and more readable):" in captured.err

    assert structured_error.emsg == "Error: An error occurred"
    assert structured_error.ecode == 1
    assert structured_error.eobj is None
    assert "Traceback (simplified message):" in structured_error.traceback_info
    assert "Exception Type: ValueError" in structured_error.traceback_info
    assert "Error: An error occurred" in structured_error.traceback_info


@pytest.mark.parametrize("error_class, default_ecode, default_msg", [
    (InvoiceModeError, 100, "InvoiceMode Error"),
    (ExcelInvoiceModeError, 101, "ExcelInvoiceMode Error"),
    (MultiDataTileModeError, 102, "MultiDataTileMode Error"),
    (RdeFormatModeError, 103, "RdeFormatMode Error"),
])
def test_custom_mode_error_default(error_class, default_ecode, default_msg):
    """Test InvoiceModeError with default parameters."""
    error = error_class()
    assert error.emsg == default_msg
    assert error.ecode == default_ecode
    assert error.eobj is None
    assert error.traceback_info is None


@pytest.mark.parametrize("error_class, default_ecode, default_msg", [
    (InvoiceModeError, 100, "InvoiceMode Error: "),
    (ExcelInvoiceModeError, 101, "ExcelInvoiceMode Error: "),
    (MultiDataTileModeError, 102, "MultiDataTileMode Error: "),
    (RdeFormatModeError, 103, "RdeFormatMode Error: "),
])
def test_mode_error_custom_message(error_class, default_ecode, default_msg):
    """Test custom error with a custom message."""
    custom_message = "Custom error message"
    error = error_class(emsg=custom_message)
    assert error.emsg == f"{default_msg}{custom_message}"
    assert error.ecode == default_ecode
    assert error.eobj is None
    assert error.traceback_info is None


@pytest.mark.parametrize("error_class, default_ecode, default_msg", [
    (InvoiceModeError, 100, "InvoiceMode Error"),
    (ExcelInvoiceModeError, 101, "ExcelInvoiceMode Error"),
    (MultiDataTileModeError, 102, "MultiDataTileMode Error"),
    (RdeFormatModeError, 103, "RdeFormatMode Error"),
])
def test_mode_error_custom_code(error_class, default_ecode, default_msg):
    """Test custom error with a custom error code."""
    custom_code = 999
    error = error_class(ecode=custom_code)
    assert error.emsg == default_msg
    assert error.ecode == custom_code
    assert error.eobj is None
    assert error.traceback_info is None


@pytest.mark.parametrize("error_class, default_ecode, default_msg", [
    (InvoiceModeError, 100, "InvoiceMode Error"),
    (ExcelInvoiceModeError, 101, "ExcelInvoiceMode Error"),
    (MultiDataTileModeError, 102, "MultiDataTileMode Error"),
    (RdeFormatModeError, 103, "RdeFormatMode Error"),
])
def test_mode_error_custom_object(error_class, default_ecode, default_msg):
    """Test custom error with a custom error object."""
    custom_object = {"key": "value"}
    error = error_class(eobj=custom_object)
    assert error.emsg == default_msg
    assert error.ecode == default_ecode
    assert error.eobj == custom_object
    assert error.traceback_info is None


@pytest.mark.parametrize("error_class, default_ecode, default_msg", [
    (InvoiceModeError, 100, "InvoiceMode Error"),
    (ExcelInvoiceModeError, 101, "ExcelInvoiceMode Error"),
    (MultiDataTileModeError, 102, "MultiDataTileMode Error"),
    (RdeFormatModeError, 103, "RdeFormatMode Error"),
])
def test_mode_error_custom_traceback(error_class, default_ecode, default_msg):
    """Test custom error with a custom traceback."""
    custom_traceback = "Custom traceback info"
    error = error_class(traceback_info=custom_traceback)
    assert error.emsg == default_msg
    assert error.ecode == default_ecode
    assert error.eobj is None
    assert error.traceback_info == custom_traceback


@pytest.mark.parametrize("error_class, default_ecode, default_msg", [
    (InvoiceModeError, 100, "InvoiceMode Error"),
    (ExcelInvoiceModeError, 101, "ExcelInvoiceMode Error"),
    (MultiDataTileModeError, 102, "MultiDataTileMode Error"),
    (RdeFormatModeError, 103, "RdeFormatMode Error"),
])
def test_mode_error_all_custom(error_class, default_ecode, default_msg):
    """Test custom error with all custom parameters."""
    custom_message = "Custom error message"
    custom_code = 999
    custom_object = {"key": "value"}
    custom_traceback = "Custom traceback info"
    error = error_class(emsg=custom_message, ecode=custom_code, eobj=custom_object, traceback_info=custom_traceback)
    assert error.emsg == f"{default_msg}: {custom_message}"
    assert error.ecode == custom_code
    assert error.eobj == custom_object
    assert error.traceback_info == custom_traceback


class CustomException(Exception):
    def __init__(self, ecode, emsg):
        super().__init__(emsg)
        self.ecode = ecode


def test_skip_exception_context_enabled():
    logger = logging.getLogger("test_logger")
    logger.setLevel(logging.WARNING)

    exception_code = 100
    exception_message = "Test exception"

    with skip_exception_context(CustomException, logger=logger, enabled=True) as error_info:
        # コンテキスト内で例外を発生させる
        raise CustomException(exception_code, exception_message)
    assert error_info["code"] == exception_code, "Error codeが正しく設定されていません。"
    assert error_info["message"] == f"Error: {exception_message}", "Error messageが正しく設定されていません。"
    assert "Traceback" in error_info["stacktrace"], "Stack traceが正しく設定されていません。"


def test_catch_exception_with_message_with_structured_error():
    """Test catch_exception_with_message decorator when StructuredError is raised inside the decorated function.

    This test reproduces the issue reported in issue_203 where the custom error message
    and error code from StructuredError should take precedence over the decorator's values.

    Steps:
    1. Create a function decorated with catch_exception_with_message
    2. Inside the function, raise a StructuredError with specific message and code
    3. Verify that the resulting StructuredError has the values from the inner StructuredError,
       not from the decorator
    """
    @catch_exception_with_message(error_message="Dataset processing failed", error_code=50)
    def dataset_function():
        raise StructuredError("error message in dataset()", 21)

    with pytest.raises(StructuredError) as exc_info:
        dataset_function()

    # The inner StructuredError values should take precedence
    assert exc_info.value.emsg == "Error: error message in dataset()"
    assert exc_info.value.ecode == 21


def test_catch_exception_with_message_with_generic_exception():
    """Test catch_exception_with_message decorator when generic Exception is raised.

    This test verifies that when a generic exception is raised inside a decorated function,
    the decorator's custom message and error code are used.

    Steps:
    1. Create a function decorated with catch_exception_with_message
    2. Inside the function, raise a generic Exception
    3. Verify that the resulting StructuredError has the values from the decorator
    """
    @catch_exception_with_message(error_message="Wrapper error", error_code=100)
    def dataset_function():
        raise ValueError("Generic error")

    with pytest.raises(StructuredError) as exc_info:
        dataset_function()

    # The decorator's values should be used
    assert exc_info.value.emsg == "Error: Wrapper error"
    assert exc_info.value.ecode == 100


def test_handle_and_exit_on_structured_error_with_traceback_info(capfd):
    """Test handle_and_exit_on_structured_error when StructuredError has traceback_info.

    This test verifies that when a StructuredError already has traceback_info,
    that information is used directly without additional processing.
    """
    logger = Mock()
    existing_traceback = "Existing traceback information"
    error = StructuredError("Test error", 42, traceback_info=existing_traceback)

    with patch('rdetoolkit.errors.write_job_errorlog_file') as mock_write:
        with pytest.raises(SystemExit):
            handle_and_exit_on_structured_error(error, logger)

    # Check that existing traceback_info was used
    captured = capfd.readouterr()
    assert existing_traceback in captured.err

    # Check that job.failed was written with correct values
    mock_write.assert_called_once_with(42, "Test error")
    logger.exception.assert_called_once_with("Test error")


def test_handle_and_exit_on_structured_error_without_traceback_info(capfd):
    """Test handle_and_exit_on_structured_error when StructuredError has no traceback_info.

    This test verifies that when a StructuredError has no traceback_info,
    handle_exception is called to generate a formatted traceback.
    """
    logger = Mock()
    error = StructuredError("Test error", 42)

    with patch('rdetoolkit.errors.write_job_errorlog_file') as mock_write:
        with patch('rdetoolkit.errors.handle_exception') as mock_handle:
            mock_handle.return_value = StructuredError(traceback_info="Generated traceback")

            with pytest.raises(SystemExit):
                handle_and_exit_on_structured_error(error, logger)

    # Check that handle_exception was called to generate traceback
    mock_handle.assert_called_once_with(error, verbose=True, config=None)

    # Check that generated traceback was used
    captured = capfd.readouterr()
    assert "Generated traceback" in captured.err

    # Check that job.failed was written with correct values
    mock_write.assert_called_once_with(42, "Test error")
    logger.exception.assert_called_once_with("Test error")


def test_handle_exception_with_config_compact():
    config = Config(
        traceback=TracebackSettings(
            enable=True,
            format="compact",
            include_context=True,
        )
    )

    try:
        password = "secret123"
        raise ValueError("Test error with config")
    except Exception as e:
        result = handle_exception(e, config=config)

    assert isinstance(result, StructuredError)
