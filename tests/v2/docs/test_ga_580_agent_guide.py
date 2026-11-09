"""GA580 EP/BV: shipped agent guides teach and execute the public v2 entry."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from rdetoolkit import get_agent_guide, workflows
from tests.v2.runner.test_event_log_robustness_k4 import _build_tree


@pytest.mark.parametrize("detailed", [False, True])
def test_guide_describes_v2_and_compatibility__ga580_ep_1_neg_1(detailed: bool) -> None:
    """GA580-EP-1/NEG-1: both guides cover v2 without retired import/CLI advice."""
    # Given: either supported form of the public agent guide
    # When: loading it through the package API
    guide = get_agent_guide(detailed=detailed)
    # Then: the v2 surface and frozen compatibility entry are explicit
    for term in ("@flow", "@node", "InputPaths", "OutputContext", "InvoiceData", "IterationInfo", "RdeConfig", "ProcessingTemplate", "build_meta", "rdetoolkit run --flow", "rdetoolkit.testing", "frozen compatibility"):
        assert term in guide
    for obsolete in ("from rdetoolkit.processing", "core.cpython-", "rdetoolkit validate", "rdetoolkit gen-excelinvoice"):
        assert obsolete not in guide


@pytest.mark.parametrize("detailed", [False, True])
def test_shipped_flow_example_executes__ga580_ep_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, detailed: bool) -> None:
    """GA580-EP-2: the exact code shipped in the guide runs through the Runner."""
    # Given: the tagged guide example and a complete, isolated RDE dataset
    guide = get_agent_guide(detailed=detailed)
    match = re.search(r"<!-- test: agent-guide-v2 -->\s*```python\n(.*?)```", guide, re.DOTALL)
    assert match is not None
    _build_tree(tmp_path / "data")
    monkeypatch.chdir(tmp_path)
    namespace: dict[str, Any] = {"__name__": f"ga580_example_{detailed}"}
    exec(compile(match.group(1), "<agent-guide-v2>", "exec"), namespace)
    # When: executing the exact example using the public v2 entry
    report = workflows.run(flow=namespace["pipeline"], config={"system": {"save_thumbnail_image": False}})
    # Then: the example succeeds and writes its promised artifact
    assert report.status == "success", report.error
    assert (tmp_path / "data" / "structured" / "structured-0.txt").read_text(encoding="utf-8") == "data-0\n"
