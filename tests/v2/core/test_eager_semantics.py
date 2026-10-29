"""Eager-semantics integration suite (Session C1, mirrors Design v2.1 §3.1).

This is the core acceptance test for the eager execution model: the sample
pipeline from Design §3.1 (if / for / f-string / literal argument / default
argument / nested flow / repeated node calls) must run as **plain Python**
with no Trace/Compile/RustDAG machinery, and the resulting call log must be
deterministic.

A lightweight ``dict[str, list[float]]`` stands in for ``pandas.DataFrame``
to avoid a hard pandas dependency in this test; the control-flow shape
(iterating columns, branching on a config flag, an f-string node argument, a
literal float argument, a defaulted argument) is otherwise a direct mirror of
Design §3.1's sample.

Nested-flow parent_flow attribution has its own dedicated coverage in
``test_flow.py`` (TC-EP-206 / TC-BV-202); it is intentionally not repeated
as a separate ID here — the table below covers the other six §3.1 patterns.

EP Table:
| §3.1 pattern         | Partition                                | Rationale                    | Expected                                                  | Test ID   |
|------------------------|---------------------------------------------|---------------------------------|----------------------------------------------------------------|-----------|
| if branch              | config flag True/False                      | former Blocker pattern          | normalize node is called / not called accordingly              | TC-EP-401 |
| for loop               | iterate over dict columns                    | former Blocker pattern          | plot node called exactly once per column                       | TC-EP-402 |
| f-string               | node argument built with an f-string         | former Blocker pattern          | the string is evaluated correctly and passed through            | TC-EP-403 |
| literal argument       | threshold=0.3 passed literally               | former Blocker pattern          | the literal value is actually applied                           | TC-EP-404 |
| default argument       | threshold omitted                            | former Blocker pattern          | the function's own default value is used                        | TC-EP-405 |
| repeated node calls    | same node called once per column (>=2)       | Design §3.2                     | each call gets a distinct call_id                                | TC-EP-406 |
| call-log determinism   | same flow + same input run twice             | Design §3.4                     | seq sequence is identical across both runs                      | TC-EP-407 |
"""

from __future__ import annotations

import pytest

from rdetoolkit.core.calllog import CallLogRecorder
from rdetoolkit.core.flow import flow
from rdetoolkit.core.node import node

FakeFrame = dict[str, list[float]]


@node
def read_source_fn(source_name: str) -> tuple[dict[str, str], FakeFrame]:
    """Read a fake data source and return (meta, df) — mirrors read_xrd."""
    meta = {"source": source_name}
    df: FakeFrame = {"alpha": [1.0, 2.0, 3.0], "beta": [4.0, 5.0, 6.0]}
    return meta, df


@node
def normalize_fn(df: FakeFrame, threshold: float = 0.5) -> FakeFrame:
    """Scale every value in every column by threshold — mirrors normalize()."""
    return {col: [v * threshold for v in values] for col, values in df.items()}


@node
def plot_column_fn(values: list[float], name: str) -> str:
    """Simulate saving a plot; returns the generated file name — mirrors plot_lines()."""
    return name


@flow
def eager_sample_pipeline(
    source_name: str,
    plotted: list[str],
    should_normalize: bool = True,
    threshold: float = 0.3,
) -> FakeFrame:
    """Mirrors Design §3.1's sample pipeline using plain Python control flow."""
    _meta, df = read_source_fn(source_name)
    if should_normalize:  # plain if statement
        df = normalize_fn(df, threshold=threshold)  # literal/forwarded kwarg
    for col in df:  # plain for loop
        plotted.append(plot_column_fn(df[col], name=f"{col}.png"))  # f-string arg
    return df


class TestIfBranchSemantics:
    """TC-EP-401: if-branch controls whether normalize is called."""

    def test_if_true_branch_calls_normalize__tc_ep_401(self) -> None:
        """TC-EP-401 (true branch): should_normalize=True calls normalize_fn."""
        plotted: list[str] = []
        with CallLogRecorder() as recorder:
            eager_sample_pipeline("s1", plotted, should_normalize=True, threshold=0.3)

        node_ids = [r.node_id for r in recorder.records]
        assert normalize_fn.__node_spec__.id in node_ids  # type: ignore[attr-defined]

    def test_if_false_branch_skips_normalize__tc_ep_401_false(self) -> None:
        """TC-EP-401 (false branch): should_normalize=False skips normalize_fn."""
        plotted: list[str] = []
        with CallLogRecorder() as recorder:
            eager_sample_pipeline("s2", plotted, should_normalize=False)

        node_ids = [r.node_id for r in recorder.records]
        assert normalize_fn.__node_spec__.id not in node_ids  # type: ignore[attr-defined]


class TestForLoopSemantics:
    """TC-EP-402: for-loop calls the plot node once per column."""

    def test_for_loop_calls_plot_once_per_column__tc_ep_402(self) -> None:
        """TC-EP-402: the number of plot_column_fn calls equals the number of
        columns in the (post-branch) dataframe."""
        plotted: list[str] = []
        with CallLogRecorder() as recorder:
            df = eager_sample_pipeline("s3", plotted, should_normalize=False)

        plot_calls = [r for r in recorder.records if r.node_id == plot_column_fn.__node_spec__.id]  # type: ignore[attr-defined]
        assert len(plot_calls) == len(df)
        assert len(plotted) == len(df)


class TestFStringSemantics:
    """TC-EP-403: f-string node arguments are evaluated as plain Python."""

    def test_fstring_argument_evaluated_correctly__tc_ep_403(self) -> None:
        """TC-EP-403: each plotted name is exactly "{col}.png" for its column."""
        plotted: list[str] = []
        eager_sample_pipeline("s4", plotted, should_normalize=False)

        assert plotted == [f"{col}.png" for col in ("alpha", "beta")]


class TestLiteralAndDefaultArguments:
    """TC-EP-404/405: literal and default arguments are applied correctly."""

    def test_literal_threshold_argument_applied__tc_ep_404(self) -> None:
        """TC-EP-404: threshold=0.3 passed literally through the if-branch
        actually scales the output values."""
        plotted: list[str] = []
        df = eager_sample_pipeline("s5", plotted, should_normalize=True, threshold=0.3)

        assert df["alpha"][0] == pytest.approx(1.0 * 0.3)

    def test_default_argument_used_when_omitted__tc_ep_405(self) -> None:
        """TC-EP-405: calling normalize_fn without threshold uses its own
        default (0.5), not the flow's default."""
        df: FakeFrame = {"alpha": [2.0]}
        result = normalize_fn(df)

        assert result["alpha"][0] == pytest.approx(2.0 * 0.5)


class TestRepeatedCallsAndDeterminism:
    """TC-EP-406/407: repeated call_id uniqueness and call-log determinism."""

    def test_repeated_node_calls_have_distinct_call_ids__tc_ep_406(self) -> None:
        """TC-EP-406: repeated plot_column_fn calls (one per column) each get
        a distinct call_id."""
        plotted: list[str] = []
        with CallLogRecorder() as recorder:
            eager_sample_pipeline("s6", plotted, should_normalize=False)

        plot_call_ids = [
            r.call_id for r in recorder.records if r.node_id == plot_column_fn.__node_spec__.id  # type: ignore[attr-defined]
        ]
        assert len(plot_call_ids) >= 2
        assert len(plot_call_ids) == len(set(plot_call_ids))

    def test_call_log_deterministic_across_two_runs__tc_ep_407(self) -> None:
        """TC-EP-407: running the same pipeline with the same input twice
        yields an identical (node_id, seq) sequence both times."""
        with CallLogRecorder() as r1:
            eager_sample_pipeline("same-input", [], should_normalize=True, threshold=0.3)
        with CallLogRecorder() as r2:
            eager_sample_pipeline("same-input", [], should_normalize=True, threshold=0.3)

        seq1 = [(r.node_id, r.seq) for r in r1.records]
        seq2 = [(r.node_id, r.seq) for r in r2.records]
        assert seq1 == seq2
