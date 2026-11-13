"""Names of the generated project layout shared by init, validate and migrate.

``rdetoolkit init`` generates ``template/tasksupport/``. Projects created by
v1 have ``templates/tasksupport/`` instead (#615). ``validate all`` still
reads the old directory as a fallback, and ``migrate apply`` renames it.
"""

from __future__ import annotations

from pathlib import Path

TEMPLATE_DIR = "template"
LEGACY_TEMPLATE_DIR = "templates"
TASKSUPPORT_DIR = "tasksupport"


def template_tasksupport_dir(root: Path) -> Path:
    """Return the ``template/tasksupport`` directory under ``root``."""
    return root / TEMPLATE_DIR / TASKSUPPORT_DIR


def legacy_template_tasksupport_dir(root: Path) -> Path:
    """Return the v1 ``templates/tasksupport`` directory under ``root``."""
    return root / LEGACY_TEMPLATE_DIR / TASKSUPPORT_DIR


def has_legacy_template_layout(root: Path) -> bool:
    """Return whether ``root`` has the v1 ``templates/tasksupport`` directory.

    The check looks for ``tasksupport/`` inside ``templates/`` so that an
    unrelated ``templates/`` directory, such as one holding Jinja files, is
    not treated as the generated layout.
    """
    return legacy_template_tasksupport_dir(root).is_dir()
