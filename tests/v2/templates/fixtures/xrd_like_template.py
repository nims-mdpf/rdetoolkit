"""Real, file-backed ``ProcessingTemplate`` fixtures for
``tests/v2/cli/test_cli_templates.py``'s ``--module`` tests (Session F2).

Deliberately named to resemble a domain template (mirroring Design
§5.2.1's XRD worked example shape) WITHOUT being a real production
skeleton: Conflict #10 forbids shipping any concrete skeleton class under
``src/rdetoolkit/templates/`` in this session -- ``rdetoolkit-xrd`` is
Phase G territory, a separate package. This fixture lives under
``tests/v2/templates/fixtures/`` only.
"""

from __future__ import annotations

from typing import final

from rdetoolkit.templates import ProcessingTemplate, slot
from rdetoolkit.types import InputPaths, InvoiceData


class DemoSkeletonTemplate(ProcessingTemplate):
    """Depth-1 skeleton fixture -- must appear in ``templates list``
    (Conflict #6: the Template Registry holds skeletons only)."""

    @slot
    def read(self, paths: InputPaths) -> None: ...

    @slot
    def extract_meta(self, invoice: InvoiceData) -> None: ...

    def transform(self) -> None:
        """Optional hook with a working default implementation."""
        return None

    @final
    def __flow__(self, paths: InputPaths, invoice: InvoiceData) -> None:
        self.read(paths)
        self.transform()
        self.extract_meta(invoice)


class DemoConcreteProcessing(DemoSkeletonTemplate):
    """Depth-2 concrete user fixture -- must NEVER appear in ``templates
    list`` output, even when this module has been ``--module``-imported
    (Conflict #6's scope guard / Verification command #11)."""

    def read(self, paths: InputPaths) -> None:
        return None

    def extract_meta(self, invoice: InvoiceData) -> None:
        return None
