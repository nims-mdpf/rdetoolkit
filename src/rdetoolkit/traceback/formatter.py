from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
import platform
import linecache
import traceback
from pathlib import Path
from types import TracebackType, FrameType

from rdetoolkit.models.config import TracebackSettings
from rdetoolkit.traceback.masking import SecretsSanitizer


class CompactTraceFormatter:
    """Formats exception traceback in compact format, machine-readable format.

    This formatter generates strucured stacktraces optimized for LLMs
    consumptions while maintaining human readability through key=value pairs.
    """

    def __init__(self, config: TracebackSettings | None = None):
        self.config = config or TracebackSettings()  # type: ignore[call-arg]
        self._cwd = os.getcwd()
        self.masker = SecretsSanitizer(custom_patterns=self.config.sensitive_patterns)

    def format(self, exc: Exception) -> str:
        """Format an exceptino into compact stacktrace format.

        Args:
            exc: The exception to format.

        Returns:
            str: Formatted stacktrace string wrapped in <STACKTRACE> sentinels.

        """
        lines = []

        exc_type, exc_value, exc_traceback = sys.exc_info()
        if exc_traceback is None:
            exc_traceback = exc.__traceback__

        lines.append(self._format_cfg_line())
        lines.append(self._format_e_line(exc, exc_type))

        if self.config.include_env:
            lines.append(self._format_t_line())

        # Keep track of traceback for root cause analysis
        traceback_list = []
        if exc_traceback:
            if self.config.include_locals:
                frames_with_locals = self._extract_frames_with_locals(exc_traceback)
                for idx, (frame_summary, frame_locals) in enumerate(frames_with_locals):
                    lines.append(self._format_f_line(idx, frame_summary, frame_locals))
                    traceback_list.append(frame_summary)
            else:
                tb_list = traceback.extract_tb(exc_traceback)
                for idx, frame in enumerate(tb_list):
                    lines.append(self._format_f_line(idx, frame, None))
                    traceback_list.append(frame)

        lines.append(self._format_rc_line(exc, traceback_list))
        content = "\n".join(lines)
        return f"<STACKTRACE>\n{content}\n</STACKTRACE>"

    def _format_cfg_line(self) -> str:
        """Format the CFG (configration) line.

        Returns:
            str: CFG line with version and setting.
        """
        ctx = 1 if self.config.include_context else 0
        local_flag = 1 if self.config.include_locals else 0
        env = 1 if self.config.include_env else 0

        return f"CFG v=1 ctx={ctx} locals={local_flag} env={env}"

    def _format_e_line(self, exc: Exception, exc_type: type | None) -> str:
        """Format the E (exception) line.

        Args:
            exc: The exception to format.
            exc_type: The type of the exception.

        Returns:
            str: Formatted exception line.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        exc_type_name = exc_type.__name__ if exc_type else type(exc).__name__
        msg = json.dumps(str(exc), ensure_ascii=False)

        return f'E ts={timestamp} type="{exc_type_name}" msg={msg}'

    def _format_t_line(self) -> str:
        """Format the T (environment) line.

        Returns:
            str: T line with Python version and OS info.
        """
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        os_info = f"{platform.system()}{platform.release()}"
        return f'T python="{python_version}" os="{os_info}"'

    def _format_f_line(self, index: int, frame: traceback.FrameSummary, frame_locals: dict | None = None) -> str:
        """Format the F (frame) line.

        Args:
            index: The index of the frame.
            frame: The frame to format.
            frame_locals: Optional dict of local variable name -> value captured for this frame.
                Provided only when `TracebackSettings.include_locals` is enabled; otherwise None.
                Values are sanitized/truncated before serialization

        Returns:
            str: Formatted frame line.
        """
        module = self._extract_module_name(frame.filename)
        filename = Path(frame.filename).name
        file_loc = f"{filename}:{frame.lineno}"

        in_app = self._is_in_app(frame.filename)
        in_app_flag = 1 if in_app else 0

        line = f'F{index} mod="{module}" fn="{frame.name}" file="{file_loc}" in_app={in_app_flag}'

        if self.config.include_context and index != 0:
            raw_line = getattr(frame, "line", None)
            if raw_line:
                stripped = raw_line.strip()
                if stripped:
                    context_json = json.dumps(stripped, ensure_ascii=False)
                    line += f' context={context_json}'

        if self.config.include_locals and frame_locals:
            processed_locals = self.masker.process_locals(
                frame_locals,
                max_size=self.config.max_locals_size,
            )
            for var_name, var_value in processed_locals.items():
                value_json = json.dumps(var_value, ensure_ascii=False)
                line += f' locals.{var_name}={value_json}'

        return line

    def _format_rc_line(self, exc: Exception, traceback_list: list) -> str:
        """Format the RC (root cause) line.

        Args:
            exc: The exception to format.
            traceback_list: List of traceback frames.

        Returns:
            str: Formatted root cause line.
        """
        hint = str(exc).split('\n')[0] if str(exc) else "Error occurred"
        hint_json = json.dumps(hint, ensure_ascii=False)
        # Determine the root cause frame
        # If there's an exception chain, the deepest frame is typically the root cause
        # Otherwise, use the first frame (F0) where the error was raised
        frame_idx = 0

        # Check for exception chain to find the actual root cause
        if hasattr(exc, '__cause__') and exc.__cause__ is not None:
            # For explicit exception chaining (raise ... from ...)
            # The root cause is typically in the earlier frames
            # We could analyze __cause__.__traceback__ but for now keep it simple
            frame_idx = len(traceback_list) - 1 if traceback_list else 0
        elif hasattr(exc, '__context__') and exc.__context__ is not None:
            # For implicit exception chaining
            # Similar logic - the context is often the root cause
            frame_idx = len(traceback_list) - 1 if traceback_list else 0
        else:
            # No exception chain - the immediate frame is the root cause
            frame_idx = 0

        # Ensure frame_idx is within bounds
        if traceback_list:
            frame_idx = min(frame_idx, len(traceback_list) - 1)
            frame_idx = max(frame_idx, 0)

        return f'RC frame="F{frame_idx}" hint={hint_json}'

    def _extract_module_name(self, filepath: str) -> str:
        """Extract module name from filepath.

        Args:
            filepath: Full path to the python file.

        Returns:
            Module name in dot notation or filepath if extraction fails.

        """
        path = Path(filepath)

        parts = path.parts
        if "site-packages" in parts:
            idx = parts.index("site-packages")
            module_parts = parts[idx + 1:]
            if module_parts and module_parts[-1].endswith('.py'):
                module_parts = module_parts[:-1] + (module_parts[-1][:-3],)
            return ".".join(module_parts)

        try:
            relative = path.relative_to(self._cwd)
            module_parts = relative.parts
            if module_parts and module_parts[-1].endswith('.py'):
                module_parts = module_parts[:-1] + (module_parts[-1][:-3],)
            return ".".join(module_parts)
        except ValueError:
            pass

        return path.stem

    def _is_in_app(self, filepath: str) -> bool:
        """Determin if a file is part of the application code.

        Args:
            filepath: Full path to the Python file.

        Returns:
            bool: True if the file is application code, False if it's a dependency.
        """
        path = Path(filepath).absolute()
        sfilepath = str(path)

        try:
            path.relative_to(self._cwd)
            return True
        except ValueError:
            pass

        package_indicators = ['site-packages', 'dist-packages', 'vendor', 'venv', 'virtualenv', '.tox']
        for indicator in package_indicators:
            if indicator in sfilepath:
                return False

        if sfilepath.startswith(sys.prefix):
            return False

        return False

    def _extract_frames_with_locals(self, tb: TracebackType) -> list[tuple[traceback.FrameSummary, dict]]:
        frames_with_locals = []
        current: TracebackType | None = tb
        frames = []
        while current is not None:
            frames.append(current.tb_frame)
            current = current.tb_next

        for frame in frames:
            summary = traceback.FrameSummary(
                filename=frame.f_code.co_filename,
                lineno=frame.f_lineno,
                name=frame.f_code.co_name,
                line=self._get_source_line(frame),
            )
            frame_locals = frame.f_locals.copy()
            frames_with_locals.append((summary, frame_locals))
        return frames_with_locals

    def _get_source_line(self, frame: FrameType) -> str | None:
        try:
            return linecache.getline(frame.f_code.co_filename, frame.f_lineno).strip()
        except Exception:
            return None
