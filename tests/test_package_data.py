"""Test that guide files are included in package distribution.

This module tests package data configuration to ensure that _agent/*.md files
are properly included in the wheel distribution and accessible after installation.
"""

import importlib.util
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

# Conditionally import tomli/tomllib
try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # Python 3.10


class TestPackageData:
    """Test that guide files are included in package distribution."""

    @staticmethod
    def _require_build_backend() -> None:
        """Skip package build tests when the local build backend is unavailable."""
        if importlib.util.find_spec("build") is None:
            pytest.skip("build is not installed in the current test environment")
        if importlib.util.find_spec("maturin") is None:
            pytest.skip("maturin is not installed in the current test environment")

    def test_guide_files_exist_in_source(self) -> None:
        """Test: Guide files exist in source tree."""
        # Given: Source tree
        agent_dir = Path("src/rdetoolkit/_agent")

        # When: Checking for guide files
        # Then: Files should exist
        assert (agent_dir / "AGENTS.md").exists()
        assert (agent_dir / "guide.md").exists()

    def test_package_data_configuration(self) -> None:
        """Test: pyproject.toml includes _agent/*.md in package_data."""
        # Given: pyproject.toml file
        with Path("pyproject.toml").open("rb") as f:
            config = tomllib.load(f)

        # When: Checking package_data
        package_data = config.get("tool", {}).get("setuptools", {}).get("package_data", {})
        rdetoolkit_data = package_data.get("rdetoolkit", [])

        # Then: Should include _agent/*.md
        assert "_agent/*.md" in rdetoolkit_data

    @pytest.mark.slow
    def test_built_wheel_contains_guide_files(self, tmp_path: Path) -> None:
        """Test: Built wheel contains guide files."""
        self._require_build_backend()

        # Given: Project root
        # When: Building wheel
        result = subprocess.run(
            [sys.executable, "-m", "build", "--wheel", "--no-isolation", "--outdir", str(tmp_path)],
            capture_output=True,
            text=True,
            check=False,
        )

        # Then: Build should succeed
        assert result.returncode == 0, f"Build failed: {result.stderr}"

        # And: Wheel should contain guide files
        wheels = list(tmp_path.glob("*.whl"))
        assert len(wheels) > 0, "No wheel file generated"

        with zipfile.ZipFile(wheels[0]) as zf:
            files = zf.namelist()
            assert any("_agent/AGENTS.md" in f for f in files), "_agent/AGENTS.md not in wheel"
            assert any("_agent/guide.md" in f for f in files), "_agent/guide.md not in wheel"

    @pytest.mark.slow
    def test_installed_package_can_access_guides(self, tmp_path: Path) -> None:
        """Test: Installed package can access guide files."""
        self._require_build_backend()

        # Given: Built and installed package
        venv_dir = tmp_path / "venv"
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)

        pip_path = venv_dir / "bin" / "pip"
        python_path = venv_dir / "bin" / "python"

        # Build wheel
        wheel_dir = tmp_path / "wheels"
        wheel_dir.mkdir()
        subprocess.run(
            [sys.executable, "-m", "build", "--wheel", "--no-isolation", "--outdir", str(wheel_dir)],
            check=True,
        )

        # Install wheel
        wheels = list(wheel_dir.glob("*.whl"))
        subprocess.run(
            [str(pip_path), "install", "--no-deps", str(wheels[0])],
            check=True,
        )

        # When: Importing and calling get_agent_guide
        test_script = """
import rdetoolkit
summary = rdetoolkit.get_agent_guide()
detailed = rdetoolkit.get_agent_guide(detailed=True)
assert len(summary) > 0
assert len(detailed) > 0
assert len(detailed) > len(summary)
print("SUCCESS")
"""
        result = subprocess.run(
            [str(python_path), "-c", test_script],
            capture_output=True,
            text=True,
            check=False,
        )

        # Then: Should work without errors
        assert result.returncode == 0, f"Import failed: {result.stderr}"
        assert "SUCCESS" in result.stdout
