from __future__ import annotations

import sys
import traceback
from collections.abc import Callable, Generator
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast


if TYPE_CHECKING:
    from rdetoolkit.models.config import Config
    from rdetoolkit.models.rde2types import DatasetCallback, PathTuple, RawFiles, RdeInputDirPaths, RdeOutputResourcePath, SmartTableRawFiles
    from rdetoolkit.report.run_report import RunReport
    from rdetoolkit.result import Result
    from rdetoolkit.templates import ProcessingTemplate


from rdetoolkit.exceptions import StructuredError

# Expected arity of a SmartTableRawFiles element: (row_csv | None, user_files).
_SMARTTABLE_PAIR_LEN = 2


def check_files_result(srcpaths: RdeInputDirPaths, *, mode: str | None, config: Config | None = None) -> Result[tuple[RawFiles | SmartTableRawFiles, Path | None, Path | None], StructuredError]:
    """Classify input files with explicit Result type error handling.

    Returns Result type instead of raising exceptions, enabling type-safe error handling.

    Args:
        srcpaths: Input directory paths
        mode: Processing mode (invoice, excelinvoice, etc.)
        config: Optional configuration object

    Returns:
        Result containing:
            Success: tuple of (RawFiles | SmartTableRawFiles, excel_invoice_path, smarttable_path).
                In SmartTable mode, the first element is a ``SmartTableRawFiles`` sequence of
                ``(row_csv | None, user_files)`` pairs; in other modes it is a plain ``RawFiles``
                sequence of file path tuples.
            Failure: StructuredError with error details

    Example:
        >>> result = check_files_result(srcpaths, mode="invoice")
        >>> if result.is_success():
        ...     rawfiles, excel_invoice, smarttable = result.unwrap()
        ... else:
        ...     error = result.error
        ...     print(f"Error: {error.emsg}")
    """
    from rdetoolkit.modeproc import selected_input_checker
    from rdetoolkit.rde2util import StorageDir
    from rdetoolkit.result import Success, Failure

    try:
        out_dir_temp = StorageDir.get_specific_outputdir(True, "temp")
        if mode is None:
            mode = ""

        input_checker = selected_input_checker(srcpaths, out_dir_temp, mode, config)
        rawfiles, special_file = input_checker.parse(srcpaths.inputdata)

        # Use checker_type property to distinguish between different checkers
        if input_checker.checker_type == "smarttable":
            return Success((rawfiles, None, special_file))  # excelinvoice=None, smarttable_file=Path
        if input_checker.checker_type == "excel_invoice":
            return Success((rawfiles, special_file, None))  # excelinvoice=Path, smarttable_file=None
        return Success((rawfiles, None, None))  # InvoiceMode
    except StructuredError as e:
        return Failure(e)
    except Exception as e:
        # Wrap unexpected exceptions in StructuredError
        emsg = f"Unexpected error in check_files: {e}"
        error = StructuredError(
            emsg,
            999,
            eobj=e,
            traceback_info=traceback.format_exc(),
        )
        return Failure(error)


def check_files(srcpaths: RdeInputDirPaths, *, mode: str | None, config: Config | None = None) -> tuple[RawFiles | SmartTableRawFiles, Path | None, Path | None]:
    """Classify input files to determine if the input pattern is appropriate.

    1. Invoice
        1. File mode (e.g. sample.txt)
        2. Folder mode (e.g. sample1.txt, sample2.txt)
        3. Input file none
    2. ExcelInvoice
        1. File mode (e.g. sample.zip (compressed with only one file) + *_excel_invoice.xlsx)
        2. Folder mode (e.g. sample.zip (folder compressed) + *_excel_invoice.xlsx)
        2-3. None (e.g. *_excel_invoice.xlsx)
    3. Format (e.g. *.zip, tasksupport/rdeformat.txt)
    4. Multiple Files in a Flat Structure (e.g., sample1.txt, sample2.txt, sample3.txt)

    Returns:
        tuple(list[tuple[Path, ...]]), Optional[Path], Optional[Path]):
        Registered data file path group, presence of Excel invoice file, presence of SmartTable file.
        In SmartTable mode, the file path group is a ``SmartTableRawFiles`` sequence of
        ``(row_csv | None, user_files)`` pairs instead of a plain ``RawFiles`` sequence.

    Example:
        ```python
        # MODE: Invoice / Mode: File / Input: single file
        check_files(srcpaths, fmt_flags=format_flags)
        tuple([(Path('data/inputdata/sample.txt'),)], None)

        # MODE: Invoice / Mode: Folder / Input: multi files
        check_files(srcpaths, fmt_flags=format_flags)
        tuple([(Path('data/inputdata/sample1.txt'), (Path('data/inputdata/sample2.txt'))], None)

        # MODE: Invoice / Mode: None / Input: no files
        check_files(srcpaths, fmt_flags=format_flags)
        tuple([()], None)

        # MODE: ExcelInvoice / Mode: File / Input: zip + *_excel_invoice.xlsx
        check_files(srcpaths, fmt_flags=format_flags)
        tuple([(Path('data/inputdata/sample.txt'),)], Path("data/inputdata/dataset_excel_invoice.xlsx"))

        # MODE: ExcelInvoice / Mode: Folder / Input: zip + *_excel_invoice.xlsx
        checkFiles(srcpaths, fmt_flags=format_flags)
        tuple([(Path('data/inputdata/sample1.txt'), (Path('data/inputdata/sample2.txt'))], Path("data/inputdata/dataset_excel_invoice.xlsx"))

        # MODE: ExcelInvoice / Mode: None / Input: *_excel_invoice.xlsx
        check_files(srcpaths, fmt_flags=format_flags)
        tuple([], Path("data/inputdata/dataset_excel_invoice.xlsx"))
        ```

    Note:
        The destination paths for reading input files are different for the shipping label and ExcelInvoice.
        invoice: /data/inputdata/<registered_files>
        excelinvoice: /data/temp/<registered_files>

    Raises:
        StructuredError: When file classification fails
        Exception: Propagates unexpected exceptions from input checker
    """
    from rdetoolkit.result import Failure

    result = check_files_result(srcpaths, mode=mode, config=config)
    if isinstance(result, Failure):
        error = result.error
        if isinstance(error, StructuredError) and isinstance(error.eobj, Exception):
            raise error.eobj
        raise error
    return result.unwrap()


def generate_folder_paths_iterator(
    raw_files_group: RawFiles | SmartTableRawFiles,
    invoice_org_filepath: Path,
    invoice_schema_filepath: Path,
    *,
    smarttable_mode: bool = False,
) -> Generator[RdeOutputResourcePath, None, None]:
    """Generates iterator for RDE output folder paths.

    Create data folders for registration in the RDE system.
    Excel invoice: Create divided folders according to the number of registered data.

    Args:
        raw_files_group (RawFiles | SmartTableRawFiles): A list of tuples containing raw
            file paths. When ``smarttable_mode`` is True, each element is instead a
            ``(row_csv | None, user_files)`` pair as returned by ``SmartTableChecker.parse()``.
        invoice_org_filepath (pathlib.Path): invoice_org.json file path
        invoice_schema_filepath (Path): invoice.schema.json file path
        smarttable_mode (bool): Set to True when running in SmartTable mode. In that case
            each element of ``raw_files_group`` is unpacked directly into the per-tile row
            CSV (``smarttable_rawfile``) and the user's data files (``rawfiles``); no
            heuristic detection of the row CSV is performed.

    Yields:
        RdeOutputResourcePath: A named tuple of output folder paths for RDE resources

    Raises:
        StructuredError: Occurs when the structured process fails to process correctly.
        TypeError: If an element of ``raw_files_group`` does not match the shape
            implied by ``smarttable_mode`` (e.g. a flat ``RawFiles`` tuple passed
            with ``smarttable_mode=True``, or vice versa).

    Example:
        ```python
        rawfiles_tplList = [(Path('data/temp/samle1.txt'),), (Path('data/temp/sample2.txt'),), (Path('data/temp/sample3.txt'),)]

        excel_invoice_files = Path("data/inputdata/sample_excel_invoice.xlsx")

        create_folders(raw_files_group, excel_invoice_files)
        ```

        ```python
        # SmartTable mode: each element is a (row_csv, user_files) pair.
        smarttable_raw_files = [(Path('data/temp/fsmarttable_test_0000.csv'), (Path('data/temp/file0.txt'),))]

        list(generate_folder_paths_iterator(smarttable_raw_files, invoice_org, invoice_schema, smarttable_mode=True))
        ```
    """
    from rdetoolkit.core import DirectoryOps
    from rdetoolkit.models.rde2types import RdeOutputResourcePath

    dir_ops = DirectoryOps("data")
    for idx, raw_files in enumerate(raw_files_group):
        if smarttable_mode:
            # raw_files is a SmartTableRawFiles element: (row_csv | None, user_files).
            # This is a runtime-only distinction (driven by smarttable_mode), so mypy
            # cannot narrow the RawFiles | SmartTableRawFiles union statically here.
            # Validate the shape explicitly so that a legacy flat RawFiles tuple
            # fails with a clear message instead of an obscure unpacking error.
            if (
                len(raw_files) != _SMARTTABLE_PAIR_LEN
                or not (raw_files[0] is None or isinstance(raw_files[0], Path))
                or not isinstance(raw_files[1], tuple)
            ):
                msg = (
                    "smarttable_mode=True requires each raw_files_group element to be a "
                    f"(row_csv | None, user_files) pair; got {raw_files!r} at index {idx}"
                )
                raise TypeError(msg)
            row_csv, user_files = cast("tuple[Path | None, PathTuple]", raw_files)
        else:
            if not all(isinstance(f, Path) for f in raw_files):
                msg = (
                    "smarttable_mode=False requires each raw_files_group element to be a "
                    f"tuple of Path objects; got {raw_files!r} at index {idx}"
                )
                raise TypeError(msg)
            row_csv, user_files = None, cast("PathTuple", raw_files)

        rdeoutput_resource_path = RdeOutputResourcePath(
            raw=Path(dir_ops.raw(idx).path),
            rawfiles=user_files,
            struct=Path(dir_ops.structured(idx).path),
            main_image=Path(dir_ops.main_image(idx).path),
            other_image=Path(dir_ops.other_image(idx).path),
            thumbnail=Path(dir_ops.thumbnail(idx).path),
            meta=Path(dir_ops.meta(idx).path),
            logs=Path(dir_ops.logs(idx).path),
            invoice=Path(dir_ops.invoice(idx).path),
            invoice_schema_json=invoice_schema_filepath,
            invoice_org=invoice_org_filepath,
            smarttable_rawfile=row_csv,
            temp=Path(dir_ops.temp(idx).path),
            nonshared_raw=Path(dir_ops.nonshared_raw(idx).path),
            invoice_patch=Path(dir_ops.invoice_patch(idx).path),
            attachment=Path(dir_ops.attachment(idx).path),
        )
        yield rdeoutput_resource_path


#: Single stderr line the v1 callback entry writes before exiting non-zero.
#: v1 printed the failure through its ``handle_*_error`` helpers; the unified
#: entry's failure detail already reached ``data/job.failed`` and the RunReport,
#: so this line only tells an operator where to look.
_CALLBACK_ENTRY_FAILURE_NOTICE = (
    "rdetoolkit: the structured process failed; see data/job.failed for the error code\n"
)


def _callback_entry_log_path(root: Path, data_root: Path) -> Path:
    """Return the ``rdesys_<ts>.log`` path the v1 callback entry logs into.

    Decided **after** ``resolve_data_root`` (Session J-REVIEW ruling #3). For
    the standard layout -- ``data_root == <cwd>/data`` -- the path is taken
    through v1's own ``StorageDir``, the identical ritual the v1 loop
    performed: it is the only seam a v1 caller (or a v1 test) can redirect, and
    there it names the same directory. For any other data root (an alias-flat
    project, or a CWD that already is ``data``) ``StorageDir`` would create
    ``<cwd>/data``, and an existing ``data`` child outranks the RDE markers in
    ``resolve_data_root`` -- creating the log directory would move the data
    root the Runner resolves next. The log then lives below the data root.

    Args:
        root: The process CWD the entry point runs from.
        data_root: ``resolve_data_root(root)``, resolved before anything exists.

    Returns:
        ``<data root>/logs/rdesys_<timestamp>.log``, its parent created.
    """
    from rdetoolkit.rde2util import StorageDir
    from rdetoolkit.rdelogger import generate_log_timestamp

    log_filename = f"rdesys_{generate_log_timestamp()}.log"
    if data_root == root / "data":
        return StorageDir.get_specific_outputdir(True, "logs").joinpath(log_filename)
    logs_dir = data_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir / log_filename


def _run_callback_entry(custom_dataset_function: DatasetCallback | None, config: Any = None) -> str:
    """Run the v1 dataset-callback entry point through the unified Runner.

    Session J2 / merge-v1 I7 (Phase J ruling #2): ``run(custom_dataset_function=...)``
    calls the single Runner exactly once while keeping every observable half of
    the v1 contract — the ``rdesys_<ts>.log`` file logger, the legacy JSON return
    value, ``SystemExit(1)`` for a failed run, and v1's fail-fast iteration
    policy. The v1 orchestration itself was removed in Phase K2; the frozen
    contract fixtures carry its observable behaviour.

    Order matters (Session J-REVIEW ruling #3): the data root is resolved
    before anything is created, so neither the log directory nor any later
    step can move it.

    Args:
        custom_dataset_function: Optional v1 dataset callback, invoked once per
            data tile by ``LegacyCallbackInvoker``.
        config: ``None`` resolves the v1 configuration from
            ``<data root>/tasksupport`` with v1's own loader; a v1 ``Config`` is
            passed through unchanged. Both keep the v1 contract — fail-fast
            unless ``multidata_tile.ignore_errors`` says otherwise. An
            ``RdeConfig`` or mapping is normalized as a v2 source.

    Returns:
        The v1 ``{"statuses": [...]}`` JSON string for a successful or partial
        run.

    Raises:
        SystemExit: With code 1 when the run failed. ``Runner.finalize`` has
            already written ``<data root>/job.failed``, exactly as v1 did before
            it exited. A configuration that cannot be loaded exits the same way
            after writing v1's generic ``ErrorCode=999`` marker.
    """
    from rdetoolkit.api.request import LegacyCallbackTarget, RunRequest
    from rdetoolkit.config import load_config as load_v1_config
    from rdetoolkit.rdelogger import get_logger
    from rdetoolkit.runner.lifecycle import Runner
    from rdetoolkit.runner.paths import resolve_data_root

    root = Path.cwd()
    data_root = resolve_data_root(root)
    get_logger("rdetoolkit", file_path=_callback_entry_log_path(root, data_root))
    # The handler is created with ``delay=True``, so the log file only appears
    # once a record is emitted. v1 emitted plenty of them from the pipeline it
    # ran next; the Runner logs through its own channels, so the entry point
    # opens the file itself -- the frozen v1 observations carry
    # ``data/logs/rdesys_<ts>.log`` as an existing file (Phase J ruling #3).
    get_logger(__name__).debug("rdetoolkit structured process started (unified Runner)")

    # ``config=None`` must not fall through to v2 config discovery: that path
    # takes the v2 default ``on_iteration_error: continue`` and ignores the v1
    # material a structured program ships, while Design §7.2 contracts the v1
    # API as fail-fast. v1's own loader answers both questions at once -- it
    # honours ``system.extended_mode`` and ``multidata_tile.ignore_errors`` from
    # ``data/tasksupport``, exactly as the v1 loop did, and the v1
    # ``Config`` it returns reaches ``ConfigNormalizer`` with ``origin="v1"``
    # (Phase J ruling #2c, amended by the Session J2 B-ruling #1b). It runs
    # before the Runner's failure route exists, so its failure takes v1's
    # generic route here (Session J-REVIEW ruling #4).
    config_source: Any = config
    if config is None:
        try:
            config_source = load_v1_config(str(data_root / "tasksupport"), config=None)
        except Exception as error:  # noqa: BLE001 -- v1 converted every loader failure
            # v1's ``handle_generic_error`` observation, field for field --
            # stderr traceback, ``ErrorCode=999`` with its fixed message, the
            # exception in the rdesys log, exit 1 -- except that the marker is
            # written below the *resolved* data root: the helper itself writes
            # below ``<cwd>/data``, which an alias-flat project does not have.
            from rdetoolkit.errors import handle_exception, write_job_errorlog_file

            sys.stderr.write((handle_exception(error, verbose=True).traceback_info or "") + "\n")
            data_root.mkdir(parents=True, exist_ok=True)
            write_job_errorlog_file(
                999,
                "Error: Please check the logs and code, then try again.",
                filename=str(data_root / "job.failed"),
            )
            get_logger(__name__).exception(str(error))
            sys.exit(1)
    report = Runner(
        root=root,
        inputdata_path=data_root / "inputdata",
        unpacked_dir_path=data_root / "temp",
    ).run(
        RunRequest(
            root=root,
            target=LegacyCallbackTarget(function=custom_dataset_function),
            config_source=config_source,
        ),
    )
    if report.status == "failed":
        sys.stderr.write(_CALLBACK_ENTRY_FAILURE_NOTICE)
        sys.exit(1)
    return report.to_legacy_statuses()


def run(  # pragma: no cover
    *,
    flow: Callable[..., Any] | type[ProcessingTemplate] | None = None,
    custom_dataset_function: DatasetCallback | None = None,
    config: Any = None,
) -> str | RunReport:
    """Execute the RDE workflow pipeline with custom processing.

    This is the main entry point for rdetoolkit. It orchestrates the entire RDE workflow:
    processing input data, generating invoices, creating thumbnails, and executing custom
    data transformations. The workflow supports multiple processing modes (Invoice,
    Excelinvoice, MultiDataTile, SmartTable) configured via the Config object.

    Both public forms execute through the **single unified Runner** (merge-v1
    I7): ``run(flow=...)`` returns its ``RunReport``, while
    ``run(custom_dataset_function=...)`` keeps the v1 return and exit contract on
    top of it — the ``rdesys_<ts>.log`` file logger, the legacy ``{"statuses":
    [...]}`` JSON string, v1's fail-fast iteration policy, and ``SystemExit(1)``
    after ``data/job.failed`` has been written for a failed run. No
    DeprecationWarning is emitted for either form.

    The workflow pipeline processes data in the following stages:
    1. Validation: Verify directory structure and configuration
    2. File Processing: Collect and organize input files
    3. Invoice Generation: Create/process invoice metadata
    4. Custom Processing: Execute user-defined transformations (custom_dataset_function)
    5. Thumbnail Generation: Create image thumbnails if configured
    6. Output Generation: Produce final RDE-structured output

    Args:
        flow: Optional v2 flow function. When provided, execution is delegated
            to the v2 Runner and a RunReport is returned.
        custom_dataset_function: Optional user-defined function for data processing.
            Must have signature: (RdeDatasetPaths) -> None or (RdeInputDirPaths, RdeOutputResourcePath) -> None.
            The recommended signature uses the unified `RdeDatasetPaths` class, which bundles
            input (`RdeInputDirPaths`) and output (`RdeOutputResourcePath`) directory information.
            For backward compatibility, callbacks accepting the two legacy arguments are still supported.
            This function receives input paths (raw data) and output paths (processed data)
            and should perform domain-specific data transformations.
        config: Optional Config object with system settings. The config controls
            processing mode (extended_mode), output options (save_raw,
            save_thumbnail_image, save_main_image), and mode-specific settings
            (multidata_tile, smarttable configurations). On the
            ``custom_dataset_function`` path ``None`` means "the v1 defaults",
            which keeps the v1 fail-fast iteration policy; on the ``flow`` path
            ``None`` lets the Runner discover ``rdeconfig.yaml`` /
            ``tasksupport/`` configuration.

    Returns:
        For ``run(flow=...)``, a v2 ``RunReport``. For the v1
        ``custom_dataset_function`` path, a JSON ``str`` containing a list of
        WorkflowExecutionStatus objects (one per dataset). Each status includes:
            - run_id: Dataset identifier
            - title: Processing title
            - status: "success" or "failed"
            - mode: Processing mode used (Invoice, Excelinvoice, MultiDataTile, SmartTable)
            - error_code: Error code if failed (None if success)
            - error_message: Error message if failed (None if success)
            - stacktrace: Stack trace if failed (None if success)
            - target: Target files processed

    Raises:
        StructuredError: For critical workflow errors:
            - Configuration file not found or invalid
            - Required directory structure missing
            - Invoice schema validation failures
            - Custom function execution errors
        Exception: For unexpected errors during processing

    Examples:
        Basic usage with custom processing:
            >>> from rdetoolkit.workflows import run
            >>> from rdetoolkit.models.rde2types import RdeDatasetPaths
            >>>
            >>> def process_csv_data(paths: RdeDatasetPaths) -> None:
            ...     import pandas as pd
            ...     for csv_file in paths.inputdata.glob("*.csv"):
            ...         df = pd.read_csv(csv_file)
            ...         # Process dataframe
            ...         result_path = paths.struct / f"processed_{csv_file.name}"
            ...         df.to_csv(result_path, index=False)
            >>>
            >>> result_json = run(custom_dataset_function=process_csv_data)
            >>> # Result is JSON string with execution statuses

        With custom configuration:
            >>> from rdetoolkit.models.config import Config, SystemSettings
            >>>
            >>> config = Config(
            ...     system=SystemSettings(
            ...         extended_mode="MultiDataTile",
            ...         save_thumbnail_image=True
            ...     )
            ... )
            >>> result_json = run(custom_dataset_function=process_csv_data, config=config)

        Legacy callback signature (backward compatibility):
            >>> from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath
            >>>
            >>> def legacy_process(srcpaths: RdeInputDirPaths, output: RdeOutputResourcePath) -> None:
            ...     # Process using separate input/output paths
            ...     pass
            >>>
            >>> result_json = run(custom_dataset_function=legacy_process)

        With MultiDataTile mode and error handling:
            >>> from rdetoolkit.models.config import Config, SystemSettings, MultiDataTileSettings
            >>>
            >>> config = Config(
            ...     system=SystemSettings(
            ...         extended_mode="MultiDataTile",
            ...         save_raw=False,
            ...         save_nonshared_raw=True,
            ...         save_thumbnail_image=True
            ...     ),
            ...     multidata_tile=MultiDataTileSettings(ignore_errors=False)
            ... )
            >>> result_json = run(custom_dataset_function=process_csv_data, config=config)

    Notes:
        - Processing mode is selected in the following order:
            1. SmartTable CSV is present (smarttable_file is not None) -> SmartTableInvoice mode
            2. Excel invoice bundle is provided (excel_invoice_files is not None) -> Excelinvoice mode
            3. extended_mode matches (case-insensitive) "rdeformat" or "MultiDataTile" -> corresponding extended mode
            4. Otherwise -> Invoice mode

        - Directory structure must follow RDE conventions:
            tasksupport/
                config.toml
                invoice.schema.json
                invoice.json (or invoice.xlsx)
            container/data/
                inputdata/        # Input data
                invoice/          # Output resources
                raw/              # Raw data copies
                structured/       # Processed data
                main_image/       # Main images
                other_image/      # Other images
                thumbnail/        # Thumbnails
                meta/             # Metadata
                logs/             # Log files

        - The custom_dataset_function is called once per dataset in the invoice.
          For MultiDataTile mode, it may be called multiple times per dataset.

        - Thumbnail generation (if enabled) runs automatically for supported image formats
          (PNG, JPG, JPEG, BMP, GIF, TIFF).

        - The workflow creates backups of invoice.json files before processing.

        - Use get_agent_guide() or `rdetoolkit agent-guide` for comprehensive usage documentation.

    See Also:
        - Config: Configuration schema and options
        - RdeDatasetPaths: Unified input/output path structure
        - RdeInputDirPaths: Input path structure (legacy)
        - RdeOutputResourcePath: Output path structure (legacy)
        - WorkflowExecutionStatus: Execution result details
    """
    if flow is not None:
        from rdetoolkit.api.request import build_run_request
        from rdetoolkit.runner.lifecycle import Runner
        from rdetoolkit.runner.paths import resolve_data_root

        request = build_run_request(
            flow=flow,
            custom_dataset_function=custom_dataset_function,
            config=config,
        )
        # The public entry is a consumer of the single data root, not a second
        # authority on it (Session I-REVIEW-A ruling #1). Hardcoding
        # ``request.root / "data"`` made an alias-flat project -- one whose
        # inputdata/invoice/tasksupport sit directly below the root -- run with
        # zero inputs and still report success.
        data_root = resolve_data_root(request.root)
        return Runner(
            root=request.root,
            inputdata_path=data_root / "inputdata",
            unpacked_dir_path=data_root / "temp",
        ).run(request)

    return _run_callback_entry(custom_dataset_function, config)
