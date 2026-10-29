"""Property-based tests for CallLogRecorder (Session C1, Design v2.1 §13.2).

Scope note: this file intentionally avoids the "edge reconstruction" /
"producer precedes consumer" vocabulary used by AGENTS.md §7.6's PBT table —
that language predates ADR-022 and describes value-lineage reconstruction,
which v2.0's call log does not implement (R2 scope reduction). The invariants
pinned here are strictly about the call log: sequence order, call_id
uniqueness, and run-to-run determinism (Design §3.4, kickoff C-3-4).

Flow shapes are branching + merging (not a single linear chain), generated
via a boolean pattern that selects, at each step, one of two branch nodes
before merging into an accumulator — this exercises non-trivial call
sequences per AGENTS.md §7.6's "diverse flow shapes" guidance.

Property Table:
| Property                          | Invariant                                                                 | Test ID    |
|-------------------------------------|-------------------------------------------------------------------------------|------------|
| seq matches execution order         | records, sorted by seq, are exactly 1..N with no gaps or reordering            | TC-PBT-001 |
| call_id uniqueness within a run     | no two records in the same run share a call_id                                 | TC-PBT-002 |
| determinism                         | running the same flow with the same input twice yields an identical            | TC-PBT-003 |
|                                      | (node_id, seq, call_id) sequence both times                                     |            |
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from rdetoolkit.core.calllog import CallLogRecorder
from rdetoolkit.core.flow import flow
from rdetoolkit.core.node import node


@node
def branch_a_fn(x: int) -> int:
    """One branch of the merge shape."""
    return x + 1


@node
def branch_b_fn(x: int) -> int:
    """The other branch of the merge shape."""
    return x - 1


@node
def merge_fn(x: int, y: int) -> int:
    """Merges the accumulator with the branch result."""
    return x + y


@flow
def dynamic_pattern_flow(seed: int, pattern: tuple[bool, ...]) -> int:
    """Runs a branching+merging call sequence driven by `pattern`.

    For each element of `pattern`, calls branch_a_fn (True) or branch_b_fn
    (False), then merges the result back into the running accumulator —
    a plain-Python branch+merge shape, not a linear chain.
    """
    acc = seed
    for take_a in pattern:
        branched = branch_a_fn(acc) if take_a else branch_b_fn(acc)
        acc = merge_fn(acc, branched)
    return acc


_pattern_strategy = st.lists(st.booleans(), min_size=0, max_size=8).map(tuple)


@pytest.mark.property
class TestCallLogProperties:
    """Hypothesis-driven invariants over CallLogRecorder."""

    @given(pattern=_pattern_strategy)
    @settings(max_examples=25, deadline=None)
    def test_seq_matches_execution_order__tc_pbt_001(self, pattern: tuple[bool, ...]) -> None:
        """TC-PBT-001: seq values in `.records` are exactly 1..N, strictly
        increasing with no gaps — i.e. they match the actual call order."""
        with CallLogRecorder() as recorder:
            dynamic_pattern_flow(1, pattern)

        seqs = [r.seq for r in recorder.records]
        assert seqs == sorted(seqs)
        assert seqs == list(range(1, len(seqs) + 1))

    @given(pattern=_pattern_strategy)
    @settings(max_examples=25, deadline=None)
    def test_call_id_unique_within_run__tc_pbt_002(self, pattern: tuple[bool, ...]) -> None:
        """TC-PBT-002: no two call_ids collide within a single run."""
        with CallLogRecorder() as recorder:
            dynamic_pattern_flow(2, pattern)

        call_ids = [r.call_id for r in recorder.records]
        assert len(call_ids) == len(set(call_ids))

    @given(pattern=_pattern_strategy)
    @settings(max_examples=25, deadline=None)
    def test_deterministic_across_repeated_runs__tc_pbt_003(self, pattern: tuple[bool, ...]) -> None:
        """TC-PBT-003: the same flow + same input run twice produces an
        identical (node_id, seq, call_id) sequence both times."""
        with CallLogRecorder() as r1:
            dynamic_pattern_flow(3, pattern)
        with CallLogRecorder() as r2:
            dynamic_pattern_flow(3, pattern)

        seq1 = [(r.node_id, r.seq, r.call_id) for r in r1.records]
        seq2 = [(r.node_id, r.seq, r.call_id) for r in r2.records]
        assert seq1 == seq2
