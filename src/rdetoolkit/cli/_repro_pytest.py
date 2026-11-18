"""Render a pytest regression scaffold for ``rdetoolkit repro to-pytest`` (#700).

The archive is untrusted, so nothing it records is pasted into the generated
source as code: the flow import comes from the developer's ``--ref`` (checked to
be identifiers only), the project path from the developer's options, and the
archive contributes only validated tokens (a run id that matches the
identifier pattern, a status from the fixed vocabulary, an integer error code)
plus provenance values rendered inside ``#`` comments.

The expected status is the developer's decision: without ``--expect-status``
the scaffold expects ``"success"``, the behaviour after the fix, and it is
never copied from the archived failure.
"""

from __future__ import annotations

import json
import keyword
import os
import platform
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Any

from rdetoolkit import __version__
from rdetoolkit.cli._repro_provenance import _file_digest, read_provenance
from rdetoolkit.report.diagnostics import safe_identifier
from rdetoolkit.report.run_report import RunReport

#: Run statuses a RunReport can record, in the order ``rde_case`` documents them.
STATUSES = ("success", "partial", "failed")

_INPUT_DIRS = ("inputdata", "invoice", "tasksupport")
_MAX_NAME = 60
#: How many differences a refusal lists before summarising the rest.
_MAX_PROBLEMS = 5


@dataclass(frozen=True)
class ArchivedRun:
    """The facts about the archived run that the scaffold may quote.

    Attributes:
        run_id: The run id, if it matches the identifier pattern.
        status: The recorded status, if it is one of :data:`STATUSES`.
        error_code: The run's (or first failed tile's) integer error code.
    """

    run_id: str | None
    status: str | None
    error_code: int | None


def parse_ref(ref: str) -> tuple[str, tuple[str, ...]]:
    """Split ``pkg.mod:attr.path`` into the module name and the attribute names.

    Every part must be a Python identifier that is not a keyword, so the
    reference can be written into the generated import statement verbatim.

    Args:
        ref: The ``--ref`` value.

    Returns:
        The dotted module name and the attribute path.

    Raises:
        ValueError: If the reference is not of that form.
    """
    module, separator, attributes = ref.partition(":")
    module_parts, attribute_parts = module.split("."), attributes.split(".")
    if not separator or not all(_identifier(part) for part in (*module_parts, *attribute_parts)):
        msg = f"Invalid --ref {ref!r}: expected pkg.mod:callable made of Python identifiers (no keywords, calls or extra ':')"
        raise ValueError(msg)
    return module, tuple(attribute_parts)


def _identifier(part: str) -> bool:
    return part.isidentifier() and not keyword.iskeyword(part)


def archived_run(report_text: str) -> ArchivedRun:
    """Extract the quotable facts from the archived run report.

    Args:
        report_text: The JSON of ``data/logs/run_report_*.json``.

    Returns:
        The run id, status and error code; each is None when not usable.

    Raises:
        KeyError: If the report lacks a required field.
        TypeError: If a field has the wrong type.
        ValueError: If the report is not valid JSON.
    """
    report = RunReport.from_json(report_text)
    return ArchivedRun(
        run_id=safe_identifier(report.run_id),
        status=report.status if report.status in STATUSES else None,
        error_code=_error_code(report),
    )


def _error_code(report: RunReport) -> int | None:
    errors = [report.error, *(item.get("error") for item in report.iterations if isinstance(item, Mapping))]
    for error in errors:
        code = error.get("code") if isinstance(error, Mapping) else None
        if isinstance(code, int) and not isinstance(code, bool):
            return code
    return None


def project_problems(project: Path, files: Mapping[str, tuple[int, str]], config_digest: str) -> list[str]:
    """Compare a project's inputs and effective config with a full archive's manifest.

    Args:
        project: Project directory (``<project>/data``) or alias-flat data root.
        files: The manifest's ``path -> (size, sha256)`` listing.
        config_digest: The manifest's ``config_digest``.

    Returns:
        One readable line per difference, named by archive path; empty when the
        project holds exactly the archived inputs and reproduces the digest.
    """
    from rdetoolkit.runner.config_loader import compute_config_digest, load_config  # noqa: PLC0415
    from rdetoolkit.runner.paths import resolve_data_root  # noqa: PLC0415

    data_root = resolve_data_root(project)
    expected = {name: digest for name, (_, digest) in files.items() if name.startswith(tuple(f"data/{d}/" for d in _INPUT_DIRS))}
    actual = _project_digests(data_root)
    differences = (_difference(name, expected.get(name), actual.get(name)) for name in sorted(expected.keys() | actual.keys()))
    problems = [problem for problem in differences if problem is not None]
    try:
        digest = compute_config_digest(load_config(project, data_root=data_root))
    except Exception:  # noqa: BLE001 -- any loader failure means the config cannot match
        digest = None
    if digest != config_digest:
        problems.append(f"the project's effective config does not reproduce the archived config_digest {config_digest}")
    return problems


def _project_digests(data_root: Path) -> dict[str, str]:
    """Map ``data/<dir>/...`` names to digests; a link or unreadable file maps to a marker."""
    digests: dict[str, str] = {}
    for dirname in _INPUT_DIRS:
        source = data_root / dirname
        for path in sorted(source.rglob("*")) if source.is_dir() else ():
            if path.is_dir() and not path.is_symlink():
                continue
            name = "data/" + path.relative_to(data_root).as_posix()
            try:
                digests[name] = "link" if path.is_symlink() or not path.is_file() else _file_digest(path)
            except OSError:
                digests[name] = "unreadable"
    return digests


def _difference(name: str, expected: str | None, actual: str | None) -> str | None:
    if expected is None:
        return f"{name} is not in the archive"
    if actual is None:
        return f"{name} is missing"
    return None if actual == expected else f"{name} differs from the archive"


def summarize(problems: Sequence[str]) -> str:
    """Join the first differences, noting how many more there are."""
    shown = "\n".join(f"  {problem}" for problem in problems[:_MAX_PROBLEMS])
    extra = len(problems) - _MAX_PROBLEMS
    return shown + (f"\n  ... and {extra} more" if extra > 0 else "")


def project_expression(project: Path, output: Path) -> tuple[str, bool]:
    """Return the source expression for the case project, relative to the test file.

    A relative expression keeps the generated test independent of the
    developer's absolute paths and of pytest's rootdir.

    Args:
        project: The project the case runs.
        output: The generated test file.

    Returns:
        The expression and whether it had to fall back to an absolute path
        (only when no relative path exists, e.g. another Windows drive).
    """
    try:
        relative = os.path.relpath(project.resolve(), output.parent.resolve())
    except ValueError:
        return f"Path({_literal(project.resolve().as_posix())})", True
    if relative == os.curdir:
        return "Path(__file__).parent", False
    return f"Path(__file__).parent / {_literal(PurePath(relative).as_posix())}", False


def _literal(text: str) -> str:
    # JSON string syntax is valid Python; non-printable text (control
    # characters, undecodable bytes) is escaped so the source stays readable.
    return json.dumps(text, ensure_ascii=not text.isprintable())


def provenance_notes(manifest: Mapping[str, Any], verified_files: int | None) -> tuple[list[str], list[str]]:
    """Describe the archive's provenance for the scaffold and the terminal.

    Args:
        manifest: The archive's parsed ``repro_manifest.json``.
        verified_files: Files checked against per-file digests, or None when
            the manifest has none (``schema_version`` ``"1"``).

    Returns:
        ``(comment lines, warnings)``: ``#`` lines for the generated source,
        and the environment differences to print on stderr.
    """
    captured_at, known, unavailable = read_provenance(dict(manifest))
    version = _comment(str(manifest.get("schema_version")))
    lines = [
        f"# Per-file checksums: {verified_files} files verified against repro_manifest.json"
        if verified_files is not None
        else f"# Per-file checksums: unavailable (manifest schema_version {version})",
        "# Provenance (" + ("captured at export" if captured_at else "capture point not recorded") + "):",
        *(f"# {name}: {_comment(_describe(name, fields))}" for name, fields in known.items()),
        # Never empty: source_code is always not_included.
        "# Unavailable in the archive: " + ", ".join(unavailable),
        *(f"#   {name}: {_comment(reason)}" for name, reason in unavailable.items()),
    ]
    warnings = _environment_differences(known)
    lines.extend(f"# WARNING: {warning}" for warning in warnings)
    return lines, warnings


def _describe(name: str, fields: Mapping[str, Any]) -> str:
    if name == "git":
        return f"{fields['commit']} ({'tracked files changed' if fields['dirty'] else 'clean'})"
    return " ".join(str(value) for value in fields.values())


def _comment(text: str) -> str:
    # A comment ends only at a line break; anything not printable is replaced
    # so an archived value can never start a new source line.
    return "".join(char if char.isprintable() else "?" for char in text)


def _environment_differences(known: Mapping[str, Mapping[str, Any]]) -> list[str]:
    differences: list[str] = []
    archived = known.get("rdetoolkit", {}).get("version")
    if archived is not None and archived != __version__:
        differences.append(f"archived with rdetoolkit {_comment(archived)}, this environment has {__version__}")
    python = known.get("python", {}).get("version")
    current = platform.python_version()
    if python is not None and str(python).split(".")[:2] != current.split(".")[:2]:
        differences.append(f"archived with Python {_comment(python)}, this environment has {current}")
    return differences


def render_test(  # noqa: PLR0913 -- every argument is one independent part of the source
    *,
    module: str,
    attributes: Sequence[str],
    project: str,
    run: ArchivedRun,
    expect_status: str | None,
    notes: Sequence[str],
) -> str:
    """Return the pytest module source.

    Args:
        module: Module of the flow (validated by :func:`parse_ref`).
        attributes: Attribute path of the flow inside ``module``.
        project: Source expression for the case project.
        run: Facts about the archived run.
        expect_status: The developer's ``--expect-status``, or None for the
            post-fix default ``"success"``.
        notes: ``#`` comment lines describing the archive.

    Returns:
        Python source that ``ruff format`` leaves unchanged.
    """
    status = expect_status or "success"
    flow_expression = ".".join(("flow_under_test", *attributes[1:]))
    lines = [
        *_docstring(run, explicit=expect_status is not None),
        "",
        "from pathlib import Path",
        "",
        "from rdetoolkit.testing import RdeTestResult, rde_case",
        "",
        f"from {module} import {attributes[0]} as flow_under_test",
        "",
        *notes,
        f"PROJECT = {project}",
        "",
        "",
        "@rde_case(",
        f"    flow={flow_expression},",
        "    project=PROJECT,",
        *_expectation(run, expect_status),
        "    # Artifacts the fixed flow must write, relative to the data root, such as",
        '    # "structured/result.csv". rde_case checks them before the test body runs.',
        "    expect_files=[],",
        ")",
        f"def {_test_name(run.run_id)}(rde_run: RdeTestResult) -> None:",
        f'    """The archived run {run.run_id or "(id not recorded)"} must end {status!r}."""',
        f'    assert rde_run.status == "{status}"',
        "    # Add expectations derived independently of the implementation under test:",
        "    # values you checked by hand or a reviewed golden file, never output",
        "    # captured from the same code. For example:",
        '    #     text = rde_run.artifact_path("structured/result.csv").read_text()',
        '    #     assert text.splitlines()[0] == "time,intensity"',
    ]
    return "\n".join(lines) + "\n"


def _docstring(run: ArchivedRun, *, explicit: bool) -> list[str]:
    observed = f"status {run.status!r}" if run.status else "status not recorded"
    code = f", error code {run.error_code}" if run.error_code is not None else ""
    first = (
        ["1. ``expect_status`` was given with --expect-status. Confirm that it is the", "   correct behaviour, not just what the archived run did."]
        if explicit
        else [
            "1. ``expect_status`` is the behaviour expected after the fix; it is not copied",
            "   from the archived run. Change it only after confirming that the archived",
            "   outcome is the correct behaviour.",
        ]
    )
    return [
        '"""Regression test generated by ``rdetoolkit repro to-pytest`` from a repro archive.',
        "",
        f"Archived run: {run.run_id or 'id not recorded'}, {observed}{code}.",
        "",
        "Review before committing:",
        "",
        *first,
        "2. Replace the assertion template in the test body with expectations derived",
        "   independently of the implementation under test.",
        "3. After a verified fix, list the artifacts the fix must write in",
        "   ``expect_files``, assert their content, and run pytest on this file.",
        '"""',
    ]


def _expectation(run: ArchivedRun, expect_status: str | None) -> list[str]:
    observed = f"ended {run.status!r}" if run.status else "has no recorded status"
    if expect_status is None:
        code = f" (error code {run.error_code})" if run.error_code is not None else ""
        return [
            "    # The behaviour expected after the fix, not the archived outcome: the",
            f"    # archived run {observed}{code}.",
            '    expect_status="success",',
        ]
    lines = [f"    # Expected status given with --expect-status; the archived run {observed}.", f'    expect_status="{expect_status}",']
    if expect_status != "success" and run.error_code is not None:
        lines += ["    # The archived run's error code: confirm it is the expected failure.", f"    expect_error_code={run.error_code},"]
    return lines


def _test_name(run_id: str | None) -> str:
    suffix = re.sub(r"[^0-9a-z]+", "_", (run_id or "").lower(), flags=re.ASCII).strip("_")[:_MAX_NAME].rstrip("_")
    return f"test_regression_{suffix or 'archived_run'}"
