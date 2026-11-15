"""Characterize frozen v1 traceback behavior and its disclosure limits (#673).

Test ids LEG-001 to LEG-010 name the retained behaviours in the compatibility matrix
of docs/usage/structured_process/traceback.en.md.
These are existing compatibility contracts; no legacy implementation changes.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from rdetoolkit.config import get_traceback_settings_from_env
from rdetoolkit.errors import handle_exception
from rdetoolkit.models.config import Config, TracebackSettings
from rdetoolkit.traceback.formatter import CompactTraceFormatter
from rdetoolkit.traceback.masking import SecretsSanitizer


@pytest.fixture(autouse=True)
def clear_trace_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate compatibility controls from the developer's environment."""
    monkeypatch.delenv("TRACE_VERBOSE", raising=False)
    monkeypatch.delenv("TRACE_FORMAT", raising=False)


class ExplosiveRepr:
    """Expose accidental evaluation of arbitrary values."""

    def __repr__(self) -> str:
        msg = "local repr must not be evaluated"
        raise AssertionError(msg)


def test_default_formatter_does_not_inspect_local_values() -> None:
    """LEG-001: source, local values and runtime details are opt-in."""
    # Given: the legacy formatter defaults and a value unsafe to represent.
    measurement = ExplosiveRepr()
    formatter = CompactTraceFormatter()
    # When: formatting the current exception with default flags.
    try:
        msg = "ordinary failure"
        raise ValueError(msg)
    except ValueError as exc:
        output = formatter.format(exc)
    # Then: no local representation or source line/environment is included.
    assert measurement is not None
    assert "CFG v=1 ctx=0 locals=0 env=0" in output
    assert "locals.measurement=" not in output
    assert " context=" not in output
    assert "T python=" not in output


@pytest.mark.parametrize("value", [None, "", "off", "false", "disable", "disabled", "OFF"])
def test_disabling_compact_keeps_traditional_traceback(value: str | None, monkeypatch: pytest.MonkeyPatch) -> None:
    """LEG-002: disabling compact formatting does not silence traceback text."""
    # Given: a disabled or absent compatibility environment control.
    if value is not None:
        monkeypatch.setenv("TRACE_VERBOSE", value)
    # When: handling a legacy failure.
    try:
        msg = "legacy fallback"
        raise ValueError(msg)
    except ValueError as exc:
        result = handle_exception(exc)
    # Then: the traditional traceback contract remains active.
    assert result.traceback_info is not None
    assert "Traceback (simplified message):" in result.traceback_info
    assert "<STACKTRACE>" not in result.traceback_info


@pytest.mark.parametrize("output_format", ["compact", "python", "duplex"])
def test_legacy_environment_flags(output_format: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """LEG-003: TRACE_* continues selecting all legacy formats and flags."""
    # Given: each documented output format with explicit detail flags.
    monkeypatch.setenv("TRACE_VERBOSE", "context,locals,env")
    monkeypatch.setenv("TRACE_FORMAT", output_format)
    # When: reading the existing environment configuration.
    settings = get_traceback_settings_from_env()
    # Then: flags and format retain their original meanings.
    assert settings is not None
    assert settings.enabled and settings.include_context and settings.include_locals and settings.include_env
    assert settings.format == output_format


def test_explicit_disabled_config_wins_over_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """LEG-004: explicit Config retains precedence over TRACE_VERBOSE."""
    # Given: compact enabled through the environment but disabled in Config.
    monkeypatch.setenv("TRACE_VERBOSE", "context,locals,env")
    monkeypatch.setenv("TRACE_FORMAT", "compact")
    config = Config(traceback=TracebackSettings(enabled=False))
    # When: handling a failure with explicit Config.
    try:
        msg = "configured fallback"
        raise ValueError(msg)
    except ValueError as exc:
        result = handle_exception(exc, config=config)
    # Then: Config wins and the legacy fallback is retained.
    assert "<STACKTRACE>" not in (result.traceback_info or "")
    assert "Traceback (simplified message):" in (result.traceback_info or "")


def test_name_masking_avoids_sensitive_repr() -> None:
    """LEG-005: recognized sensitive names are masked before repr."""
    # Given: a value that must not be represented.
    sanitizer = SecretsSanitizer()
    # When: representing it under a recognized sensitive variable name.
    result = sanitizer.mask_value("api_token", ExplosiveRepr())
    # Then: masking does not call arbitrary value methods.
    assert result == "***"


def test_neutral_nested_values_are_not_anonymized() -> None:
    """LEG-006: preserved name masking is not a recursive privacy boundary."""
    # Given: a secret nested under a neutral top-level variable name.
    sanitizer = SecretsSanitizer()
    # When: the compatibility sanitizer represents that value.
    result = sanitizer.mask_value("measurement", {"token": "synthetic-private-value"})
    # Then: the value remains visible, matching the documented limitation.
    assert "synthetic-private-value" in result


def test_legacy_exception_message_remains_user_text() -> None:
    """LEG-007: legacy messages retain their public raw-text contract."""
    # Given: a sensitive message unsuitable for sharing.
    formatter = CompactTraceFormatter()
    # When: formatting it with the compatibility API.
    result = formatter.format(ValueError("token=synthetic-private-value"))
    # Then: raw message text remains; agent diagnostics use a separate boundary.
    assert "token=synthetic-private-value" in result


@pytest.mark.parametrize("chain", ["cause", "context", "suppressed"])
def test_verbose_python_exception_chain(chain: str, capsys: pytest.CaptureFixture[str]) -> None:
    """LEG-008: verbose Python traceback honors the Python chain display."""
    # Given: explicit, implicit or suppressed Python exception chaining.
    config = Config(traceback=TracebackSettings(enabled=True, format="python"))
    try:
        try:
            msg = "synthetic-inner-message"
            raise KeyError(msg)
        except KeyError as inner:
            if chain == "cause":
                msg = "synthetic-outer-message"
                raise ValueError(msg) from inner
            if chain == "suppressed":
                msg = "synthetic-outer-message"
                raise ValueError(msg) from None
            msg = "synthetic-outer-message"
            raise ValueError(msg)  # noqa: B904 -- deliberately test implicit exception context
    except ValueError as exc:
        # When: preserving verbose Python formatting on the v1 entry.
        result = handle_exception(exc, config=config, verbose=True)
    # Then: Python's full traceback preserves its cause/context display rules.
    output = capsys.readouterr().err
    assert "synthetic-outer-message" in output
    assert ("synthetic-inner-message" in output) == (chain != "suppressed")
    if chain == "cause":
        assert "direct cause" in output
    elif chain == "context":
        assert "During handling" in output
    assert "Traceback (simplified message):" in (result.traceback_info or "")


def test_invalid_environment_format_keeps_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """LEG-009: invalid compatibility formats retain model validation."""
    # Given: explicit compact details and an invalid format.
    monkeypatch.setenv("TRACE_VERBOSE", "context")
    monkeypatch.setenv("TRACE_FORMAT", "invalid")
    # When / Then: resolving settings keeps the existing validation failure.
    with pytest.raises(ValidationError, match="Invalid format"):
        get_traceback_settings_from_env()


def test_errors_compatibility_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    """LEG-010: runtime aliases declared by errors.pyi remain callable."""
    # Given: retained public compatibility exports.
    from rdetoolkit.errors import CompactTraceFormatter as FormatterAlias
    from rdetoolkit.errors import get_traceback_settings_from_env as settings_alias

    monkeypatch.setenv("TRACE_VERBOSE", "env")
    # When: constructing the formatter and resolving its environment alias.
    formatter = FormatterAlias(TracebackSettings())
    settings = settings_alias()
    # Then: aliases resolve to the existing implementation and model.
    assert isinstance(formatter, CompactTraceFormatter)
    assert settings == get_traceback_settings_from_env()
