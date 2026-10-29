"""K4-F6 review (PR #556 R1): slot signatures are compared as resolved types, not text.

| ID | Kind | Scenario | Expected |
|----|------|----------|----------|
| TC-K4F6-SIG-EP-001 | EP | skeleton ``Optional[Path]``, implementation ``Path | None`` | accepted |
| TC-K4F6-SIG-EP-002 | EP | skeleton ``list[Path]``, implementation ``list[str]`` | 2102 |
| TC-K4F6-SIG-BV-001 | BV | implementation drops the annotation | 2102 (unchanged shallow rule) |
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, final

import pytest

from rdetoolkit.errors import RdeRegistryError
from rdetoolkit.templates import ProcessingTemplate, slot
from rdetoolkit.types import InputPaths


class _OptionalSkeleton(ProcessingTemplate):
    @slot
    def locate(self, root: Optional[Path], items: list[Path]) -> Optional[Path]: ...  # noqa: UP045

    @final
    def __flow__(self, paths: InputPaths) -> None:
        self.locate(None, [])


def test_equivalent_spellings_are_accepted__tc_k4f6_sig_ep_001() -> None:
    """TC-K4F6-SIG-EP-001: ``Path | None`` satisfies a slot declared ``Optional[Path]``."""

    class Impl(_OptionalSkeleton):
        def locate(self, root: Path | None, items: list[Path]) -> Path | None:
            return root

    assert Impl().locate(None, []) is None


def test_different_generic_argument_is_rejected__tc_k4f6_sig_ep_002() -> None:
    """TC-K4F6-SIG-EP-002: a different type inside the generic is still a mismatch."""
    with pytest.raises(RdeRegistryError) as excinfo:

        class Impl(_OptionalSkeleton):  # noqa: F841
            def locate(self, root: Path | None, items: list[str]) -> Path | None:
                return root

    assert excinfo.value.code == 2102


def test_missing_annotation_is_rejected__tc_k4f6_sig_bv_001() -> None:
    """TC-K4F6-SIG-BV-001: dropping an annotation is still a mismatch (shallow rule kept)."""
    with pytest.raises(RdeRegistryError) as excinfo:

        class Impl(_OptionalSkeleton):  # noqa: F841
            def locate(self, root, items: list[Path]) -> Path | None:  # noqa: ANN001
                return root

    assert excinfo.value.code == 2102
