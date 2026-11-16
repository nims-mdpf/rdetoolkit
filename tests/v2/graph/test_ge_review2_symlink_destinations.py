"""Fix round 2 / F1: artifact collisions are detected through symlinked destinations.

Two jobs of one run collide when their *real* targets coincide: the destination
file itself is resolved (a symlinked file, a dangling link and a link chain are
followed), then the resolved directory is compared exactly and the resolved file
name by collision key. A symlink leaving the sink directory is rejected earlier by
the sink's containment rule (``OutputPathError`` from ``sink.resolve``), so that
check still fires first. Directories differing only by case stay distinct (R-9,
covered by ``test_ge_review_engine.py``).

EP table:
| TC | Partition | Input | Expected |
|----|-----------|-------|----------|
| TC-FIX2-F1-EP-001 | symlinked destination to an unrelated name inside the sink | plot.png -> other.png | both artifacts written, other.png holds the overlay |
| TC-FIX2-F1-EP-002 | no symlink (control) | plain directory | plot.png and plot_y.png written |

Negative table:
| TC | Partition | Input | Expected |
|----|-----------|-------|----------|
| TC-FIX2-F1-NEG-001 | absolute-target link onto a sibling, target exists | plot.png -> /abs/plot_y.png | ArtifactCollisionError, target bytes and mtime unchanged |
| TC-FIX2-F1-NEG-002 | relative-target link onto a sibling, dangling | plot.png -> plot_y.png (missing) | ArtifactCollisionError, nothing created |
| TC-FIX2-F1-NEG-003 | link chain onto a sibling | plot.png -> hop.png -> plot_y.png | ArtifactCollisionError, nothing created |
| TC-FIX2-F1-NEG-004 | link onto a collision-key variant of a sibling | plot.png -> PLOT_Y.png | ArtifactCollisionError, nothing created |
| TC-FIX2-F1-NEG-005 | the sibling is the link | plot_y.png -> plot.png | ArtifactCollisionError, nothing created |
| TC-FIX2-F1-NEG-006 | link escaping the sink | plot.png -> ../elsewhere/plot_y.png | OutputPathError (containment fires first), nothing created |
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest

from rdetoolkit.graph.engine import render_graph
from rdetoolkit.graph.exceptions import ArtifactCollisionError, OutputPathError
from rdetoolkit.graph.outputs import DirectorySink
from rdetoolkit.graph.spec import GraphSpec, OutputSpec


def _frame() -> pd.DataFrame:
    return pd.DataFrame({"x": [1, 2, 3], "y": [2, 3, 5]})


def _render(root: Path) -> object:
    return render_graph(_frame(), GraphSpec(layout="both"), output=OutputSpec(DirectorySink(root)))


def _entries(root: Path) -> list[str]:
    """Every entry (files, links, dangling links) under ``root``, sorted."""
    return sorted(str(path.relative_to(root)) for path in root.rglob("*"))


def test_link_to_an_unrelated_name_is_written_through__tc_fix2_f1_ep_001(tmp_path: Path) -> None:
    """TC-FIX2-F1-EP-001: a link to a name no other job uses is not a collision."""
    # Given: plot.png is a link to other.png inside the sink
    (tmp_path / "plot.png").symlink_to("other.png")
    # When
    _render(tmp_path)
    # Then: the overlay went through the link, the individual figure to its own file
    assert _entries(tmp_path) == ["other.png", "plot.png", "plot_y.png"]
    assert (tmp_path / "other.png").read_bytes().startswith(b"\x89PNG")
    assert (tmp_path / "other.png").read_bytes() != (tmp_path / "plot_y.png").read_bytes()


def test_plain_directory_writes_both_artifacts__tc_fix2_f1_ep_002(tmp_path: Path) -> None:
    """TC-FIX2-F1-EP-002: control without links."""
    _render(tmp_path)
    assert _entries(tmp_path) == ["plot.png", "plot_y.png"]


def test_absolute_link_onto_an_existing_sibling__tc_fix2_f1_neg_001(tmp_path: Path) -> None:
    """TC-FIX2-F1-NEG-001: the overlay would overwrite the individual figure."""
    # Given: plot_y.png exists with known bytes and an old mtime; plot.png links to it absolutely
    target = tmp_path / "plot_y.png"
    target.write_bytes(b"original")
    os.utime(target, (1_000_000, 1_000_000))
    (tmp_path / "plot.png").symlink_to(target.resolve())
    # When / Then
    with pytest.raises(ArtifactCollisionError, match="same destination"):
        _render(tmp_path)
    assert target.read_bytes() == b"original"
    assert target.stat().st_mtime == 1_000_000
    assert _entries(tmp_path) == ["plot.png", "plot_y.png"]


def test_relative_dangling_link_onto_a_sibling__tc_fix2_f1_neg_002(tmp_path: Path) -> None:
    """TC-FIX2-F1-NEG-002: a dangling relative link is followed too."""
    (tmp_path / "plot.png").symlink_to("plot_y.png")
    with pytest.raises(ArtifactCollisionError):
        _render(tmp_path)
    assert _entries(tmp_path) == ["plot.png"]
    assert not (tmp_path / "plot_y.png").exists()


def test_link_chain_onto_a_sibling__tc_fix2_f1_neg_003(tmp_path: Path) -> None:
    """TC-FIX2-F1-NEG-003: every hop of a chain is followed."""
    (tmp_path / "hop.png").symlink_to("plot_y.png")
    (tmp_path / "plot.png").symlink_to("hop.png")
    with pytest.raises(ArtifactCollisionError):
        _render(tmp_path)
    assert _entries(tmp_path) == ["hop.png", "plot.png"]


def test_link_onto_a_collision_key_variant__tc_fix2_f1_neg_004(tmp_path: Path) -> None:
    """TC-FIX2-F1-NEG-004: the resolved name is compared by collision key."""
    (tmp_path / "plot.png").symlink_to("PLOT_Y.png")
    with pytest.raises(ArtifactCollisionError):
        _render(tmp_path)
    assert _entries(tmp_path) == ["plot.png"]


def test_sibling_is_the_link__tc_fix2_f1_neg_005(tmp_path: Path) -> None:
    """TC-FIX2-F1-NEG-005: the later job's link points at the earlier job's file."""
    (tmp_path / "plot_y.png").symlink_to("plot.png")
    with pytest.raises(ArtifactCollisionError):
        _render(tmp_path)
    assert _entries(tmp_path) == ["plot_y.png"]


def test_escaping_link_is_rejected_by_containment_first__tc_fix2_f1_neg_006(tmp_path: Path) -> None:
    """TC-FIX2-F1-NEG-006: containment (OutputPathError) is checked before collisions."""
    out = tmp_path / "out"
    out.mkdir()
    (tmp_path / "elsewhere").mkdir()
    (out / "plot.png").symlink_to(tmp_path / "elsewhere" / "plot_y.png")
    with pytest.raises(OutputPathError):
        _render(out)
    assert _entries(tmp_path) == ["elsewhere", "out", "out/plot.png"]
