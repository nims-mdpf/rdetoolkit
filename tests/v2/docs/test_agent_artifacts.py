"""EP/BV archive gate: clean wheel/sdist pass; retired assets fail.

EP-1: clean wheel, sdist -> accepted (test_clean_artifact).
EP-2: retired _agent module or Markdown / old Skills / canonical Skills -> rejected
      (test_retired_instruction_rejected).
BV-1: empty archive -> rejected (test_empty_artifact).
BV-2: CLI returns nonzero and names offending member (test_cli_failure).
BV-3: no CLI artifacts -> usage error; wheel and sdist -> checked together.
"""

from __future__ import annotations

import importlib.util
import io
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts/check_agent_artifacts.py"


def _load_gate():
    spec = importlib.util.spec_from_file_location("artifact_gate", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _archive(path: Path, members: list[str]) -> None:
    if path.suffix == ".whl":
        with zipfile.ZipFile(path, "w") as archive:
            for member in members:
                archive.writestr(member, "content")
    else:
        with tarfile.open(path, "w:gz") as archive:
            for member in members:
                info = tarfile.TarInfo(member)
                info.size = 7
                archive.addfile(info, io.BytesIO(b"content"))


@pytest.mark.parametrize("suffix", [".whl", ".tar.gz"])
def test_clean_artifact(tmp_path: Path, suffix: str) -> None:
    # Given: runtime code and typing data only.
    artifact = tmp_path / f"rdetoolkit{suffix}"
    _archive(artifact, ["rdetoolkit/__init__.py", "rdetoolkit/py.typed"])
    # When/Then: archive inspection accepts it without extracting anything.
    _load_gate().check_artifact(artifact)


@pytest.mark.parametrize("suffix", [".whl", ".tar.gz"])
@pytest.mark.parametrize("member", [
    "rdetoolkit/_agent/__init__.py", "rdetoolkit/_agent/AGENTS.md", "rdetoolkit/_agent/guide.md",
    "rdetoolkit/.agents/SKILL.md", ".agents/skills/rdetoolkit-testing/SKILL.md",
])
def test_retired_instruction_rejected(tmp_path: Path, suffix: str, member: str) -> None:
    # Given: an archive carrying instructions forbidden at the runtime boundary.
    artifact = tmp_path / f"rdetoolkit{suffix}"
    _archive(artifact, [f"rdetoolkit-2.0.0rc1/{member}"])
    # When/Then: failure names the member so packaging drift is actionable.
    with pytest.raises(ValueError, match="Agent instructions") as error:
        _load_gate().check_artifact(artifact)
    assert member in str(error.value)


@pytest.mark.parametrize("suffix", [".whl", ".tar.gz"])
def test_empty_artifact(tmp_path: Path, suffix: str) -> None:
    # Given: a malformed/empty build output.
    artifact = tmp_path / f"empty{suffix}"
    _archive(artifact, [])
    # When/Then: it cannot pass the packaging gate accidentally.
    with pytest.raises(ValueError, match="Empty"):
        _load_gate().check_artifact(artifact)


def test_cli_failure(tmp_path: Path) -> None:
    # Given: a built artifact containing retired guidance.
    artifact = tmp_path / "bad.whl"
    _archive(artifact, ["rdetoolkit/_agent/guide.md"])
    # When: invoking the same CLI used by CI.
    result = subprocess.run([sys.executable, str(SCRIPT), "--wheel", str(artifact)], capture_output=True, text=True, check=False)
    # Then: CI fails with the exact offending path.
    assert result.returncode != 0
    assert "rdetoolkit/_agent/guide.md" in result.stderr


def test_cli_requires_artifact(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: a gate invocation without any build output.
    monkeypatch.setattr(sys, "argv", [str(SCRIPT)])
    # When/Then: a usage error prevents a falsely green packaging job.
    with pytest.raises(SystemExit) as error:
        _load_gate().main()
    assert error.value.code == 2


def test_cli_checks_both_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given: a clean wheel and sdist from one build.
    wheel = tmp_path / "good.whl"
    sdist = tmp_path / "good.tar.gz"
    for path in (wheel, sdist):
        _archive(path, ["rdetoolkit/__init__.py"])
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--wheel", str(wheel), "--sdist", str(sdist)])
    # When: executing the public gate command.
    _load_gate().main()
    # Then: both boundaries were inspected and reported.
    output = capsys.readouterr().out
    assert "good.whl" in output and "good.tar.gz" in output
