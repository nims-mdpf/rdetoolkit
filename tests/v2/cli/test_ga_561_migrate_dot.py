"""GA561 EP/BV: current-directory migration derives a real sibling name."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from rdetoolkit.cli.app import app


@pytest.mark.parametrize("argument", [[], ["."], ["../container"]])
@pytest.mark.parametrize("write", [False, True])
def test_relative_directory_migration__ga561_ep_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, argument: list[str], write: bool) -> None:
    """GA561-EP-1: dry-run and write work for dot and omitted directory arguments."""
    # Given: a legacy container and its byte-identical source snapshot
    source = tmp_path / "container"
    source.mkdir()
    main = source / "main.py"
    before = b"from rdetoolkit import workflows\ndef dataset(src, out):\n    pass\nworkflows.run(custom_dataset_function=dataset)\n"
    main.write_bytes(before)
    monkeypatch.chdir(source)
    # When: migrating from within the container
    result = CliRunner().invoke(app, ["migrate", "apply", *argument, *(["--no-dry-run"] if write else [])])
    # Then: the derived external destination is valid and the input is untouched
    assert result.exit_code == 0, result.output
    assert "container_migrated" in result.output
    assert main.read_bytes() == before
    destination = tmp_path / "container_migrated"
    assert destination.exists() is write
    if write:
        assert "def pipeline" in (destination / "main.py").read_text()


@pytest.mark.parametrize("failure", ["existing", "inside", "empty", "existing_file", "source_itself", "symlink_parent"])
def test_dot_retains_usage_errors__ga561_neg_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str) -> None:
    """GA561-NEG-1: dot normalization cannot bypass write protections."""
    # Given: an unsafe output or a directory without Python input
    source = tmp_path / "container"
    source.mkdir()
    if failure != "empty":
        (source / "main.py").write_text("value = 1\n", encoding="utf-8")
    args = ["migrate", "apply", ".", "--no-dry-run"]
    if failure == "existing":
        (tmp_path / "container_migrated").mkdir()
    elif failure == "existing_file":
        (tmp_path / "container_migrated").write_text("user output", encoding="utf-8")
    elif failure == "source_itself":
        args += ["--out", "."]
    elif failure == "symlink_parent":
        (tmp_path / "alias").symlink_to(source, target_is_directory=True)
        args += ["--out", "../alias/nested"]
    elif failure == "inside":
        args += ["--out", "nested"]
    monkeypatch.chdir(source)
    # When: the actual command validates its destination
    result = CliRunner().invoke(app, args)
    # Then: it reports the existing usage error without creating files
    assert result.exit_code == 3
    assert "Remediation:" in result.output
    assert not (source / "nested").exists()
