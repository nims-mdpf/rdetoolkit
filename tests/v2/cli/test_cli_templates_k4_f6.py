"""Release PR #553 review fixes F6-3 and F6-5 (Session K4-F6).

F6-3: ``init --processing-template`` must generate a ``processing.py`` that
imports: ``None`` return annotations render as ``None`` (never ``NoneType``)
and every dotted annotation name is imported from its module.

F6-5: ``templates describe`` and ``init --processing-template`` load
``rdetoolkit.plugins`` entry points exactly as ``templates list`` does, so a
template that ``list`` shows is never "Unknown" for the other two commands.

EP table:

| TC-ID              | Partition                                               | Expected                                                    |
|--------------------|---------------------------------------------------------|-------------------------------------------------------------|
| TC-K4F6-TPL-EP-001 | init for the DemoSkeletonTemplate fixture                | processing.py imports; class subclasses the skeleton         |
| TC-K4F6-TPL-EP-002 | spec with typing / builtins / dotted / None annotations  | grouped, sorted, deduplicated imports; None rendered as None |
| TC-K4F6-TPL-EP-003 | plugin-only template, templates describe                 | exit 0, the template id is described                         |
| TC-K4F6-TPL-EP-004 | plugin-only template, init --processing-template         | exit 0, processing.py generated and importable               |

BV / negative table:

| TC-ID              | Boundary                                                | Expected                                                    |
|--------------------|---------------------------------------------------------|-------------------------------------------------------------|
| TC-K4F6-TPL-BV-001 | slot types that are all undotted builtins                | no import line other than the skeleton's                     |
| TC-K4F6-TPL-BV-002 | plugin-only template with no plugin installed (describe) | still a usage error, exit 3                                  |
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from collections.abc import Iterator
from importlib.metadata import EntryPoint
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from typer.testing import CliRunner

from rdetoolkit.cli.app import app
from rdetoolkit.cli.templates_cmd import _render_processing_module
from rdetoolkit.core import registry as node_registry
from rdetoolkit.templates import registry as template_registry
from rdetoolkit.templates.registry import TemplateMethodSpec, TemplateParameterSpec, TemplateSpec

FIXTURE_MODULE = "tests.v2.templates.fixtures.xrd_like_template"
PLUGIN_MODULE = "k4f6_plugin_provider"
PLUGIN_TEMPLATE = "K4F6PluginTemplate"
_NODE_MAPS = ("_node_specs", "_node_wrappers", "_node_functions")
_TEMPLATE_MAPS = ("_template_specs", "_template_classes")

_PLUGIN_SOURCE = '''"""Plugin provider whose template exists only through its entry point."""

from __future__ import annotations

from typing import final

from rdetoolkit.templates import ProcessingTemplate, slot
from rdetoolkit.types import InputPaths


class K4F6PluginTemplate(ProcessingTemplate):
    """Plugin-only skeleton."""

    @slot
    def read(self, paths: InputPaths) -> None: ...

    @final
    def __flow__(self, paths: InputPaths) -> None:
        self.read(paths)
'''


@pytest.fixture(autouse=True)
def isolate_registries() -> Iterator[None]:
    """Restore the process-global registries and imported fixture modules."""
    node_maps = tuple(getattr(node_registry, name).copy() for name in _NODE_MAPS)
    template_maps = tuple(getattr(template_registry, name).copy() for name in _TEMPLATE_MAPS)
    concrete = list(template_registry._concrete_classes)
    modules_before = set(sys.modules)
    yield
    for name, saved in zip(_NODE_MAPS, node_maps, strict=True):
        getattr(node_registry, name).clear()
        getattr(node_registry, name).update(saved)
    for name, saved in zip(_TEMPLATE_MAPS, template_maps, strict=True):
        getattr(template_registry, name).clear()
        getattr(template_registry, name).update(saved)
    template_registry._concrete_classes.clear()
    template_registry._concrete_classes.extend(concrete)
    # A module first imported here registered into the registries restored
    # above, so it is dropped too: a later ``--module`` import must re-run it.
    for name in set(sys.modules) - modules_before:
        if name == FIXTURE_MODULE or name.startswith(("k4f6_", "processing")):
            sys.modules.pop(name, None)


@pytest.fixture
def isolated_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run the command from an empty project directory."""
    root = tmp_path / "project"
    root.mkdir()
    monkeypatch.chdir(root)
    return root


@pytest.fixture
def plugin_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> EntryPoint:
    """Install a fake ``rdetoolkit.plugins`` entry point whose load registers a template."""
    provider_dir = tmp_path / "site"
    provider_dir.mkdir()
    (provider_dir / f"{PLUGIN_MODULE}.py").write_text(_PLUGIN_SOURCE, encoding="utf-8")
    monkeypatch.syspath_prepend(str(provider_dir))
    entry = EntryPoint(name="k4f6-plugin", value=PLUGIN_MODULE, group="rdetoolkit.plugins")
    discovery = importlib.import_module("rdetoolkit.plugin.discovery")
    monkeypatch.setattr(discovery.metadata, "entry_points", lambda *, group: (entry,))
    discovery.__dict__["_discovered"].clear()
    return entry


def _import_generated(path: Path, module_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _registered(name: str) -> bool:
    return any(spec.name == name for spec in template_registry.list_templates())


def _spec(*slots: TemplateMethodSpec) -> TemplateSpec:
    return TemplateSpec(id="pkg.skeletons.DemoTemplate", name="DemoTemplate", slots=slots, hooks=(), domain_types=())


def _method(name: str, return_type: str, **parameters: str) -> TemplateMethodSpec:
    return TemplateMethodSpec(
        name=name,
        parameters=tuple(TemplateParameterSpec(name=key, type_name=value) for key, value in parameters.items()),
        return_type=return_type,
    )


# --- F6-3 --------------------------------------------------------------------


def test_generated_processing_module_imports__tc_k4f6_tpl_ep_001(isolated_root: Path) -> None:
    """TC-K4F6-TPL-EP-001: the generated module imports and subclasses the skeleton."""
    # Given: the DemoSkeletonTemplate fixture (slots typed InputPaths / InvoiceData, returning None)
    runner = CliRunner()

    # When: generating its processing template
    result = runner.invoke(app, ["init", "--processing-template", "DemoSkeletonTemplate", "--module", FIXTURE_MODULE])

    # Then: the source names no NoneType and imports the rdetoolkit.types names it uses
    assert result.exit_code == 0, result.output
    processing_path = isolated_root / "processing.py"
    source = processing_path.read_text(encoding="utf-8")
    assert "NoneType" not in source
    assert "from rdetoolkit.types import InputPaths, InvoiceData\n" in source
    assert "-> None:" in source

    # Then: importing it succeeds and yields a concrete subclass of the skeleton
    module = _import_generated(processing_path, "k4f6_generated_processing")
    skeleton = importlib.import_module(FIXTURE_MODULE).DemoSkeletonTemplate
    generated = module.DemoSkeletonProcessing
    assert issubclass(generated, skeleton)


def test_rendered_imports_are_grouped_sorted_and_deduplicated__tc_k4f6_tpl_ep_002() -> None:
    """TC-K4F6-TPL-EP-002: typing, dotted and None annotations render with exact imports."""
    # Given: slots mixing typing, builtins NoneType, repeated dotted names and plain builtins
    spec = _spec(
        _method("read", "builtins.NoneType", paths="rdetoolkit.types.InputPaths", extra="typing.Any"),
        _method("extract", "NoneType", invoice="rdetoolkit.types.InvoiceData", paths="rdetoolkit.types.InputPaths"),
        _method("save", "pathlib.Path", count="int", option="typing.Any"),
        _method("noop", "None"),
    )

    # When: rendering the processing module
    source = _render_processing_module(spec)

    # Then: one sorted import line per module, typing names bare, None never NoneType
    import_lines = [line for line in source.splitlines() if line.startswith("from ") and "__future__" not in line]
    assert import_lines == [
        "from pathlib import Path",
        "from pkg.skeletons import DemoTemplate",
        "from rdetoolkit.types import InputPaths, InvoiceData",
        "from typing import Any",
    ]
    assert "def read(self, paths: InputPaths, extra: Any) -> None:" in source
    assert "def extract(self, invoice: InvoiceData, paths: InputPaths) -> None:" in source
    assert "def save(self, count: int, option: Any) -> Path:" in source
    assert "def noop(self) -> None:" in source
    assert "NoneType" not in source
    compile(source, "processing.py", "exec")


def test_builtin_only_slots_emit_no_extra_imports__tc_k4f6_tpl_bv_001() -> None:
    """TC-K4F6-TPL-BV-001: undotted builtin annotations add no import lines."""
    # Given: a slot typed only with builtins
    spec = _spec(_method("read", "str", count="int"))

    # When: rendering the processing module
    source = _render_processing_module(spec)

    # Then: the skeleton import is the only import besides __future__
    import_lines = [line for line in source.splitlines() if line.startswith("from ") and "__future__" not in line]
    assert import_lines == ["from pkg.skeletons import DemoTemplate"]
    assert "def read(self, count: int) -> str:" in source


# --- F6-5 --------------------------------------------------------------------


def test_describe_loads_plugin_templates__tc_k4f6_tpl_ep_003(plugin_entry: EntryPoint) -> None:
    """TC-K4F6-TPL-EP-003: describe finds a template registered only by a plugin."""
    # Given: a plugin entry point whose template is not yet registered
    assert not _registered(PLUGIN_TEMPLATE)

    # When: describing the plugin template
    result = CliRunner().invoke(app, ["templates", "describe", PLUGIN_TEMPLATE])

    # Then: it is described rather than reported unknown
    assert result.exit_code == 0, result.output
    assert f"{PLUGIN_MODULE}.{PLUGIN_TEMPLATE}" in result.output


def test_init_loads_plugin_templates__tc_k4f6_tpl_ep_004(plugin_entry: EntryPoint, isolated_root: Path) -> None:
    """TC-K4F6-TPL-EP-004: init --processing-template generates from a plugin-only template."""
    # Given: a plugin entry point whose template is not yet registered
    assert not _registered(PLUGIN_TEMPLATE)

    # When: generating a processing template from it
    result = CliRunner().invoke(app, ["init", "--processing-template", PLUGIN_TEMPLATE])

    # Then: both files are generated and the module imports
    assert result.exit_code == 0, result.output
    processing_path = isolated_root / "processing.py"
    assert (isolated_root / "tests" / "test_processing.py").exists()
    module = _import_generated(processing_path, "k4f6_generated_plugin_processing")
    assert issubclass(module.K4F6PluginProcessing, importlib.import_module(PLUGIN_MODULE).K4F6PluginTemplate)


def test_describe_without_the_plugin_is_still_unknown__tc_k4f6_tpl_bv_002(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-K4F6-TPL-BV-002: no installed plugin keeps the unknown-name usage error."""
    # Given: no rdetoolkit.plugins entry points at all
    discovery: Any = importlib.import_module("rdetoolkit.plugin.discovery")
    monkeypatch.setattr(discovery.metadata, "entry_points", lambda *, group: ())
    discovery.__dict__["_discovered"].clear()

    # When: describing the plugin-only template name
    result = CliRunner().invoke(app, ["templates", "describe", PLUGIN_TEMPLATE])

    # Then: it is a usage error
    assert result.exit_code == 3


def test_slot_type_names_use_the_public_module__tc_k4f6_tpl_ep_007() -> None:
    """TC-K4F6-TPL-EP-007: a Path slot renders ``from pathlib import Path`` on every interpreter.

    On Python 3.13 ``Path.__module__`` is ``pathlib._local``; a generated
    template must not import a private module (audit debt 2 of K4-F6).
    """
    from rdetoolkit.templates import ProcessingTemplate, slot

    class PathSkeletonTemplate(ProcessingTemplate):
        @slot
        def locate(self, root: Path) -> Path: ...

    spec = template_registry.get_template(f"{PathSkeletonTemplate.__module__}.{PathSkeletonTemplate.__qualname__}")
    assert spec.slots[0].parameters[0].type_name == "pathlib.Path"
    assert spec.slots[0].return_type == "pathlib.Path"
    source = _render_processing_module(spec)
    assert "from pathlib import Path\n" in source
    assert "_local" not in source
