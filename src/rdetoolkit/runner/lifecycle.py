"""Runner lifecycle skeleton for rdetoolkit v2."""

from __future__ import annotations

import hashlib
import signal
import sys
import time
import uuid
from collections.abc import Callable, Mapping
from pathlib import Path
from types import FrameType
from typing import Any

from rdetoolkit.api.request import (
    ExecutionTarget,
    FlowTarget,
    LegacyCallbackTarget,
    RunRequest,
    build_run_request,
)
from rdetoolkit.config.normalize import ConfigNormalizer
from rdetoolkit.domain.artifacts import ImageArtifactService, RawArtifactService
from rdetoolkit.domain.invoice_service import InvoiceService
from rdetoolkit.domain.validation import invoice_validate, validate_tile_outputs, wrap_validation_error
from rdetoolkit.errors import (
    ERROR_CATALOG,
    RdeConfigError,
    RdeError,
    RdeExecutionError,
    RdeInternalError,
    RdeValidationError,
)
from rdetoolkit.models.config import Config
from rdetoolkit.report.events import Event, EventSink, MemoryEventSink
from rdetoolkit.report.run_report import RunReport
from rdetoolkit.runner.aggregator import RunAggregator
from rdetoolkit.runner.config_loader import load_config as load_config_from_root
from rdetoolkit.runner.executor import TileExecutor
from rdetoolkit.runner.finalize import RunFinalizer, structured_error_record
from rdetoolkit.runner.invoker import InvokerRegistry
from rdetoolkit.runner.mode_resolver import ModeKind, resolve_mode as resolve_mode_from_paths
from rdetoolkit.runner.paths import resolve_data_root, resolve_tile_paths
from rdetoolkit.runner.planner import RunPlanner
from rdetoolkit.types import RdeConfig


_RUN_INTERRUPTED_CODE = 3004
_REQUIRED_ARTIFACT_MISSING_CODE = 4003


class Runner:
    """Own lifecycle order, cancellation, events, and run-level failure state."""

    def __init__(
        self,
        *,
        root: Path | None = None,
        inputdata_path: Path | None = None,
        unpacked_dir_path: Path | None = None,
        event_sink: EventSink | None = None,
        run_id_factory: Callable[[], str] | None = None,
        planner: RunPlanner | None = None,
        executor: TileExecutor | None = None,
        finalizer: RunFinalizer | None = None,
        invoice_service: InvoiceService | None = None,
    ) -> None:
        """Create a Runner.

        Args:
            root: Project or data root used for config loading.
            inputdata_path: Input data directory for mode resolution.
            unpacked_dir_path: Legacy unpack directory for input checkers.
            event_sink: Event sink owned by this run.
            run_id_factory: Optional factory for deterministic tests.
            planner: Optional request-to-plan collaborator.
            executor: Optional common tile executor.
            finalizer: Optional report persistence collaborator.
            invoice_service: Run-owned path-based invoice operations.
        """
        # Imported here because the mode modules import the planner, so a
        # module-level import would close a runner -> modes -> runner cycle.
        from rdetoolkit.modes.install import install_default_handlers  # noqa: PLC0415

        install_default_handlers()
        self.root = root or Path.cwd()
        self.inputdata_path = inputdata_path or self.root / "inputdata"
        self.unpacked_dir_path = unpacked_dir_path or self.root / "unpacked"
        self.event_sink = event_sink or MemoryEventSink()
        self._run_id_factory = run_id_factory or (lambda: uuid.uuid4().hex)
        self._invoice_service = invoice_service or InvoiceService()
        self.run_id = ""
        # One run, one data root (Session I-REVIEW-A ruling #1). It is resolved
        # by ``run`` before anything is created and handed to every consumer;
        # a Runner driven step-by-step resolves it lazily on first use so the
        # answer is still taken exactly once.
        self._data_root: Path | None = None
        self._planner = planner or RunPlanner(
            inputdata_path=lambda: self.inputdata_path,
            unpacked_dir_path=lambda: self.unpacked_dir_path,
            run_id_factory=lambda: self.run_id,
            invoice_service=self._invoice_service,
        )
        # The services read save_raw / save_nonshared_raw / save_thumbnail_image
        # from the per-run config themselves, so injecting them unconditionally
        # keeps configuration -- not construction -- in charge of publication.
        self._executor = executor or TileExecutor(
            event_sink=self.event_sink,
            flow_invoker=InvokerRegistry(),
            raw_artifact_service=RawArtifactService(),
            image_artifact_service=ImageArtifactService(),
            invoice_service=self._invoice_service,
        )
        self._finalizer = finalizer or RunFinalizer(data_root=lambda: self.data_root)

    @property
    def data_root(self) -> Path:
        """Return the directory that owns this run's RDE inputs and outputs.

        The four-tier ``resolve_data_root`` rule is evaluated once per run and
        cached, because an alias-flat root gains a ``data`` child as soon as
        tile 0 is created: re-resolving later would silently move the run.
        """
        if self._data_root is None:
            self._data_root = resolve_data_root(self.root)
        return self._data_root

    def run(self, request: RunRequest | Callable[..., Any], **overrides: Any) -> RunReport:
        """Execute the six Runner lifecycle steps in Design §6.1 order.

        Runner may know only ``RunRequest``, ``ExecutionPlan``, ``TilePlan``,
        ``RunReport``, ``RdeConfig``, ``ModeKind``, ``EventSink``, and invoker
        collaborators. Mode-specific parsing and invoice construction belong
        behind the planner/executor boundary (merge-v1 Design §6/§7).

        Args:
            request: Normalized request or deprecated direct flow callable.
            **overrides: Config values merged over file configuration.

        Returns:
            Run report produced by ``iterate`` and finalized by this Runner.
        """
        run_request = (
            request
            if isinstance(request, RunRequest)
            else build_run_request(
                flow=request,
                custom_dataset_function=None,
                config=overrides or None,
                root=self.root,
            )
        )
        if isinstance(request, RunRequest) and overrides:
            msg = "Config overrides must be carried by RunRequest.config_source"
            raise TypeError(msg)
        target = run_request.target
        self._apply_request_root(run_request.root)
        # Resolved before any directory is created, so the alias-flat answer
        # cannot change once tile 0 exists (ruling #1).
        self._data_root = resolve_data_root(self.root)
        self._invoice_service.begin_run()

        previous_sigterm: Any = None
        sigterm_installed = False
        try:
            started = time.time()
            self.run_id = self._run_id_factory()
            self.event_sink.open(self.run_id)
            config: RdeConfig | None = None
            mode: ModeKind | None = None
            report: RunReport | None = None
            try:
                previous_sigterm = signal.getsignal(signal.SIGTERM)
                signal.signal(signal.SIGTERM, _raise_run_interrupted)
                sigterm_installed = True
            except ValueError:
                pass

            try:
                try:
                    self.event_sink.emit(Event.run_started(run_id=self.run_id))
                    config = self.load_config(run_request.config_source)
                    mode = self.resolve_mode(config)
                    self.pre_validate(config)
                    report = self.iterate(target, mode, config)
                    self.post_validate(config, report)
                except Exception as exc:  # noqa: BLE001
                    config = config or RdeConfig()
                    report = _failed_report(
                        run_id=self.run_id,
                        flow_id=_target_flow_id(target),
                        mode=mode,
                        started=started,
                        config=config,
                        exc=exc,
                    )
                try:
                    self.finalize(report, config)
                except Exception as exc:  # noqa: BLE001
                    raise _finalize_error(exc) from exc
                return report
            finally:
                if report is not None:
                    self.event_sink.emit(Event.run_completed(run_id=self.run_id, status=report.status))
                self.event_sink.close()
        finally:
            if sigterm_installed:
                signal.signal(signal.SIGTERM, previous_sigterm)
            # Runs are bounded, so this run's invoice material is released here
            # as well as at begin_run: a long-lived host process never
            # accumulates the material of the runs it already finished.
            self._invoice_service.end_run()

    def load_config(self, source: object | None = None) -> RdeConfig:
        """Load the effective v2 Runner config.

        Args:
            source: Explicit v2 config source or mapping overrides.

        Returns:
            Effective configuration.
        """
        # The data root was resolved before anything existed (ruling #1), and
        # config discovery needs it to reach data/tasksupport (ruling #4).
        data_root = self.data_root
        if source is None:
            return load_config_from_root(self.root, data_root=data_root)
        if isinstance(source, RdeConfig):
            return load_config_from_root(self.root, overrides=source.model_dump(), data_root=data_root)
        if isinstance(source, Mapping):
            return load_config_from_root(self.root, overrides=source, data_root=data_root)
        if isinstance(source, Config):
            return ConfigNormalizer().normalize(source, root=self.root, origin="v1")
        return ConfigNormalizer().normalize(source, root=self.root, origin="v2")

    def _apply_request_root(self, root: Path) -> None:
        """Make an explicit request root authoritative for default Runner paths."""
        previous_root = self.root
        if self.inputdata_path == previous_root / "inputdata":
            self.inputdata_path = root / "inputdata"
        if self.unpacked_dir_path == previous_root / "unpacked":
            self.unpacked_dir_path = root / "unpacked"
        self.root = root

    def resolve_mode(self, config: RdeConfig) -> ModeKind:
        """Resolve the effective mode for this run.

        Args:
            config: Effective configuration.

        Returns:
            Effective internal mode.
        """
        return resolve_mode_from_paths(
            config,
            self.inputdata_path,
            self.unpacked_dir_path,
            self.event_sink,
            self.run_id,
        )

    def pre_validate(self, config: RdeConfig) -> None:
        """Validate source structure and invoice schema before flow execution.

        Args:
            config: Effective configuration.
        """
        _ = config
        data_root = self.data_root
        invoice_path = data_root / "invoice" / "invoice.json"
        schema_path = data_root / "tasksupport" / "invoice.schema.json"
        for path in (invoice_path, schema_path):
            if not path.exists():
                raise _validation_error(4003, str(path))
        try:
            invoice_validate(invoice_path, schema_path)
        except Exception as exc:  # noqa: BLE001
            raise _wrap_domain_validation_error(exc) from exc

    def iterate(
        self,
        target: ExecutionTarget | Callable[..., Any],
        mode: ModeKind,
        config: RdeConfig,
    ) -> RunReport:
        """Execute the target once per tile and return a minimal run report.

        Args:
            target: Normalized execution target, or a bare flow callable.
            mode: Effective mode.
            config: Effective configuration.

        Returns:
            Minimal successful run report.
        """
        started = time.time()
        execution_target = target if isinstance(target, (FlowTarget, LegacyCallbackTarget)) else FlowTarget(function=target)
        request = RunRequest(
            root=self.root,
            target=execution_target,
            config_source=config,
        )
        plan = self._planner.create(request, config=config, mode=mode, data_root=self.data_root)
        aggregator = RunAggregator(
            run_id=self.run_id,
            flow_id=_target_flow_id(execution_target),
            mode=mode.value,
            config_digest=_config_digest(config),
            logs_dir=self.data_root / "logs",
        )
        failed_count = 0
        completed_count = 0
        terminal_error: dict[str, Any] | None = None
        for tile in plan.tiles:
            info = tile.iteration
            iteration_status = "failed"
            self.event_sink.emit(Event.iteration_started(run_id=self.run_id, index=info.index))
            try:
                result = self._executor.execute(plan, tile)
                iteration_status = result.status
                if result.status == "failed":
                    failed_count += 1
                    terminal_error = result.error
                    aggregator.record(result)
                    if plan.error_policy == "fail_fast":
                        break
                    continue
                completed_count += 1
                aggregator.record(result)
            except Exception as exc:  # noqa: BLE001
                if _is_run_interrupted(exc):
                    raise
                failed_count += 1
                raise
            finally:
                self.event_sink.emit(
                    Event(
                        run_id=self.run_id,
                        name="iteration.completed",
                        payload={"iteration_index": info.index, "status": iteration_status},
                    ),
                )
        status = _run_status(
            completed_count=completed_count,
            failed_count=failed_count,
            fail_fast=plan.error_policy == "fail_fast",
        )
        warnings = _failure_warnings(failed_count) if failed_count else []
        if failed_count:
            sys.stderr.write(f"{failed_count} iteration(s) failed\n")
        return aggregator.build_report(
            status=status,
            started_at=_iso_timestamp(started),
            duration_ms=(time.time() - started) * 1000.0,
            warnings=warnings,
            error=terminal_error if status == "failed" else None,
        )

    def post_validate(self, config: RdeConfig, report: RunReport) -> None:
        """Validate final artifacts for completed iterations only.

        Args:
            config: Effective configuration.
            report: Report produced by iteration.
        """
        _ = config
        data_root = self.data_root
        schema_path = data_root / "tasksupport" / "invoice.schema.json"
        output_root = data_root
        for iteration in report.iterations:
            if iteration.get("status") != "completed":
                continue
            index = iteration.get("index")
            if not isinstance(index, int):
                raise _validation_error(4003, f"Completed iteration has invalid index: {index!r}")
            paths = resolve_tile_paths(output_root, index)
            try:
                validate_tile_outputs(
                    invoice_path=paths.invoice / "invoice.json",
                    schema_path=schema_path,
                    metadata_path=paths.meta / "metadata.json",
                )
            except Exception as exc:  # noqa: BLE001
                raise _wrap_domain_validation_error(exc) from exc

    def finalize(self, report: RunReport, config: RdeConfig) -> None:
        """Finalize the report and job failure contract (Design §6.1 step 6, §6.3).

        Persists the RunReport JSON and, for failed runs, writes ``data/job.failed``
        through the v1 contract. This is the production path; tests may still
        replace this step through the injectable-step seam.

        Args:
            report: Report produced by iteration.
            config: Effective configuration.
        """
        self._finalizer.finalize(report, config)


def _flow_id(flow_fn: Callable[..., Any]) -> str:
    module = getattr(flow_fn, "__module__", "")
    qualname = getattr(flow_fn, "__qualname__", getattr(flow_fn, "__name__", repr(flow_fn)))
    return f"{module}.{qualname}" if module else qualname


def _target_flow_id(target: ExecutionTarget) -> str:
    """Identify the executed target for the report.

    A v1 callback-free run has no callable at all, so it reports a stable
    sentinel instead of an identifier derived from ``None``.
    """
    function = target.function
    return _flow_id(function) if function is not None else "rdetoolkit.compat.v1.callback:none"


def _raise_run_interrupted(signum: int, frame: FrameType | None) -> None:
    """Interrupt the active Runner so its existing failure path can finalize."""
    _ = (signum, frame)
    error_def = ERROR_CATALOG[_RUN_INTERRUPTED_CODE]
    message = f"{error_def.message_template} Remediation: {error_def.remediation}"
    error_cls: Any = RdeExecutionError
    raise error_cls(code=_RUN_INTERRUPTED_CODE, name=error_def.name, message=message)


def _is_run_interrupted(exc: Exception) -> bool:
    return isinstance(exc, RdeExecutionError) and exc.code == _RUN_INTERRUPTED_CODE


def _config_digest(config: RdeConfig) -> str:
    encoded = config.model_dump_json().encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _iso_timestamp(timestamp: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(timestamp))


def _exception_error(exc: Exception) -> dict[str, Any]:
    code = getattr(exc, "code", 3001)
    error_def = ERROR_CATALOG.get(code) if isinstance(code, int) else None
    error: dict[str, Any] = {
        "code": code,
        "name": getattr(exc, "name", error_def.name if error_def is not None else type(exc).__name__),
        "message": getattr(exc, "message", str(exc)),
    }
    if error_def is not None:
        error["remediation"] = error_def.remediation
    return error


def _run_error(exc: Exception) -> dict[str, Any]:
    """Translate a lifecycle-escaping exception into a run-level error record.

    Any v1 ``StructuredError`` — raised by user code or by the framework's own
    v1-derived helpers — publishes its ``ecode``/``emsg`` verbatim and bypasses
    the 1002 mapping (Design §6.3). Everything else is catalogued; validation
    keeps 4001/4002/4003 because those steps raise ``RdeValidationError``.
    """
    passthrough = structured_error_record(exc)
    if passthrough is not None:
        return passthrough
    return _exception_error(_lifecycle_error(exc))


def _lifecycle_error(exc: Exception) -> RdeError:
    if isinstance(exc, RdeError):
        return exc
    error_def = ERROR_CATALOG[1002]
    message = error_def.message_template.format(reason=str(exc))
    message = f"{message} Remediation: {error_def.remediation}"
    error_cls: Any = RdeConfigError
    return error_cls(
        code=1002,
        name=error_def.name,
        message=message,
    )


def _failed_report(
    *,
    run_id: str,
    flow_id: str,
    mode: ModeKind | None,
    started: float,
    config: RdeConfig,
    exc: Exception,
) -> RunReport:
    return RunReport(
        run_id=run_id,
        status="failed",
        flow_id=flow_id,
        mode=mode.value if mode is not None else "unknown",
        started_at=_iso_timestamp(started),
        duration_ms=(time.time() - started) * 1000.0,
        config_digest=_config_digest(config),
        iterations=[],
        warnings=[],
        error=_run_error(exc),
    )


def _finalize_error(exc: Exception) -> RdeError:
    if isinstance(exc, RdeError):
        return exc
    error_def = ERROR_CATALOG[5001]
    message = error_def.message_template.format(reason=f"finalize I/O failed: {exc}")
    message = f"{message} Remediation: {error_def.remediation}"
    error_cls: Any = RdeInternalError
    return error_cls(code=5001, name=error_def.name, message=message)


def _run_status(*, completed_count: int, failed_count: int, fail_fast: bool = False) -> str:
    """Classify the run outcome (Design §7.2).

    Under fail_fast, any tile failure aborts the run, so the run as a whole is
    "failed" even when earlier tiles completed — "partial" exists only for the
    continue policy (no implicit partial success).
    """
    if failed_count == 0:
        return "success"
    if fail_fast or completed_count == 0:
        return "failed"
    return "partial"


def _failure_warnings(failed_count: int) -> list[dict[str, Any]]:
    return [
        {
            "code": 3001,
            "message": f"{failed_count} iteration(s) failed",
            "failed_count": failed_count,
        },
    ]


def _validation_error(code: int, reason: str) -> RdeValidationError:
    error_def = ERROR_CATALOG[code]
    error_cls: Any = RdeValidationError
    message = (
        error_def.message_template.format(path=reason)
        if code == _REQUIRED_ARTIFACT_MISSING_CODE
        else error_def.message_template.format(reason=reason)
    )
    message = f"{message} Remediation: {error_def.remediation}"
    return error_cls(
        code=code,
        name=error_def.name,
        message=message,
    )


def _wrap_domain_validation_error(exc: Exception) -> RdeValidationError:
    """Delegate to the single owner of the validation-code mapping (ruling #6)."""
    return wrap_validation_error(exc)
