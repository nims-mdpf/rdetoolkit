#!/usr/bin/env python3
"""Run the coding-agent readiness gate (#676) against an installed rdetoolkit.

The gate is ``tests/v2/acceptance``; see docs/development/agent-readiness-gate.md.
This script supplies what the gate must not take from the checkout:

1. it builds the version-matched offline Skills pack (``scripts/skills_pack.py``)
   and installs it into a fresh project with the installer bundled in the pack,
   using ``--python`` (so the installer's exact-version check applies to the
   runtime under test);
2. it runs the gate with that interpreter, pointing it at the installed Skills
   and requiring the CLI to import rdetoolkit from outside this checkout.

No conftest of the repository is loaded (``--noconftest``) and the repository's
pytest ``addopts`` are cleared, so the interpreter needs only the rdetoolkit
wheel and pytest. The JUnit report and pytest's temporary directories (every
project and command output of the gate) stay under ``--work`` for inspection.

Example::

    python -m venv /tmp/gate-venv
    /tmp/gate-venv/bin/python -m pip install dist/rdetoolkit-*.whl pytest
    python scripts/agent_readiness_gate.py --python /tmp/gate-venv/bin/python --work /tmp/agent-readiness
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GATE = "tests/v2/acceptance"
SKILLS_ENV = "RDETOOLKIT_GATE_SKILLS_DIR"
REQUIRE_INSTALLED_ENV = "RDETOOLKIT_GATE_REQUIRE_INSTALLED"


def install_pack(python: str, work: Path) -> Path:
    """Build the Skills pack and install it for ``python``'s rdetoolkit.

    Args:
        python: Interpreter whose installed rdetoolkit version the pack must match.
        work: Empty or new directory for the pack and the agent project.

    Returns:
        The installed ``<project>/.agents/skills`` directory.
    """
    dist = work / "skill-dist"
    subprocess.run(  # noqa: S603 -- fixed interpreter and repository script
        [sys.executable, str(REPO / "scripts" / "skills_pack.py"), "build", "--repo", str(REPO), "--output", str(dist)],
        check=True,
    )
    (pack,) = dist.glob("rdetoolkit-skills-*.zip")
    installer = work / "install_skills.py"
    with zipfile.ZipFile(pack) as archive:
        installer.write_bytes(archive.read("install_skills.py"))
    project = work / "agent-project"
    project.mkdir(parents=True)
    subprocess.run(  # noqa: S603 -- the pack's own installer, run by the interpreter under test
        [python, str(installer), "install", "--pack", str(pack), "--project", str(project), "--agent", "codex"],
        check=True,
    )
    return project / ".agents" / "skills"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--python", required=True, help="interpreter with the rdetoolkit wheel and pytest installed")
    parser.add_argument("--work", type=Path, required=True, help="new directory for the pack, reports and run evidence")
    parser.add_argument("pytest_args", nargs="*", help="extra pytest arguments (after --)")
    args = parser.parse_args(argv)
    work = args.work.resolve()
    if work.exists() and any(work.iterdir()):
        parser.error(f"--work must be new or empty: {work}")
    work.mkdir(parents=True, exist_ok=True)
    skills = install_pack(args.python, work)
    env = {**os.environ, SKILLS_ENV: str(skills), REQUIRE_INSTALLED_ENV: "1"}
    env.pop("PYTHONPATH", None)
    command = [
        args.python, "-m", "pytest", GATE,
        "-p", "no:cacheprovider", "--noconftest", "-o", "addopts=",
        f"--basetemp={work / 'pytest'}", f"--junitxml={work / 'junit.xml'}", "-v",
        *args.pytest_args,
    ]
    print("+", " ".join(command), flush=True)
    return subprocess.run(command, cwd=REPO, env=env, check=False).returncode  # noqa: S603


if __name__ == "__main__":
    sys.exit(main())
