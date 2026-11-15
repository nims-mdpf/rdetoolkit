"""Issue #638 (RDE-002): ``Result`` and factory-only ``OutputContext`` stubs match runtime.

The shipped stubs must describe the API the runtime actually supports: both result
variants implement ``is_failure()``, both are frozen dataclasses, and
``OutputContext`` can only be created through ``OutputContext.from_resource_paths()``
(direct construction raises ``TypeError`` at runtime, so it must be a type error too).

EP/BV table:

| ID | Input / partition | Class | Expected |
|----|-------------------|-------|----------|
| TC-RES638-001 | ``Success(1).is_success()/is_failure()`` | positive | ``True`` / ``False`` |
| TC-RES638-002 | ``Failure(exc).is_success()/is_failure()`` | positive | ``False`` / ``True`` |
| TC-RES638-003 | exactly one of the two predicates holds (both variants) | positive (BV) | ``is_success() != is_failure()`` |
| TC-RES638-004 | assigning ``Success.value`` at runtime | negative | ``FrozenInstanceError`` |
| TC-OUT638-001 | ``from_resource_paths`` on non-existent dirs | positive | context built, no directory created |
| TC-OUT638-002 | ``path_for`` after factory | positive | path resolved, nothing created |
| TC-OUT638-003 | direct construction with all fields | negative | ``TypeError`` naming the factory |
| TC-OUT638-004 | direct construction with a forged token | negative | ``TypeError`` |
| TC-OUT638-005 | ``dataclasses.replace`` on a factory context | negative | ``TypeError`` (why the stub is not a dataclass) |
| TC-OUT638-006 | assigning a field on a factory context | negative | ``FrozenInstanceError`` |
| TC-TYPE638-POS | strict mypy: ``is_failure`` both variants, factory, methods, fields, match | positive | exit 0 |
| TC-TYPE638-NEG-1 | mypy: direct construction with all fields | negative | ``[call-arg]`` |
| TC-TYPE638-NEG-2 | mypy: ``OutputContext()`` | negative | ``[call-arg]`` |
| TC-TYPE638-NEG-3 | mypy: forged ``_token=object()`` | negative | ``[arg-type]`` |
| TC-TYPE638-NEG-4 | mypy: ``dataclasses.replace(out, ...)`` | negative | ``[type-var]`` |
| TC-TYPE638-NEG-5 | mypy: assigning ``out.struct`` | negative | ``[misc]`` read-only |
| TC-TYPE638-NEG-6 | mypy: assigning ``Success.value`` | negative | ``[misc]`` read-only |
| TC-TYPE638-NEG-7 | mypy: ``is_failure()`` result used as ``str`` | negative | ``[assignment]`` (typed ``bool``, not ``Any``) |
| TC-TYPE638-NEG-8 | mypy: ``path_for`` with an unknown kind | negative | ``[arg-type]`` |
"""

from __future__ import annotations

import dataclasses
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from rdetoolkit.result import Failure, Success
from rdetoolkit.types import OutputContext

_FIELDS = (
    "struct", "meta", "main_image", "other_image", "thumbnail",
    "raw", "logs", "attachment", "nonshared_raw", "invoice",
)


def _resource_paths(root: Path) -> SimpleNamespace:
    return SimpleNamespace(**{name: root / "out" / name for name in _FIELDS})


def _mypy(tmp_path: Path, source: str) -> subprocess.CompletedProcess[str]:
    consumer = tmp_path / "consumer.py"
    consumer.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "--no-incremental", "--show-error-codes", str(consumer)],
        cwd=tmp_path, capture_output=True, text=True, check=False, timeout=300,
    )


# --- runtime: Result predicates ------------------------------------------------------


def test_success_predicates__tc_res638_001() -> None:
    """TC-RES638-001: ``Success`` reports success and not failure."""
    # Given: a success value
    result = Success(1)
    # When/Then: the predicates agree with the variant
    assert result.is_success() is True
    assert result.is_failure() is False


def test_failure_predicates__tc_res638_002() -> None:
    """TC-RES638-002: ``Failure`` reports failure and not success."""
    # Given: a failure value
    result = Failure(ValueError("x"))
    # When/Then: the predicates agree with the variant
    assert result.is_success() is False
    assert result.is_failure() is True


@pytest.mark.parametrize("result", [Success(None), Success(0), Failure(None), Failure("")])
def test_predicates_are_complementary__tc_res638_003(result: Success[object] | Failure[object]) -> None:
    """TC-RES638-003 (BV): falsy payloads never confuse the predicates."""
    # Given/When/Then: exactly one predicate holds
    assert result.is_success() != result.is_failure()


def test_success_value_is_frozen__tc_res638_004() -> None:
    """TC-RES638-004: the runtime dataclass is frozen, as the stub now declares."""
    # Given: a success value
    result = Success(1)
    # When/Then: rebinding the payload fails
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.value = 2  # type: ignore[misc]


# --- runtime: OutputContext factory-only invariant ------------------------------------


def test_factory_creates_no_directories__tc_out638_001(tmp_path: Path) -> None:
    """TC-OUT638-001: building the context is pure; directory creation is Runner-owned."""
    # Given: resource paths that do not exist yet
    paths = _resource_paths(tmp_path)
    # When: adapting them through the factory
    out = OutputContext.from_resource_paths(paths)
    # Then: every field is carried over and nothing was created on disk
    assert {name: getattr(out, name) for name in _FIELDS} == vars(paths)
    assert not (tmp_path / "out").exists()
    assert sorted(tmp_path.iterdir()) == []


def test_path_for_creates_nothing__tc_out638_002(tmp_path: Path) -> None:
    """TC-OUT638-002: resolving an artifact path has no side effects."""
    # Given: a factory-built context
    out = OutputContext.from_resource_paths(_resource_paths(tmp_path))
    # When: resolving a path
    target = out.path_for("struct", "data.csv")
    # Then: the path is under the kind directory and still absent
    assert target == tmp_path / "out" / "struct" / "data.csv"
    assert sorted(tmp_path.iterdir()) == []


def test_direct_construction_rejected__tc_out638_003(tmp_path: Path) -> None:
    """TC-OUT638-003: direct construction keeps failing at runtime."""
    # Given: every field supplied, but no factory token
    kwargs = vars(_resource_paths(tmp_path))
    # When/Then: construction raises and names the supported factory
    with pytest.raises(TypeError, match="from_resource_paths"):
        OutputContext(**kwargs)  # type: ignore[call-arg]


def test_forged_token_rejected__tc_out638_004(tmp_path: Path) -> None:
    """TC-OUT638-004: only the private factory token is accepted."""
    # Given: every field plus an arbitrary token object
    kwargs = vars(_resource_paths(tmp_path))
    # When/Then: construction raises
    with pytest.raises(TypeError, match="from_resource_paths"):
        OutputContext(**kwargs, _token=object())  # type: ignore[arg-type]


def test_replace_rejected__tc_out638_005(tmp_path: Path) -> None:
    """TC-OUT638-005: ``dataclasses.replace`` re-enters ``__init__`` without the token."""
    # Given: a factory-built context
    out = OutputContext.from_resource_paths(_resource_paths(tmp_path))
    # When/Then: replace fails, so the stub must not advertise dataclass semantics
    with pytest.raises(TypeError, match="from_resource_paths"):
        dataclasses.replace(out, struct=tmp_path)


def test_fields_are_frozen__tc_out638_006(tmp_path: Path) -> None:
    """TC-OUT638-006: the context is immutable at runtime (read-only in the stub)."""
    # Given: a factory-built context
    out = OutputContext.from_resource_paths(_resource_paths(tmp_path))
    # When/Then: rebinding a field fails
    with pytest.raises(dataclasses.FrozenInstanceError):
        out.struct = tmp_path  # type: ignore[misc]


# --- static typing ---------------------------------------------------------------------

_POSITIVE = '''from pathlib import Path
from types import SimpleNamespace

from rdetoolkit.result import Failure, Result, Success
from rdetoolkit.types import OutputContext

ok: bool = Success(1).is_failure()
bad: bool = Failure(ValueError("x")).is_failure()
flags: tuple[bool, bool] = (Success(1).is_success(), Failure("e").is_success())


def describe(r: Result[int, str]) -> str:
    match r:
        case Success(value):
            return str(value + 1)
        case Failure(error):
            return error


out: OutputContext = OutputContext.from_resource_paths(SimpleNamespace())
target: Path = out.path_for("struct", "data.csv")
written: Path = out.write_bytes("attachment", "blob.bin", b"x")
dirs: list[Path] = [
    out.struct, out.meta, out.main_image, out.other_image, out.thumbnail,
    out.raw, out.logs, out.attachment, out.nonshared_raw, out.invoice,
]
same: bool = out == out
'''

_NEGATIVE = '''import dataclasses
from pathlib import Path

from rdetoolkit.result import Success
from rdetoolkit.types import OutputContext

p = Path("x")
out = OutputContext.from_resource_paths(object())
OutputContext(struct=p, meta=p, main_image=p, other_image=p, thumbnail=p, raw=p, logs=p, attachment=p, nonshared_raw=p, invoice=p)  # NEG-1
OutputContext()  # NEG-2
OutputContext(struct=p, meta=p, main_image=p, other_image=p, thumbnail=p, raw=p, logs=p, attachment=p, nonshared_raw=p, invoice=p, _token=object())  # NEG-3
dataclasses.replace(out, struct=p)  # NEG-4
out.struct = p  # NEG-5
Success(1).value = 2  # NEG-6
text: str = Success(1).is_failure()  # NEG-7
out.path_for("temp", "x.txt")  # NEG-8
'''

_EXPECTED_NEGATIVE = {
    "NEG-1": "[call-arg]",
    "NEG-2": "[call-arg]",
    "NEG-3": "[arg-type]",
    "NEG-4": "[type-var]",
    "NEG-5": "[misc]",
    "NEG-6": "[misc]",
    "NEG-7": "[assignment]",
    "NEG-8": "[arg-type]",
}


def test_strict_mypy_accepts_supported_patterns__tc_type638_pos(tmp_path: Path) -> None:
    """TC-TYPE638-POS: the supported Result and OutputContext usage type-checks."""
    # Given: a client using is_failure on both variants, the factory and its methods
    # When: type checking it with --strict
    result = _mypy(tmp_path, _POSITIVE)
    # Then: mypy accepts it
    assert result.returncode == 0, result.stdout + result.stderr


def test_strict_mypy_rejects_unsupported_patterns__tc_type638_neg(tmp_path: Path) -> None:
    """TC-TYPE638-NEG-1..8: every runtime-failing pattern is a type error."""
    # Given: one client holding each unsupported pattern on its own tagged line
    tags = {
        index: re.search(r"# (NEG-\d)", line).group(1)  # type: ignore[union-attr]
        for index, line in enumerate(_NEGATIVE.splitlines(), start=1)
        if "# NEG-" in line
    }
    # When: type checking it with --strict
    result = _mypy(tmp_path, _NEGATIVE)
    # Then: each tagged line carries its expected diagnostic, and nothing else fails
    assert result.returncode == 1, result.stdout + result.stderr
    # (mypy reports one [call-arg] per missing argument, hence sets of codes per line)
    reported: dict[str, set[str]] = {}
    for line in result.stdout.splitlines():
        match = re.match(r"consumer\.py:(\d+): error: .*(\[[a-z-]+\])$", line)
        if match:
            reported.setdefault(tags.get(int(match.group(1)), "untagged"), set()).add(match.group(2))
    assert {tag: codes for tag, codes in reported.items() if tag != "untagged"} == {
        tag: {code} for tag, code in _EXPECTED_NEGATIVE.items()
    }, result.stdout
    assert "untagged" not in reported, result.stdout
