"""GA567 EP/BV: input path messages retain the v1 relative spelling."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from rdetoolkit import flow, workflows
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.types import InputPaths
from tests.v2.runner.test_event_log_robustness_k4 import _build_tree


@pytest.mark.parametrize("entry", ["v1", "v2"])
@pytest.mark.parametrize("field", ["rawfiles", "inputdata"])
def test_job_failed_uses_relative_input_path__ga567_ep_1_neg_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, entry: str, field: str) -> None:
    """GA567-EP-1/NEG-1: both public entries publish the same path in errors."""
    # Given: a standard RDE dataset and the issue's path-based failure
    _build_tree(tmp_path / "data")
    monkeypatch.chdir(tmp_path)

    def callback(srcpaths: Any, resource_paths: Any) -> None:
        path = resource_paths.rawfiles[0] if field == "rawfiles" else srcpaths.inputdata
        raise StructuredError(f"Invalid input: {path}", 7)

    @flow
    def pipeline(paths: InputPaths) -> None:
        path = paths.rawfiles[0] if field == "rawfiles" else paths.inputdata
        raise StructuredError(f"Invalid input: {path}", 7)

    # When: executing the requested entry
    config = {"system": {"save_thumbnail_image": False}}
    if entry == "v1":
        with pytest.raises(SystemExit) as raised:
            workflows.run(custom_dataset_function=callback, config=config)
        assert raised.value.code == 1
    else:
        report = workflows.run(flow=pipeline, config=config)
        assert report.status == "failed"
        assert report.error is not None and report.error["code"] == 7
    # Then: the exact v1 error text contains no absolute project prefix
    suffix = "data/inputdata/file_0.txt" if field == "rawfiles" else "data/inputdata"
    text = (tmp_path / "data" / "job.failed").read_text(encoding="utf-8")
    assert text == f"ErrorCode=7\nErrorMessage=Invalid input: {suffix}\n"
    assert str(tmp_path) not in text


@pytest.mark.property
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(st.lists(st.sampled_from(["a.txt", "測定.dat", "folder/b.csv"]), unique=True), st.booleans())
def test_projection_preserves_input_locations__ga567_bv_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, files: list[str], optional: bool) -> None:
    """GA567-BV-1 property: relative projection preserves every input location."""
    from rdetoolkit.domain.paths import relative_input_paths

    # Given: paths below an arbitrary root, including optional and repeated paths
    monkeypatch.chdir(tmp_path)
    root = tmp_path.parent / "external-root"
    paths = InputPaths(
        inputdata=root / "inputdata", invoice=root / "invoice", tasksupport=root / "tasksupport",
        raw=root / "one.dat" if optional else None, rawfiles=tuple(root / name for name in files),
        smarttable_rawfile=root / "row.csv" if optional else None, invoice_org=root / "invoice_org.json" if optional else None,
    )
    # When: projecting the user-facing bundle relative to cwd
    projected = relative_input_paths(paths)
    # Then: all targets, order and optional absences are preserved
    for name in ("inputdata", "invoice", "tasksupport", "raw", "smarttable_rawfile", "invoice_org"):
        original = getattr(paths, name)
        actual = getattr(projected, name)
        if original is None:
            assert actual is None
        else:
            assert not actual.is_absolute()
            assert actual.resolve() == original.resolve()
    assert tuple(path.resolve() for path in projected.rawfiles) == paths.rawfiles
    assert all(not path.is_absolute() for path in projected.rawfiles)
