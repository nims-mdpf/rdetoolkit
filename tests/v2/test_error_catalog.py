"""Tests for rdetoolkit v2 unified error catalog (Session A1).

Written before implementation (TDD Red phase).
Target: make all tests pass after Session A1 implementation.
Authority: local/develop/v2/Design.md §9, decisions_pre_A1.md.

Coverage:
  A1.2 ERROR_CATALOG structure, code uniqueness, band alignment
  A1.4 RdeError v2 hierarchy (int code + name attr, __cause__ chain, call_id)
  A1.6 E001-E025 / E_CYCLE deprecated but still importable
  A1.7 errors.pyi restored declarations (StorageDir, CompactTraceFormatter,
        get_traceback_settings_from_env)
  A1.8 scripts/gen_error_docs.py exists and exits 0 under --check
  decisions_pre_A1.md Ruling 4: 1xxx code reserved for run() mutual-exclusion

All imports of not-yet-implemented names are inside test function bodies so
the module collects cleanly. Tests fail on ImportError or AttributeError —
never on SyntaxError or fixture misconfiguration.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# A1.2 — ERROR_CATALOG structure
# ---------------------------------------------------------------------------


class TestErrorCatalogStructure:
    """ERROR_CATALOG is dict[int, ErrorDef] with unique keys and band-aligned codes."""

    def test_error_catalog_is_importable(self) -> None:
        """ERROR_CATALOG must be importable from rdetoolkit.errors."""
        from rdetoolkit.errors import ERROR_CATALOG  # noqa: F401

    def test_error_def_is_importable(self) -> None:
        """ErrorDef type must be importable from rdetoolkit.errors."""
        from rdetoolkit.errors import ErrorDef  # noqa: F401

    def test_error_catalog_is_dict(self) -> None:
        """ERROR_CATALOG must be a dict instance."""
        from rdetoolkit.errors import ERROR_CATALOG

        assert isinstance(ERROR_CATALOG, dict)

    def test_error_catalog_keys_are_ints(self) -> None:
        """Every key in ERROR_CATALOG must be an int."""
        from rdetoolkit.errors import ERROR_CATALOG

        for key in ERROR_CATALOG:
            assert isinstance(key, int), f"Key {key!r} is not int"

    def test_error_catalog_codes_are_unique(self) -> None:
        """ERROR_CATALOG must have no duplicate int keys."""
        from rdetoolkit.errors import ERROR_CATALOG

        keys = list(ERROR_CATALOG.keys())
        assert len(keys) == len(set(keys)), "Duplicate int codes found in ERROR_CATALOG"

    def test_errordef_has_name_field(self) -> None:
        """Each ErrorDef value must have a 'name' field."""
        from rdetoolkit.errors import ERROR_CATALOG

        for code, defn in ERROR_CATALOG.items():
            assert hasattr(defn, "name"), f"ErrorDef for code {code} missing 'name'"

    def test_errordef_has_message_template_field(self) -> None:
        """Each ErrorDef value must have a 'message_template' field."""
        from rdetoolkit.errors import ERROR_CATALOG

        for code, defn in ERROR_CATALOG.items():
            assert hasattr(defn, "message_template"), (
                f"ErrorDef for code {code} missing 'message_template'"
            )

    def test_errordef_name_is_nonempty_string(self) -> None:
        """Each ErrorDef.name must be a non-empty string."""
        from rdetoolkit.errors import ERROR_CATALOG

        for code, defn in ERROR_CATALOG.items():
            assert isinstance(defn.name, str), f"code {code}: name is not str"
            assert defn.name, f"code {code}: name is empty"

    def test_error_catalog_is_not_empty(self) -> None:
        """ERROR_CATALOG must contain at least one entry."""
        from rdetoolkit.errors import ERROR_CATALOG

        assert len(ERROR_CATALOG) > 0


# ---------------------------------------------------------------------------
# A1.2 — Band membership
# ---------------------------------------------------------------------------


class TestErrorBandMembership:
    """Band constraints: 1xxx config, 2xxx registry, 3xxx execution, 4xxx validation, 5xxx internal."""

    def test_1xxx_band_contains_at_least_one_code(self) -> None:
        """ERROR_CATALOG must have at least one code in the 1xxx (config) band."""
        from rdetoolkit.errors import ERROR_CATALOG

        codes_1xxx = [c for c in ERROR_CATALOG if 1000 <= c <= 1999]
        assert codes_1xxx, "No 1xxx-band code found in ERROR_CATALOG"

    def test_2xxx_band_contains_at_least_one_code(self) -> None:
        """ERROR_CATALOG must have at least one code in the 2xxx (registry) band."""
        from rdetoolkit.errors import ERROR_CATALOG

        codes_2xxx = [c for c in ERROR_CATALOG if 2000 <= c <= 2999]
        assert codes_2xxx, "No 2xxx-band code found in ERROR_CATALOG"

    def test_3xxx_band_contains_at_least_one_code(self) -> None:
        """ERROR_CATALOG must have at least one code in the 3xxx (execution) band."""
        from rdetoolkit.errors import ERROR_CATALOG

        codes_3xxx = [c for c in ERROR_CATALOG if 3000 <= c <= 3999]
        assert codes_3xxx, "No 3xxx-band code found in ERROR_CATALOG"

    def test_4xxx_band_contains_at_least_one_code(self) -> None:
        """ERROR_CATALOG must have at least one code in the 4xxx (validation) band."""
        from rdetoolkit.errors import ERROR_CATALOG

        codes_4xxx = [c for c in ERROR_CATALOG if 4000 <= c <= 4999]
        assert codes_4xxx, "No 4xxx-band code found in ERROR_CATALOG"

    def test_5xxx_band_contains_at_least_one_code(self) -> None:
        """ERROR_CATALOG must have at least one code in the 5xxx (internal) band."""
        from rdetoolkit.errors import ERROR_CATALOG

        codes_5xxx = [c for c in ERROR_CATALOG if 5000 <= c <= 5999]
        assert codes_5xxx, "No 5xxx-band code found in ERROR_CATALOG"

    def test_duplicate_node_id_code_is_in_2xxx_band(self) -> None:
        """DuplicateNodeId error (E2001) must be registered in the 2xxx band."""
        from rdetoolkit.errors import ERROR_CATALOG

        # Design §9 names DuplicateNodeId as a registry error
        codes_2xxx = {c for c in ERROR_CATALOG if 2000 <= c <= 2999}
        names_2xxx = {ERROR_CATALOG[c].name for c in codes_2xxx}
        assert any("DuplicateNodeId" in n or "duplicate" in n.lower() for n in names_2xxx), (
            "DuplicateNodeId / 2xxx code not found in ERROR_CATALOG"
        )

    def test_node_execution_failed_code_is_in_3xxx_band(self) -> None:
        """NodeExecutionFailed error must be registered in the 3xxx band."""
        from rdetoolkit.errors import ERROR_CATALOG

        codes_3xxx = {c for c in ERROR_CATALOG if 3000 <= c <= 3999}
        names_3xxx = {ERROR_CATALOG[c].name for c in codes_3xxx}
        assert any("ExecutionFailed" in n or "execution" in n.lower() for n in names_3xxx), (
            "NodeExecutionFailed / 3xxx code not found in ERROR_CATALOG"
        )

    def test_warning_catalog_has_w1001_mode_override_warning(self) -> None:
        """WARNING_CATALOG must contain W1001 (ModeOverriddenByFileDetection)."""
        from rdetoolkit.errors import WARNING_CATALOG

        assert 1001 in WARNING_CATALOG, (
            "W1001 (ModeOverriddenByFileDetection) not found in WARNING_CATALOG"
        )

    def test_no_catalog_code_outside_valid_bands(self) -> None:
        """All ERROR_CATALOG keys must be in the defined bands 1xxx-5xxx."""
        from rdetoolkit.errors import ERROR_CATALOG

        for code in ERROR_CATALOG:
            assert 1000 <= code <= 5999, (
                f"Code {code} falls outside the reserved bands 1xxx-5xxx"
            )


# ---------------------------------------------------------------------------
# decisions_pre_A1.md Ruling 4 — reserved 1xxx usage-error code for run()
# ---------------------------------------------------------------------------


class TestReservedUsageErrorCode:
    """A 1xxx code is reserved for run(flow=..., custom_dataset_function=...) mutual-exclusion."""

    def test_run_mutual_exclusion_error_code_exists_in_catalog(self) -> None:
        """A 1xxx code for run(flow=...) exclusivity must exist in ERROR_CATALOG."""
        from rdetoolkit.errors import ERROR_CATALOG

        # The code must sit in 1xxx (usage/config error band)
        codes_1xxx = {c: ERROR_CATALOG[c] for c in ERROR_CATALOG if 1000 <= c <= 1999}
        assert codes_1xxx, "No 1xxx code found; run() mutual-exclusion code not reserved"

    def test_run_mutual_exclusion_code_name_signals_exclusivity(self) -> None:
        """The reserved 1xxx run() code name must convey mutual-exclusion or usage-error intent."""
        from rdetoolkit.errors import ERROR_CATALOG

        codes_1xxx = {c: ERROR_CATALOG[c] for c in ERROR_CATALOG if 1000 <= c <= 1999}
        # At least one 1xxx entry should reference flow, run, or mutual exclusion
        found = any(
            any(kw in defn.name.lower() for kw in ("flow", "run", "exclusive", "mutual", "usage", "config"))
            for defn in codes_1xxx.values()
        )
        assert found, (
            "No 1xxx code with flow/run/usage semantics found — "
            "run() mutual-exclusion code (decisions_pre_A1.md Ruling 4) is missing"
        )


# ---------------------------------------------------------------------------
# A1.4 — RdeError v2 hierarchy: int code, name attr, subclass relations
# ---------------------------------------------------------------------------


class TestRdeErrorHierarchyV2:
    """Design §9.2: RdeError carries code: int and name: str; subclasses are band-specific."""

    def test_rde_error_has_name_attribute_of_type_str(self) -> None:
        """New-style RdeError must expose a 'name' attribute (str)."""
        from rdetoolkit.errors import RdeError

        # New interface: code is int, name is str
        err = RdeError(code=1001, name="E1001", message="config error")
        assert hasattr(err, "name"), "RdeError is missing 'name' attribute"
        assert isinstance(err.name, str)

    def test_rde_error_code_is_int(self) -> None:
        """New-style RdeError.code must be int, not str."""
        from rdetoolkit.errors import RdeError

        err = RdeError(code=1001, name="E1001", message="config error")
        assert isinstance(err.code, int), f"RdeError.code is {type(err.code)!r}, expected int"

    def test_rde_config_error_is_subclass_of_rde_error(self) -> None:
        """RdeConfigError must be a subclass of RdeError (Design §9.2)."""
        from rdetoolkit.errors import RdeConfigError, RdeError

        assert issubclass(RdeConfigError, RdeError)

    def test_rde_config_error_carries_int_code_and_name(self) -> None:
        """RdeConfigError must accept int code and name kwarg per Design §9.2."""
        from rdetoolkit.errors import RdeConfigError

        err = RdeConfigError(code=1001, name="E1001", message="config load failed")
        assert err.code == 1001
        assert err.name == "E1001"

    def test_rde_registry_error_is_importable(self) -> None:
        """RdeRegistryError must be importable from rdetoolkit.errors (Design §9.2)."""
        from rdetoolkit.errors import RdeRegistryError  # noqa: F401

    def test_rde_registry_error_is_subclass_of_rde_error(self) -> None:
        """RdeRegistryError must be a subclass of RdeError."""
        from rdetoolkit.errors import RdeError, RdeRegistryError

        assert issubclass(RdeRegistryError, RdeError)

    def test_rde_registry_error_carries_int_code_in_2xxx_band(self) -> None:
        """RdeRegistryError instantiated with 2xxx code must carry that int code."""
        from rdetoolkit.errors import RdeRegistryError

        err = RdeRegistryError(code=2001, name="E2001", message="duplicate node id")
        assert isinstance(err.code, int)
        assert 2000 <= err.code <= 2999

    def test_rde_execution_error_carries_call_id(self) -> None:
        """RdeExecutionError must accept and expose a call_id attribute."""
        from rdetoolkit.errors import RdeExecutionError

        err = RdeExecutionError(code=3001, name="E3001", message="node failed", call_id="my_node#1")
        assert hasattr(err, "call_id"), "RdeExecutionError missing call_id"
        assert err.call_id == "my_node#1"

    def test_rde_execution_error_preserves_cause_chain(self) -> None:
        """RdeExecutionError must preserve __cause__ when raised with 'raise ... from ...'."""
        from rdetoolkit.errors import RdeExecutionError

        original = ValueError("user code error")
        with pytest.raises(RdeExecutionError) as exc_info:
            try:
                raise original
            except ValueError as e:
                err = RdeExecutionError(code=3001, name="E3001", message="node failed", call_id="fn#1")
                raise err from e

        assert exc_info.value.__cause__ is original

    @pytest.mark.parametrize("exc_class,code,name", [
        ("RdeExecutionError", 3001, "E3001"),
    ])
    def test_rde_execution_error_cause_is_preserved_in_pytest_raises(
        self, exc_class: str, code: int, name: str,
    ) -> None:
        """__cause__ is set when using 'raise RdeExecutionError(...) from original'."""
        from rdetoolkit.errors import RdeExecutionError

        original = RuntimeError("upstream failure")
        with pytest.raises(RdeExecutionError) as exc_info:
            try:
                raise original
            except RuntimeError as e:
                raise RdeExecutionError(code=code, name=name, message="wrapped", call_id="node#1") from e

        assert exc_info.value.__cause__ is original, (
            "__cause__ chain not preserved in RdeExecutionError"
        )

    def test_rde_validation_error_is_importable(self) -> None:
        """RdeValidationError must be importable from rdetoolkit.errors (Design §9.2)."""
        from rdetoolkit.errors import RdeValidationError  # noqa: F401

    def test_rde_validation_error_is_subclass_of_rde_error(self) -> None:
        """RdeValidationError must be a subclass of RdeError."""
        from rdetoolkit.errors import RdeError, RdeValidationError

        assert issubclass(RdeValidationError, RdeError)

    def test_rde_validation_error_carries_int_code_in_4xxx_band(self) -> None:
        """RdeValidationError instantiated with 4xxx code must carry that int code."""
        from rdetoolkit.errors import RdeValidationError

        err = RdeValidationError(code=4001, name="E4001", message="invoice schema invalid")
        assert isinstance(err.code, int)
        assert 4000 <= err.code <= 4999

    def test_rde_internal_error_is_importable(self) -> None:
        """RdeInternalError must be importable from rdetoolkit.errors (Design §9.2)."""
        from rdetoolkit.errors import RdeInternalError  # noqa: F401

    def test_rde_internal_error_is_subclass_of_rde_error(self) -> None:
        """RdeInternalError must be a subclass of RdeError."""
        from rdetoolkit.errors import RdeError, RdeInternalError

        assert issubclass(RdeInternalError, RdeError)

    def test_rde_internal_error_carries_int_code_in_5xxx_band(self) -> None:
        """RdeInternalError instantiated with 5xxx code must carry that int code."""
        from rdetoolkit.errors import RdeInternalError

        err = RdeInternalError(code=5001, name="E5001", message="internal assertion failed")
        assert isinstance(err.code, int)
        assert 5000 <= err.code <= 5999

    def test_all_hierarchy_subclasses_are_exception_subclasses(self) -> None:
        """Every new-style RdeError subclass must be catchable as Exception."""
        from rdetoolkit.errors import (
            RdeConfigError,
            RdeExecutionError,
            RdeInternalError,
            RdeRegistryError,
            RdeValidationError,
        )

        for cls in (RdeConfigError, RdeRegistryError, RdeExecutionError, RdeValidationError, RdeInternalError):
            assert issubclass(cls, Exception), f"{cls.__name__} is not an Exception subclass"


# ---------------------------------------------------------------------------
# A1.6 — Deprecated identifiers: E001-E025 and E_CYCLE still importable
# ---------------------------------------------------------------------------


class TestV1DeprecatedIdentifiers:
    """E001-E025 and E_CYCLE remain importable (v1 compat) but are marked deprecated."""

    def test_error_code_e001_is_still_importable(self) -> None:
        """ErrorCode.E001 must still be importable after deprecation marking (append-only)."""
        from rdetoolkit.errors import ErrorCode

        assert hasattr(ErrorCode, "E001")

    def test_error_code_e025_is_still_importable(self) -> None:
        """ErrorCode.E025 must still be importable — last of the deprecated range."""
        from rdetoolkit.errors import ErrorCode

        assert hasattr(ErrorCode, "E025")

    def test_all_e001_to_e025_codes_still_present(self) -> None:
        """All 25 deprecated ErrorCode members E001-E025 must still be accessible."""
        from rdetoolkit.errors import ErrorCode

        for i in range(1, 26):
            name = f"E{i:03d}"
            assert hasattr(ErrorCode, name), f"ErrorCode.{name} missing after deprecation"

    def test_e_cycle_is_importable_as_deprecated_symbol(self) -> None:
        """E_CYCLE must be importable from rdetoolkit.errors (廃番だが削除しない)."""
        from rdetoolkit.errors import E_CYCLE  # noqa: F401

    def test_error_code_class_docstring_mentions_deprecation(self) -> None:
        """ErrorCode class docstring must mention '廃番' (Design §9, A1.6)."""
        from rdetoolkit.errors import ErrorCode

        doc = ErrorCode.__doc__ or ""
        assert "廃番" in doc or "deprecated" in doc.lower(), (
            "ErrorCode class docstring does not mention deprecation (廃番 / deprecated)"
        )


# ---------------------------------------------------------------------------
# A1.7 — errors.pyi: restore StorageDir, CompactTraceFormatter,
#                    get_traceback_settings_from_env
# ---------------------------------------------------------------------------


class TestErrorsPyiRestoredDeclarations:
    """Three declarations lost from errors.pyi must be importable from rdetoolkit.errors."""

    def test_storage_dir_importable_from_rdetoolkit_errors(self) -> None:
        """StorageDir must be importable from rdetoolkit.errors (errors.pyi restoration)."""
        from rdetoolkit.errors import StorageDir  # noqa: F401

    def test_compact_trace_formatter_importable_from_rdetoolkit_errors(self) -> None:
        """CompactTraceFormatter must be importable from rdetoolkit.errors (errors.pyi restoration)."""
        from rdetoolkit.errors import CompactTraceFormatter  # noqa: F401

    def test_get_traceback_settings_from_env_importable_from_rdetoolkit_errors(self) -> None:
        """get_traceback_settings_from_env must be importable from rdetoolkit.errors."""
        from rdetoolkit.errors import get_traceback_settings_from_env  # noqa: F401

    def test_storage_dir_is_callable_from_errors(self) -> None:
        """StorageDir imported via rdetoolkit.errors must be callable (type or function)."""
        from rdetoolkit.errors import StorageDir

        assert callable(StorageDir)

    def test_get_traceback_settings_from_env_is_callable_from_errors(self) -> None:
        """get_traceback_settings_from_env imported via rdetoolkit.errors must be callable."""
        from rdetoolkit.errors import get_traceback_settings_from_env

        assert callable(get_traceback_settings_from_env)


# ---------------------------------------------------------------------------
# A1.8 — scripts/gen_error_docs.py --check passes (catalog → docs consistency)
# ---------------------------------------------------------------------------


class TestCatalogDocConsistency:
    """scripts/gen_error_docs.py --check must exist and pass once ERROR_CATALOG is built."""

    def test_gen_error_docs_script_file_exists(self) -> None:
        """scripts/gen_error_docs.py must exist in the repository root."""
        # Resolve relative to this test file: tests/v2/ → repo_root/scripts/
        repo_root = Path(__file__).parent.parent.parent
        script = repo_root / "scripts" / "gen_error_docs.py"
        assert script.exists(), f"Expected {script} to exist (A1.8)"

    def test_gen_error_docs_check_exits_zero(self) -> None:
        """Python scripts/gen_error_docs.py --check must exit 0 (docs match catalog)."""
        repo_root = Path(__file__).parent.parent.parent
        script = repo_root / "scripts" / "gen_error_docs.py"

        result = subprocess.run(
            [sys.executable, str(script), "--check"],
            check=False, capture_output=True,
            text=True,
            cwd=str(repo_root),
        )
        assert result.returncode == 0, (
            f"gen_error_docs.py --check exited {result.returncode}:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


class TestV21CatalogRevisions:
    """Design v2.1 A' retrofit pins (R1 / R9, applied in Session R)."""

    def test_every_error_def_has_nonempty_remediation(self) -> None:
        """R9: remediation is required and never empty on every catalog entry."""
        from rdetoolkit.errors import ERROR_CATALOG

        for code, entry in ERROR_CATALOG.items():
            assert entry.remediation.strip(), f"E{code} has empty remediation"

    def test_reserved_param_mismatch_2002_is_retired(self) -> None:
        """R1: name-based DI mismatch is retired; the number is pinned, not reused."""
        from rdetoolkit.errors import ERROR_CATALOG

        entry = ERROR_CATALOG[2002]
        assert entry.retired is True
        assert entry.name == "ReservedParamMismatch"

    def test_retired_numbers_keep_their_original_names(self) -> None:
        """Retired numbers must never be reassigned to a different meaning."""
        from rdetoolkit.errors import ERROR_CATALOG

        RETIRED = {2002: "ReservedParamMismatch"}
        for code, name in RETIRED.items():
            assert ERROR_CATALOG[code].retired is True
            assert ERROR_CATALOG[code].name == name

    def test_non_retired_entries_are_active(self) -> None:
        """Only documented retirements carry retired=True."""
        from rdetoolkit.errors import ERROR_CATALOG

        retired = {code for code, e in ERROR_CATALOG.items() if e.retired}
        assert retired == {2002}

    def test_duplicate_reserved_type_annotation_2006_exists(self) -> None:
        """R1: E2006 replaces name-based mismatch for real ambiguity."""
        from rdetoolkit.errors import ERROR_CATALOG

        assert ERROR_CATALOG[2006].name == "DuplicateReservedTypeAnnotation"
        assert ERROR_CATALOG[2006].retired is False

    def test_template_error_codes_2101_to_2105_are_reserved(self) -> None:
        """R6: template error numbers are defined now, raised from Phase F."""
        from rdetoolkit.errors import ERROR_CATALOG

        expected = {
            2101: "TemplateSlotMissing",
            2102: "TemplateSlotSignatureMismatch",
            2103: "TemplateFinalOverride",
            2104: "TemplateDeepInheritance",
            2105: "TemplateCtorNotDefault",
        }
        for code, name in expected.items():
            assert ERROR_CATALOG[code].name == name


class TestUnstableNodeIdCatalogEntry:
    """Session C1 (Design v2.1 §3.2): catalog entry 2005, UnstableNodeId.

    2005 is a lint-style, non-eager detection (Registry.find_unstable_node_ids)
    for node ids whose `__qualname__` contains "<locals>" — it must never be
    raised automatically at @node decoration time (see
    local/develop/v2/tasks/session_c1.md Conflict #1). 2004 stays permanently
    unassigned (R1); this session must not touch it.
    """

    def test_unstable_node_id_name__tc_err_c1_001(self) -> None:
        """TC-ERR-C1-001: ERROR_CATALOG[2005].name == "UnstableNodeId"."""
        from rdetoolkit.errors import ERROR_CATALOG

        assert ERROR_CATALOG[2005].name == "UnstableNodeId"

    def test_unstable_node_id_not_retired__tc_err_c1_002(self) -> None:
        """TC-ERR-C1-002: ERROR_CATALOG[2005].retired is False."""
        from rdetoolkit.errors import ERROR_CATALOG

        assert ERROR_CATALOG[2005].retired is False

    def test_unstable_node_id_remediation_nonempty__tc_err_c1_003(self) -> None:
        """TC-ERR-C1-003: ERROR_CATALOG[2005].remediation is non-empty (R9)."""
        from rdetoolkit.errors import ERROR_CATALOG

        assert ERROR_CATALOG[2005].remediation.strip() != ""

    def test_retired_set_unchanged_after_2005_addition__tc_err_c1_004(self) -> None:
        """TC-ERR-C1-004: adding 2005 must not change the retired-code set —
        it must remain exactly {2002} (regression guard on top of the
        existing test_non_retired_entries_are_active).
        """
        from rdetoolkit.errors import ERROR_CATALOG

        retired = {code for code, entry in ERROR_CATALOG.items() if entry.retired}
        assert retired == {2002}

    def test_2004_remains_unassigned__tc_err_c1_005(self) -> None:
        """Guard: 2004 (permanently retired number, R1) must stay absent from
        the catalog — it must never be reused for UnstableNodeId or anything
        else.
        """
        from rdetoolkit.errors import ERROR_CATALOG

        assert 2004 not in ERROR_CATALOG


# ---------------------------------------------------------------------------
# Session D2 — E2201-E2299 band reservation (Conflict #2, Ruling-2-recommended,
# non-blocking: PhaseD_prompts.md's D2 goal contract allows this addition to
# be dropped after one failed attempt if it proves disruptive).
# ---------------------------------------------------------------------------


class TestRdetoolkitNbBandReservation:
    """TC-ERR-2201/2208/2211/2212: 4 drafted rdetoolkit-nb entries exist as
    full ErrorDef entries (name/message_template/remediation), mirroring the
    2101-2105 "reserved here, raised from a future session" comment style
    (session_d2.md Conflict #2). Only these 4 codes are asserted -- the rest
    of the E2201-E2299 band is comment-only reservation, not catalog entries.
    """

    @pytest.mark.parametrize("code", [2201, 2208, 2211, 2212])
    def test_rdetoolkit_nb_entry_exists_with_nonempty_remediation__tc_err_2201_family(
        self,
        code: int,
    ) -> None:
        """TC-ERR-2201/2208/2211/2212: the entry exists and remediation is non-empty (R9)."""
        from rdetoolkit.errors import ERROR_CATALOG

        assert code in ERROR_CATALOG, f"{code} must be reserved as a full ErrorDef entry (Conflict #2)"
        entry = ERROR_CATALOG[code]
        assert entry.name.strip() != ""
        assert entry.message_template.strip() != ""
        assert entry.remediation.strip() != ""
        assert entry.retired is False

    def test_rest_of_band_not_individually_catalogued__tc_err_2201_family_scope(self) -> None:
        """The remaining ~95 codes in E2201-E2299 must NOT be catalogued yet
        (Conflict #2: only 4 codes have a documented basis; the rest stay a
        comment-only reservation until a future nb design session defines
        them).
        """
        from rdetoolkit.errors import ERROR_CATALOG

        reserved_but_undefined = set(range(2202, 2300)) - {2208, 2211, 2212}
        catalogued_prematurely = reserved_but_undefined & set(ERROR_CATALOG)
        assert catalogued_prematurely == set(), (
            f"codes catalogued without a documented basis: {sorted(catalogued_prematurely)}"
        )
