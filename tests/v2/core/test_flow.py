"""Tests for Trace proxy and @flow decorator (Phase 1.3.10-1.3.14).

EP Table:
| API                       | Partition                     | Expected                         | Test ID     |
|---------------------------|-------------------------------|----------------------------------|-------------|
| NodeProxy.__iter__        | tuple unpack                  | yields OutputProxy per output    | TC-EP-040   |
| NodeProxy as @node arg    | edge recording                | edge recorded in DAG             | TC-EP-041   |
| OutputProxy               | port info                     | correct node_id and port_name    | TC-EP-042   |
| @flow (trace mode)        | DAG construction              | returns FlowResult with DAG      | TC-EP-043   |
| @flow (execute mode)      | actual execution              | nodes execute in topo order      | TC-EP-044   |
| @flow data-dependent if   | branch on proxy               | raises FlowDefinitionError       | TC-EP-045   |

BV Table:
| API                       | Boundary                      | Expected                         | Test ID     |
|---------------------------|-------------------------------|----------------------------------|-------------|
| @flow                     | single node, no edges         | DAG with 1 node, 0 edges        | TC-BV-010   |
| @flow                     | linear 3-node chain           | DAG with 3 nodes, 2 edges       | TC-BV-011   |
| NodeProxy                 | single output (no unpack)     | iter yields 1 OutputProxy        | TC-BV-012   |
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from rdetoolkit.core.node import node


def _dummy_fn() -> None:
    pass


# === 1.3.10: Trace proxy tests ===


class TestOutputProxy:
    """Tests for OutputProxy."""

    def test_output_proxy_stores_node_id_and_port__tc_ep_042(self) -> None:
        """TC-EP-042: OutputProxy stores correct node_id and port_name."""
        from rdetoolkit.core.flow import OutputProxy

        proxy = OutputProxy(node_id="read_csv", port_name="data")
        assert proxy.node_id == "read_csv"
        assert proxy.port_name == "data"


class TestNodeProxy:
    """Tests for NodeProxy."""

    def test_tuple_unpack__tc_ep_040(self) -> None:
        """TC-EP-040: NodeProxy supports tuple unpack via __iter__."""
        from rdetoolkit.core.dag import DAG
        from rdetoolkit.core.flow import NodeProxy, OutputProxy
        from rdetoolkit.core.node import NodeSpec

        spec = NodeSpec(
            id="read_csv",
            name="read_csv",
            fn=_dummy_fn,
            input_schema={"paths": Path},
            output_schema={"_0": str, "_1": list},
            tags=(),
            version="0.0.0",
            idempotent=False,
            source_location="test:read_csv",
        )
        dag = DAG()
        dag.add_node("read_csv", spec)
        proxy = NodeProxy(node_spec=spec, dag=dag, output_names=("metadata", "data"))

        # When: tuple unpack
        meta, data = proxy

        # Then: both are OutputProxy with correct info
        assert isinstance(meta, OutputProxy)
        assert isinstance(data, OutputProxy)
        assert meta.node_id == "read_csv"
        assert meta.port_name == "metadata"
        assert data.node_id == "read_csv"
        assert data.port_name == "data"

    def test_single_output_iter__tc_bv_012(self) -> None:
        """TC-BV-012: NodeProxy with single output yields 1 OutputProxy."""
        from rdetoolkit.core.dag import DAG
        from rdetoolkit.core.flow import NodeProxy, OutputProxy
        from rdetoolkit.core.node import NodeSpec

        spec = NodeSpec(
            id="write_meta",
            name="write_meta",
            fn=_dummy_fn,
            input_schema={"meta": str},
            output_schema={},
            tags=(),
            version="0.0.0",
            idempotent=False,
            source_location="test:write_meta",
        )
        dag = DAG()
        dag.add_node("write_meta", spec)
        proxy = NodeProxy(node_spec=spec, dag=dag, output_names=("result",))

        outputs = list(proxy)
        assert len(outputs) == 1
        assert isinstance(outputs[0], OutputProxy)

    def test_edge_recording_when_proxy_passed_as_arg__tc_ep_041(self) -> None:
        """TC-EP-041: Passing NodeProxy/OutputProxy to another @node records edge in DAG."""
        from rdetoolkit.core.dag import DAG
        from rdetoolkit.core.flow import NodeProxy, OutputProxy
        from rdetoolkit.core.node import NodeSpec

        # Given: two nodes in a DAG
        spec_a = NodeSpec(
            id="node_a", name="node_a", fn=_dummy_fn,
            input_schema={}, output_schema={"_0": str, "_1": int},
            tags=(), version="0.0.0", idempotent=False,
            source_location="test:node_a",
        )
        spec_b = NodeSpec(
            id="node_b", name="node_b", fn=_dummy_fn,
            input_schema={"x": str, "y": int}, output_schema={},
            tags=(), version="0.0.0", idempotent=False,
            source_location="test:node_b",
        )
        dag = DAG()
        dag.add_node("node_a", spec_a)
        dag.add_node("node_b", spec_b)

        # When: node_a produces outputs, passed to node_b
        proxy_a = NodeProxy(node_spec=spec_a, dag=dag, output_names=("x", "y"))
        out_x, out_y = proxy_a

        # Simulate recording edges when node_b receives OutputProxy args
        proxy_b = NodeProxy.record_call(
            node_spec=spec_b,
            dag=dag,
            args={"x": out_x, "y": out_y},
            output_names=("result",),
        )

        # Then: edges exist from node_a -> node_b with correct port info
        edges = dag.edge_list()
        assert len(edges) == 2
        edge_set = {(e[0], e[1], e[2], e[3]) for e in edges}
        assert ("node_a", "node_b", "x", "x") in edge_set
        assert ("node_a", "node_b", "y", "y") in edge_set


# === 1.3.12: @flow decorator tests ===


class TestFlowDecorator:
    """Tests for @flow decorator."""

    def test_flow_trace_mode_builds_dag__tc_ep_043(self) -> None:
        """TC-EP-043: @flow in trace mode constructs a DAG."""
        from rdetoolkit.core.flow import flow, FlowResult

        @node
        def read_csv(paths: str) -> tuple[str, list[int]]:
            return ("meta", [1, 2, 3])

        @node
        def normalize(meta: str, data: list[int]) -> list[float]:
            return [float(x) for x in data]

        @node
        def write_out(normalized: list[float]) -> None:
            pass

        @flow
        def pipeline(paths: str) -> None:
            meta, data = read_csv(paths)
            normalized = normalize(meta, data)
            write_out(normalized)

        # When: calling flow to build the DAG (trace mode)
        result = pipeline.build()

        # Then: result contains a DAG with correct structure
        assert isinstance(result, FlowResult)
        dag = result.dag
        assert dag.node_count() == 3
        assert dag.edge_count() >= 2  # read_csv->normalize, normalize->write_out

        # Verify topological order respects edges
        order = dag.topological_sort()
        assert order.index("read_csv") < order.index("normalize")
        assert order.index("normalize") < order.index("write_out")

    def test_flow_single_node__tc_bv_010(self) -> None:
        """TC-BV-010: @flow with single node produces DAG with 1 node."""
        from rdetoolkit.core.flow import flow

        @node
        def only_step(x: int) -> int:
            return x + 1

        @flow
        def simple(x: int) -> None:
            only_step(x)

        result = simple.build()
        assert result.dag.node_count() == 1
        assert result.dag.edge_count() == 0

    def test_flow_linear_chain__tc_bv_011(self) -> None:
        """TC-BV-011: @flow with linear 3-node chain."""
        from rdetoolkit.core.flow import flow

        @node
        def step1(x: int) -> int:
            return x + 1

        @node
        def step2(y: int) -> int:
            return y * 2

        @node
        def step3(z: int) -> str:
            return str(z)

        @flow
        def chain(x: int) -> None:
            a = step1(x)
            b = step2(a)
            step3(b)

        result = chain.build()
        assert result.dag.node_count() == 3
        order = result.dag.topological_sort()
        assert order.index("step1") < order.index("step2")
        assert order.index("step2") < order.index("step3")

    def test_flow_execute_mode__tc_ep_044(self) -> None:
        """TC-EP-044: @flow in execute mode runs nodes in topological order."""
        from rdetoolkit.core.flow import flow

        execution_log: list[str] = []

        @node
        def producer(x: int) -> int:
            execution_log.append("producer")
            return x * 10

        @node
        def consumer(value: int) -> str:
            execution_log.append("consumer")
            return str(value)

        @flow
        def pipeline(x: int) -> None:
            val = producer(x)
            consumer(val)

        # When: executing the flow
        pipeline.execute(5)

        # Then: nodes executed in order
        assert execution_log == ["producer", "consumer"]


# === 1.3.14: Data-dependent branching prohibition ===


class TestFlowBranchProhibition:
    """Tests for data-dependent branching prohibition."""

    def test_if_on_proxy_raises__tc_ep_045(self) -> None:
        """TC-EP-045: Using proxy value in if-condition raises FlowDefinitionError."""
        from rdetoolkit.core.flow import flow, FlowDefinitionError

        @node
        def maybe_none(x: int) -> int:
            return x

        @node
        def use_value(v: int) -> None:
            pass

        @flow
        def branching_flow(x: int) -> None:
            result = maybe_none(x)
            if result:  # Data-dependent branch on proxy!
                use_value(result)

        with pytest.raises(FlowDefinitionError, match="[Dd]ata.dependent"):
            branching_flow.build()
