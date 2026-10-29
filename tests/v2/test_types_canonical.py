"""Canonical acceptance tests for rdetoolkit v2 reserved types — Session A2.

Written before implementation (TDD Red phase).
Target: make all tests pass in the codex-worker Green phase.

TC-TYPES-001..015 as inventoried in local/develop/v2/tasks/session_a2.md.
Authority: local/develop/v2/Design.md §4.2 and decisions_pre_A1.md §A2.

Compat anchors (expected to PASS already in Red phase):
    TC-TYPES-014 — OutputContext.rawfiles absent (never existed)
    TC-TYPES-015 — OutputContext.temp absent (never existed)
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helper — builds a valid v1 RdeOutputResourcePath for factory tests.
# Defined here so each test class can call it without duplication.
# Uses a local import to avoid module-level failures.
# ---------------------------------------------------------------------------


def _make_v1_paths(base: Path):  # type: ignore[return]  # no annotation avoids circular import
    """Return a minimal valid RdeOutputResourcePath rooted at *base*."""
    from rdetoolkit.models.rde2types import RdeOutputResourcePath  # noqa: PLC0415

    return RdeOutputResourcePath(
        raw=base / "raw",
        nonshared_raw=base / "nonshared_raw",
        rawfiles=(),
        struct=base / "struct",
        main_image=base / "main_image",
        other_image=base / "other_image",
        meta=base / "meta",
        thumbnail=base / "thumbnail",
        logs=base / "logs",
        invoice=base / "invoice",
        invoice_schema_json=base / "invoice" / "invoice.schema.json",
        invoice_org=base / "invoice" / "invoice.json",
        attachment=base / "attachment",
    )


# ---------------------------------------------------------------------------
# TC-TYPES-001: OutputContext canonical field set
# ---------------------------------------------------------------------------


class TestOutputContextCanonicalFields:
    """OutputContext must have exactly the 10 directories defined in Design §4.2."""

    def test_output_context_has_exactly_ten_directories__tc_types_001(self) -> None:
        """TC-TYPES-001: Field names match the 10-dir canonical set from Design §4.2."""
        from rdetoolkit.types import OutputContext  # noqa: PLC0415

        expected = {
            "struct",
            "meta",
            "main_image",
            "other_image",
            "thumbnail",
            "attachment",
            "nonshared_raw",
            "raw",
            "invoice",
            "logs",
        }
        actual = {f.name for f in dataclasses.fields(OutputContext)}
        assert actual == expected, (
            f"OutputContext field mismatch.\n"
            f"  Expected : {sorted(expected)}\n"
            f"  Got      : {sorted(actual)}\n"
            f"  Missing  : {sorted(expected - actual)}\n"
            f"  Extra    : {sorted(actual - expected)}"
        )


# ---------------------------------------------------------------------------
# TC-TYPES-002: from_resource_paths() factory
# ---------------------------------------------------------------------------


class TestOutputContextFactory:
    """The canonical public construction path for OutputContext is from_resource_paths()."""

    def test_from_resource_paths_exists_and_returns_output_context__tc_types_002(
        self, tmp_path: Path
    ) -> None:
        """TC-TYPES-002: from_resource_paths(v1_paths) exists and returns OutputContext."""
        from rdetoolkit.types import OutputContext  # noqa: PLC0415

        assert hasattr(OutputContext, "from_resource_paths"), (
            "OutputContext.from_resource_paths() classmethod must exist. "
            "Direct __init__ construction is the non-public path."
        )
        v1_paths = _make_v1_paths(tmp_path)
        ctx = OutputContext.from_resource_paths(v1_paths)
        assert isinstance(ctx, OutputContext)
        assert ctx.struct == tmp_path / "struct"
        assert ctx.raw == tmp_path / "raw"
        assert ctx.logs == tmp_path / "logs"
        assert ctx.attachment == tmp_path / "attachment"
        assert ctx.nonshared_raw == tmp_path / "nonshared_raw"
        assert ctx.invoice == tmp_path / "invoice"


# ---------------------------------------------------------------------------
# TC-TYPES-003: save_bytes() — canonical name (renamed from save_file)
# ---------------------------------------------------------------------------


class TestOutputContextSaveBytes:
    """OutputContext.save_bytes() writes bytes; the old save_file() name is retired."""

    def test_write_bytes_low_level_api_exists_and_writes__tc_types_003(
        self, tmp_path: Path
    ) -> None:
        """TC-TYPES-003 (v2.1 R3): write_bytes(kind, filename, content) writes bytes."""
        from rdetoolkit.types import OutputContext  # noqa: PLC0415

        assert hasattr(OutputContext, "write_bytes"), (
            "OutputContext must expose the low-level write_bytes(kind, filename, content)"
        )
        ctx = OutputContext.from_resource_paths(_make_v1_paths(tmp_path))
        result = ctx.write_bytes("struct", "output.bin", b"canonical bytes")
        assert result.exists(), "write_bytes() must write the file to disk"
        assert result.read_bytes() == b"canonical bytes"

    def test_path_for_resolves_kind_paths__tc_types_004(self, tmp_path: Path) -> None:
        """TC-TYPES-004 (v2.1 R3): path_for(kind, filename) resolves without writing."""
        from rdetoolkit.types import OutputContext  # noqa: PLC0415

        assert hasattr(OutputContext, "path_for")
        ctx = OutputContext.from_resource_paths(_make_v1_paths(tmp_path))
        dest = ctx.path_for("raw", "source_data.raw")
        assert dest == tmp_path / "raw" / "source_data.raw"
        assert not dest.exists()

    def test_save_file_does_not_exist_on_output_context__tc_types_005(self) -> None:
        """TC-TYPES-005: save_file() must NOT exist (renamed to save_bytes())."""
        from rdetoolkit.types import OutputContext  # noqa: PLC0415

        assert not hasattr(OutputContext, "save_file"), (
            "save_file() must be removed from OutputContext. "
            "It was renamed to save_bytes() for name-meaning alignment."
        )

    def test_save_raw_does_not_exist_on_output_context__tc_types_006(self) -> None:
        """TC-TYPES-006: save_raw() must NOT exist (renamed to copy_raw())."""
        from rdetoolkit.types import OutputContext  # noqa: PLC0415

        assert not hasattr(OutputContext, "save_raw"), (
            "save_raw() must be removed from OutputContext. "
            "It was renamed to copy_raw() for name-meaning alignment."
        )


# ---------------------------------------------------------------------------
# TC-TYPES-007/008: InputPaths.raw — the 4th field (Path | None, default None)
# ---------------------------------------------------------------------------


class TestInputPathsRawField:
    """InputPaths must have a raw: Path | None field with default None, plus
    rawfiles: tuple[Path, ...] (Decision D1-A, local/develop/v2/decisions_pre_D.md)."""

    def test_input_paths_has_raw_field_defaulting_to_none__tc_types_007(self) -> None:
        """TC-TYPES-007: InputPaths.raw exists with None default; total field count
        is 5 (updated per Decision D1-A: additive rawfiles: tuple[Path, ...] = ()
        field, decisions_pre_D.md — this replaces the prior 4-field pin, which
        predates D1's need to carry a tile's raw file tuple).

        UPDATED (Session K0-iii ruling #1): 6 fields -- the append-only
        ``smarttable_rawfile: Path | None = None`` carries the v1.7 SmartTable
        row CSV that ``rawfiles`` no longer holds (#503); its name and default
        are pinned here as well."""
        from rdetoolkit.types import InputPaths  # noqa: PLC0415

        field_names = {f.name for f in dataclasses.fields(InputPaths)}
        assert "raw" in field_names, (
            "InputPaths must have a raw: Path | None field per Design §4.2"
        )
        assert "rawfiles" in field_names, (
            "InputPaths must have a rawfiles: tuple[Path, ...] field per "
            "Decision D1-A (decisions_pre_D.md)"
        )
        assert "smarttable_rawfile" in field_names, (
            "InputPaths must have a smarttable_rawfile: Path | None field per "
            "Session K0-iii ruling #1 (v1.7 #503)"
        )
        assert [f.name for f in dataclasses.fields(InputPaths)] == [
            "inputdata",
            "invoice",
            "tasksupport",
            "raw",
            "rawfiles",
            "smarttable_rawfile",
        ], (
            f"InputPaths must have exactly 6 fields in append-only order, got "
            f"{len(dataclasses.fields(InputPaths))}: {field_names}"
        )
        # Omitting raw/rawfiles must work (defaults: None / ())
        paths = InputPaths(
            inputdata=Path("/data/inputdata"),
            invoice=Path("/data/invoice"),
            tasksupport=Path("/data/tasksupport"),
        )
        assert paths.raw is None
        assert paths.rawfiles == ()
        assert paths.smarttable_rawfile is None

    def test_input_paths_raw_accepts_path_value__tc_types_008(self) -> None:
        """TC-TYPES-008: InputPaths.raw can be set to a Path (non-None)."""
        from rdetoolkit.types import InputPaths  # noqa: PLC0415

        raw_path = Path("/data/raw_tiles")
        paths = InputPaths(
            inputdata=Path("/data/inputdata"),
            invoice=Path("/data/invoice"),
            tasksupport=Path("/data/tasksupport"),
            raw=raw_path,
        )
        assert paths.raw == raw_path


# ---------------------------------------------------------------------------
# TC-TYPES-009..012: Reserved mapping — canonical 5-key dict
# ---------------------------------------------------------------------------


class TestReservedMapping:
    """get_reserved_mapping() must return the canonical 5-key mapping from Design §4.1."""

    def test_reserved_mapping_has_exactly_five_keys__tc_types_009(self) -> None:
        """TC-TYPES-009: Key set == {"paths","out","config","invoice","iteration"}."""
        from rdetoolkit.core.context import get_reserved_mapping  # noqa: PLC0415

        mapping = get_reserved_mapping()
        expected_keys = {"paths", "out", "config", "invoice", "iteration"}
        assert set(mapping.keys()) == expected_keys, (
            f"Reserved mapping key mismatch.\n"
            f"  Expected : {sorted(expected_keys)}\n"
            f"  Got      : {sorted(mapping.keys())}\n"
            f"  Missing  : {sorted(expected_keys - set(mapping.keys()))}\n"
            f"  Extra    : {sorted(set(mapping.keys()) - expected_keys)}"
        )

    def test_reserved_mapping_does_not_contain_deprecated_output_key__tc_types_010(
        self,
    ) -> None:
        """TC-TYPES-010: 'output' must not appear — replaced by 'out' per Design §4.1."""
        from rdetoolkit.core.context import get_reserved_mapping  # noqa: PLC0415

        mapping = get_reserved_mapping()
        assert "output" not in mapping, (
            "Key 'output' must be replaced by 'out' in the reserved mapping. "
            "The old name 'output' was the source of the B7 divergence."
        )

    def test_reserved_mapping_does_not_contain_context_key__tc_types_011(self) -> None:
        """TC-TYPES-011: 'context' must not appear — it is not one of the 5 reserved names."""
        from rdetoolkit.core.context import get_reserved_mapping  # noqa: PLC0415

        mapping = get_reserved_mapping()
        assert "context" not in mapping, (
            "Key 'context' (RunContext itself) must be removed from reserved mapping. "
            "RunContext is not a user-injectable parameter — only the 5 named types are."
        )

    def test_reserved_mapping_types_for_paths_out_config__tc_types_012(self) -> None:
        """TC-TYPES-012: paths→InputPaths, out→OutputContext, config→RdeConfig."""
        from rdetoolkit.core.context import get_reserved_mapping  # noqa: PLC0415
        from rdetoolkit.types import InputPaths, OutputContext  # noqa: PLC0415

        mapping = get_reserved_mapping()

        assert mapping.get("paths") is InputPaths, (
            f"'paths' must map to InputPaths, got {mapping.get('paths')}"
        )
        assert mapping.get("out") is OutputContext, (
            f"'out' must map to OutputContext, got {mapping.get('out')}"
        )
        config_type = mapping.get("config")
        assert config_type is not None, (
            "'config' key must be present with a type value in the reserved mapping"
        )
        assert config_type.__name__ == "RdeConfig", (
            f"'config' must map to RdeConfig, got {config_type!r}"
        )


# ---------------------------------------------------------------------------
# TC-TYPES-013: RunContext.config slot
# ---------------------------------------------------------------------------


class TestRunContextConfigSlot:
    """RunContext must carry a config slot for RdeConfig per Design §4.1."""

    def test_run_context_has_config_slot__tc_types_013(self) -> None:
        """TC-TYPES-013: 'config' appears in RunContext.__slots__."""
        from rdetoolkit.core.context import RunContext  # noqa: PLC0415

        assert "config" in RunContext.__slots__, (
            f"RunContext must have a 'config' slot. "
            f"Current slots: {RunContext.__slots__}"
        )


# ---------------------------------------------------------------------------
# TC-TYPES-014/015: Documented exclusions from v1 RdeOutputResourcePath
# These are compat anchors — expected to PASS already in Red phase.
# ---------------------------------------------------------------------------


class TestOutputContextDocumentedExclusions:
    """Excluded v1 fields must NOT appear on OutputContext (Design §4.2 + decisions §A2)."""

    def test_rawfiles_is_not_a_field_of_output_context__tc_types_014(self) -> None:
        """TC-TYPES-014 (anchor): rawfiles excluded — it is an input concept, not an output dir.

        Per decisions_pre_A1.md §A2: rawfiles is a tuple[Path,...] of input file references.
        v2 models this via InputPaths or IterationInfo, not OutputContext.
        """
        from rdetoolkit.types import OutputContext  # noqa: PLC0415

        assert not hasattr(OutputContext, "rawfiles"), (
            "OutputContext must NOT have 'rawfiles'. "
            "It is an input-side concept handled by InputPaths / IterationInfo."
        )

    def test_temp_is_not_a_field_of_output_context__tc_types_015(self) -> None:
        """TC-TYPES-015 (anchor): temp excluded — not in the canonical 10 dirs.

        Per decisions_pre_A1.md §A2: the 'temp' directory is not part of Design §4.2's
        10-dir canonical set. v2 users use the standard library tempfile module instead.
        """
        from rdetoolkit.types import OutputContext  # noqa: PLC0415

        assert not hasattr(OutputContext, "temp"), (
            "OutputContext must NOT have 'temp'. "
            "Not in the canonical 10 dirs; use the standard tempfile module."
        )


class TestFactoryOnlyConstruction:
    """Design §4.2: OutputContext is factory-only (PR #501 review follow-up)."""

    def test_direct_construction_is_rejected(self, tmp_path) -> None:
        """OutputContext(...) without the factory must raise TypeError."""
        from pathlib import Path

        from rdetoolkit.types import OutputContext

        kwargs = {
            name: tmp_path / name
            for name in (
                "struct", "meta", "main_image", "other_image", "thumbnail",
                "raw", "logs", "attachment", "nonshared_raw", "invoice",
            )
        }
        with pytest.raises(TypeError, match="from_resource_paths"):
            OutputContext(**kwargs)

    def test_all_ten_fields_are_required(self) -> None:
        """No field may fall back to a relative default path."""
        import dataclasses

        from rdetoolkit.types import OutputContext

        for f in dataclasses.fields(OutputContext):
            assert f.default is dataclasses.MISSING, (
                f"OutputContext.{f.name} must not have a default"
            )


class TestFilenameTraversalGuard:
    """Artifact filenames must be simple basenames (PR #501 review follow-up)."""

    @pytest.mark.parametrize(
        "bad_name",
        ["../escape.csv", "sub/dir.csv", "/abs.csv", "..", "", "a\\b.csv"],
    )
    def test_write_bytes_rejects_path_components(self, tmp_path, bad_name) -> None:
        from types import SimpleNamespace

        from rdetoolkit.types import OutputContext

        ctx = OutputContext.from_resource_paths(
            SimpleNamespace(**{
                name: tmp_path / name
                for name in (
                    "struct", "meta", "main_image", "other_image", "thumbnail",
                    "raw", "logs", "attachment", "nonshared_raw", "invoice",
                )
            })
        )
        with pytest.raises(ValueError, match="basename"):
            ctx.write_bytes("struct", bad_name, b"x")


class TestCanonicalReExports:
    """Design §4.1.1: rdetoolkit.types is the single schema entry point."""

    def test_run_context_event_run_report_importable_from_types(self) -> None:
        from rdetoolkit.types import Event, EventSink, RunContext, RunReport  # noqa: F401

        assert RunContext is not None
        assert Event is not None
        assert EventSink is not None
        assert RunReport is not None


class TestV21ConfigModel:
    """Design v2.1 R2/R9 config retrofit pins (Session R)."""

    def test_rdeconfig_rejects_policy_section(self) -> None:
        """R9: the policy section (node_enforcement era) no longer exists."""
        import pydantic

        from rdetoolkit.types import RdeConfig

        with pytest.raises(pydantic.ValidationError):
            RdeConfig(policy={"node_enforcement": "strict"})

    def test_rdeconfig_rejects_lineage_keys_in_provenance(self) -> None:
        """R2/ADR-022: lineage settings do not exist in v2.0."""
        import pydantic

        from rdetoolkit.types import RdeConfig

        with pytest.raises(pydantic.ValidationError):
            RdeConfig(provenance={"lineage": "on"})

    def test_recording_settings_defaults(self) -> None:
        """provenance section is V2RecordingSettings: repr_head on, 80 chars."""
        from rdetoolkit.types import RdeConfig

        cfg = RdeConfig()
        assert cfg.provenance.repr_head == "on"
        assert cfg.provenance.repr_head_len == 80

    def test_recording_settings_rejects_unknown_keys(self) -> None:
        import pydantic

        from rdetoolkit.types import RdeConfig

        with pytest.raises(pydantic.ValidationError):
            RdeConfig(provenance={"edge_confidence": True})


class TestR3DomainSaveMethodsRemoved:
    """Design v2.1 R3: domain save methods live in builtin nodes, not OutputContext."""

    @pytest.mark.parametrize(
        "method",
        ["save_csv", "save_meta", "save_graph", "save_bytes",
         "save_thumbnail", "save_main_image", "copy_raw"],
    )
    def test_domain_save_method_absent(self, method: str) -> None:
        from rdetoolkit.types import OutputContext

        assert not hasattr(OutputContext, method), (
            f"R3: OutputContext.{method} must be removed (canonical API is rdetoolkit.nodes)"
        )


class TestOnIterationErrorSetting:
    """PR #504 review: Design §7.2 execution.on_iteration_error is part of the config contract."""

    def test_default_is_continue(self) -> None:
        from rdetoolkit.types import RdeConfig

        assert RdeConfig().execution.on_iteration_error == "continue"

    def test_accepts_fail_fast(self) -> None:
        from rdetoolkit.types import RdeConfig

        cfg = RdeConfig(execution={"on_iteration_error": "fail_fast"})
        assert cfg.execution.on_iteration_error == "fail_fast"

    def test_rejects_unknown_value(self) -> None:
        import pydantic

        from rdetoolkit.types import RdeConfig

        with pytest.raises(pydantic.ValidationError):
            RdeConfig(execution={"on_iteration_error": "abort"})
