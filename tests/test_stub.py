import os
import importlib.util
from types import ModuleType
from pathlib import Path
import sys

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))


def get_module_members(module_name: ModuleType):
    """Get all functions and classes defined in the given module.

    Args:
        module: The module to inspect.

    Returns:
        A list of names of functions and classes defined in the module.
    """
    members = []
    for name in dir(module_name):
        if name.startswith("__") or name.startswith("_"):
            continue  # Skip dunder methods
        obj = getattr(module_name, name)
        if isinstance(obj, type) or callable(obj):
            if obj.__module__ == module_name.__name__:
                members.append(name)
    return members


def check_stubfile(module_name: str):
    spec = importlib.util.find_spec(module_name)
    if spec is None:
        raise ImportError(f"Modules: {module_name} not found")

    # 余計な手動ロードをやめ標準インポート
    module = importlib.import_module(module_name)
    if module.__name__ == "src.rdetoolkit.models.rde2types":
        return

    module_file_path = getattr(module, "__file__", None)
    if module_file_path is None:
        return

    # 単純化
    stub_file_path = module_file_path[:-3] + ".pyi"

    if not os.path.exists(stub_file_path):
        msg = (
            f"Stub file: {stub_file_path} not found. "
            "Generate: stubgen -m {module_name} -o src/rdetoolkit (生成後整形)"
        )
        raise FileNotFoundError(msg)

    with open(stub_file_path, "r", encoding="utf-8") as f:
        stub_content = f.read()

    members = get_module_members(module)
    for name in members:
        if name not in stub_content:
            raise AssertionError(
                f"{name} not found in {stub_file_path}. "
                f"Regenerate: stubgen -m {module_name} -o src/rdetoolkit"
            )
    print(f"All functions and classes in {module_name} are defined in {stub_file_path}")


def find_python_moduels(modules_dir_path: Path) -> list[str]:
    modules = []
    for root, _, files in os.walk(modules_dir_path):
        for file in files:
            if file.endswith(".py") and file != "__init__.py":
                module_path = Path(root) / file
                module_name = module_path.relative_to(modules_dir_path).with_suffix("")
                module = str(module_name).replace("/", ".")
                modules.append(module)
    return modules


rdetoolkit_modules = find_python_moduels(Path("src/rdetoolkit"))


@pytest.mark.parametrize("module_name", rdetoolkit_modules)
def test_stub_files(module_name):
    check_stubfile(f"src.rdetoolkit.{module_name}")
