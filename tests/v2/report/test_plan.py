"""Tests for Phase 2.1.5: ExecutionPlan JSON output.

EP Table:
| API                    | Partition               | Rationale           | Expected                   | Test ID    |
|------------------------|-------------------------|---------------------|----------------------------|------------|
| plan_to_json           | valid plan              | normal              | valid JSON with order      | TC-EP-001  |
| plan_to_json           | plan with specs         | node_specs included | specs in JSON              | TC-EP-002  |

BV Table:
| API                    | Boundary                | Rationale           | Expected                   | Test ID    |
|------------------------|-------------------------|---------------------|----------------------------|------------|
| plan_to_json           | empty plan              | no nodes            | empty order list           | TC-BV-001  |
"""

from __future__ import annotations

import json

import pytest

from rdetoolkit.core.compiler import ExecutionPlan
from rdetoolkit.core.node import node
from rdetoolkit.report.plan import plan_to_dict, plan_to_json


class TestPlanToJson:
    """Tests for ExecutionPlan JSON output."""

    def test_valid_plan_to_json__tc_ep_001(self) -> None:
        """TC-EP-001: plan_to_json outputs valid JSON with order."""
        # Given: an ExecutionPlan
        plan = ExecutionPlan(order=["a", "b", "c"], node_specs={"a": None, "b": None, "c": None})
        # When: converting to JSON
        json_str = plan_to_json(plan)
        data = json.loads(json_str)
        # Then: order is present
        assert data["order"] == ["a", "b", "c"]
        assert len(data["node_specs"]) == 3

    def test_plan_with_specs__tc_ep_002(self) -> None:
        """TC-EP-002: plan_to_json includes NodeSpec details."""
        # Given: a plan with actual NodeSpecs
        @node(tags=["io"], version="1.0.0")
        def read_csv() -> str:
            return "data"

        spec = read_csv.__node_spec__  # type: ignore[attr-defined]
        plan = ExecutionPlan(
            order=["read_csv"],
            node_specs={"read_csv": spec},
        )
        # When: converting to JSON
        json_str = plan_to_json(plan)
        data = json.loads(json_str)
        # Then: node_specs has spec details
        spec_data = data["node_specs"]["read_csv"]
        assert spec_data["id"] == "read_csv"
        assert spec_data["name"] == "read_csv"
        assert spec_data["tags"] == ["io"]
        assert spec_data["version"] == "1.0.0"

    def test_empty_plan__tc_bv_001(self) -> None:
        """TC-BV-001: Empty plan outputs empty order."""
        # Given: empty plan
        plan = ExecutionPlan(order=[], node_specs={})
        # When: converting to JSON
        json_str = plan_to_json(plan)
        data = json.loads(json_str)
        # Then: empty
        assert data["order"] == []
        assert data["node_specs"] == {}

    def test_plan_to_dict(self) -> None:
        """plan_to_dict returns a serializable dict."""
        # Given: a plan
        plan = ExecutionPlan(order=["x"], node_specs={"x": None})
        # When: converting to dict
        d = plan_to_dict(plan)
        # Then: it is a dict with expected keys
        assert d["order"] == ["x"]
        assert d["node_specs"]["x"] is None
