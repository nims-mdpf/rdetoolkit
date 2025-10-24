import json
from unittest.mock import Mock, patch
from types import SimpleNamespace
from pathlib import Path
import tempfile

import pytest
from rdetoolkit.models.config import TracebackSettings
from rdetoolkit.traceback.formatter import CompactTraceFormatter


class TestCompactTraceFormatter:
    @pytest.fixture
    def formatter(self):
        return CompactTraceFormatter()

    @pytest.fixture
    def formatter_with_all_option(self):
        config = TracebackSettings(
            include_context=True,
            include_locals=True,
            include_env=True,
        )
        return CompactTraceFormatter(config)

    @pytest.fixture
    def sample_exception(self):
        """
        This fixture is set up because the test for `CompactTraceFormatter` needs an exception object
        that actually contains traceback information. By raising and catching an exception inside a nested function,
        it ensures that the exception object has a valid `__traceback__` and returns that object.
        """
        try:
            def inner_function():
                raise ValueError("Test error message")

            def outer_function():
                inner_function()

            outer_function()
        except Exception as e:
                return e

    def test_formatter_initialization(self):
        formatter = CompactTraceFormatter()
        assert isinstance(formatter.config, TracebackSettings)
        assert formatter.config.include_context is False

        config = TracebackSettings(include_context=True)
        formatter_with_config = CompactTraceFormatter(config)
        assert formatter_with_config.config.include_context is True

    def test_format_basic_structure(self, formatter, sample_exception):
        """Test basic format structure with sentinels."""
        result = formatter.format(sample_exception)

        assert result.startswith("<STACKTRACE>")
        assert result.endswith("</STACKTRACE>")

        lines = result.strip().split('\n')
        assert lines[0] == "<STACKTRACE>"
        assert lines[-1] == "</STACKTRACE>"

        content_lines = lines[1:-1]
        assert len(content_lines) >= 4

    def test_cfg_line_format(self, formatter):
        """Test CFG line formatting with different configurations."""
        cfg_line = formatter._format_cfg_line()
        assert cfg_line == "CFG v=1 ctx=0 locals=0 env=0"

        config = TracebackSettings(
            include_context=True,
            include_locals=True,
            include_env=True
        )

    @patch('rdetoolkit.traceback.formatter.datetime')
    def test_e_line_format(self, mock_datetime_class, formatter):
        """Test E line formatting with different configurations."""
        fixed_time = Mock()
        fixed_time.strftime.return_value = "2023-01-01T12:00:00Z"
        mock_datetime_class.now.return_value = fixed_time
        exc = ValueError("Test message with \"quotes\" and\nnewlines")
        exc_type = type(exc)
        e_line = formatter._format_e_line(exc, exc_type)

        expected_msg = json.dumps("Test message with \"quotes\" and\nnewlines", ensure_ascii=False)
        expected = f'E ts=2023-01-01T12:00:00Z type="ValueError" msg={expected_msg}'
        assert e_line == expected

    @patch('rdetoolkit.traceback.formatter.sys')
    @patch('rdetoolkit.traceback.formatter.platform')
    def test_t_line_format(self, mock_platform, mock_sys, formatter_with_all_option):
        """TEST T line formatting."""
        mock_sys.version_info = SimpleNamespace(major=3, minor=10, micro=12)
        mock_platform.system.return_value = "Linux"
        mock_platform.release.return_value = "6.8.0"

        t_line = formatter_with_all_option._format_t_line()
        expected = 'T python="3.10.12" os="Linux6.8.0"'
        assert t_line == expected

    def test_f_line_format_basic(self, formatter_with_all_option):
        """Test F line formatting without context"""
        frame = Mock()
        frame.filename = "/path/to/myapp/module.py"
        frame.name = "test_function"
        frame.lineno = 40
        frame.line = "    raise Exception('test with \"quotes\"')"

        with patch.object(formatter_with_all_option, '_extract_module_name') as mock_extract:
            mock_extract.return_value = "myapp.module"
            with patch.object(formatter_with_all_option, '_is_in_app') as mock_is_in_app:
                mock_is_in_app.return_value = True
                f_line = formatter_with_all_option._format_f_line(0, frame, None)
                # context_json = json.dumps("raise Exception('test with \"quotes\"')", ensure_ascii=False)
                expected = 'F0 mod="myapp.module" fn="test_function" file="module.py:40" in_app=1'
                assert f_line == expected

    def test_f_line_format_with_context(self, formatter_with_all_option):
        frame = Mock()
        frame.filename = "/path/to/myapp/module.py"
        frame.name = "test_function"
        frame.lineno = 42
        frame.line = "    raise Exception('test with \"quotes\"')"
        assert frame.line is not None
        assert frame.line.strip() != ""

        with patch.object(formatter_with_all_option, '_extract_module_name') as mock_extract:
            mock_extract.return_value = "myapp.module"
            with patch.object(formatter_with_all_option, '_is_in_app') as mock_is_in_app:
                mock_is_in_app.return_value = True
                f_line = formatter_with_all_option._format_f_line(1, frame, None)

                context_json = json.dumps("raise Exception('test with \"quotes\"')", ensure_ascii=False)
                expected = f'F1 mod="myapp.module" fn="test_function" file="module.py:42" in_app=1 context={context_json}'
                assert f_line == expected

    def test_rc_line_format(self, formatter):
        """Test RC line formatting"""
        exc = ValueError("Multi-line\nerror message")
        # Test with empty traceback list (defaults to F0)
        rc_line = formatter._format_rc_line(exc, [])

        hint_json = json.dumps("Multi-line", ensure_ascii=False)
        expected = f'RC frame="F0" hint={hint_json}'
        assert rc_line == expected
        
        # Test with traceback list
        import traceback
        try:
            raise ValueError("Test error")
        except Exception as e:
            tb_list = traceback.extract_tb(e.__traceback__)
            rc_line = formatter._format_rc_line(e, tb_list)
            # Should still be F0 for simple exception
            assert 'RC frame="F0"' in rc_line

    def test_extract_module_name_relative_to_cwd(self, formatter):
        """Test extracting module name relative to cwd"""
        with tempfile.TemporaryDirectory() as temp_dir:
            tempdir_path = Path(temp_dir)
            module_file = tempdir_path / "mypackage" / "submodule" / "mymodule.py"
            module_file.parent.mkdir(parents=True, exist_ok=True)
            module_file.touch()

            formatter._cwd = tempdir_path

            result = formatter._extract_module_name(str(module_file))
            assert result == "mypackage.submodule.mymodule"

    def test_extract_module_name_fallback(self, formatter):
        filepath = "/some/random/path/module.py"
        result = formatter._extract_module_name(filepath)
        assert result == "module"

    def test_is_in_app_current_directory(self, formatter):
        with tempfile.TemporaryDirectory() as temp_dir:
            tmpdir_path = Path(temp_dir)
            app_file = tmpdir_path / "myapp.py"
            app_file.touch()

            formatter._cwd = tmpdir_path

            result = formatter._is_in_app(str(app_file))
            assert result is True

    def test_is_in_app_site_packages(self, formatter):
        """Test in_app detection for site-packages files."""
        filepath = "/usr/local/lib/python3.10/site-packages/requests/api.py"
        result = formatter._is_in_app(filepath)
        assert result is False

    def test_is_in_app_standard_library(self, formatter):
        with patch('rdetoolkit.traceback.formatter.sys.prefix', '/usr/local'):
            filepath = "/usr/local/lib/python3.10/json/__init__.py"
            result = formatter._is_in_app(filepath)
            assert result is False

    def test_is_in_app_external_directory(self, formatter):
        filepath = "/tmp/custom/location/module.py"
        result = formatter._is_in_app(filepath)
        assert result is False

    def test_full_format_integration(self, formatter, sample_exception):
        """Test full format integration with real exception."""
        result = formatter.format(sample_exception)

        lines = result.strip().split('\n')
        content_lines = lines[1:-1]

        assert content_lines[0].startswith("CFG ")
        assert content_lines[1].startswith("E ")

        frame_lines = [line for line in content_lines if line.startswith("F")]
        assert len(frame_lines) >= 1

        assert content_lines[-1].startswith("RC ")

    def test_format_with_no_traceback(self, formatter):
        """Test formatting when exception has no traceback."""
        exc = ValueError("Test error")
        exc.__traceback__ = None

        with patch('rdetoolkit.traceback.formatter.sys.exc_info') as mock_exc_info:
            mock_exc_info.return_value = (None, None, None)

            result = formatter.format(exc)

            lines = result.strip().split('\n')
            content_lines = lines[1:-1]

            assert content_lines[0].startswith("CFG ")
            assert content_lines[1].startswith("E ")
            assert content_lines[-1].startswith("RC ")

    def test_json_escaping_in_output(self, formatter):
        exc = ValueError('Message with "quotes", \n newlines, and \t tabs')
        result = formatter.format(exc)

        e_line = [line for line in result.split('\n') if line.startswith('E')][0]

        assert 'quotes' in e_line
        assert '\\n' in e_line
        assert '\\t' in e_line

    def test_format_with_locals_disable(self, formatter):
        """Test that locals are not included when disabled."""
        try:
            password = "secret123"
            data = {"key": "value"}
            raise ValueError("Test error")
        except Exception as e:
            result = formatter.format(e)

            assert "local.password" not in result
            assert "local.data" not in result

    def test_format_includes_env_context_and_locals(self):
        """Ensure format emits env/context information and sanitized locals."""
        config = TracebackSettings(
            include_context=True,
            include_locals=True,
            include_env=True,
            max_locals_size=64,
        )
        formatter = CompactTraceFormatter(config)

        def inner_function():
            secret_token = "abc123"
            regular_value = {"key": "value"}
            raise RuntimeError("boom")

        def outer_function():
            helper = "outer"
            inner_function()

        formatted = ""
        try:
            outer_function()
        except RuntimeError as exc:
            formatted = formatter.format(exc)

        lines = formatted.split('\n')
        t_line = next(line for line in lines if line.startswith('T '))
        assert 'python="' in t_line

        frame_lines = [line for line in lines if line.startswith('F')]
        assert any(' context=' in line for line in frame_lines)
        assert any('locals.secret_token="***"' in line for line in frame_lines)
        assert any('locals.regular_value=' in line for line in frame_lines)

    def test_extract_module_name_site_packages(self, formatter):
        path = "/usr/local/lib/python3.10/site-packages/example/pkg/module.py"
        result = formatter._extract_module_name(path)
        assert result == "example.pkg.module"

    def test_get_source_line_error_handling(self, formatter):
        fake_frame = SimpleNamespace(
            f_code=SimpleNamespace(co_filename="nonexistent.py"),
            f_lineno=10,
        )
        with patch('rdetoolkit.traceback.formatter.linecache.getline', side_effect=OSError):
            assert formatter._get_source_line(fake_frame) is None

    def test_rc_line_with_explicit_cause_uses_last_frame(self, formatter):
        import traceback

        rc_line = ""
        tb_list: list = []
        try:
            try:
                raise ValueError("primary error")
            except ValueError as inner:
                raise RuntimeError("wrapped error") from inner
        except RuntimeError as exc:
            tb_list = traceback.extract_tb(exc.__traceback__)
            rc_line = formatter._format_rc_line(exc, tb_list)
        assert f'frame="F{len(tb_list) - 1}"' in rc_line

    def test_rc_line_with_implicit_context_uses_last_frame(self, formatter):
        import traceback

        rc_line = ""
        tb_list: list = []
        try:
            try:
                raise KeyError("first error")
            except KeyError:
                raise RuntimeError("second error")
        except RuntimeError as exc:
            tb_list = traceback.extract_tb(exc.__traceback__)
            rc_line = formatter._format_rc_line(exc, tb_list)
        assert f'frame="F{len(tb_list) - 1}"' in rc_line
