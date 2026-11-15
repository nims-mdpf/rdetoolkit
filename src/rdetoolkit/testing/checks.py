"""Reusable, opt-in output checks for RDE test runs: ``rde_check``.

A check is any callable taking an
:class:`~rdetoolkit.testing.runner.RdeTestResult`; it fails by raising
(normally ``assert``) and returns ``None``. ``rde_check(id=...)`` only
attaches a stable rule ID to a function and returns that same function, so it
stays directly callable from an ordinary test.

Checks are never registered anywhere: they run only where a test lists them
(``rde_case(checks=...)`` or ``run.assert_checks(...)``), after the real
Runner has finished, and they cannot change the ``RunReport`` or
``job.failed`` the run produced. A failing check fails the pytest test with
the rule ID, the dataset, the artifacts it read (with their tile) and the
assertion. The module never imports pytest.
"""

from __future__ import annotations

import re
import traceback
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, TypeVar

from rdetoolkit.testing.assertions import context_lines
from rdetoolkit.testing.runner import ARTIFACT_ACCESS

if TYPE_CHECKING:
    from rdetoolkit.testing.runner import RdeTestResult

#: Attribute ``rde_check`` sets on the decorated function.
CHECK_ID_ATTRIBUTE = "__rde_check_id__"

_CheckT = TypeVar("_CheckT", bound=Callable[..., object])
_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_PACKAGE_DIR = Path(__file__).resolve().parent


def rde_check(*, id: str) -> Callable[[_CheckT], _CheckT]:  # noqa: A002 - the public parameter name is the rule "id"
    """Give a check function a stable rule ID, leaving it otherwise unchanged.

    Args:
        id: Rule ID shown in failure messages: letters, digits, ``.``, ``_``,
            ``:`` and ``-``, starting with a letter or digit, at most 128
            characters.

    Returns:
        A decorator that returns the decorated function itself.

    Raises:
        ValueError: If ``id`` is not a valid rule ID.
        TypeError: If the decorated object is not callable or cannot carry
            an attribute.
    """
    if not isinstance(id, str) or not _ID_PATTERN.fullmatch(id):
        msg = f"rde_check id= must match {_ID_PATTERN.pattern!r}, got {id!r}"
        raise ValueError(msg)

    def decorate(check: _CheckT) -> _CheckT:
        if not callable(check):
            msg = f"rde_check decorates a callable taking the test result, got {type(check).__name__}"
            raise TypeError(msg)
        try:
            setattr(check, CHECK_ID_ATTRIBUTE, id)
        except (AttributeError, TypeError) as exc:
            msg = f"rde_check cannot attach an id to {check!r}; wrap it in a def function"
            raise TypeError(msg) from exc
        return check

    return decorate


def check_id(check: Callable[..., object]) -> str:
    """Return the rule ID of a check: its ``rde_check`` id, else its qualified name."""
    explicit = getattr(check, CHECK_ID_ATTRIBUTE, None)
    if isinstance(explicit, str):
        return explicit
    name = getattr(check, "__qualname__", None) or getattr(check, "__name__", None)
    return str(name) if name else repr(check)


def run_checks(result: RdeTestResult, checks: Iterable[Callable[[RdeTestResult], object]]) -> list[str]:
    """Run every check on ``result`` and return one message per failing check.

    Every check runs, so one test reports all broken rules at once.

    Args:
        result: The finished test run.
        checks: Callables taking the result.

    Returns:
        Failure messages, in check order; empty when every check passed.
    """
    failures: list[str] = []
    for check in checks:
        failure = _run_one(result, check)
        if failure is not None:
            failures.append(failure)
    return failures


def _run_one(result: RdeTestResult, check: Callable[[RdeTestResult], object]) -> str | None:
    accessed: list[PurePosixPath] = []
    token = ARTIFACT_ACCESS.set(accessed)
    try:
        returned = check(result)
    except Exception as exc:  # noqa: BLE001 - any error inside a check is that check's failure
        return _failure(result, check, accessed, _describe(exc))
    finally:
        ARTIFACT_ACCESS.reset(token)
    if returned is not None:
        # ``return all(...)`` would otherwise pass silently when it is False.
        detail = [f"the check returned {returned!r}; a check fails by raising (e.g. assert) and returns None"]
        return _failure(result, check, accessed, detail)
    return None


def _failure(result: RdeTestResult, check: Callable[..., object], accessed: list[PurePosixPath], detail: list[str]) -> str:
    origin = f"{getattr(check, '__module__', '?')}.{getattr(check, '__qualname__', type(check).__name__)}"
    lines = [
        f"output contract failed: rde_check {check_id(check)!r} ({origin})",
        f"  dataset: {result.project_root.name}",
        *_artifact_lines(result, accessed),
        *(f"  {line}" for line in detail),
    ]
    return "\n".join([*lines, *(f"  {line}" for line in context_lines(result))])


def _artifact_lines(result: RdeTestResult, accessed: list[PurePosixPath]) -> list[str]:
    unique = list(dict.fromkeys(accessed))
    if not unique:
        return ["  artifacts read: none through the result helpers"]
    datatiles = {summary.index: summary.datatile_id for summary in result.iterations}
    lines = ["  artifacts read:"]
    for path in unique:
        tile = _tile_index(path)
        lines.append(f"    {path.as_posix()} (tile {tile}, datatile {datatiles.get(tile)!r})")
    return lines


def _tile_index(path: PurePosixPath) -> int:
    # Tile 0 writes below the data root; tile N >= 1 below divided/<NNNN>.
    parts = path.parts
    if len(parts) >= 2 and parts[0] == "divided" and parts[1].isdigit():  # noqa: PLR2004 - "divided/<index>"
        return int(parts[1])
    return 0


def _describe(exc: Exception) -> list[str]:
    message = str(exc).strip()
    lines = [f"{type(exc).__name__}: {line}" if index == 0 else f"    {line}" for index, line in enumerate(message.splitlines() or [""])]
    frame = _user_frame(exc)
    if frame is not None:
        lines.append(f"at {frame.filename}:{frame.lineno}")
    return lines


def _user_frame(exc: Exception) -> traceback.FrameSummary | None:
    # The deepest frame outside rdetoolkit.testing is the user's failing line,
    # also when the assertion was raised by a helper such as run.read_csv.
    frames = [frame for frame in traceback.extract_tb(exc.__traceback__) if not _in_package(frame.filename)]
    return frames[-1] if frames else None


def _in_package(filename: str) -> bool:
    try:
        return Path(filename).resolve().is_relative_to(_PACKAGE_DIR)
    except (OSError, ValueError):
        return False
