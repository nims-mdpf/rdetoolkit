"""Issue 602 EP/BV: rawfiles preserves length, order, duplicates and containment.

| Partition / boundary | Expected | Test ID |
|---|---|---|
| generated nested and flat file names, including duplicates | rawfiles matches the request exactly | I602-PBT-001 |
| empty generated iterable | empty rawfiles and the existing invoice_org default | I602-PBT-001 |
| generated parent / descendant pairs, either order | RdeConfigError 1003 before creating the input root | R605-PBT-001 |
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import given, strategies as st

from rdetoolkit.errors import RdeConfigError
from rdetoolkit.testing import make_input_paths


@pytest.mark.property
@given(names=st.lists(st.sampled_from(["a.txt", "b.csv", "nested/c.dat"]), max_size=5))
def test_requested_files_preserve_order_and_containment__i602_pbt_001(names: list[str]) -> None:
    """I602-PBT-001: requested files and rawfiles stay in one-to-one correspondence."""
    # Given: arbitrary requested names, possibly empty or repeated
    with TemporaryDirectory() as directory:
        root = Path(directory)
        # When: consuming a one-shot iterable through the public builder
        paths = make_input_paths(root, files=(name for name in names))
        # Then: every requested occurrence is present, in order, within inputdata
        assert paths.rawfiles == tuple(paths.inputdata / name for name in names)
        assert all(path.is_file() and path.resolve().is_relative_to(paths.inputdata.resolve()) for path in paths.rawfiles)
        assert paths.invoice_org == paths.invoice / "invoice.json"


@pytest.mark.property
@given(parts=st.lists(st.sampled_from(["a", "b", "c"]), min_size=1, max_size=4), reverse=st.booleans())
def test_file_directory_collisions_never_create_partial_tree__r605_pbt_001(parts: list[str], reverse: bool) -> None:
    """R605-PBT-001: rejection of ancestor collisions is independent of order or depth."""
    # Given: a generated file path and a descendant, optionally in reverse order
    ancestor = "/".join(parts)
    names = [ancestor, f"{ancestor}/leaf.txt"]
    if reverse:
        names.reverse()
    with TemporaryDirectory() as directory:
        root = Path(directory) / "data"
        # When: the caller supplies the conflicting names as a one-shot iterable
        with pytest.raises(RdeConfigError) as raised:
            make_input_paths(root, files=(name for name in names))
        # Then: the public error is stable and no partial fixture tree exists
        assert raised.value.code == 1003
        assert raised.value.name == "InvalidTestInputPath"
        assert not root.exists()
