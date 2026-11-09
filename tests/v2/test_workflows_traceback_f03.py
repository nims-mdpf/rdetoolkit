"""Session RC1-INT-F03: v1 traceback settings on the v1 entry, v1.7.1 as the oracle.

Operator ruling 2026-11-08 (Design §11 overrides contracts.md §3.2): the seven
``traceback.*`` keys raise no ``DeprecationWarning`` anywhere, stay out of the
strict ``RdeConfig``, and are carried out of band to the v1 entry, which writes
the stderr traceback v1.7.1 wrote for a failed run. v1.7.1 was installed in a
scratch venv and run as the oracle; the markers below are the stable lines its
formatter (``errors.handle_exception``) emitted:

* compact -- ``<STACKTRACE>`` ... ``</STACKTRACE>`` only;
* python -- ``traceback.format_exc()`` (the full ``__cause__`` chain), the
  ``Custom Traceback (simplified and more readable)`` banner, then the
  ``Traceback (simplified message)`` block;
* duplex -- format_exc + banner, then the compact block, then the simplified
  block;
* disabled / nothing -- the python form (v1's unconditional fallback);
* ``TRACE_*`` only -- the compact form with the env flags in the ``CFG`` line;
* ``ignore_errors=True`` -- nothing at all on stderr, exit 0.

v1 formatted the exception that reached ``run()``: the raw ``StructuredError``
when the callback raised one, otherwise the ``StructuredError`` wrapper chained
``from`` the callback's exception -- in both cases the exception whose code and
message ``job.failed`` carries. The unified Runner's counterpart of that wrapper
is the ``TileExecutionError`` (3001) chained from the callback's exception.

EP / BV table:

| TC-ID      | Class    | Input                                                               | Expected                                              |
|------------|----------|---------------------------------------------------------------------|-------------------------------------------------------|
| TC-F03-001 | EP valid | each of 7 keys x {dict, v1 Config, v1 YAML} via normalize(v1)       | no warning; ``traceback`` absent from ``RdeConfig``    |
| TC-F03-002 | EP valid | 7 keys in ``data/tasksupport/rdeconfig.yaml``, v2 discovery          | no warning; ``traceback`` absent                      |
| TC-F03-003 | EP valid | successful ``workflows.run`` with ``Config(traceback=<7 keys>)``     | no new warning                                        |
| TC-F03-004 | EP valid | successful ``workflows.run``, ``config=None``, tasksupport YAML     | no new warning                                        |
| TC-F03-010 | EP inval | failing callback, ``Config`` compact                                | compact block only; job.failed = rc1; exit 1          |
| TC-F03-011 | EP inval | failing callback, ``Config`` python                                 | format_exc chain + simplified; no compact block       |
| TC-F03-012 | EP inval | failing callback, ``Config`` duplex                                 | both, in v1.7.1 order                                 |
| TC-F03-013 | EP inval | failing callback, ``Config`` disabled                               | python form (v1 fallback)                             |
| TC-F03-014 | EP inval | failing callback, ``config=None``, ``TRACE_*`` only                 | compact with ``ctx=1 locals=1``                       |
| TC-F03-015 | BV       | failing callback, ``Config()`` (traceback ``None``) + ``TRACE_*``   | env settings win (v1 fallback)                        |
| TC-F03-016 | EP inval | failing callback, nothing configured                                | python form                                           |
| TC-F03-017 | EP inval | failing callback, ``config=None``, tasksupport YAML compact         | compact block (v1 loader carries it)                  |
| TC-F03-018 | EP inval | callback raises ``StructuredError(50)``, compact                    | that error formatted, frames reach the callback       |
| TC-F03-019 | BV       | ``StructuredError`` with ``traceback_info``                         | ``traceback_info`` verbatim, formatter not consulted  |
| TC-F03-020 | EP inval | compact + ``include_locals`` + ``sensitive_patterns``               | sensitive locals masked as ``***``                    |
| TC-F03-021 | EP valid | MultiDataTile ``ignore_errors=True``, one tile fails                | exit 0, no traceback (v1.7.1 stderr was empty)        |
| TC-F03-022 | EP inval | failing callback                                                    | ``iteration(s) failed`` < traceback < notice (last)   |
| TC-F03-023 | EP inval | the formatter itself raises                                         | exit 1, notice, job.failed unchanged                  |
| TC-F03-024 | EP inval | stderr unusable                                                     | exit 1, job.failed unchanged                          |
| TC-F03-025 | EP valid | v2 entry ``run(flow=...)`` fails with ``TRACE_*`` set               | no traceback (out of scope, unchanged)                |
| TC-F03-030 | BV       | ``_v1_failure_exception``: no captured failure                      | ``None``                                              |
| TC-F03-031 | EP inval | run error without ``call_id`` (not a tile failure)                  | ``None``                                              |
| TC-F03-032 | BV       | run error ``None``                                                  | ``None``                                              |
| TC-F03-033 | EP valid | captured wrapper whose cause is a ``StructuredError``               | the cause                                             |
| TC-F03-034 | EP valid | captured wrapper with a plain cause                                 | the wrapper                                           |
| TC-F03-040 | EP valid | ``InvokerRegistry.invoke`` fails inside ``capture_target_failures`` | the exception is recorded and re-raised               |
| TC-F03-041 | EP inval | the same failure outside any capture                                | re-raised, nothing recorded, no error                 |
| TC-F03-042 | EP valid | successful invoke inside a capture                                  | nothing recorded                                      |
| TC-F03-043 | BV       | nested captures                                                     | inner records only its own; outer restored after      |
| TC-F03-044 | BV       | two failures inside one capture                                     | only the latest is held (earlier ones released)       |
| TC-F03-026 | EP valid | implicit KeyError -> StructuredError chain; run() plain / from an except | KeyError kept in the chain before the StructuredError |
"""

from __future__ import annotations

import json
import warnings
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

from rdetoolkit import workflows
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.models.config import Config, MultiDataTileSettings, SystemSettings, TracebackSettings

#: All seven v1 ``TracebackSettings`` keys with non-default values.
_ALL_TRACEBACK_KEYS: dict[str, Any] = {
    "enabled": True,
    "format": "compact",
    "include_context": True,
    "include_locals": True,
    "include_env": True,
    "max_locals_size": 1024,
    "sensitive_patterns": ["TOKEN"],
}

_CALLBACK_MESSAGE = "boom from callback"

#: rc1's ``job.failed`` for a plain callback exception -- unchanged by F03.
_RC1_JOB_FAILED = (
    "ErrorCode=3001\n"
    "ErrorMessage=Node execution failed for call unknown: boom from callback Remediation: "
    "Inspect the chained original exception (__cause__) and the call-log entry for the failing call; "
    "fix the node implementation or its inputs. Nodes are plain functions - reproduce directly with pytest.\n"
)

#: Stable v1.7.1 formatter markers (``errors.handle_exception``).
_COMPACT_OPEN = "<STACKTRACE>"
_COMPACT_CLOSE = "</STACKTRACE>"
_PY_FULL = "Traceback (most recent call last):"
_PY_CHAIN = "The above exception was the direct cause of the following exception:"
_PY_BANNER = "Custom Traceback (simplified and more readable):"
_PY_SIMPLIFIED = "Traceback (simplified message):"
_PY_EXC_TYPE = "Exception Type:"
_ITERATION_NOTICE = "1 iteration(s) failed"
_FAILURE_NOTICE = "rdetoolkit: the structured process failed; see data/job.failed for the error code"

#: Pre-existing warnings a successful v1-entry run already emitted before F03
#: (v1 ``StorageDir`` behind the log path, jsonschema's metaschema notice).
_PRE_EXISTING_WARNINGS = (
    r"get_datadir is deprecated",
    r"The metaschema specified by \$schema was not found",
)


@pytest.fixture(autouse=True)
def _no_trace_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every case starts without ``TRACE_*`` so only its own source applies."""
    monkeypatch.delenv("TRACE_VERBOSE", raising=False)
    monkeypatch.delenv("TRACE_FORMAT", raising=False)


def _seed(data_root: Path, inputs: tuple[str, ...] = ("sample.txt",)) -> None:
    """Create a valid invoice-mode input tree (one tile per input in MDT)."""
    for dirname in ("inputdata", "invoice", "tasksupport"):
        (data_root / dirname).mkdir(parents=True, exist_ok=True)
    for name in inputs:
        (data_root / "inputdata" / name).write_text("input", encoding="utf-8")
    invoice = {
        "datasetId": "f03-dataset",
        "basic": {"dateSubmitted": "2026-11-09", "dataOwnerId": "0" * 56, "dataName": "f03"},
    }
    (data_root / "invoice" / "invoice.json").write_text(json.dumps(invoice), encoding="utf-8")
    (data_root / "tasksupport" / "invoice.schema.json").write_text('{"properties": {}}', encoding="utf-8")
    (data_root / "tasksupport" / "metadata-def.json").write_text('{"constant": {}, "variable": []}', encoding="utf-8")


def _write_tasksupport_yaml(data_root: Path, traceback: dict[str, Any]) -> None:
    document = {"system": {"extended_mode": None}, "traceback": traceback}
    (data_root / "tasksupport" / "rdeconfig.yaml").write_text(yaml.safe_dump(document), encoding="utf-8")


def _failing(srcpaths: Any, resource_paths: Any) -> None:
    del srcpaths, resource_paths
    raise ValueError(_CALLBACK_MESSAGE)


def _succeeding(srcpaths: Any, resource_paths: Any) -> None:
    del srcpaths, resource_paths


def _run_v1(root: Path, monkeypatch: pytest.MonkeyPatch, callback: Callable[..., Any], config: Any) -> tuple[Any, int]:
    """Run the public v1 entry from ``root`` and return (result, exit code)."""
    monkeypatch.chdir(root)
    try:
        return workflows.run(custom_dataset_function=callback, config=config), 0
    except SystemExit as error:
        return None, int(error.code or 0)


def _job_failed(root: Path) -> str:
    return (root / "data" / "job.failed").read_text(encoding="utf-8")


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Return a project root holding a valid one-tile invoice-mode input tree."""
    _seed(tmp_path / "data")
    return tmp_path


# ---------------------------------------------------------------------------
# No DeprecationWarning for traceback.* on any path
# ---------------------------------------------------------------------------


_SOURCE_KINDS = ("dict", "config", "yaml")


def _v1_source(kind: str, key: str, value: Any, tmp_path: Path) -> object:
    section = {key: value}
    if kind == "dict":
        return {"traceback": section}
    if kind == "config":
        return Config(traceback=TracebackSettings(**section))
    path = tmp_path / "rdeconfig.yaml"
    path.write_text(yaml.safe_dump({"traceback": section}), encoding="utf-8")
    return path


@pytest.mark.parametrize("kind", _SOURCE_KINDS)
@pytest.mark.parametrize(("key", "value"), list(_ALL_TRACEBACK_KEYS.items()))
def test_v1_traceback_keys_normalize_warning_free__tc_f03_001(tmp_path: Path, kind: str, key: str, value: Any) -> None:
    """TC-F03-001: every traceback key from every v1 source normalizes silently."""
    from rdetoolkit.config.normalize import ConfigNormalizer

    # Given: one traceback key carried by a v1 dict, v1 Config, or v1 YAML file
    source = _v1_source(kind, key, value, tmp_path)

    # When: normalizing it with every warning promoted to an error
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        config = ConfigNormalizer().normalize(source, root=tmp_path, origin="v1")

    # Then: no warning was raised and the strict v2 model does not admit it
    assert "traceback" not in config.model_dump()


def test_tasksupport_traceback_discovery_warning_free__tc_f03_002(tmp_path: Path) -> None:
    """TC-F03-002: the v1 tasksupport file with all seven keys normalizes silently."""
    from rdetoolkit.config.normalize import ConfigNormalizer

    # Given: a structured program's tasksupport YAML carrying all traceback keys
    _seed(tmp_path / "data")
    _write_tasksupport_yaml(tmp_path / "data", _ALL_TRACEBACK_KEYS)

    # When: the Runner's v2 discovery falls back to the v1 tasksupport loader
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        config = ConfigNormalizer().normalize(None, root=tmp_path, origin="v2", data_root=tmp_path / "data")

    # Then: nothing warned and the setting stays out of RdeConfig
    assert "traceback" not in config.model_dump()


def _assert_run_without_new_warnings(root: Path, monkeypatch: pytest.MonkeyPatch, config: Any) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        for pattern in _PRE_EXISTING_WARNINGS:
            warnings.filterwarnings("ignore", message=pattern)
        result, code = _run_v1(root, monkeypatch, _succeeding, config)
    assert code == 0
    assert json.loads(result)["statuses"][0]["status"] == "success"


def test_successful_run_with_config_traceback_warning_free__tc_f03_003(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-F03-003: an explicit v1 Config with all traceback keys adds no warning."""
    # Given: a v1 Config carrying every traceback setting
    config = Config(traceback=TracebackSettings(**_ALL_TRACEBACK_KEYS))

    # When / Then: a successful public v1 run raises no new warning
    _assert_run_without_new_warnings(project, monkeypatch, config)


def test_successful_run_with_tasksupport_traceback_warning_free__tc_f03_004(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-F03-004: tasksupport YAML traceback settings add no warning either."""
    # Given: the settings in data/tasksupport/rdeconfig.yaml and config=None
    _write_tasksupport_yaml(project / "data", _ALL_TRACEBACK_KEYS)

    # When / Then: a successful public v1 run raises no new warning
    _assert_run_without_new_warnings(project, monkeypatch, None)


# ---------------------------------------------------------------------------
# Failing callback: stderr carries v1.7.1's traceback
# ---------------------------------------------------------------------------


def _failed_stderr(
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    config: Any,
    callback: Callable[..., Any] = _failing,
) -> str:
    capsys.readouterr()
    _, code = _run_v1(project, monkeypatch, callback, config)
    assert code == 1
    return capsys.readouterr().err


def _assert_python_form(err: str) -> None:
    assert _PY_FULL in err
    assert _PY_CHAIN in err
    assert f"ValueError: {_CALLBACK_MESSAGE}" in err
    assert _PY_BANNER in err
    assert _PY_SIMPLIFIED in err
    assert _PY_EXC_TYPE in err
    assert err.index(_PY_FULL) < err.index(_PY_BANNER) < err.index(_PY_SIMPLIFIED)


def test_config_compact__tc_f03_010(project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """TC-F03-010: Config compact writes only v1's compact block."""
    # Given: v1 Config selecting the compact format
    config = Config(traceback=TracebackSettings(enabled=True, format="compact"))

    # When: the callback fails
    err = _failed_stderr(project, monkeypatch, capsys, config)

    # Then: the compact block with the failure message, nothing python-style
    assert _COMPACT_OPEN in err
    assert _COMPACT_CLOSE in err
    assert "CFG v=1 ctx=0 locals=0 env=0" in err
    assert _CALLBACK_MESSAGE in err[err.index(_COMPACT_OPEN) : err.index(_COMPACT_CLOSE)]
    assert _PY_FULL not in err
    assert _PY_SIMPLIFIED not in err
    assert _job_failed(project) == _RC1_JOB_FAILED


def test_config_python__tc_f03_011(project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """TC-F03-011: Config python writes the chained traceback and simplified block."""
    # Given: v1 Config selecting the python format
    config = Config(traceback=TracebackSettings(enabled=True, format="python"))

    # When: the callback fails
    err = _failed_stderr(project, monkeypatch, capsys, config)

    # Then: v1's python form, the callback frame included, and no compact block
    _assert_python_form(err)
    assert "in _failing" in err
    assert _COMPACT_OPEN not in err
    assert _job_failed(project) == _RC1_JOB_FAILED


def test_config_duplex__tc_f03_012(project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """TC-F03-012: duplex writes both forms in v1.7.1's order."""
    # Given: v1 Config selecting the duplex format
    config = Config(traceback=TracebackSettings(enabled=True, format="duplex"))

    # When: the callback fails
    err = _failed_stderr(project, monkeypatch, capsys, config)

    # Then: format_exc, banner, compact block, simplified block -- in that order
    _assert_python_form(err)
    assert err.index(_PY_FULL) < err.index(_PY_BANNER) < err.index(_COMPACT_OPEN)
    assert err.index(_COMPACT_CLOSE) < err.index(_PY_SIMPLIFIED)
    assert _job_failed(project) == _RC1_JOB_FAILED


def test_config_disabled__tc_f03_013(project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """TC-F03-013: disabled settings fall back to the plain python form."""
    # Given: traceback explicitly disabled although a format is named
    config = Config(traceback=TracebackSettings(enabled=False, format="compact"))

    # When: the callback fails
    err = _failed_stderr(project, monkeypatch, capsys, config)

    # Then: v1's unconditional python form, no compact block
    _assert_python_form(err)
    assert _COMPACT_OPEN not in err


def test_trace_env_only__tc_f03_014(project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """TC-F03-014: with config=None, TRACE_* selects the format."""
    # Given: no configuration at all, only the TRACE_* environment
    monkeypatch.setenv("TRACE_VERBOSE", "context,locals")
    monkeypatch.setenv("TRACE_FORMAT", "compact")

    # When: the callback fails
    err = _failed_stderr(project, monkeypatch, capsys, None)

    # Then: the compact block reflects the env flags
    assert "CFG v=1 ctx=1 locals=1 env=0" in err
    assert _CALLBACK_MESSAGE in err
    assert _PY_FULL not in err


def test_config_without_traceback_uses_env__tc_f03_015(project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """TC-F03-015: a Config whose traceback is None defers to TRACE_*."""
    # Given: an explicit v1 Config without traceback settings, plus TRACE_*
    monkeypatch.setenv("TRACE_VERBOSE", "context")
    monkeypatch.setenv("TRACE_FORMAT", "compact")

    # When: the callback fails
    err = _failed_stderr(project, monkeypatch, capsys, Config())

    # Then: the environment decided the format
    assert "CFG v=1 ctx=1 locals=0 env=0" in err
    assert _PY_FULL not in err


def test_nothing_configured__tc_f03_016(project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """TC-F03-016: nothing configured still yields v1's python traceback."""
    # Given: config=None and no TRACE_* (autouse fixture)
    # When: the callback fails
    err = _failed_stderr(project, monkeypatch, capsys, None)

    # Then: the python form with the callback's exception
    _assert_python_form(err)
    assert _COMPACT_OPEN not in err
    assert _job_failed(project) == _RC1_JOB_FAILED


def test_tasksupport_yaml_compact__tc_f03_017(project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """TC-F03-017: tasksupport YAML traceback reaches the formatter via the v1 loader."""
    # Given: compact selected in data/tasksupport/rdeconfig.yaml, config=None
    _write_tasksupport_yaml(project / "data", {"enabled": True, "format": "compact"})

    # When: the callback fails
    err = _failed_stderr(project, monkeypatch, capsys, None)

    # Then: the compact block only
    assert _COMPACT_OPEN in err
    assert _PY_FULL not in err
    assert _job_failed(project) == _RC1_JOB_FAILED


def _structured_failing(srcpaths: Any, resource_paths: Any) -> None:
    del srcpaths, resource_paths
    msg = "custom structured failure"
    raise StructuredError(msg, 50)


def test_structured_error_formatted_itself__tc_f03_018(project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """TC-F03-018: a callback StructuredError is formatted itself, as v1 did."""
    # Given: compact settings and a callback raising StructuredError(50)
    config = Config(traceback=TracebackSettings(enabled=True, format="compact"))

    # When: the callback fails
    err = _failed_stderr(project, monkeypatch, capsys, config, _structured_failing)

    # Then: the StructuredError (not the Runner wrapper) with frames down to the callback
    assert 'type="StructuredError" msg="custom structured failure"' in err
    assert 'fn="_structured_failing"' in err
    assert _job_failed(project) == "ErrorCode=50\nErrorMessage=custom structured failure\n"


def test_structured_error_traceback_info_verbatim__tc_f03_019(
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """TC-F03-019: a StructuredError's own traceback_info is written verbatim."""

    # Given: a callback StructuredError that already carries traceback text
    def callback(srcpaths: Any, resource_paths: Any) -> None:
        del srcpaths, resource_paths
        msg = "prepared"
        raise StructuredError(msg, 51, traceback_info="PREPARED-TRACEBACK-TEXT")

    config = Config(traceback=TracebackSettings(enabled=True, format="compact"))

    # When: the callback fails
    err = _failed_stderr(project, monkeypatch, capsys, config, callback)

    # Then: v1's handle_and_exit_on_structured_error branch -- text as given, no formatting
    assert "PREPARED-TRACEBACK-TEXT\n" in err
    assert _COMPACT_OPEN not in err
    assert _PY_FULL not in err


def test_include_locals_masks_sensitive_values__tc_f03_020(
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """TC-F03-020: include_locals output is masked by default and custom patterns."""

    # Given: locals named by a default pattern and by a custom pattern
    def callback(srcpaths: Any, resource_paths: Any) -> None:
        del srcpaths, resource_paths
        password = "hunter2-secret"  # noqa: S105 -- the masking probe value
        dataset_label = "label-secret"
        visible_value = "plain-visible"
        # Read every local without binding a combined value: a tuple in ``_``
        # would itself be an unmasked local in the compact output.
        if password and dataset_label and visible_value:
            msg = "masked failure"
            raise StructuredError(msg, 52)

    config = Config(
        traceback=TracebackSettings(enabled=True, format="compact", include_locals=True, sensitive_patterns=["dataset_label"]),
    )

    # When: the callback fails
    err = _failed_stderr(project, monkeypatch, capsys, config, callback)

    # Then: both sensitive values are masked, an ordinary local is shown
    assert 'locals.password="***"' in err
    assert 'locals.dataset_label="***"' in err
    assert "hunter2-secret" not in err
    assert "label-secret" not in err
    assert "plain-visible" in err


def test_ignore_errors_partial_run_prints_no_traceback__tc_f03_021(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """TC-F03-021: ignore_errors=True never failed the v1 run, so no traceback (= v1.7.1)."""
    # Given: two MultiDataTile tiles, one failing, errors ignored, compact on
    _seed(tmp_path / "data", ("a.txt", "b.txt"))

    def callback(srcpaths: Any, resource_paths: Any) -> None:
        del srcpaths
        if any(path.name == "b.txt" for path in resource_paths.rawfiles):
            raise ValueError(_CALLBACK_MESSAGE)

    config = Config(
        system=SystemSettings(extended_mode="MultiDataTile"),
        multidata_tile=MultiDataTileSettings(ignore_errors=True),
        traceback=TracebackSettings(enabled=True, format="compact"),
    )
    capsys.readouterr()

    # When: running the public v1 entry
    result, code = _run_v1(tmp_path, monkeypatch, callback, config)

    # Then: the v1 return contract, no job.failed, no traceback of any form
    err = capsys.readouterr().err
    assert code == 0
    assert [status["status"] for status in json.loads(result)["statuses"]] == ["success", "failed"]
    assert not (tmp_path / "data" / "job.failed").exists()
    assert _COMPACT_OPEN not in err
    assert _PY_FULL not in err
    assert _PY_SIMPLIFIED not in err
    assert _FAILURE_NOTICE not in err


def test_stderr_order__tc_f03_022(project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """TC-F03-022: rc1's lines stay; the traceback sits before the final notice."""
    # Given: compact settings
    config = Config(traceback=TracebackSettings(enabled=True, format="compact"))

    # When: the callback fails
    err = _failed_stderr(project, monkeypatch, capsys, config)

    # Then: iteration notice, traceback, then the failure notice as the last line
    assert err.index(_ITERATION_NOTICE) < err.index(_COMPACT_OPEN) < err.index(_COMPACT_CLOSE) < err.index(_FAILURE_NOTICE)
    assert err.rstrip("\n").splitlines()[-1] == _FAILURE_NOTICE


def test_formatter_failure_keeps_the_contract__tc_f03_023(
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """TC-F03-023: a formatter defect cannot change exit code, notice, or job.failed."""
    import rdetoolkit.errors as errors_module

    # Given: the v1 formatter itself raises
    def broken(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        msg = "formatter defect"
        raise RuntimeError(msg)

    monkeypatch.setattr(errors_module, "handle_exception", broken)

    # When: the callback fails
    err = _failed_stderr(project, monkeypatch, capsys, None)

    # Then: the v1 failure contract is intact and the defect stays silent
    assert _FAILURE_NOTICE in err
    assert "formatter defect" not in err
    assert _job_failed(project) == _RC1_JOB_FAILED


class _BrokenStream:
    """A stderr whose every write fails (closed pipe / ENOSPC)."""

    def write(self, text: str) -> int:
        del text
        msg = "stderr is gone"
        raise OSError(msg)

    def flush(self) -> None:
        msg = "stderr is gone"
        raise OSError(msg)


def test_unusable_stderr_keeps_the_contract__tc_f03_024(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-F03-024: python-form formatting writes stderr directly; a broken stream is tolerated."""
    import sys

    # Given: the python form (it writes format_exc straight to sys.stderr) and a broken stderr
    monkeypatch.setattr(sys, "stderr", _BrokenStream())

    # When: the callback fails
    _, code = _run_v1(project, monkeypatch, _failing, None)

    # Then: the exit code and job.failed are those of rc1
    assert code == 1
    assert _job_failed(project) == _RC1_JOB_FAILED


def test_v2_entry_unchanged__tc_f03_025(project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """TC-F03-025: run(flow=...) is out of scope and prints no traceback."""
    from rdetoolkit.core.flow import flow

    # Given: TRACE_* set and a failing v2 flow
    monkeypatch.setenv("TRACE_VERBOSE", "context")
    monkeypatch.setenv("TRACE_FORMAT", "compact")

    @flow
    def failing_flow() -> None:
        raise ValueError(_CALLBACK_MESSAGE)

    monkeypatch.chdir(project)
    capsys.readouterr()

    # When: running the v2 entry
    report = workflows.run(flow=failing_flow)

    # Then: a failed RunReport and no v1 traceback text
    err = capsys.readouterr().err
    assert report.status == "failed"  # type: ignore[union-attr]
    assert _COMPACT_OPEN not in err
    assert _PY_FULL not in err


# ---------------------------------------------------------------------------
# Selecting the exception v1 formatted
# ---------------------------------------------------------------------------


def _tile_failure(cause: Exception) -> Exception:
    """Build the Runner's wrapper exactly as LegacyCallbackInvoker raises it."""
    from rdetoolkit.runner.execute import ExecutionResult, TileExecutionError, _failed_error

    failed = ExecutionResult(iteration_index=0, status="failed", call_records=(), outputs=(), error=_failed_error(cause, ()))
    try:
        raise TileExecutionError(failed, cause) from cause
    except TileExecutionError as wrapper:
        return wrapper


_TILE_ERROR: dict[str, Any] = {"code": 3001, "name": "NodeExecutionFailed", "message": "m", "call_id": "unknown"}


def test_no_captured_failure__tc_f03_030() -> None:
    """TC-F03-030: nothing captured means nothing to format."""
    # Given / When: a failed tile error but no captured exception
    selected = workflows._v1_failure_exception(_TILE_ERROR, [])
    # Then: no traceback is selected
    assert selected is None


def test_non_tile_run_error__tc_f03_031() -> None:
    """TC-F03-031: a run error that is not a tile failure is never paired with a stale capture."""
    # Given: a captured tile failure but a run-level (pre/post-validate) error record
    run_error = {"code": 4001, "name": "InvoiceSchemaInvalid", "message": "m"}
    # When: selecting
    selected = workflows._v1_failure_exception(run_error, [_tile_failure(ValueError("x"))])
    # Then: nothing is selected
    assert selected is None


def test_missing_run_error__tc_f03_032() -> None:
    """TC-F03-032: a failed report without an error record selects nothing."""
    # Given / When: an error record of None
    selected = workflows._v1_failure_exception(None, [_tile_failure(ValueError("x"))])
    # Then
    assert selected is None


def test_structured_cause_selected__tc_f03_033() -> None:
    """TC-F03-033: the callback's StructuredError is what v1 formatted."""
    # Given: the Runner wrapper of a callback StructuredError
    cause = StructuredError("emsg", 50)
    # When: selecting
    selected = workflows._v1_failure_exception(_TILE_ERROR, [_tile_failure(cause)])
    # Then: the StructuredError itself
    assert selected is cause


def test_plain_cause_keeps_wrapper__tc_f03_034() -> None:
    """TC-F03-034: a plain exception is shown through its chained wrapper, as v1 did."""
    # Given: the Runner wrapper of a ValueError
    cause = ValueError("plain")
    wrapper = _tile_failure(cause)
    # When: selecting
    selected = workflows._v1_failure_exception(_TILE_ERROR, [wrapper])
    # Then: the wrapper (whose __cause__ is the callback exception)
    assert selected is wrapper
    assert selected.__cause__ is cause


# ---------------------------------------------------------------------------
# Runner seam: capture_target_failures
# ---------------------------------------------------------------------------


class _RaisingInvoker:
    def __init__(self, error: Exception | None) -> None:
        self.error = error

    def invoke(self, target: Any, context: Any, **kwargs: Any) -> Any:
        del target, context, kwargs
        if self.error is not None:
            raise self.error
        return "result"


def _registry(error: Exception | None) -> Any:
    from rdetoolkit.runner.invoker import InvokerRegistry

    return InvokerRegistry(legacy_invoker=_RaisingInvoker(error))


def _invoke(registry: Any) -> Any:
    from rdetoolkit.api.request import LegacyCallbackTarget

    return registry.invoke(LegacyCallbackTarget(function=None), None, event_sink=None, run_id="r", config=None, material=None)


@pytest.fixture
def captures() -> Iterator[Callable[[], Any]]:
    """Return the capture context manager under test."""
    from rdetoolkit.runner.invoker import capture_target_failures

    yield capture_target_failures


def test_capture_records_and_reraises__tc_f03_040(captures: Callable[[], Any]) -> None:
    """TC-F03-040: a target failure is recorded and still propagates unchanged."""
    # Given: an invoker that raises inside a capture
    error = ValueError("tile")
    registry = _registry(error)

    # When: invoking
    with captures() as failures, pytest.raises(ValueError) as raised:
        _invoke(registry)

    # Then: the same object was recorded and re-raised
    assert raised.value is error
    assert failures == [error]


def test_no_capture_records_nothing__tc_f03_041() -> None:
    """TC-F03-041: outside a capture the failure propagates and nothing is kept."""
    from rdetoolkit.runner import invoker as invoker_module

    # Given: a failing invoker and no active capture
    registry = _registry(ValueError("tile"))

    # When / Then: the failure propagates and no capture list exists
    with pytest.raises(ValueError, match="tile"):
        _invoke(registry)
    assert invoker_module._TARGET_FAILURES.get() is None


def test_success_records_nothing__tc_f03_042(captures: Callable[[], Any]) -> None:
    """TC-F03-042: a successful invoke leaves the capture empty."""
    # Given / When: a succeeding invoker inside a capture
    with captures() as failures:
        result = _invoke(_registry(None))
    # Then
    assert result == "result"
    assert failures == []


def test_nested_captures__tc_f03_043(captures: Callable[[], Any]) -> None:
    """TC-F03-043: an inner capture owns its failures; the outer is restored after it."""
    from rdetoolkit.runner import invoker as invoker_module

    inner_error = ValueError("inner")
    outer_error = ValueError("outer")
    # Given: nested captures
    with captures() as outer:
        with captures() as inner, pytest.raises(ValueError):
            _invoke(_registry(inner_error))
        # When: failing again after the inner capture closed
        with pytest.raises(ValueError):
            _invoke(_registry(outer_error))
    # Then: each list holds only its own failure and the variable is reset
    assert inner == [inner_error]
    assert outer == [outer_error]
    assert invoker_module._TARGET_FAILURES.get() is None


def test_capture_keeps_only_the_latest_failure__tc_f03_044(captures: Callable[[], Any]) -> None:
    """TC-F03-044: repeated failures leave only the latest one held (earlier tracebacks are released)."""
    first = ValueError("first")
    second = ValueError("second")
    # Given: a capture that sees two failing invokes (continue policy, several tiles)
    with captures() as failures:
        for error in (first, second):
            with pytest.raises(ValueError):
                _invoke(_registry(error))
        # Then: only the latest failure is held
        assert failures == [second]


def _structured_from_key_error(srcpaths: Any, resource_paths: Any) -> None:
    """Raise a StructuredError while handling a KeyError (implicit ``__context__`` chain)."""
    del srcpaths, resource_paths
    try:
        _ = {}["missing-key"]
    except KeyError:
        msg = "lookup failed"
        raise StructuredError(msg, 53)  # noqa: B904 -- implicit chaining is the point


@pytest.mark.parametrize("inside_caller_except", [False, True], ids=["plain_call", "called_from_except"])
def test_implicit_chain_survives_reformatting__tc_f03_026(
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    inside_caller_except: bool,
) -> None:
    """TC-F03-026: the callback's implicit chain (KeyError -> StructuredError) stays in stderr.

    Re-raising the selected exception to format it must not replace its
    ``__context__`` with whatever the caller happens to be handling.
    """
    # Given: python format and a callback whose StructuredError implicitly chains a KeyError
    config = Config(traceback=TracebackSettings(enabled=True, format="python"))

    # When: run() is called plainly, or from inside the caller's own except block
    capsys.readouterr()
    if inside_caller_except:
        try:
            msg = "caller-context"
            raise RuntimeError(msg)
        except RuntimeError:
            _, code = _run_v1(project, monkeypatch, _structured_from_key_error, config)
    else:
        _, code = _run_v1(project, monkeypatch, _structured_from_key_error, config)
    err = capsys.readouterr().err

    # Then: the StructuredError still chains the callback's KeyError. The caller's
    # exception may appear only where Python really put it -- as the KeyError's own
    # context, before it -- never in place of the KeyError (rc1 re-raise lost it).
    assert code == 1
    key_error = err.index("KeyError: 'missing-key'")
    assert "During handling of the above exception, another exception occurred" in err[key_error:]
    assert "lookup failed" in err[key_error:]
    if inside_caller_except:
        assert err.index("RuntimeError: caller-context") < key_error
    assert _job_failed(project) == "ErrorCode=53\nErrorMessage=lookup failed\n"
