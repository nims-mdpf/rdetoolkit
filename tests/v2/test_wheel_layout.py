"""B6 settlement: the Rust extension module is ``rdetoolkit._core`` (Design §11).

Fast checks run against the installed package in every environment; the true
wheel-content check builds a wheel and therefore only runs where the build
backend (build + maturin) is available — e.g. CI (same convention as
tests/test_package_data.py).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent


class TestInstalledLayout:
    """Fast checks against the installed package (no wheel build needed)."""

    def test_core_extension_module_is_importable_as_underscore_core(self) -> None:
        spec = importlib.util.find_spec("rdetoolkit._core")
        assert spec is not None, "rdetoolkit._core extension module missing"
        assert spec.origin is not None
        assert spec.origin.endswith(".so") or spec.origin.endswith(".pyd"), (
            f"rdetoolkit._core should be a compiled extension, got {spec.origin}"
        )

    def test_core_is_a_python_package_not_an_extension(self) -> None:
        spec = importlib.util.find_spec("rdetoolkit.core")
        assert spec is not None
        assert spec.origin is not None
        assert spec.origin.endswith("__init__.py"), (
            f"rdetoolkit.core must be the v2 Python package, got {spec.origin}"
        )

    def test_no_stale_core_extension_binary_in_installed_package(self) -> None:
        pkg_spec = importlib.util.find_spec("rdetoolkit")
        assert pkg_spec is not None and pkg_spec.origin is not None
        pkg_dir = Path(pkg_spec.origin).parent
        stale = list(pkg_dir.glob("core.cpython-*.so")) + list(pkg_dir.glob("core.*.pyd"))
        assert stale == [], f"stale pre-rename extension binaries found: {stale}"

    def test_old_core_pyi_stub_is_gone_and_underscore_core_pyi_exists(self) -> None:
        src_pkg = PROJECT_ROOT / "src" / "rdetoolkit"
        assert not (src_pkg / "core.pyi").exists(), "lying core.pyi must be deleted (B6)"
        assert (src_pkg / "_core.pyi").exists(), "_core.pyi stub must exist (B6)"

    def test_v1_compat_symbols_reexported_from_core_package(self) -> None:
        from rdetoolkit.core import (  # noqa: PLC0415
            DirectoryOps,
            ManagedDirectory,
            detect_encoding,
            read_file_with_encoding,
            resize_image_aspect_ratio,
        )

        assert callable(detect_encoding)
        assert callable(read_file_with_encoding)
        assert callable(resize_image_aspect_ratio)
        assert DirectoryOps is not None
        assert ManagedDirectory is not None


class TestWheelContents:
    """True wheel-content verification; requires the local build backend."""

    @staticmethod
    def _require_build_backend() -> None:
        if importlib.util.find_spec("build") is None:
            pytest.skip("build is not installed in the current test environment")
        if importlib.util.find_spec("maturin") is None:
            pytest.skip("maturin is not installed in the current test environment")

    @pytest.mark.slow
    def test_wheel_contains_underscore_core_and_no_old_name(self, tmp_path: Path) -> None:
        self._require_build_backend()

        result = subprocess.run(
            [sys.executable, "-m", "build", "--wheel", "--no-isolation", "--outdir", str(tmp_path)],
            capture_output=True,
            text=True,
            check=False,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, f"wheel build failed:\n{result.stderr[-2000:]}"

        wheels = list(tmp_path.glob("*.whl"))
        assert len(wheels) == 1, f"expected exactly one wheel, got {wheels}"

        with zipfile.ZipFile(wheels[0]) as zf:
            names = zf.namelist()

        new_ext = [n for n in names if "_core.cpython" in n or n.endswith("_core.pyd")]
        old_ext = [
            n
            for n in names
            if ("/core.cpython" in n or n.startswith("rdetoolkit/core.cpython"))
        ]
        assert new_ext, f"wheel must bundle rdetoolkit._core extension; contents: {names[:20]}"
        assert old_ext == [], f"wheel must not contain the old core.cpython extension: {old_ext}"
        assert "rdetoolkit/_core.pyi" in names, "wheel must ship the _core.pyi stub"
        assert "rdetoolkit/core.pyi" not in names, "wheel must not ship the lying core.pyi"
        # Phase K2: the v1 orchestration must not ship in the wheel.
        legacy = [
            name
            for name in names
            if name.startswith(("rdetoolkit/processing/", "rdetoolkit/modeproc.", "rdetoolkit/domain/mode."))
            or name in ("rdetoolkit/processing.pyi", "rdetoolkit/processing/processors.pyi")
        ]
        assert legacy == [], f"wheel must not contain the removed v1 orchestration: {legacy}"
