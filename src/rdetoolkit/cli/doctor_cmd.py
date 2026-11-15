"""``rdetoolkit doctor``: read-only project preflight built from the Runner's own checks.

Doctor composes existing facilities -- ``resolve_data_root``, ``load_run_config``,
the invoice/metadata-definition validators and ``Runner.run(validate_only=True)``
-- and adds no validation rules of its own (#668). The Runner preflight runs on a
temporary copy of the inputs with a no-op target, so it never calls a user flow
or its ``prepare=`` hook and cannot write into the project.
"""

from __future__ import annotations

import inspect
import io
import json
import shutil
import sys
import typing
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, Any, NoReturn, cast

import typer

from rdetoolkit.cli._help import EXIT_CLICK_USAGE, CommandHelp
from rdetoolkit.errors import ERROR_CATALOG, WARNING_CATALOG, RdeError
from rdetoolkit.report.diagnostics import diagnostic, envelope, safe_error
from rdetoolkit.runner.paths import resolve_data_root

DOCTOR_HELP = CommandHelp(
    summary="Check that a project can run: inputs, config, mode, invoice and metadata definitions, and optionally a flow.",
    details=(
        "Doctor reuses the Runner's data-root, config and mode resolution and its validate-only preflight, "
        "run on a temporary copy of the inputs. It never calls the flow or its `prepare=` hook, never writes into "
        "the project, and makes no network requests. `--ref` imports the flow's module, which runs its top-level code."
    ),
    inputs=(
        (
            "`PROJECT_DIR`: the project root, or its `data/` directory (default: the current directory). "
            "Nested `data/` and alias-flat layouts resolve as in `rdetoolkit run`."
        ),
        (
            "`--ref REF`: also import and check a flow `pkg.mod:callable` (the `rdetoolkit run` REF): "
            "its import and that the Runner can inject every parameter."
        ),
        "`--format`: `text` (default) or `json` (the versioned diagnostics envelope).",
    ),
    outputs=(
        (
            "Prints one line per finding, or one JSON object with `--format json`. Paths are relative to `PROJECT_DIR`; "
            "input values, config values and exception text are not printed. Writes no files."
        ),
    ),
    examples=(
        "rdetoolkit doctor",
        "rdetoolkit doctor --format json --ref modules.processing:pipeline",
    ),
    exit_codes=(
        (0, "every check passed (warnings allowed)"),
        (1, "one or more checks failed"),
        EXIT_CLICK_USAGE,
        (3, "`PROJECT_DIR` is not a directory, or `--format` is not text or json"),
    ),
    see_also=("rdetoolkit validate all", "rdetoolkit run", "rdetoolkit nodes lint"),
)

_MODE_OVERRIDE_CODE = 1001
#: Inputs the Runner fails without; it reports a missing one as E4003.
_REQUIRED_INPUTS = (
    ("inputs.directory", "inputdata"),
    ("invoice.source", "invoice/invoice.json"),
    ("invoice.schema", "tasksupport/invoice.schema.json"),
)
_MISSING_INPUT_CODE = 4003


class _Checks:
    """Collect passed checks and findings, with paths relative to the project root."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.checks: list[dict[str, Any]] = []
        self.diagnostics: list[dict[str, Any]] = []

    def relative(self, path: Path) -> str:
        # Never an absolute path: it names the user's directories (#670).
        return path.relative_to(self.root).as_posix() if path.is_relative_to(self.root) else "<outside PROJECT_DIR>"

    def passed(self, check_id: str, path: Path | None = None) -> None:
        record: dict[str, Any] = {"check_id": check_id, "status": "passed"}
        if path is not None:
            record["path"] = self.relative(path)
        self.checks.append(record)

    def finding(
        self,
        check_id: str,
        *,
        code: int | None,
        message: str,
        path: Path | None = None,
        name: str | None = None,
        remediation: str | None = None,
        severity: str = "error",
    ) -> None:
        # Warnings pass their name and remediation: WARNING_CATALOG has no remediation text.
        entry = ERROR_CATALOG.get(code) if code is not None and severity == "error" else None
        item = diagnostic(
            code=code,
            severity=severity,
            name=name or (entry.name if entry else check_id),
            message=message,
            remediation=remediation or (entry.remediation if entry else "Correct the reported project input and rerun doctor."),
            subject=check_id,
            location={"path": self.relative(path)} if path is not None else None,
        )
        item["check_id"] = check_id
        self.diagnostics.append(item)
        self.checks.append({"check_id": check_id, "status": severity, **({"path": item["location"]["path"]} if path is not None else {})})


def _usage_error(message: str) -> NoReturn:
    typer.echo(message, err=True)
    raise typer.Exit(code=3)


def _required_inputs(checks: _Checks, data_root: Path) -> bool:
    ready = True
    for check_id, relative in _REQUIRED_INPUTS:
        path = data_root / relative
        if path.is_dir() if relative == "inputdata" else path.is_file():
            checks.passed(check_id + ".exists", path)
            continue
        ready = False
        checks.finding(
            check_id + ".exists", code=_MISSING_INPUT_CODE, path=path,
            message="A required project input is missing or has the wrong file type.",
            remediation="Restore the input at the reported path (`rdetoolkit init` creates the standard layout).",
        )
    metadata_definition = data_root / "tasksupport/metadata-def.json"
    if metadata_definition.is_file():
        checks.passed("metadata.definition.exists", metadata_definition)
    else:
        # A run succeeds without it; RDE datasets that save metadata need it.
        checks.finding(
            "metadata.definition.exists", code=None, name="MetadataDefinitionMissing", severity="warning", path=metadata_definition,
            message="tasksupport/metadata-def.json is missing; saving metadata.json will not be validated against it.",
            remediation="Add metadata-def.json when the dataset saves metadata (`rdetoolkit init` creates one).",
        )
    return ready


def _load_json(checks: _Checks, check_id: str, path: Path, code: int) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, RecursionError):
        checks.finding(check_id, code=code, message="The file must contain readable UTF-8 JSON.", path=path)
        return None
    if not isinstance(value, dict):
        checks.finding(check_id, code=code, message="The file must contain a JSON object.", path=path)
        return None
    checks.passed(check_id, path)
    return value


def _has_external_reference(value: Any) -> bool:
    pending = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, list):
            pending.extend(current)
        elif isinstance(current, dict):
            for key, item in current.items():
                if key in {"$ref", "$dynamicRef", "$recursiveRef"} and isinstance(item, str) and not item.startswith("#"):
                    return True
                pending.append(item)
    return False


def _validate_definitions(checks: _Checks, data_root: Path) -> bool:
    from jsonschema import Draft202012Validator

    from rdetoolkit.domain.validation import InvoiceValidator, MetadataDefinitionValidator

    invoice = _load_json(checks, "invoice.json", data_root / "invoice/invoice.json", 4001)
    schema_path = data_root / "tasksupport/invoice.schema.json"
    schema = _load_json(checks, "schema.json", schema_path, 4001)
    metadata_path = data_root / "tasksupport/metadata-def.json"
    metadata = _load_json(checks, "metadata.json", metadata_path, 4002)
    if metadata is not None:
        try:
            MetadataDefinitionValidator().validate(json_obj=metadata)
            checks.passed("metadata.definition", metadata_path)
        except Exception:  # noqa: BLE001  # the validator's message quotes the file
            checks.finding("metadata.definition", code=4002, message="Metadata definitions do not satisfy the metadata definition schema.", path=metadata_path)
    if _has_external_reference(schema):
        # Resolving it could mean a network request; doctor never makes one.
        checks.finding(
            "schema.references", code=None, name="ExternalSchemaReference", path=schema_path,
            message="invoice.schema.json references an external schema, which doctor does not retrieve.",
            remediation="Bundle the referenced definitions into invoice.schema.json and use local references (#/...).",
        )
        return False
    if schema is None:
        return False
    try:
        Draft202012Validator.check_schema(InvoiceValidator(schema_path).schema)
        checks.passed("schema.definition", schema_path)
    except Exception:  # noqa: BLE001  # the validator's message quotes the file
        checks.finding("schema.definition", code=4001, message="Invoice schema definitions are invalid.", path=schema_path)
        return False
    return invoice is not None


def _copy_inputs(root: Path, data_root: Path, isolated_root: Path) -> Path:
    """Copy the config files and the three input directories; nothing else."""
    isolated_root.mkdir()
    isolated_data = isolated_root if data_root == root else isolated_root / "data"
    isolated_data.mkdir(exist_ok=True)
    for filename in ("rdeconfig.yaml", "pyproject.toml"):
        if (root / filename).is_file():
            shutil.copy2(root / filename, isolated_root / filename)
    for dirname in ("inputdata", "invoice", "tasksupport"):
        shutil.copytree(data_root / dirname, isolated_data / dirname)
    return isolated_data


def _preflight_target() -> None:
    """Stand-in flow for the validate-only run: no body, no ``prepare=`` hook."""


def _run_isolated(checks: _Checks, root: Path, data_root: Path) -> str | None:
    from rdetoolkit.api.request import build_run_request
    from rdetoolkit.report.events import MemoryEventSink
    from rdetoolkit.runner.lifecycle import Runner

    with TemporaryDirectory(prefix="rdetoolkit-doctor-") as temporary:
        # Keep a ``data``-named root's name: resolve_data_root treats it as the data root.
        isolated_root = Path(temporary) / ("data" if root.name == "data" else "project")
        isolated_data = _copy_inputs(root, data_root, isolated_root)
        events = MemoryEventSink()
        runner = Runner(root=isolated_root, inputdata_path=isolated_data / "inputdata", unpacked_dir_path=isolated_data / "temp", event_sink=events)
        request = build_run_request(flow=_preflight_target, custom_dataset_function=None, config=None, root=isolated_root, validate_only=True)
        report = runner.run(request)
    for event in events.events:
        if event.name == "warning" and event.payload.get("code") == _MODE_OVERRIDE_CODE:
            checks.finding(
                "mode.selection", code=_MODE_OVERRIDE_CODE, name=WARNING_CATALOG[_MODE_OVERRIDE_CODE].name,
                severity="warning", path=data_root / "inputdata",
                message="Input file detection overrides the configured mode.",
                remediation="Use the reported effective mode, or make the input files and the configured mode agree.",
            )
    if report.status == "success":
        checks.passed("runner.preflight", data_root)
    else:
        error = safe_error(report.error)
        checks.finding("runner.preflight", code=error["code"], name=error["name"], message=error["message"], remediation=error["remediation"], path=data_root)
    return report.mode or None


def _flow_signature(value: Callable[..., Any]) -> Callable[..., Any]:
    """Return a callable with the signature the Runner injects into, without instantiating a template."""
    if not inspect.isclass(value):
        return value
    from rdetoolkit.templates.base import is_concrete_template_class

    if not is_concrete_template_class(value):
        raise TypeError
    method = cast(Any, value).__flow__
    signature = inspect.signature(method)

    def signature_only(**kwargs: Any) -> None:
        pass

    signature_only.__signature__ = signature.replace(parameters=list(signature.parameters.values())[1:])  # type: ignore[attr-defined]
    signature_only.__annotations__ = typing.get_type_hints(method)
    return signature_only


def _check_flow_signature(checks: _Checks, value: Callable[..., Any]) -> None:
    from rdetoolkit.core.context import RunContext
    from rdetoolkit.core.injection import resolve_flow_kwargs

    try:
        target = _flow_signature(value)
        inspect.signature(target).bind(**resolve_flow_kwargs(target, RunContext()))
        checks.passed("flow.signature")
    except RdeError as exc:
        code = exc.code if isinstance(exc.code, int) and exc.code in ERROR_CATALOG else None
        checks.finding("flow.signature", code=code, name=None if code else "FlowSignatureInvalid", message="The Runner cannot inject every flow parameter.")
    except Exception:  # noqa: BLE001
        checks.finding(
            "flow.signature", code=None, name="FlowSignatureInvalid", message="The flow signature cannot be inspected.",
            remediation="Reference a function or a concrete ProcessingTemplate subclass with an annotated flow signature.",
        )


def _check_flow(checks: _Checks, root: Path, ref: str) -> None:
    from rdetoolkit.cli.run_cmd import resolve_flow
    from rdetoolkit.core.flow import flow_prepare

    previous_path = list(sys.path)
    previous_bytecode = sys.dont_write_bytecode
    try:
        sys.path.insert(0, str(root))
        sys.dont_write_bytecode = True
        try:
            # resolve_flow owns the REF syntax and import rules; its messages
            # (which quote the import error) are swallowed with the module's output.
            with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                value = resolve_flow(ref)
        except (Exception, typer.Exit):  # noqa: BLE001
            checks.finding(
                "flow.import", code=None, name="FlowImportFailed", message="The flow reference cannot be resolved to a flow.",
                remediation="Pass --ref pkg.mod:callable and check that the module imports from the project root.",
            )
            return
        checks.passed("flow.import")
        _check_flow_signature(checks, value)
        if flow_prepare(value) is not None:
            checks.finding(
                "flow.preparation", code=None, name="FlowPreparationSkipped", severity="warning",
                message="The flow declares prepare=; doctor checked the current input files without running it.",
                remediation="If prepare= generates the inputs that decide the mode, prepare them before running doctor.",
            )
    finally:
        sys.path[:] = previous_path
        sys.dont_write_bytecode = previous_bytecode


def _config_summary(checks: _Checks, root: Path) -> dict[str, Any] | None:
    from rdetoolkit.runner.config_loader import compute_config_digest, load_run_config

    try:
        config = load_run_config(root)
    except Exception:  # noqa: BLE001  # the error quotes the offending key or value
        checks.finding("config.effective", code=1002, message="The configuration could not be loaded.", path=root)
        return None
    checks.passed("config.effective", root)
    # A digest and two policies only: custom values may be secrets.
    return {
        "digest": compute_config_digest(config),
        "on_iteration_error": config.execution.on_iteration_error,
        "repr_head": config.provenance.repr_head,
    }


def _inspect_project(checks: _Checks, root: Path, data_root: Path, ref: str | None) -> tuple[dict[str, Any] | None, str | None]:
    mode = None
    with redirect_stdout(sys.stderr):
        inputs_ready = _required_inputs(checks, data_root)
        config = _config_summary(checks, root)
        definitions_ready = _validate_definitions(checks, data_root)
        if inputs_ready and config is not None and definitions_ready:
            try:
                mode = _run_isolated(checks, root, data_root)
            except Exception:  # noqa: BLE001
                checks.finding(
                    "runner.preflight", code=None, name="PreflightUnavailable", path=data_root,
                    message="The isolated preflight could not be completed.",
                    remediation="Check that the project inputs are readable and the temporary directory has space, then rerun doctor.",
                )
        if ref is not None:
            _check_flow(checks, root, ref)
    return config, mode


def doctor(
    project_dir: Annotated[Path | None, typer.Argument(metavar="PROJECT_DIR", help="Project root or its data/ directory.")] = None,
    ref: Annotated[str | None, typer.Option("--ref", metavar="REF", help="Also check the flow pkg.mod:callable (imports it; never calls it).")] = None,
    output_format: Annotated[str, typer.Option("--format", help="Output format: text or json.")] = "text",
) -> None:
    """Check the project's inputs, config, mode and (with --ref) flow without running it."""
    if output_format not in {"text", "json"}:
        _usage_error(f"Unsupported --format {output_format!r}.\nRemediation: pass --format text or --format json.")
    root = (project_dir or Path.cwd()).resolve()
    if not root.is_dir():
        _usage_error(f"PROJECT_DIR is not a directory: {project_dir}\nRemediation: pass the project root or its data/ directory.")
    data_root = resolve_data_root(root)
    checks = _Checks(root)
    config, mode = _inspect_project(checks, root, data_root, ref)
    payload = envelope(
        checks.diagnostics, command="doctor", data_root=checks.relative(data_root), mode=mode, config=config, checks=checks.checks,
    )
    if output_format == "json":
        typer.echo(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        typer.echo(f"doctor: {payload['status']} (data root: {payload['data_root']}, mode: {mode or 'unavailable'})")
        for item in payload["diagnostics"]:
            where = f" [{item['location']['path']}]" if "location" in item else ""
            typer.echo(f"{item['severity']}: {item['check_id']}{where}: {item['message']}\n  Remediation: {item['remediation']}")
    if payload["status"] == "failed":
        raise typer.Exit(code=1)
