"""Issue #609: the ``system.extended_mode`` input/output contract.

The validated attribute is always ``str``. A null mode in mapping or YAML
input means "not set" (the invoice default, outside ``model_fields_set``).
Typed Python code omits the argument instead of passing ``None``: the public
type, in both ``types.py`` and ``types.pyi``, stays ``str``. The unset and
explicit forms stay distinct through normalization, the config digest, and
``repro`` export -> import -> run.

EP table:
    TC-609-EP-001 | strict mypy: omitted mode, str mode, null via mapping/overrides | accepted; attribute typed ``str``
    TC-609-EP-002 | omitted / null mapping / YAML null / null override / explicit | validated value is ``str``
    TC-609-EP-003 | same forms through normalizer, deep copy, digest, replay dump, reload | unset vs explicit retained
    TC-609-EP-004 | ``repro`` round trip of a YAML-null run and an explicit-invoice run | digests reproduced and distinct

Negative table:
    TC-609-NEG-001 | strict mypy: ``V2SystemSettings(extended_mode=None)`` | rejected as ``arg-type``

BV table:
    TC-609-BV-001 | runtime annotation and stub annotation of ``extended_mode`` | both exactly ``str``
"""

from __future__ import annotations

import ast
import json
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

import rdetoolkit.types as types_module
from rdetoolkit.cli.app import app
from rdetoolkit.config.normalize import ConfigNormalizer
from rdetoolkit.runner import load_run_config
from rdetoolkit.runner.config_loader import compute_config_digest, config_for_replay, load_config
from rdetoolkit.types import RdeConfig, V2SystemSettings
from tests.v2.cli.test_cli_repro_config_rc1 import _cwd, _export, _report_path, _run, _seed


def _from_mapping(tmp_path: Path, system: dict[str, Any]) -> RdeConfig:
    return RdeConfig.model_validate({"system": system})


def _from_yaml(tmp_path: Path, system: dict[str, Any]) -> RdeConfig:
    (tmp_path / "rdeconfig.yaml").write_text(yaml.safe_dump({"system": system}), encoding="utf-8")
    return load_run_config(tmp_path)


def _from_override(tmp_path: Path, system: dict[str, Any]) -> RdeConfig:
    (tmp_path / "rdeconfig.yaml").write_text("system:\n  extended_mode: MultiDataTile\n", encoding="utf-8")
    return load_run_config(tmp_path, overrides={"system": system})


SOURCES: dict[str, Callable[[Path, dict[str, Any]], RdeConfig]] = {
    "mapping": _from_mapping,
    "yaml": _from_yaml,
    "override": _from_override,
}

# (system input, explicitly configured?)
FORMS: dict[str, tuple[dict[str, Any], bool]] = {
    "null": ({"extended_mode": None}, False),
    "explicit_invoice": ({"extended_mode": "invoice"}, True),
    "explicit_alias": ({"extended_mode": "Invoice"}, True),
}


def _mypy(tmp_path: Path, source: str) -> tuple[str, int]:
    from mypy import api as mypy_api

    consumer = tmp_path / "consumer.py"
    consumer.write_text(source, encoding="utf-8")
    stdout, stderr, exit_status = mypy_api.run(
        ["--strict", "--no-incremental", "--cache-dir", str(tmp_path / ".mypy_cache"), str(consumer)],
    )
    return stdout + stderr, exit_status


def test_typed_api_accepts_supported_forms__tc_609_ep_001(tmp_path: Path) -> None:
    """TC-609-EP-001: omission, a string, and mapping null type-check; the attribute is ``str``."""
    # Given: a strict consumer using every supported way to set or clear the mode
    source = (
        "from rdetoolkit.runner import load_run_config\n"
        "from rdetoolkit.types import RdeConfig, V2SystemSettings\n\n"
        "omitted: str = V2SystemSettings().extended_mode\n"
        "explicit: str = V2SystemSettings(extended_mode='MultiDataTile').extended_mode\n"
        "mapped: str = RdeConfig.model_validate({'system': {'extended_mode': None}}).system.extended_mode\n"
        "loaded: str = load_run_config(overrides={'system': {'extended_mode': None}}).system.extended_mode\n"
    )
    # When: strict mypy checks it against the installed public stub
    output, exit_status = _mypy(tmp_path, source)
    # Then: all forms are accepted and the attribute is typed as str
    assert exit_status == 0, output


def test_typed_constructor_rejects_none__tc_609_neg_001(tmp_path: Path) -> None:
    """TC-609-NEG-001: ``None`` is not part of the typed constructor contract."""
    # Given: a strict consumer passing None to the typed constructor
    source = "from rdetoolkit.types import V2SystemSettings\n\nV2SystemSettings(extended_mode=None)\n"
    # When: strict mypy checks it
    output, exit_status = _mypy(tmp_path, source)
    # Then: the type checker directs the caller to omit the argument instead
    assert exit_status == 1
    assert '"extended_mode"' in output
    assert "[arg-type]" in output


def test_runtime_and_stub_declare_str__tc_609_bv_001() -> None:
    """TC-609-BV-001: the runtime model and the stub both declare ``str``."""
    # Given: the runtime field and the stub's class body
    stub = ast.parse(Path(types_module.__file__).with_suffix(".pyi").read_text(encoding="utf-8"))
    cls = next(node for node in stub.body if isinstance(node, ast.ClassDef) and node.name == "V2SystemSettings")
    stub_annotation = next(
        ast.unparse(item.annotation)
        for item in cls.body
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name) and item.target.id == "extended_mode"
    )
    # When / Then: neither admits None as the declared type
    assert V2SystemSettings.model_fields["extended_mode"].annotation is str
    assert stub_annotation == "str"


@pytest.mark.parametrize("source", list(SOURCES))
@pytest.mark.parametrize("form", list(FORMS))
def test_validated_mode_is_str__tc_609_ep_002(tmp_path: Path, source: str, form: str) -> None:
    """TC-609-EP-002: every accepted input yields a ``str`` and the right explicitness."""
    # Given: one input form delivered through one public source
    system, explicit = FORMS[form]
    # When: the configuration is validated
    config = SOURCES[source](tmp_path, system)
    # Then: the value is a str naming invoice, explicit only when a string was given
    assert type(config.system.extended_mode) is str
    assert config.system.extended_mode.lower() == "invoice"
    assert ("extended_mode" in config.system.model_fields_set) is explicit


def _replay(tmp_path: Path, config: RdeConfig, *, compact: bool) -> RdeConfig:
    root = tmp_path / f"replay_{compact}"
    root.mkdir()
    (root / "rdeconfig.yaml").write_text(yaml.safe_dump(config_for_replay(config, compact=compact)), encoding="utf-8")
    return load_config(root, data_root=root / "data")


@pytest.mark.parametrize("source", list(SOURCES))
@pytest.mark.parametrize("form", list(FORMS))
def test_explicitness_survives_pipeline__tc_609_ep_003(tmp_path: Path, source: str, form: str) -> None:
    """TC-609-EP-003: unset and explicit stay distinct after normalization, digest and replay."""
    # Given: one input form and the matching omitted / explicit reference digests
    system, explicit = FORMS[form]
    config = SOURCES[source](tmp_path, system)
    unset_digest = compute_config_digest(RdeConfig())
    explicit_digest = compute_config_digest(RdeConfig.model_validate({"system": {"extended_mode": "invoice"}}))
    # When: the config passes through every stage that re-creates it
    stages = {
        "normalized": ConfigNormalizer().normalize(config.model_dump(exclude_unset=True), root=tmp_path, origin="v2"),
        "copied": config.model_copy(deep=True),
        "replayed": _replay(tmp_path, config, compact=False),
        "replayed_compact": _replay(tmp_path, config, compact=True),
    }
    # Then: each stage keeps the explicitness and the digest of its form
    assert unset_digest != explicit_digest
    expected = explicit_digest if explicit else unset_digest
    assert compute_config_digest(config) == expected
    for name, stage in stages.items():
        assert ("extended_mode" in stage.system.model_fields_set) is explicit, name
        assert stage.system.extended_mode.lower() == "invoice", name
        assert compute_config_digest(stage) == expected, name
    assert ("extended_mode" in config_for_replay(config).get("system", {})) is explicit


def _round_trip(tmp_path: Path, mode_line: str) -> tuple[str, str, dict[str, Any]]:
    root = tmp_path / "project"
    data_root = root / "data"
    _seed(data_root)
    (root / "rdeconfig.yaml").write_text(f"system:\n  {mode_line}\ncustom:\n  label: issue609\n", encoding="utf-8")
    original = _run(root)
    archive = tmp_path / "archive.zip"
    exported = _export(_report_path(data_root, original), archive)
    assert exported.exit_code == 0, exported.output
    with zipfile.ZipFile(archive) as opened:
        archived = yaml.safe_load(opened.read("rdeconfig.yaml")) or {}
    target = tmp_path / "imported"
    imported = CliRunner().invoke(app, ["repro", "import", str(archive), str(target)])
    assert imported.exit_code == 0, imported.output
    (target / "data" / "temp").mkdir(parents=True, exist_ok=True)
    with _cwd(target):
        replay = json.loads(CliRunner().invoke(app, ["run", "tests.v2.cli.fixtures.repro_config_flows:config_pipeline"]).output)
    assert replay["config_digest"] == original["config_digest"]
    return original["config_digest"], replay["config_digest"], archived


def test_repro_round_trip_keeps_explicitness__tc_609_ep_004(tmp_path: Path) -> None:
    """TC-609-EP-004: a YAML-null run and an explicit-invoice run replay with distinct digests."""
    # Given / When: one run with ``extended_mode: null`` and one with ``invoice``, each round-tripped
    null_digest, _, null_archived = _round_trip(tmp_path / "null", "extended_mode: null")
    explicit_digest, _, explicit_archived = _round_trip(tmp_path / "explicit", "extended_mode: invoice")
    # Then: the null run is the unset config, and only the explicit run archives a mode
    assert null_digest == compute_config_digest(RdeConfig.model_validate({"custom": {"label": "issue609"}}))
    assert null_digest != explicit_digest
    assert "extended_mode" not in null_archived.get("system", {})
    assert explicit_archived["system"]["extended_mode"] == "invoice"
