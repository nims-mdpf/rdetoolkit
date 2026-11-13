"""Config-sensitive flow for the ``repro export`` effective-config tests (RC1-INT-CLI F09).

The flow writes ``config.custom["label"]`` to ``structured/label.txt`` so a
round trip that loses configuration is visible in the output bytes, not only
in the report digest. Ids are explicit so the module can be resolved by
``run`` any number of times in one pytest session.
"""

from __future__ import annotations

from rdetoolkit.core.flow import flow
from rdetoolkit.core.node import node
from rdetoolkit.types import OutputContext, RdeConfig


@node(id="rc1_f09_fixture_save_label")
def save_label(out: OutputContext, label: str) -> None:
    """Persist the configuration-dependent label."""
    out.write_bytes("struct", "label.txt", label.encode("utf-8"))


@flow(id="rc1_f09_fixture_config_pipeline")
def config_pipeline(out: OutputContext, config: RdeConfig) -> None:
    """Expose the effective configuration as a reproducible output file."""
    save_label(out, str(config.custom.get("label", "DEFAULT")))


def legacy_callback(srcpaths: object, resource_paths: object) -> None:
    """A v1 dataset callback, for exports of runs that used the v1 entry config."""
