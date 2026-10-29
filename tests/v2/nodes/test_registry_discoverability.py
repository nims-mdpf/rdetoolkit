"""Tests for builtin-node discoverability (Session F1, Conflict #1 + #7,
TC-F1-DISCOVER-*).

Written before implementation (TDD Red phase). Target: make all tests pass
in codex-worker Green phase. Authority: local/develop/v2/tasks/session_f1.md
Conflict #1 (exactly 15 builtin nodes -- PhaseF_prompts.md's "17" is a
documented error, disregard it) and Conflict #7 (``rdetoolkit nodes list``
must show all 15 without ``--module``, via one additive
``import rdetoolkit.nodes`` line in ``cli/nodes_cmd.py``).

The exact 15 ids (Design §5.1's table, verbatim node names -- this file
checks for a node id *ending with* each bare name via ``str.endswith``,
tolerant of whatever module-qualified id prefix Codex chooses, e.g.
``rdetoolkit.nodes.io.read_text`` -- the bare suffix is the binding part):

    io:         read_text, read_csv_with_header, read_excel, unzip_inputs
    structured: save_csv, save_json
    meta:       parse_invoice_meta, save_meta
    image:      to_png, to_jpeg, make_thumbnail, save_main_image, copy_raw
    plot:       plot_lines, plot_scatter

Both tests below are subprocess-isolated (fresh interpreter via
``python -m rdetoolkit``), for the same reason ``tests/v2/cli/test_cli_nodes.py``
uses subprocess isolation for its "clean registry" cases: the process-wide
node registry persists for the whole pytest session, so an in-process
"exactly 15" assertion would be corrupted by every other node registered
anywhere else in the suite (including this directory's own fixture nodes).
A fresh ``python -m rdetoolkit`` subprocess whose only node-registering
import is the one additive ``import rdetoolkit.nodes`` line in
``cli/nodes_cmd.py`` is the only way to observe a genuinely clean count.
"""
from __future__ import annotations

import subprocess
import sys

_EXPECTED_BUILTIN_NODE_SUFFIXES = (
    "read_text",
    "read_csv_with_header",
    "read_excel",
    "unzip_inputs",
    "save_csv",
    "save_json",
    "parse_invoice_meta",
    "save_meta",
    "to_png",
    "to_jpeg",
    "make_thumbnail",
    "save_main_image",
    "copy_raw",
    "plot_lines",
    "plot_scatter",
)


class TestRegistryContainsExactly15BuiltinNodes:
    """TC-F1-DISCOVER-COUNT-001 (Conflict #1)."""

    def test_registry_has_exactly_15_ids_after_import_rdetoolkit_nodes(self) -> None:
        """After `import rdetoolkit.nodes` in a fresh interpreter,
        registry.list_nodes() contains exactly 15 builtin ids matching the
        Design §5.1 table's names verbatim (as id suffixes)."""
        script = (
            "import rdetoolkit.nodes\n"
            "from rdetoolkit.core import registry\n"
            "ids = sorted(spec.id for spec in registry.list_nodes())\n"
            "print(len(ids))\n"
            "for i in ids:\n"
            "    print(i)\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

        assert proc.returncode == 0, proc.stdout + proc.stderr
        lines = proc.stdout.strip().splitlines()
        count = int(lines[0])
        ids = lines[1:]
        assert count == 15, f"expected exactly 15 builtin node ids, got {count}: {ids}"
        for suffix in _EXPECTED_BUILTIN_NODE_SUFFIXES:
            assert any(node_id.endswith(suffix) for node_id in ids), (suffix, ids)


class TestCliNodesListShowsAllBuiltinsWithoutModule:
    """TC-F1-DISCOVER-CLI-001 (Conflict #7)."""

    def test_cli_nodes_list_shows_all_15_without_module_flag(self) -> None:
        """`python -m rdetoolkit nodes list` (no --module) shows exactly 15
        lines, all 15 builtin node ids present, in a fresh subprocess."""
        proc = subprocess.run(
            [sys.executable, "-m", "rdetoolkit", "nodes", "list"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

        assert proc.returncode == 0, proc.stdout + proc.stderr
        lines = [line for line in proc.stdout.strip().splitlines() if line.strip()]
        assert len(lines) == 15, f"expected exactly 15 lines from `nodes list` with no --module, got {len(lines)}: {lines}"
        for suffix in _EXPECTED_BUILTIN_NODE_SUFFIXES:
            assert any(line.endswith(suffix) for line in lines), (suffix, lines)
