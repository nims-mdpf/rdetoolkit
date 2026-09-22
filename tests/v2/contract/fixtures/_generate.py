"""Build Phase G contract fixtures from the v1 runtime oracle.

Source tag: v2.0.0a1; writer revision: each snapshot's ``source.commit``.
Generated on: 2026-07-15. Re-run this script; never hand-edit snapshots.

The generator owns both static input construction and expected-output
freezing. Expected values are observed from isolated v1 executions, then
normalized before comparison or persistence. Tests may execute v1 as the
subject under test, but they must never use v1 to create expected values.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Callable, Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tests.fixtures.excelinvoice import (  # noqa: E402
    EXCELINVOICE_ENTRYDATA_SHEET1_MULTI,
    EXCELINVOICE_ENTRYDATA_SHEET2,
    EXCELINVOICE_ENTRYDATA_SHEET3,
)
from tests.v2.compat.canary_assembly import (  # noqa: E402
    CANARY_MODES,
    assemble_canary_case,
)

SOURCE_TAG = "v2.0.0a1"
GENERATED_ON = "2026-07-15"

FIXTURE_ROOT = Path(__file__).resolve().parent
INPUT_ROOT = FIXTURE_ROOT / "inputs"
EXPECTED_ROOT = FIXTURE_ROOT / "expected" / "v1"
CANARY_EXPECTED_ROOT = FIXTURE_ROOT / "expected" / "canary"

_SEED_INVOICE = {
    "datasetId": "seed-dataset",
    "basic": {
        "dateSubmitted": "2026-07-15",
        "dataOwnerId": "0" * 56,
        "dataName": "seed",
    },
}
_EMPTY_METADATA_DEF = {"constant": {}, "variable": []}

_KEY_PLACEHOLDERS = {
    "started_at": "<TIMESTAMP>",
    "finished_at": "<TIMESTAMP>",
    "timestamp": "<TIMESTAMP>",
    "emitted_at": "<TIMESTAMP>",
    "duration_ms": "<DURATION_MS>",
    "config_digest": "<CONFIG_DIGEST>",
    "traceback": "<TRACEBACK>",
    "stacktrace": "<TRACEBACK>",
    "dateSubmitted": "<DATE>",
}
_VERSION_PATTERN = re.compile(r"(?m)^rdetoolkit==[^\s]+$")

# v1 genuinely records an order-dependent ``target``: the pipeline sets
# ``WorkflowExecutionStatus.target = ProcessingContext.basedir`` which is
# ``rawfiles[0].parent`` (src/rdetoolkit/processing/context.py), and in
# rdeformat mode the rawfiles tuple order comes from ``Path.glob("**/*")``
# inside ``RDEFormatChecker._unpacked`` (src/rdetoolkit/impl/input_controller.py)
# -- raw os.scandir filesystem order, which differs across machines.
# Within one tile the first raw file may live in raw/, meta/, or structured/,
# so the tile-subdirectory component of ``target`` is not a stable contract.
# v1 source is read-only for these fixtures, so normalization keeps the
# deterministic tile prefix and replaces only the order-dependent remainder.
_TILE_TARGET_PATTERN = re.compile(r"^(data/temp/\d{4})/.+$")
_TILE_TARGET_PLACEHOLDER = r"\1/<TILE_SUBDIR>"
_EXPECTED_RELATIVE_ROOT = EXPECTED_ROOT.relative_to(REPOSITORY_ROOT)
_CANARY_EXPECTED_RELATIVE_ROOT = CANARY_EXPECTED_ROOT.relative_to(REPOSITORY_ROOT)
_PROVENANCE_REMEDIATION = (
    "commit code changes first, regenerate on the clean tree, then commit the snapshots"
)


def _git_revision() -> str:
    """Return the 12-character commit revision used by this generator process."""
    git = shutil.which("git")
    if git is None:
        msg = "git is required to record contract fixture provenance"
        raise RuntimeError(msg)
    completed = subprocess.run(  # noqa: S603
        [git, "rev-parse", "--short=12", "HEAD"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _git_dirty_paths() -> tuple[Path, ...]:
    """Return repository-relative paths reported by Git porcelain status."""
    git = shutil.which("git")
    if git is None:
        msg = "git is required to validate contract fixture provenance"
        raise RuntimeError(msg)
    completed = subprocess.run(  # noqa: S603
        [git, "status", "--porcelain"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    paths: list[Path] = []
    for line in completed.stdout.splitlines():
        raw_path = line[3:]
        if " -> " in raw_path:
            raw_path = raw_path.rsplit(" -> ", maxsplit=1)[1]
        paths.append(Path(raw_path))
    return tuple(paths)


def _require_write_tree_hygiene() -> None:
    """Refuse regeneration when dirtiness extends beyond expected snapshots."""
    dirty_paths = _git_dirty_paths()
    expected_roots = (_EXPECTED_RELATIVE_ROOT, _CANARY_EXPECTED_RELATIVE_ROOT)
    disallowed = [
        path
        for path in dirty_paths
        if not any(path == root or root in path.parents for root in expected_roots)
    ]
    if disallowed:
        rendered = ", ".join(path.as_posix() for path in disallowed)
        msg = (
            f"contract snapshot regeneration requires a clean code tree; dirty paths: "
            f"{rendered}. Remediation: {_PROVENANCE_REMEDIATION}"
        )
        raise RuntimeError(msg)


def _normalize_string(value: str, roots: Sequence[Path]) -> str:
    """Replace volatile path and installed-version text in a string."""
    normalized = value
    for root in sorted((path.resolve() for path in roots), key=lambda path: len(str(path)), reverse=True):
        normalized = normalized.replace(str(root), "<RUN_ROOT>")
    return _VERSION_PATTERN.sub("rdetoolkit==<VERSION>", normalized)


def normalize_snapshot(
    value: Any,
    *,
    roots: Sequence[Path] = (),
    _key: str | None = None,
) -> Any:
    """Return a JSON-compatible value with contract volatility normalized.

    Args:
        value: Arbitrarily nested JSON-compatible source value.
        roots: Isolated execution roots to replace with ``<RUN_ROOT>``.

    Returns:
        A recursively normalized JSON-compatible value.
    """
    if _key in _KEY_PLACEHOLDERS:
        return _KEY_PLACEHOLDERS[_key]

    if isinstance(value, Mapping):
        return {
            str(key): normalize_snapshot(item, roots=roots, _key=str(key))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [normalize_snapshot(item, roots=roots) for item in value]
    if isinstance(value, (str, Path)):
        normalized = _normalize_string(str(value), roots)
        if _key == "target":
            normalized = _TILE_TARGET_PATTERN.sub(_TILE_TARGET_PLACEHOLDER, normalized)
        return normalized
    return value


def _canonical_json(value: Any) -> str:
    """Serialize a snapshot deterministically."""
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_json_snapshot(path: Path, value: Any) -> None:
    """Write a canonical UTF-8 JSON snapshot.

    Args:
        path: Destination below the contract fixture directory.
        value: JSON-compatible normalized value.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_canonical_json(value), encoding="utf-8", newline="\n")


def compare_snapshot(path: Path, value: Any) -> str | None:
    """Compare a candidate with a frozen snapshot without modifying files.

    Args:
        path: Existing frozen snapshot.
        value: Newly generated and normalized candidate.

    Returns:
        ``None`` on equality, otherwise a concise mismatch description.
    """
    if not path.exists():
        return f"missing frozen snapshot: {path.name}"
    expected = path.read_text(encoding="utf-8")
    candidate = _canonical_json(value)
    if expected == candidate:
        return None
    return f"snapshot differs: {path.name}"


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_canonical_json(value), encoding="utf-8", newline="\n")


def _build_data_layout(
    mode_root: Path,
    *,
    invoice: Mapping[str, Any] = _SEED_INVOICE,
    schema: Mapping[str, Any] | None = None,
    metadata_def: Mapping[str, Any] = _EMPTY_METADATA_DEF,
) -> Path:
    data_root = mode_root / "data"
    for name in ("inputdata", "invoice", "tasksupport", "unpacked"):
        (data_root / name).mkdir(parents=True, exist_ok=True)
    _write_json(data_root / "invoice" / "invoice.json", invoice)
    _write_json(
        data_root / "tasksupport" / "invoice.schema.json",
        {"properties": {}} if schema is None else schema,
    )
    _write_json(data_root / "tasksupport" / "metadata-def.json", metadata_def)
    return data_root


def _write_deterministic_zip(path: Path, members: Mapping[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for member_name, content in sorted(members.items()):
            info = zipfile.ZipInfo(member_name, date_time=(2026, 7, 15, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content.encode())


def _excelinvoice_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["custom", "sample"],
        "properties": {
            "custom": {
                "type": "object",
                "label": {"ja": "固有情報", "en": "Custom Information"},
                "required": ["key1"],
                "properties": {
                    "key1": {
                        "type": "string",
                        "label": {"ja": "キー1", "en": "Key 1"},
                    },
                    "key2": {
                        "type": "string",
                        "label": {"ja": "キー2", "en": "Key 2"},
                    },
                },
            },
            "sample": {
                "type": "object",
                "label": {"ja": "試料情報", "en": "Sample Information"},
                "properties": {},
            },
        },
    }


def _write_excelinvoice(path: Path, *, zero_rows: bool) -> None:
    sheet2 = pd.DataFrame(
        EXCELINVOICE_ENTRYDATA_SHEET2,
        columns=["term_id", "key_name"],
    )
    sheet3 = pd.DataFrame(
        EXCELINVOICE_ENTRYDATA_SHEET3,
        columns=["sample_class_id", "term_id", "key_name"],
    )
    with pd.ExcelWriter(path) as writer:
        if not zero_rows:
            source_rows = EXCELINVOICE_ENTRYDATA_SHEET1_MULTI[3:]
            owner_id = "0" * 56
            derived_rows = [
                ["", "basic", "basic"],
                ["name", "dataName", "dataOwnerId"],
                ["Input filename", "Data name", "Data owner ID"],
                *[[row[0], row[4], owner_id] for row in source_rows],
            ]
            sheet1 = pd.DataFrame(
                derived_rows,
                columns=["invoiceList_format_id", "Sample_RDE_DataSet", ""],
            )
            sheet1.to_excel(writer, sheet_name="invoice_form", index=False)
        sheet2.to_excel(writer, sheet_name="generalTerm", index=False)
        sheet3.to_excel(writer, sheet_name="specificTerm", index=False)


def _build_excelinvoice_inputs(destination: Path) -> dict[str, Any]:
    data_root = _build_data_layout(destination)
    inputdata = data_root / "inputdata"
    _write_excelinvoice(inputdata / "excelinvoice_multi.xlsx", zero_rows=False)
    _write_excelinvoice(inputdata / "excelinvoice_zero_rows.xlsx", zero_rows=True)
    _write_deterministic_zip(
        destination / "excelinvoice_files.zip",
        {
            "test_child1.txt": "excelinvoice child 1\n",
            "test_child2.txt": "excelinvoice child 2\n",
        },
    )
    return {
        "multi_workbook": "data/inputdata/excelinvoice_multi.xlsx",
        "zero_row_workbook": "data/inputdata/excelinvoice_zero_rows.xlsx",
        "raw_archive": "excelinvoice_files.zip",
        "source_rows": "tests/fixtures/excelinvoice.py:EXCELINVOICE_ENTRYDATA_SHEET1_MULTI",
    }


def _build_multidatatile_inputs(destination: Path) -> dict[str, Any]:
    data_root = _build_data_layout(destination)
    inputdata = data_root / "inputdata"
    (inputdata / "tile_00.txt").write_text("first tile\n", encoding="utf-8")
    (inputdata / "tile_日本語.txt").write_text("二番目のタイル\n", encoding="utf-8")
    return {
        "files": [
            "data/inputdata/tile_00.txt",
            "data/inputdata/tile_日本語.txt",
        ],
        "expected_tree": "../../expected/multidatatile/ok.json",
    }


def _build_rdeformat_inputs(destination: Path) -> dict[str, Any]:
    data_root = _build_data_layout(destination)
    archive_path = data_root / "inputdata" / "rdeformat_sample.zip"
    _write_deterministic_zip(
        archive_path,
        {
            "0000/raw/first.txt": "first RDE tile\n",
            "0000/structured/result.csv": "x,y\n1,2\n",
            "0001/raw/日本語データ.txt": "日本語のRDEデータ\n",
            "0001/meta/metadata.json": '{"constant": {}, "variable": []}\n',
        },
    )
    return {"archive": "data/inputdata/rdeformat_sample.zip"}


def _smarttable_schema() -> dict[str, Any]:
    schema_path = REPOSITORY_ROOT / "tests" / "samplefile" / "invoice.schema.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _smarttable_invoice() -> dict[str, Any]:
    """Return the legacy sample invoice with a repository-safe owner identity."""
    invoice_path = REPOSITORY_ROOT / "tests" / "samplefile" / "invoice.json"
    invoice = json.loads(invoice_path.read_text(encoding="utf-8"))
    invoice["basic"]["description"] = ""
    # The legacy sample predates fixture PII policy and contains a real owner
    # hash. Keep that v1 input untouched while preventing every G1 rebuild from
    # copying the identity into the public contract corpus.
    invoice["basic"]["dataOwnerId"] = "0" * 55 + "1"
    invoice["sample"]["ownerId"] = "0" * 55 + "5"
    return invoice


def _smarttable_rows() -> list[list[Any]]:
    general_term = "3adf9874-7bcb-e5f8-99cb-3d6fd9d7b55e"
    class_id = "01cb3c01-37a4-5a43-d8ca-f523ca99a75b"
    specific_term = "3250c45d-0ed6-1438-43b5-eb679918604a"
    return [
        [
            "Data name", "Measured date", "Numeric value", "General attribute",
            "Specific attribute", "Sample name", "Description", "Comment",
            "Temperature", "Mapped input file",
        ],
        [
            "basic/dataName", "custom/sample1", "custom/sample2",
            f"sample/generalAttributes.{general_term}",
            f"sample/specificAttributes.{class_id}.{specific_term}",
            "sample/names", "sample/description", "meta/comment",
            "meta/temperature", "inputdata1",
        ],
        [
            "smarttable_value_0", date(2026, 7, 15), 1,
            "general-a", "specific-a", "sample-a", "first row", "memo-a",
            20.5, "measurements/row0.txt",
        ],
        [
            "smarttable_value_1", date(2026, 7, 16), 2.5,
            "general-b", "specific-b", "sample-b", "", "memo-b",
            21, "測定/行1.txt",
        ],
        [
            "smarttable_value_2", date(2026, 7, 17), 3,
            "", "specific-c", "sample-c", "third row", "", "",
            "",
        ],
    ]


def _build_smarttable_inputs(destination: Path) -> dict[str, Any]:
    metadata_def = {
        "comment": {
            "name": {"ja": "コメント", "en": "Comment"},
            "schema": {"type": "string"},
        },
        "temperature": {
            "name": {"ja": "温度", "en": "Temperature"},
            "schema": {"type": "number"},
            "unit": "C",
        },
    }
    data_root = _build_data_layout(
        destination,
        invoice=_smarttable_invoice(),
        schema=_smarttable_schema(),
        metadata_def=metadata_def,
    )
    rows = pd.DataFrame(_smarttable_rows())
    xlsx_path = data_root / "inputdata" / "smarttable_full.xlsx"
    rows.to_excel(xlsx_path, index=False, header=False)
    csv_path = destination / "smarttable_full.csv"
    pd.read_excel(xlsx_path, header=None).to_csv(csv_path, index=False, header=False)
    _write_deterministic_zip(
        data_root / "inputdata" / "smarttable_inputs.zip",
        {
            "measurements/row0.txt": "row zero measurement\n",
            "測定/行1.txt": "行1の測定\n",
        },
    )
    return {
        "workbook": "data/inputdata/smarttable_full.xlsx",
        "csv_equivalent": "smarttable_full.csv",
        "file_archive": "data/inputdata/smarttable_inputs.zip",
        "rows": 3,
    }


def _build_invoice_references(destination: Path) -> dict[str, Any]:
    destination.mkdir(parents=True, exist_ok=True)
    references = [
        "tests/samplefile/invoice.json",
        "tests/samplefile/invoice.schema.json",
        "tests/samplefile/invoice.schema.full.json",
        "tests/samplefile/invoice.schema.basic.json",
    ]
    registry = {"references": references}
    _write_json(destination / "registered_references.json", registry)
    return registry


def build_static_inputs(destination: Path = INPUT_ROOT) -> dict[str, dict[str, Any]]:
    """Build all five mode input families below ``destination``.

    Args:
        destination: Root for generated input fixtures.

    Returns:
        Mode-keyed manifest describing generated files and registered assets.
    """
    destination.mkdir(parents=True, exist_ok=True)
    manifest = {
        "invoice": _build_invoice_references(destination / "invoice"),
        "excelinvoice": _build_excelinvoice_inputs(destination / "excelinvoice"),
        "multidatatile": _build_multidatatile_inputs(destination / "multidatatile"),
        "rdeformat": _build_rdeformat_inputs(destination / "rdeformat"),
        "smarttable": _build_smarttable_inputs(destination / "smarttable"),
    }
    _write_json(destination / "manifest.json", manifest)
    return manifest


_XLSX_DRIFT_NOTE = (
    "xlsx drift check: compared workbook cell values; byte comparison skipped "
    "because openpyxl metadata is nondeterministic"
)


def _relative_files(root: Path) -> dict[Path, Path]:
    return {path.relative_to(root): path for path in root.rglob("*") if path.is_file()}


def _workbook_values_equal(left: Path, right: Path) -> bool:
    left_book = pd.read_excel(left, sheet_name=None, header=None)
    right_book = pd.read_excel(right, sheet_name=None, header=None)
    if left_book.keys() != right_book.keys():
        return False
    return all(left_book[sheet].equals(right_book[sheet]) for sheet in left_book)


def check_static_input_drift(committed_root: Path = INPUT_ROOT) -> tuple[list[str], str]:
    """Rebuild synthetic inputs and report drift, excluding imported canaries."""
    with tempfile.TemporaryDirectory(prefix="rdetoolkit-g-review-inputs-") as temporary:
        generated_root = Path(temporary) / "inputs"
        build_static_inputs(generated_root)
        committed = {
            relative: path
            for relative, path in _relative_files(committed_root).items()
            if relative.parts[0] != "canary"
        }
        generated = _relative_files(generated_root)
        mismatches: list[str] = []
        for relative in sorted(committed.keys() | generated.keys()):
            committed_path = committed.get(relative)
            generated_path = generated.get(relative)
            if committed_path is None or generated_path is None:
                mismatches.append(f"input inventory differs: {relative.as_posix()}")
                continue
            if relative.suffix.lower() == ".xlsx":
                if not _workbook_values_equal(committed_path, generated_path):
                    mismatches.append(f"xlsx input values differ: {relative.as_posix()}")
                continue
            if committed_path.read_bytes() != generated_path.read_bytes():
                mismatches.append(f"deterministic input differs: {relative.as_posix()}")
        return mismatches, _XLSX_DRIFT_NOTE


def source_revision_warnings(
    *,
    root: Path = EXPECTED_ROOT,
    current_commit: str | None = None,
) -> list[str]:
    """Return non-failing warnings for stale frozen source provenance."""
    current = current_commit or _git_revision()
    recorded = _recorded_source_commits(root)
    return [
        (
            f"warning: frozen source.commit {commit} differs from current revision {current}; "
            "remediation: regenerate all contract snapshots with _generate.py"
        )
        for commit in sorted(recorded)
        if commit not in {current, "<unrecorded>"} and "-dirty" not in commit
    ]


def _recorded_source_commits(root: Path) -> set[str]:
    """Return source commits, mapping missing or null values to unrecorded."""
    recorded: set[str] = set()
    for path in root.rglob("*.json"):
        commit = json.loads(path.read_text(encoding="utf-8")).get("source", {}).get("commit")
        recorded.add(commit if isinstance(commit, str) else "<unrecorded>")
    return recorded


def source_revision_errors(*, root: Path = EXPECTED_ROOT) -> list[str]:
    """Return fatal errors for unauditable frozen source provenance."""
    return [
        (
            f"frozen source.commit {commit!r} is unauditable. "
            f"Remediation: {_PROVENANCE_REMEDIATION}"
        )
        for commit in sorted(_recorded_source_commits(root))
        if not commit or commit == "<unrecorded>" or "-dirty" in commit
    ]


def expected_snapshot_paths(root: Path = EXPECTED_ROOT) -> list[Path]:
    """Return the complete frozen v1 snapshot inventory."""
    modes = ("invoice", "excelinvoice", "multidatatile", "rdeformat", "smarttable")
    outcomes = ("ok", "usererr", "valerr")
    snapshots = [root / mode / f"{outcome}.json" for mode in modes for outcome in outcomes]
    snapshots.append(root / "excelinvoice" / "zero_rows.json")
    return snapshots


def canary_snapshot_paths(root: Path = CANARY_EXPECTED_ROOT) -> list[Path]:
    """Return the five OK-only real-canary snapshot paths in sorted order."""
    return [root / mode / "ok.json" for mode in CANARY_MODES]


def _materialize_oracle_case(mode: str, root: Path, *, zero_rows: bool = False) -> None:
    if mode == "invoice":
        data_root = _build_data_layout(root)
        (data_root / "inputdata" / "invoice_input.txt").write_text(
            "invoice input\n",
            encoding="utf-8",
        )
        return

    shutil.copytree(INPUT_ROOT / mode / "data", root / "data")
    # git cannot track empty directories, so a fresh checkout loses the empty
    # data/unpacked/ that build_static_inputs creates on disk. Recreate it here
    # so the staged tree (and therefore the observed output tree) is identical
    # on local working copies and CI checkouts alike.
    (root / "data" / "unpacked").mkdir(exist_ok=True)
    if mode == "excelinvoice":
        _select_excelinvoice_case(root, zero_rows=zero_rows)


def _materialize_canary_case(mode: str, root: Path) -> None:
    """Assemble one repository-owned real-canary input family."""
    assemble_canary_case(mode, root)


def _select_excelinvoice_case(root: Path, *, zero_rows: bool) -> None:
    inputdata = root / "data" / "inputdata"
    selected_name = "excelinvoice_zero_rows.xlsx" if zero_rows else "excelinvoice_multi.xlsx"
    for workbook in inputdata.glob("*.xlsx"):
        if workbook.name != selected_name:
            workbook.unlink()
    (inputdata / selected_name).rename(inputdata / "contract_excel_invoice.xlsx")
    shutil.copy2(
        INPUT_ROOT / "excelinvoice" / "excelinvoice_files.zip",
        inputdata / "excelinvoice_files.zip",
    )


def _invalidate_invoice(root: Path) -> None:
    invoice_path = root / "data" / "invoice" / "invoice.json"
    invoice = json.loads(invoice_path.read_text(encoding="utf-8"))
    invoice["basic"] = None
    _write_json(invoice_path, invoice)


def oracle_config(mode: str, *, ignore_errors: bool = False) -> Any:
    """Return the v1 ``Config`` every frozen observation of ``mode`` was made with.

    Contract tests that execute the unified Runner over the same static input
    must hand it this exact object: passing a mapping instead would take the v2
    configuration defaults (notably ``on_iteration_error: continue``) and the
    comparison would then measure a configuration difference.

    Args:
        mode: One of the five unified execution modes.
        ignore_errors: v1 ``multidata_tile.ignore_errors``. Only the
            MultiDataTile pipeline honors it (``workflows._process_mode``); the
            frozen corpus is generated with the v1 default ``False``.

    Returns:
        The v1 configuration for this mode.
    """
    from rdetoolkit.models.config import (  # noqa: PLC0415
        Config,
        MultiDataTileSettings,
        SmartTableSettings,
        SystemSettings,
    )

    extended_mode = {
        "multidatatile": "MultiDataTile",
        "rdeformat": "rdeformat",
    }.get(mode)
    return Config(
        system=SystemSettings(
            extended_mode=extended_mode,
            save_raw=True,
            save_nonshared_raw=True,
            save_thumbnail_image=False,
            magic_variable=False,
        ),
        multidata_tile=MultiDataTileSettings(ignore_errors=ignore_errors),
        smarttable=SmartTableSettings(save_table_file=False),
    )


def _canary_config_path(mode: str) -> Path:
    """Return the imported source config later assembled as ``data/tasksupport``."""
    support = "tasksupport2" if mode == "multidatatile" else "tasksupport"
    return INPUT_ROOT / "canary" / mode / support / "rdeconfig.yaml"


def _effective_canary_config(mode: str, path: Path) -> tuple[Any, list[str]]:
    """Build a v1 Config from imported canary YAML plus assembly normalizations.

    The SEM/ExcelInvoice material predates the nested schema, so its top-level
    system keys are interpreted as ``system.*``. The RDEFormat material does
    not declare a mode; assembly overlays ``system.extended_mode=rdeformat`` in
    the same way the MultiDataTile material overlays its ``tasksupport2``
    config. Every unspecified field is left to the v1 Config model default.
    """
    from rdetoolkit.models.config import Config, SystemSettings  # noqa: PLC0415

    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        msg = f"canary config must contain a mapping: {path.as_posix()}"
        raise ValueError(msg)
    data = dict(loaded)
    normalizations: list[str] = []
    if "system" not in data:
        system_keys = set(SystemSettings.model_fields)
        system = {key: data.pop(key) for key in tuple(data) if key in system_keys}
        data["system"] = system
        normalizations.append("top-level system keys normalized to system.*")
    if mode == "rdeformat":
        system_data = data.setdefault("system", {})
        if not isinstance(system_data, dict):
            msg = f"canary system config must contain a mapping: {path.as_posix()}"
            raise ValueError(msg)
        system_data["extended_mode"] = "rdeformat"
        normalizations.append("system.extended_mode overlaid as rdeformat")
    return Config(**data), normalizations


def canary_effective_config_record(mode: str) -> dict[str, Any]:
    """Return the reproducible effective Config and source for a canary mode."""
    config, normalizations = _effective_canary_config(mode, _canary_config_path(mode))
    return {
        "source": {
            "path": "data/tasksupport/rdeconfig.yaml",
            "normalizations": normalizations,
        },
        "config": config.model_dump(mode="json"),
    }


#: Marker the oracle callbacks append one line to per invocation. It lives in
#: the run root (the process CWD), never below ``data/``, so it can never
#: appear in an observed output tree.
CALLBACK_MARKER_NAME = ".callback_calls"

#: Marker recording the ``RdeOutputResourcePath.smarttable_row_data`` each
#: invocation received, one JSON document per line, aligned with the call
#: marker. Session I-REVIEW-B ruling #2 compares the v1 and the v2 callback
#: material dynamically instead of freezing it.
ROW_DATA_MARKER_NAME = ".callback_row_data.jsonl"

#: The message ``_oracle_callback_usererr`` raises. The v2 contract tests raise
#: a byte-identical one, so ``job.failed`` parity is a real comparison.
CALLBACK_FAILURE_MESSAGE = (
    "Contract callback failed. Remediation: inspect the fixture callback "
    "and correct its input."
)

#: Tile the multi-tile policy callbacks fail (Session I-REVIEW-B ruling #3).
#: Index 1 is the only choice that distinguishes ``continue`` from
#: ``fail_fast`` on a three-tile run: a later tile must remain to be skipped.
FAILING_TILE_INDEX = 1


def _record_callback_call() -> None:
    marker = Path(CALLBACK_MARKER_NAME)
    with marker.open("a", encoding="utf-8") as stream:
        stream.write("called\n")


def _callback_call_count() -> int:
    """Return how many times an oracle callback has run in this process tree."""
    marker = Path(CALLBACK_MARKER_NAME)
    if not marker.exists():
        return 0
    return len(marker.read_text(encoding="utf-8").splitlines())


def _jsonable_row_data(row_data: Any) -> dict[str, Any] | None:
    """Return a JSON round-trippable form of one SmartTable row dictionary.

    ``pandas`` reads the row CSV with ``dtype=str`` and represents an empty cell
    as ``NaN``, which survives ``json.dumps`` but compares unequal to itself
    afterwards. Recording it as ``null`` keeps an equality comparison of two
    recorded rows meaningful; both sides of the comparison use this function.

    Args:
        row_data: The ``smarttable_row_data`` a callback received.

    Returns:
        A JSON-safe mapping, or ``None`` when the tile carried no row.
    """
    if row_data is None:
        return None
    normalized: dict[str, Any] = {}
    for key, value in dict(row_data).items():
        if isinstance(value, float) and math.isnan(value):
            normalized[str(key)] = None
        elif value is None or isinstance(value, (str, bool, int)):
            normalized[str(key)] = value
        else:
            normalized[str(key)] = str(value)
    return normalized


def _record_row_data(resource_paths: object) -> None:
    """Append this invocation's SmartTable row material to the row marker."""
    row_data = _jsonable_row_data(getattr(resource_paths, "smarttable_row_data", None))
    marker = Path(ROW_DATA_MARKER_NAME)
    with marker.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row_data, ensure_ascii=False, sort_keys=True) + "\n")


def read_callback_row_data(root: Path) -> list[dict[str, Any] | None]:
    """Return the row dictionaries the oracle callbacks received under ``root``.

    Args:
        root: Run root the callbacks executed in.

    Returns:
        One entry per invocation, in call order; ``None`` for a tile with no
        SmartTable row.
    """
    marker = root / ROW_DATA_MARKER_NAME
    if not marker.exists():
        return []
    return [
        json.loads(line)
        for line in marker.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _oracle_callback_ok(srcpaths: object, resource_paths: object) -> None:
    del srcpaths
    _record_callback_call()
    _record_row_data(resource_paths)


def _oracle_callback_usererr(srcpaths: object, resource_paths: object) -> None:
    from rdetoolkit.exceptions import StructuredError  # noqa: PLC0415

    del srcpaths
    _record_callback_call()
    _record_row_data(resource_paths)
    raise StructuredError(CALLBACK_FAILURE_MESSAGE, ecode=999)


def oracle_callback_tile_failure(srcpaths: object, resource_paths: object) -> None:
    """Fail only tile :data:`FAILING_TILE_INDEX`, leaving later tiles runnable.

    The call marker is the tile counter: v1 invokes the dataset callback exactly
    once per tile, in tile order, so the appended line count identifies the tile
    without the callback needing a v1-specific path convention.

    Args:
        srcpaths: v1 input paths (unused).
        resource_paths: v1 output paths for this tile.

    Raises:
        StructuredError: On the failing tile, with the same ``ecode``/message
            the single-tile user-error oracle raises.
    """
    from rdetoolkit.exceptions import StructuredError  # noqa: PLC0415

    del srcpaths
    _record_callback_call()
    _record_row_data(resource_paths)
    if _callback_call_count() == FAILING_TILE_INDEX + 1:
        raise StructuredError(CALLBACK_FAILURE_MESSAGE, ecode=999)


#: Outcome-to-callback dispatch for the isolated v1 worker. Unlisted outcomes
#: (``ok``, ``valerr``) run the success callback, as they always have.
_ORACLE_CALLBACKS: dict[str, Callable[[object, object], None]] = {
    "usererr": _oracle_callback_usererr,
    "tilefail": oracle_callback_tile_failure,
}


def _normalize_output_path(path: str) -> str:
    return re.sub(
        r"rdesys_\d{8}_\d{6}\.log",
        "rdesys_<LOG_TIMESTAMP>.log",
        path,
    )


def _output_tree(data_root: Path) -> dict[str, list[str]]:
    directories = sorted(
        _normalize_output_path(path.relative_to(data_root.parent).as_posix()) + "/"
        for path in data_root.rglob("*")
        if path.is_dir()
    )
    files = sorted(
        _normalize_output_path(path.relative_to(data_root.parent).as_posix())
        for path in data_root.rglob("*")
        if path.is_file()
    )
    return {"directories": directories, "files": files}


def _invoice_outputs(data_root: Path) -> dict[str, Any]:
    outputs: dict[str, Any] = {}
    for path in sorted(data_root.rglob("invoice/invoice.json")):
        relative = path.relative_to(data_root.parent).as_posix()
        outputs[relative] = json.loads(path.read_text(encoding="utf-8"))
    return outputs


#: Path components that make a file a raw copy rather than another artifact.
_RAW_COMPONENTS = frozenset({"raw", "nonshared_raw"})


def _classifiable_parts(path: Path, data_root: Path) -> tuple[str, ...]:
    """Return the path components a classification rule may look at.

    Only the part of a path **below the data root** describes an RDE run.
    Classifying on the absolute path made every rule depend on where the run
    happens to live: a project checked out under a directory named ``raw`` had
    all of its artifacts classified as raw copies, and one under ``logs`` had
    them all silently dropped — with no test failing, because the observation
    was then empty on both sides. This is the same ancestor-sensitivity class
    the reviewer reported as R1 for RDEFormat classification.

    Args:
        path: File below ``data_root``.
        data_root: The ``data`` directory of an observed run.

    Returns:
        The ``data_root``-relative components of ``path``.
    """
    return path.relative_to(data_root).parts


def _raw_hashes(data_root: Path) -> dict[str, str]:
    """Return sha256 digests of the raw copies below one data root."""
    hashes: dict[str, str] = {}
    for path in sorted(data_root.rglob("*")):
        if not path.is_file() or not _RAW_COMPONENTS.intersection(_classifiable_parts(path, data_root)):
            continue
        relative = path.relative_to(data_root.parent).as_posix()
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


#: Path components whose files are never a run-produced non-raw artifact:
#: ``raw``/``nonshared_raw`` belong to :func:`_raw_hashes`, ``inputdata`` and
#: ``tasksupport`` are input material the run only reads, and ``logs`` is the
#: one directory whose contents are contractually asymmetric between v1 and v2
#: (Design §6.3 addendum, Session I6-1 ruling #2).
_NON_ARTIFACT_COMPONENTS = _RAW_COMPONENTS | frozenset({"inputdata", "tasksupport", "logs"})


def _artifact_hashes(data_root: Path) -> dict[str, str]:
    """Return sha256 digests of every non-raw artifact the run produced.

    Session I-REVIEW-B ruling #1 (PR #539 review F4): comparing only paths for
    ``meta``/``structured``/``thumbnail``/``main_image``/``other_image``/
    ``attachment``/``temp`` let a corrupted artifact with the right filename
    pass full parity. Their bytes are deterministic — thumbnails are produced by
    ``img2thumb.copy_images_to_thumbnail``'s ``shutil.copy`` on both the v1 and
    the v2 side, never by a re-encode — so a digest is a legitimate contract.

    ``invoice/invoice.json`` is skipped because the ``invoices`` observation
    already carries its parsed value, which is a far better failure message.

    Classification looks only below ``data_root`` (:func:`_classifiable_parts`),
    so a run root that happens to live under a directory named ``logs`` or
    ``inputdata`` is observed like any other.

    Args:
        data_root: The ``data`` directory of an observed run.

    Returns:
        Digest per ``data/``-relative POSIX path, in sorted path order.
    """
    hashes: dict[str, str] = {}
    for path in sorted(data_root.rglob("*")):
        if not path.is_file() or _NON_ARTIFACT_COMPONENTS.intersection(_classifiable_parts(path, data_root)):
            continue
        if path.name == "invoice.json" and path.parent.name == "invoice":
            continue
        relative = path.relative_to(data_root.parent).as_posix()
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def _read_legacy_return(value: str | None) -> Any:
    if value is None:
        return None
    return json.loads(value)


def _collect_oracle_observation(root: Path, result: str | None, exit_code: int) -> dict[str, Any]:
    data_root = root / "data"
    job_failed = data_root / "job.failed"
    invoice_backup_path = data_root / "temp" / "invoice_org.json"
    callback_marker = root / ".callback_calls"
    callback_count = (
        len(callback_marker.read_text(encoding="utf-8").splitlines())
        if callback_marker.exists() else 0
    )
    job_failed_text = job_failed.read_text(encoding="utf-8") if job_failed.exists() else None
    job_failed_error_code = job_failed_text.splitlines()[0] if job_failed_text is not None else None
    invoice_backup = (
        json.loads(invoice_backup_path.read_text(encoding="utf-8"))
        if invoice_backup_path.exists()
        else None
    )
    return {
        "exit_code": exit_code,
        "callback_count": callback_count,
        "legacy_return": _read_legacy_return(result),
        "output_tree": _output_tree(data_root),
        "invoices": _invoice_outputs(data_root),
        "raw_sha256": _raw_hashes(data_root),
        "artifact_sha256": _artifact_hashes(data_root),
        "job_failed_error_code": job_failed_error_code,
        "job_failed_text": job_failed_text,
        "invoice_backup_exists": invoice_backup_path.exists(),
        "invoice_backup": invoice_backup,
    }


def _run_oracle_worker(
    mode: str,
    outcome: str,
    root: Path,
    *,
    canary: bool = False,
    ignore_errors: bool = False,
) -> int:
    from rdetoolkit.workflows import run as v1_run  # noqa: PLC0415

    if outcome == "valerr":
        _invalidate_invoice(root)
    callback = _ORACLE_CALLBACKS.get(outcome, _oracle_callback_ok)
    previous = Path.cwd()
    result: str | None = None
    exit_code = 0
    try:
        os.chdir(root)
        try:
            effective_config = (
                _effective_canary_config(
                    mode,
                    root / "data/tasksupport/rdeconfig.yaml",
                )[0]
                if canary
                else oracle_config(mode, ignore_errors=ignore_errors)
            )
            result = v1_run(
                custom_dataset_function=callback,
                config=effective_config,
            )
        except SystemExit as error:
            exit_code = int(error.code or 0)
    finally:
        os.chdir(previous)
    observation = _collect_oracle_observation(root, result, exit_code)
    _write_json(root / ".oracle_observation.json", observation)
    return 0


def _execute_v1_observation(
    mode: str,
    outcome: str,
    root: Path,
    *,
    canary: bool = False,
    ignore_errors: bool = False,
) -> dict[str, Any]:
    """Run the isolated v1 worker against an already-materialized case.

    Args:
        mode: One of the five unified execution modes.
        outcome: ``ok`` / ``usererr`` / ``valerr`` / ``tilefail``.
        root: Already-materialized run root the worker executes in.
        canary: Read the effective configuration from the assembled canary
            ``data/tasksupport/rdeconfig.yaml`` instead of the oracle config.
        ignore_errors: Run with v1 ``multidata_tile.ignore_errors=True``, the
            only v1 continue-on-error policy there is (``workflows._process_mode``).

    Returns:
        The normalized v1 observation.

    Raises:
        RuntimeError: If the worker process failed to produce an observation.
    """
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--oracle-worker",
        mode,
        outcome,
        str(root),
    ]
    if canary:
        command.append("--canary")
    if ignore_errors:
        command.append("--ignore-errors")
    completed = subprocess.run(  # noqa: S603
        command,
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    observation_path = root / ".oracle_observation.json"
    if completed.returncode != 0 or not observation_path.exists():
        message = (
            f"v1 oracle worker failed for {mode}/{outcome}: "
            f"exit={completed.returncode}; stderr={completed.stderr[-1000:]}"
        )
        raise RuntimeError(message)
    observation = json.loads(observation_path.read_text(encoding="utf-8"))
    return normalize_snapshot(observation, roots=(root,))


def _observe_materialized_v1(
    mode: str,
    outcome: str,
    *,
    prefix: str,
    materialize: Callable[[str, Path], None],
    canary: bool = False,
) -> dict[str, Any]:
    """Observe one case family through the shared isolated worker path."""
    with tempfile.TemporaryDirectory(prefix=f"{prefix}-{mode}-") as temporary:
        root = Path(temporary)
        materialize(mode, root)
        return _execute_v1_observation(mode, outcome, root, canary=canary)


def _observe_v1(mode: str, outcome: str, *, zero_rows: bool = False) -> dict[str, Any]:
    def materialize(selected_mode: str, root: Path) -> None:
        _materialize_oracle_case(selected_mode, root, zero_rows=zero_rows)

    return _observe_materialized_v1(
        mode,
        outcome,
        prefix="rdetoolkit-g1",
        materialize=materialize,
    )


def _observe_canary_v1(mode: str) -> dict[str, Any]:
    return _observe_materialized_v1(
        mode,
        "ok",
        prefix="rdetoolkit-h4-canary",
        materialize=_materialize_canary_case,
        canary=True,
    )


def materialize_sut_case(mode: str, root: Path) -> None:
    """Copy a committed mode input into an isolated SUT working directory."""
    _materialize_oracle_case(mode, root)


def run_v1_sut(mode: str, outcome: str) -> dict[str, Any]:
    """Execute v1 as the SUT and return a normalized observation.

    Expected values are deliberately not read or written here. Contract tests
    compare this observation with already-frozen JSON snapshots.
    """
    return _observe_v1(mode, outcome)


def run_v1_canary_sut(mode: str) -> dict[str, Any]:
    """Execute v1 against an imported real-canary input family."""
    return _observe_canary_v1(mode)


def _snapshot_case_from_path(path: Path) -> tuple[str, str, bool]:
    mode = path.parent.name
    outcome = path.stem
    zero_rows = outcome == "zero_rows"
    return mode, "ok" if zero_rows else outcome, zero_rows


def _frozen_source(path: Path, *, check: bool, stamped_commit: str | None) -> dict[str, Any]:
    """Return carried-forward or newly stamped snapshot provenance."""
    if check and path.exists():
        return json.loads(path.read_text(encoding="utf-8")).get(
            "source",
            {"tag": SOURCE_TAG, "commit": "<unrecorded>"},
        )
    return {"tag": SOURCE_TAG, "commit": stamped_commit}


def _compare_or_write(path: Path, payload: dict[str, Any], *, check: bool) -> str | None:
    """Compare a check candidate or write a generated snapshot."""
    if check:
        return compare_snapshot(path, payload)
    write_json_snapshot(path, payload)
    return None


def _process_v1_snapshots(*, check: bool, stamped_commit: str | None) -> list[str]:
    """Check or regenerate every G1 snapshot.

    Session H4 narrowed write mode to the SmartTable subset because that PII
    re-freeze was the only authorized rewrite at the time. Session I-REVIEW-B
    adds the ``artifact_sha256`` observation key to every mode, so write mode
    owns the whole inventory again (ruling #1 ritual step (b)).
    """
    mismatches: list[str] = []
    for path in expected_snapshot_paths():
        mode, outcome, zero_rows = _snapshot_case_from_path(path)
        payload = {
            "source": _frozen_source(path, check=check, stamped_commit=stamped_commit),
            "case": {
                "mode": mode,
                "outcome": "zero_rows" if zero_rows else outcome,
                "entry": "custom_dataset_function",
            },
            "observed": _observe_v1(mode, outcome, zero_rows=zero_rows),
        }
        mismatch = _compare_or_write(path, payload, check=check)
        if mismatch is not None:
            mismatches.append(f"{mode}/{path.stem}: {mismatch}")
    return mismatches


def _process_canary_snapshots(*, check: bool, stamped_commit: str | None) -> list[str]:
    """Write or compare the five real-canary OK snapshots."""
    mismatches: list[str] = []
    for path in canary_snapshot_paths():
        mode = path.parent.name
        payload = {
            "source": _frozen_source(path, check=check, stamped_commit=stamped_commit),
            "case": {
                "mode": mode,
                "outcome": "ok",
                "entry": "custom_dataset_function",
                "family": "canary",
                "effective_config": canary_effective_config_record(mode),
            },
            "observed": _observe_canary_v1(mode),
        }
        mismatch = _compare_or_write(path, payload, check=check)
        if mismatch is not None:
            mismatches.append(f"canary/{mode}/ok: {mismatch}")
    return mismatches


def freeze_expected_outputs(*, check: bool) -> list[str]:
    """Observe synthetic and real-canary scenarios through one snapshot path.

    Provenance semantics: ``source.commit`` records the revision that WROTE a
    snapshot. In check mode the frozen provenance is carried forward so that
    a later commit does not turn every snapshot into a false mismatch —
    staleness is surfaced by the non-failing ``source_revision_warnings``
    instead. Only a real regeneration (check=False) stamps a new revision.

    Write mode freezes the complete G1 inventory and ``expected/canary``;
    check mode regenerates and compares the same two families.
    """
    stamped_commit = None if check else _git_revision()
    return [
        *_process_v1_snapshots(check=check, stamped_commit=stamped_commit),
        *_process_canary_snapshots(check=check, stamped_commit=stamped_commit),
    ]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="regenerate normalized expectations in isolation and compare only",
    )
    parser.add_argument(
        "--rebuild-inputs",
        action="store_true",
        help="rebuild static inputs before freezing normalized expectations",
    )
    parser.add_argument("--oracle-worker", nargs=3, metavar=("MODE", "OUTCOME", "ROOT"), help=argparse.SUPPRESS)
    parser.add_argument("--canary", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--ignore-errors", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--provenance-root",
        type=Path,
        default=None,
        help=(
            "test support: run ONLY the provenance hygiene gate against this "
            "expected-snapshot root and exit (no observation, no drift check)"
        ),
    )
    return parser.parse_args()


def main() -> int:  # noqa: PLR0911
    """Run fixture generation or deterministic comparison."""
    args = _parse_args()
    if args.oracle_worker is not None:
        mode, outcome, root = args.oracle_worker
        return _run_oracle_worker(
            mode,
            outcome,
            Path(root),
            canary=args.canary,
            ignore_errors=args.ignore_errors,
        )
    if args.provenance_root is not None:
        provenance_errors = source_revision_errors(root=args.provenance_root)
        if provenance_errors:
            print("\n".join(provenance_errors), file=sys.stderr)  # noqa: T201
            return 1
        print("provenance ok")  # noqa: T201
        return 0
    if args.check:
        provenance_errors = [
            *source_revision_errors(),
            *source_revision_errors(root=CANARY_EXPECTED_ROOT),
        ]
        if provenance_errors:
            print("\n".join(provenance_errors), file=sys.stderr)  # noqa: T201
            return 1
        for root in (EXPECTED_ROOT, CANARY_EXPECTED_ROOT):
            for warning in source_revision_warnings(root=root):
                print(warning, file=sys.stderr)  # noqa: T201
        input_mismatches, xlsx_note = check_static_input_drift()
        print(xlsx_note)  # noqa: T201
        mismatches = [*input_mismatches, *freeze_expected_outputs(check=True)]
        if mismatches:
            print("\n".join(mismatches), file=sys.stderr)  # noqa: T201
            return 1
        print("all normalized v1 snapshots match frozen expectations")  # noqa: T201
        return 0
    _require_write_tree_hygiene()
    manifest = build_static_inputs() if args.rebuild_inputs else None
    freeze_expected_outputs(check=False)
    message = (
        f"built inputs and froze v1 outputs for {', '.join(sorted(manifest))}"
        if manifest is not None
        else "froze v1 outputs (static inputs unchanged)"
    )
    print(message)  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
