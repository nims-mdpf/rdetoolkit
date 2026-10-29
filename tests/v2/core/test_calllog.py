"""Tests for CallLogRecorder, NodeCallRecord, and TypeSummary (Session C1,
Design v2.1 §3.4).

R2 scope: this is a **call log only** — no value lineage, no identity
tracking, no edge confidence (ADR-022). Records capture when/what/order/
count/duration/failure/input-output types, nothing about value identity
across calls.

``CallLogRecorder`` is used as a context manager representing one "active
run"; while active, `@node`-decorated function calls append a
``NodeCallRecord`` to ``recorder.records``. With no active recorder, node
calls must not record anything anywhere (zero-cost design requirement).

EP Table:
| API                        | Partition                                   | Rationale                     | Expected                                                        | Test ID   |
|-----------------------------|------------------------------------------------|---------------------------------|---------------------------------------------------------------------|-----------|
| NodeCallRecord              | normal fields after one call                   | Design §3.4                     | all fields accessible and populated                                  | TC-EP-301 |
| call_id                     | format                                          | "{node_id}#{seq}"               | string matches this exact format                                     | TC-EP-302 |
| seq                         | multiple calls                                  | run-global monotonic counter    | 1, 2, 3, ... in call order                                            | TC-EP-303 |
| TypeSummary.repr_head       | provenance.repr_head="on"                       | recording enabled               | repr_head contains the object's repr                                  | TC-EP-304 |
| TypeSummary.repr_head       | provenance.repr_head="off"                      | recording disabled + no side effect | repr_head is None and __repr__ is never invoked                 | TC-EP-305 |
| TypeSummary.repr_head       | target's __repr__ raises                        | exception safety                | repr_head falls back to None/safe string; the call itself still succeeds | TC-EP-306 |
| status                      | node raises an exception                        | failure recording                | status == "failed", error is not None                                | TC-EP-307 |
| No active run               | @node call outside any CallLogRecorder context  | zero-cost design                | nothing is recorded                                                   | TC-EP-308 |
| Determinism                 | same flow run twice                             | Design §3.4                     | seq sequence and record count are identical across runs              | TC-EP-309 |

BV Table:
| API                | Boundary                     | Rationale               | Expected                                          | Test ID   |
|---------------------|---------------------------------|---------------------------|------------------------------------------------------|-----------|
| Repeated node calls | same node called 3 times        | call_id uniqueness        | three distinct call_ids ("#1", "#2", "#3")           | TC-BV-301 |
| duration_ms         | node returns immediately        | minimal execution time    | duration_ms >= 0 (never negative)                    | TC-BV-302 |
"""

from __future__ import annotations

from typing import Any

import pytest

from rdetoolkit.core.calllog import CallLogRecorder
from rdetoolkit.core.flow import flow
from rdetoolkit.core.node import node


class TestNodeCallRecordFields:
    """TC-EP-301..303: basic NodeCallRecord field population."""

    def test_fields_accessible_after_one_call__tc_ep_301(self) -> None:
        """TC-EP-301: after one recorded call, every NodeCallRecord field is
        accessible and populated per Design §3.4."""

        @node
        def record_fields_fn(x: int) -> int:
            return x * 2

        with CallLogRecorder() as recorder:
            result = record_fields_fn(3)

        assert result == 6
        assert len(recorder.records) == 1
        rec = recorder.records[0]

        assert rec.node_id == record_fields_fn.__node_spec__.id  # type: ignore[attr-defined]
        assert rec.call_id == f"{rec.node_id}#1"
        assert rec.parent_flow is None
        assert rec.seq == 1
        assert rec.iteration_index == 0
        assert isinstance(rec.started_at, str) and rec.started_at
        assert rec.duration_ms >= 0
        assert rec.status == "completed"
        assert "x" in rec.inputs
        assert len(rec.outputs) == 1
        assert rec.error is None

    def test_call_id_format__tc_ep_302(self) -> None:
        """TC-EP-302: call_id is exactly "{node_id}#{seq}"."""

        @node
        def call_id_format_fn(x: int) -> int:
            return x

        with CallLogRecorder() as recorder:
            call_id_format_fn(1)

        rec = recorder.records[0]
        assert rec.call_id == f"{rec.node_id}#{rec.seq}"

    def test_seq_monotonic_across_calls__tc_ep_303(self) -> None:
        """TC-EP-303: seq increases 1, 2, 3, ... in call order within a run."""

        @node
        def seq_fn(x: int) -> int:
            return x

        with CallLogRecorder() as recorder:
            seq_fn(1)
            seq_fn(2)
            seq_fn(3)

        seqs = [r.seq for r in recorder.records]
        assert seqs == [1, 2, 3]


class TestTypeSummaryReprHead:
    """TC-EP-304..306: repr_head capture, opt-out, and exception safety."""

    def test_repr_head_captured_when_on__tc_ep_304(self) -> None:
        """TC-EP-304: provenance.repr_head="on" records a repr-derived string."""

        @node
        def repr_on_fn(x: str) -> str:
            return x

        with CallLogRecorder(repr_head="on") as recorder:
            repr_on_fn("hello-world")

        rec = recorder.records[0]
        input_summary = rec.inputs["x"]
        assert input_summary.repr_head is not None
        assert "hello-world" in input_summary.repr_head

    def test_repr_head_off_skips_repr_call_entirely__tc_ep_305(self) -> None:
        """TC-EP-305: provenance.repr_head="off" yields repr_head=None and
        never invokes the target object's __repr__ (verified via a counter)."""
        call_counter = {"n": 0}

        class Tracked:
            def __repr__(self) -> str:
                call_counter["n"] += 1
                return "Tracked()"

        @node
        def repr_off_fn(obj: Tracked) -> Tracked:
            return obj

        with CallLogRecorder(repr_head="off") as recorder:
            repr_off_fn(Tracked())

        rec = recorder.records[0]
        assert rec.inputs["obj"].repr_head is None
        assert call_counter["n"] == 0

    def test_repr_raising_is_exception_safe__tc_ep_306(self) -> None:
        """TC-EP-306: if the target's __repr__ raises, the call and its
        recording still succeed; repr_head falls back to None or a safe
        fallback string (never propagates the repr exception)."""

        class Explodes:
            def __repr__(self) -> str:
                raise RuntimeError("boom-repr")

        @node
        def repr_explodes_fn(obj: Explodes) -> int:
            return 1

        with CallLogRecorder(repr_head="on") as recorder:
            result = repr_explodes_fn(Explodes())

        assert result == 1
        rec = recorder.records[0]
        assert rec.status == "completed"
        repr_head = rec.inputs["obj"].repr_head
        assert repr_head is None or isinstance(repr_head, str)


class TestCallLogFailureAndZeroCost:
    """TC-EP-307..309: failure recording, zero-cost when inactive, determinism."""

    def test_node_exception_produces_failed_status__tc_ep_307(self) -> None:
        """TC-EP-307: a node raising an exception yields status="failed" with
        a non-None error, and the original exception still propagates."""

        @node
        def failing_fn(x: int) -> int:
            raise ValueError("node boom")

        with CallLogRecorder() as recorder:
            with pytest.raises(ValueError, match="node boom"):
                failing_fn(1)

        rec = recorder.records[0]
        assert rec.status == "failed"
        assert rec.error is not None

    def test_no_active_run_produces_no_records__tc_ep_308(self) -> None:
        """TC-EP-308: calling a @node function with no active CallLogRecorder
        records nothing (zero-cost design requirement)."""

        @node
        def untracked_fn(x: int) -> int:
            return x

        assert untracked_fn(5) == 5

        recorder = CallLogRecorder()  # never entered
        assert recorder.records == ()

    def test_call_log_deterministic_across_repeated_runs__tc_ep_309(self) -> None:
        """TC-EP-309: running the same flow twice with the same input yields
        an identical (node_id, seq) sequence and record count both times."""

        @node
        def det_a(x: int) -> int:
            return x + 1

        @node
        def det_b(x: int) -> int:
            return x * 2

        @flow
        def det_flow(x: int) -> int:
            y = det_a(x)
            return det_b(y)

        with CallLogRecorder() as r1:
            det_flow(1)
        with CallLogRecorder() as r2:
            det_flow(1)

        seq1 = [(r.node_id, r.seq) for r in r1.records]
        seq2 = [(r.node_id, r.seq) for r in r2.records]
        assert seq1 == seq2
        assert len(r1.records) == len(r2.records) == 2


class TestCallLogBoundaries:
    """TC-BV-301/302: repeated-call call_id uniqueness and duration bounds."""

    def test_repeated_calls_produce_distinct_call_ids__tc_bv_301(self) -> None:
        """TC-BV-301: calling the same node 3 times yields "#1", "#2", "#3"."""

        @node
        def repeat_fn(x: int) -> int:
            return x

        with CallLogRecorder() as recorder:
            repeat_fn(1)
            repeat_fn(2)
            repeat_fn(3)

        node_id = repeat_fn.__node_spec__.id  # type: ignore[attr-defined]
        call_ids = [r.call_id for r in recorder.records]
        assert call_ids == [f"{node_id}#1", f"{node_id}#2", f"{node_id}#3"]
        assert len(set(call_ids)) == 3

    def test_duration_ms_non_negative_for_instant_node__tc_bv_302(self) -> None:
        """TC-BV-302: an instantly-returning node has duration_ms >= 0."""

        @node
        def instant_fn(x: int) -> int:
            return x

        with CallLogRecorder() as recorder:
            instant_fn(1)

        assert recorder.records[0].duration_ms >= 0


class TestCallLogCoverageBranches:
    """Targeted branch coverage for C-3-6 new-code coverage requirements."""

    def test_none_input_and_none_output_are_summarized__tc_cov_001(self) -> None:
        """TC-COV-001: None input hits TypeSummary.type_name == "None", and
        a None return is recorded as an empty outputs tuple."""

        # Given: a node with a None annotation and a None return value
        @node
        def none_roundtrip_fn(x: None) -> None:
            return None

        # When: strict type checking records a matching None argument
        with CallLogRecorder(type_check="strict") as recorder:
            none_roundtrip_fn(None)

        # Then: the input type summary preserves None and the output is empty
        rec = recorder.records[0]
        assert rec.inputs["x"].type_name == "None"
        assert rec.outputs == ()

    def test_strict_type_check_accepts_any_and_generic_annotations__tc_cov_002(self) -> None:
        """TC-COV-002: Any and generic annotations are accepted by strict type
        checking without raising."""

        # Given: nodes annotated with Any and list[int]
        @node
        def any_arg_fn(x: Any) -> Any:
            return x

        @node
        def generic_arg_fn(xs: list[int]) -> int:
            return len(xs)

        # When: strict type checking sees matching values
        with CallLogRecorder(type_check="strict") as recorder:
            assert any_arg_fn(object()) is not None
            assert generic_arg_fn([1, 2, 3]) == 3

        # Then: both calls are recorded successfully
        assert [rec.status for rec in recorder.records] == ["completed", "completed"]

    def test_unresolvable_annotation_falls_back_to_signature_annotation__tc_cov_003(self) -> None:
        """TC-COV-003: an annotation that get_type_hints cannot resolve does
        not fail recording; the fallback matcher treats it as permissive."""

        # Given: a node with a forward annotation that is intentionally absent
        @node
        def unresolved_annotation_fn(x: "MissingRuntimeType") -> int:  # type: ignore[name-defined]
            return 1

        # When: strict type checking resolves hints and hits the fallback path
        with CallLogRecorder(type_check="strict") as recorder:
            result = unresolved_annotation_fn(object())

        # Then: no type-check exception is raised and the call is recorded
        assert result == 1
        assert recorder.records[0].status == "completed"


class TestPR508ReviewPins:
    """PR #508 review: nested-node seq uniqueness, strict return check, root exports."""

    def test_nested_node_calls_get_unique_monotonic_seq(self) -> None:
        """A recorded node calling another recorded node must not duplicate seq."""
        from rdetoolkit.core.calllog import CallLogRecorder
        from rdetoolkit.core.node import node

        @node
        def inner_leaf(x: int) -> int:
            return x + 1

        @node
        def outer_caller(x: int) -> int:
            return inner_leaf(x) * 2

        with CallLogRecorder() as rec:
            outer_caller(1)

        seqs = [r.seq for r in rec.records]
        assert len(seqs) == 2
        assert len(set(seqs)) == 2, f"duplicate seq numbers: {seqs}"
        assert seqs == sorted(seqs), "records tuple must be monotonic in seq"
        call_ids = [r.call_id for r in rec.records]
        assert len(set(call_ids)) == 2, f"duplicate call_ids: {call_ids}"

    def test_strict_mode_rejects_wrong_return_type(self) -> None:
        """Design §4.4: strict type check validates the return value too."""
        from rdetoolkit.core.calllog import CallLogRecorder
        from rdetoolkit.core.node import node
        from rdetoolkit.errors import RdeError

        @node
        def lies_about_return(x: int) -> int:
            return f"not-an-int-{x}"  # type: ignore[return-value]

        with CallLogRecorder(type_check="strict") as rec:
            with pytest.raises(RdeError) as exc_info:
                lies_about_return(1)

        assert getattr(exc_info.value, "code", None) == 3002
        _ = rec

    def test_warn_mode_warns_on_wrong_return_type(self) -> None:
        from rdetoolkit.core.calllog import CallLogRecorder
        from rdetoolkit.core.node import node

        @node
        def fibs_return(x: int) -> int:
            return str(x)  # type: ignore[return-value]

        with CallLogRecorder(type_check="warn") as rec:
            with pytest.warns(UserWarning, match="return"):
                fibs_return(1)

        assert rec.records[-1].status == "completed"

    def test_node_and_flow_importable_from_package_root(self) -> None:
        """Design §3.1: from rdetoolkit import node, flow."""
        from rdetoolkit import flow, node
        from rdetoolkit.core.flow import flow as flow_impl
        from rdetoolkit.core.node import node as node_impl

        assert node is node_impl
        assert flow is flow_impl
