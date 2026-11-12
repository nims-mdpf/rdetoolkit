"""Slot signatures survive template generation (Session RC1-INT-CLI, review item F07).

``_render_slot`` rendered ``read(self, *, value: int = 3)`` as
``read(self, value: int)``: the generated class failed the skeleton's own
signature check (2102) on import, and a defaulted argument the skeleton flow
omits was lost. ``TemplateParameterSpec`` now also records the parameter kind
and the default (absent vs present), and generation reproduces the skeleton
signature exactly -- ``/``, ``*``, ``*args``, ``**kwargs`` and annotations --
keeping defaults: literal ones as their ``repr``, anything else resolved from
the skeleton's own signature when the generated module is imported.

EP table:
    TC-RC1-F07-EP-001 | keyword-only slot with a default        | exact ``*`` signature, imports, omitted arg defaults
    TC-RC1-F07-EP-002 | positional-only slot (``/``)             | exact ``/`` signature, imports, call works
    TC-RC1-F07-EP-003 | ``*args: int`` slot                      | exact ``*values: int``, call works
    TC-RC1-F07-EP-004 | ``**kwargs: str`` slot                   | exact ``**labels: str``, call works
    TC-RC1-F07-EP-005 | mixed kinds and literal defaults         | exact signature, defaults equal the skeleton's
    TC-RC1-F07-EP-006 | non-literal defaults (object, Path, nan) | no ``...``/``None`` substitute; same objects
    TC-RC1-F07-EP-007 | registry spec + describe --json          | kind/default/default_literal recorded additively

BV table:
    TC-RC1-F07-BV-001 | default ``None`` vs no default           | ``"None"`` vs ``None`` -- distinguishable
    TC-RC1-F07-BV-002 | str subclass whose repr is a str literal | treated as non-literal; type preserved
    TC-RC1-F07-BV-003 | default whose ``==`` raises              | treated as non-literal; no crash
    TC-RC1-F07-BV-004 | legacy two-field TemplateParameterSpec   | positional_or_keyword, no default, renders as before
    TC-RC1-F07-BV-005 | default whose ``__repr__`` raises        | registration survives; object repr shown; skeleton object used
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import json
import math
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from typer.testing import CliRunner

from rdetoolkit.cli.app import app
from rdetoolkit.cli.templates_cmd import _render_processing_module, generate_processing_template
from rdetoolkit.templates import registry as template_registry
from rdetoolkit.templates.registry import TemplateMethodSpec, TemplateParameterSpec, TemplateSpec

_HEADER = "from __future__ import annotations\n\nfrom rdetoolkit.templates import ProcessingTemplate, slot\n"


def _import_path(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _generate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
    skeleton_name: str,
    provider_source: str,
    body: str,
) -> tuple[ModuleType, type[Any], str]:
    """Register a provider skeleton, generate its class, fill the TODO body, import it."""
    provider_dir = tmp_path / "provider"
    provider_dir.mkdir()
    (provider_dir / f"{module_name}.py").write_text(_HEADER + provider_source, encoding="utf-8")
    monkeypatch.syspath_prepend(str(provider_dir))
    provider = importlib.import_module(module_name)
    output = tmp_path / "generated"
    generate_processing_template(f"{module_name}.{skeleton_name}", [module_name], output)
    source = (output / "processing.py").read_text(encoding="utf-8")
    # The user's job after generation: replace the TODO body, keep the signature.
    filled = source.replace(
        "        # TODO: implement the read template slot.\n        raise NotImplementedError\n",
        f"        {body}\n",
    )
    assert filled != source
    (output / "processing.py").write_text(filled, encoding="utf-8")
    generated_module = _import_path(f"{module_name}_generated", output / "processing.py")
    generated = next(
        value
        for value in vars(generated_module).values()
        if isinstance(value, type) and issubclass(value, getattr(provider, skeleton_name)) and value is not getattr(provider, skeleton_name)
    )
    return provider, generated, source


def _defaults(function: Any) -> dict[str, Any]:
    return {
        name: parameter.default
        for name, parameter in inspect.signature(function).parameters.items()
        if parameter.default is not inspect.Parameter.empty
    }


def test_keyword_only_default_is_kept__tc_rc1_f07_ep_001(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-RC1-F07-EP-001: the reviewer's keyword-only slot generates an importable class."""
    # Given: a skeleton whose flow omits a keyword-only defaulted argument
    provider_source = (
        "class Rc1KwTemplate(ProcessingTemplate):\n"
        "    @slot\n"
        "    def read(self, *, value: int = 3) -> int:\n"
        "        raise NotImplementedError\n"
        "    def __flow__(self) -> int:\n"
        "        return self.read()\n"
    )
    # When: the class is generated, its body filled and the module imported
    provider, generated, source = _generate(tmp_path, monkeypatch, "rc1_f07_kw", "Rc1KwTemplate", provider_source, "return value")
    # Then: the signature is reproduced exactly and the flow runs with the default
    assert "    def read(self, *, value: int = 3) -> int:\n" in source
    assert _defaults(generated.read) == _defaults(provider.Rc1KwTemplate.read) == {"value": 3}
    assert generated().__flow__() == 3


def test_positional_only_marker_is_kept__tc_rc1_f07_ep_002(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-RC1-F07-EP-002: ``/`` survives generation."""
    # Given: a skeleton slot with a positional-only parameter
    provider_source = (
        "class Rc1PosTemplate(ProcessingTemplate):\n"
        "    @slot\n"
        "    def read(self, a: int, /, b: int) -> int:\n"
        "        raise NotImplementedError\n"
        "    def __flow__(self) -> int:\n"
        "        return self.read(1, b=2)\n"
    )
    # When: the class is generated and imported
    _, generated, source = _generate(tmp_path, monkeypatch, "rc1_f07_pos", "Rc1PosTemplate", provider_source, "return a + b")
    # Then: the marker is present, the import passes the signature check and the call works
    assert "    def read(self, a: int, /, b: int) -> int:\n" in source
    assert generated().__flow__() == 3


def test_var_positional_is_kept__tc_rc1_f07_ep_003(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-RC1-F07-EP-003: ``*args: int`` survives generation."""
    # Given: a skeleton slot taking variadic positionals
    provider_source = (
        "class Rc1ArgsTemplate(ProcessingTemplate):\n"
        "    @slot\n"
        "    def read(self, *values: int) -> int:\n"
        "        raise NotImplementedError\n"
        "    def __flow__(self) -> int:\n"
        "        return self.read(1, 2, 3)\n"
    )
    # When: the class is generated and imported
    _, generated, source = _generate(tmp_path, monkeypatch, "rc1_f07_args", "Rc1ArgsTemplate", provider_source, "return sum(values)")
    # Then: the star parameter is reproduced with its annotation
    assert "    def read(self, *values: int) -> int:\n" in source
    assert generated().__flow__() == 6


def test_var_keyword_is_kept__tc_rc1_f07_ep_004(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-RC1-F07-EP-004: ``**kwargs: str`` survives generation."""
    # Given: a skeleton slot taking variadic keywords
    provider_source = (
        "class Rc1KwargsTemplate(ProcessingTemplate):\n"
        "    @slot\n"
        "    def read(self, **labels: str) -> str:\n"
        "        raise NotImplementedError\n"
        "    def __flow__(self) -> str:\n"
        "        return self.read(b='2', a='1')\n"
    )
    # When: the class is generated and imported
    _, generated, source = _generate(
        tmp_path, monkeypatch, "rc1_f07_kwargs", "Rc1KwargsTemplate", provider_source, "return ','.join(sorted(labels))",
    )
    # Then: the double-star parameter is reproduced with its annotation
    assert "    def read(self, **labels: str) -> str:\n" in source
    assert generated().__flow__() == "a,b"


def test_mixed_kinds_and_literal_defaults__tc_rc1_f07_ep_005(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-RC1-F07-EP-005: every kind in one signature, with literal defaults rendered as repr."""
    # Given: a slot mixing all five kinds and several literal defaults
    provider_source = (
        "class Rc1MixedTemplate(ProcessingTemplate):\n"
        "    @slot\n"
        "    def read(self, a: int, /, b: int = -2, *rest: int, c: str = \"it's\", d: tuple[int, ...] = (1, 2),"
        " e: int | None = None, f: int, **extra: str) -> str:\n"
        "        raise NotImplementedError\n"
        "    def __flow__(self) -> str:\n"
        "        return self.read(1, f=5)\n"
    )
    # When: the class is generated and imported
    provider, generated, source = _generate(
        tmp_path, monkeypatch, "rc1_f07_mixed", "Rc1MixedTemplate", provider_source, "return repr((a, b, rest, c, d, e, f, extra))",
    )
    # Then: the signature is reproduced verbatim and omitted arguments take the skeleton's defaults
    assert (
        "    def read(self, a: int, /, b: int = -2, *rest: int, c: str = \"it's\", d: tuple[int, ...] = (1, 2),"
        " e: int | None = None, f: int, **extra: str) -> str:\n"
    ) in source
    assert _defaults(generated.read) == _defaults(provider.Rc1MixedTemplate.read)
    assert generated().__flow__() == repr((1, -2, (), "it's", (1, 2), None, 5, {}))


def test_non_literal_defaults_resolve_to_skeleton_objects__tc_rc1_f07_ep_006(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-RC1-F07-EP-006: non-literal defaults are the skeleton's own objects, never a substitute."""
    # Given: a slot whose defaults are a module constant object, a Path and a NaN
    provider_source = (
        "from pathlib import Path\n"
        "SENTINEL = object()\n"
        "class Rc1ObjectTemplate(ProcessingTemplate):\n"
        "    @slot\n"
        "    def read(self, marker: object = SENTINEL, *, where: Path = Path('x'), ratio: float = float('nan')) -> tuple:\n"
        "        raise NotImplementedError\n"
        "    def __flow__(self) -> tuple:\n"
        "        return self.read()\n"
    )
    # When: the class is generated and imported
    provider, generated, source = _generate(
        tmp_path, monkeypatch, "rc1_f07_object", "Rc1ObjectTemplate", provider_source, "return (marker, where, ratio)",
    )
    # Then: no placeholder default was written and every default is the identical skeleton object
    signature_line = next(line for line in source.splitlines() if line.startswith("    def read("))
    assert "= ..." not in signature_line and "= None" not in signature_line and "PosixPath" not in signature_line
    skeleton_defaults = _defaults(provider.Rc1ObjectTemplate.read)
    generated_defaults = _defaults(generated.read)
    assert generated_defaults.keys() == skeleton_defaults.keys() == {"marker", "where", "ratio"}
    assert all(generated_defaults[name] is skeleton_defaults[name] for name in skeleton_defaults)
    marker, where, ratio = generated().__flow__()
    assert marker is provider.SENTINEL
    assert where == Path("x")
    assert math.isnan(ratio)


def test_registry_and_describe_record_kind_and_default__tc_rc1_f07_ep_007(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-RC1-F07-EP-007: kind and default are part of the spec and the describe JSON."""
    # Given: a registered skeleton with a keyword-only literal default and a non-literal default
    provider_dir = tmp_path / "provider"
    provider_dir.mkdir()
    (provider_dir / "rc1_f07_spec.py").write_text(
        _HEADER
        + "from pathlib import Path\n"
        "class Rc1SpecTemplate(ProcessingTemplate):\n"
        "    @slot\n"
        "    def read(self, plain: int, *, value: int = 3, where: Path = Path('x')) -> int:\n"
        "        raise NotImplementedError\n"
        "    def __flow__(self) -> int:\n"
        "        return self.read(1)\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(provider_dir))
    importlib.import_module("rc1_f07_spec")
    # When: the registry spec is read and described as JSON
    spec = template_registry.get_template("rc1_f07_spec.Rc1SpecTemplate")
    result = CliRunner().invoke(app, ["skeletons", "show", "rc1_f07_spec.Rc1SpecTemplate", "--json", "--module", "rc1_f07_spec"])
    # Then: each parameter records its kind and default presence additively
    plain, value, where = spec.slots[0].parameters
    assert (plain.kind, plain.default, plain.default_literal) == ("positional_or_keyword", None, False)
    assert (value.kind, value.default, value.default_literal) == ("keyword_only", "3", True)
    assert (where.kind, where.default_literal) == ("keyword_only", False)
    assert where.default is not None
    assert result.exit_code == 0, result.output
    described = json.loads(result.output)["slots"][0]["parameters"]
    assert described[1] == {"name": "value", "type_name": "int", "kind": "keyword_only", "default": "3", "default_literal": True}
    assert described[0]["default"] is None


def test_none_default_is_distinguishable_from_no_default__tc_rc1_f07_bv_001(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-RC1-F07-BV-001: ``= None`` is recorded and rendered; an absent default is not."""
    # Given: one parameter defaulting to None beside one without a default
    provider_source = (
        "class Rc1NoneTemplate(ProcessingTemplate):\n"
        "    @slot\n"
        "    def read(self, required: int, optional: int | None = None) -> int:\n"
        "        raise NotImplementedError\n"
        "    def __flow__(self) -> int:\n"
        "        return self.read(4)\n"
    )
    # When: the class is generated and imported
    _, generated, source = _generate(
        tmp_path, monkeypatch, "rc1_f07_none", "Rc1NoneTemplate", provider_source, "return required if optional is None else -1",
    )
    # Then: the two parameters differ exactly in default presence
    required, optional = template_registry.get_template("rc1_f07_none.Rc1NoneTemplate").slots[0].parameters
    assert required.default is None
    assert optional.default == "None"
    assert "    def read(self, required: int, optional: int | None = None) -> int:\n" in source
    assert generated().__flow__() == 4


def test_str_subclass_default_keeps_its_type__tc_rc1_f07_bv_002(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-RC1-F07-BV-002: a repr that evaluates to a different type is not treated as literal."""
    # Given: a default of a str subclass whose repr is a plain string literal
    provider_source = (
        "class Label(str):\n"
        "    pass\n"
        "DEFAULT_LABEL = Label('x')\n"
        "class Rc1LabelTemplate(ProcessingTemplate):\n"
        "    @slot\n"
        "    def read(self, label: str = DEFAULT_LABEL) -> str:\n"
        "        raise NotImplementedError\n"
        "    def __flow__(self) -> str:\n"
        "        return self.read()\n"
    )
    # When: the class is generated and imported
    provider, generated, _ = _generate(tmp_path, monkeypatch, "rc1_f07_label", "Rc1LabelTemplate", provider_source, "return label")
    # Then: the default is the skeleton's Label object, not a plain-str substitute
    assert template_registry.get_template("rc1_f07_label.Rc1LabelTemplate").slots[0].parameters[0].default_literal is False
    assert type(generated().__flow__()) is provider.Label


def test_default_with_raising_eq_is_non_literal__tc_rc1_f07_bv_003(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-RC1-F07-BV-003: a default whose comparison raises is resolved from the skeleton, not rendered."""
    # Given: an int subclass default whose ``==`` raises
    provider_source = (
        "class Strict(int):\n"
        "    def __eq__(self, other: object) -> bool:\n"
        "        raise TypeError('no comparison')\n"
        "    __hash__ = int.__hash__\n"
        "STRICT = Strict(5)\n"
        "class Rc1StrictTemplate(ProcessingTemplate):\n"
        "    @slot\n"
        "    def read(self, value: int = STRICT) -> int:\n"
        "        raise NotImplementedError\n"
        "    def __flow__(self) -> int:\n"
        "        return self.read()\n"
    )
    # When: the class is generated and imported
    provider, generated, _ = _generate(tmp_path, monkeypatch, "rc1_f07_strict", "Rc1StrictTemplate", provider_source, "return value")
    # Then: registration did not crash and the default is the skeleton's object
    assert template_registry.get_template("rc1_f07_strict.Rc1StrictTemplate").slots[0].parameters[0].default_literal is False
    assert generated().__flow__() is provider.STRICT


def test_two_field_spec_renders_as_before__tc_rc1_f07_bv_004() -> None:
    """TC-RC1-F07-BV-004: the additive fields default so existing construction is unchanged."""
    # Given: a parameter spec built with only the original two fields
    parameter = TemplateParameterSpec(name="count", type_name="int")
    spec = TemplateSpec(
        id="pkg.skeletons.DemoTemplate",
        name="DemoTemplate",
        slots=(TemplateMethodSpec(name="read", parameters=(parameter,), return_type="str"),),
        hooks=(),
        domain_types=(),
    )
    # When: the module is rendered
    source = _render_processing_module(spec)
    # Then: it keeps the positional-or-keyword, default-free rendering
    assert (parameter.kind, parameter.default, parameter.default_literal) == ("positional_or_keyword", None, False)
    assert "    def read(self, count: int) -> str:\n" in source
    assert "_skeleton_default" not in source


def test_default_with_raising_repr_is_registered__tc_rc1_f07_bv_005(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-RC1-F07-BV-005: a default whose ``__repr__`` raises neither breaks registration nor generation."""
    # Given: a registered skeleton whose slot default object has a raising repr
    provider_dir = tmp_path / "provider"
    provider_dir.mkdir()
    (provider_dir / "rc1_f07_opaque.py").write_text(
        _HEADER
        + "class Opaque:\n"
        "    def __repr__(self) -> str:\n"
        "        raise RuntimeError('no repr')\n"
        "OPAQUE = Opaque()\n"
        "class Rc1OpaqueTemplate(ProcessingTemplate):\n"
        "    @slot\n"
        "    def read(self, value: object = OPAQUE) -> object:\n"
        "        raise NotImplementedError\n"
        "    def __flow__(self) -> object:\n"
        "        return self.read()\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(provider_dir))
    importlib.import_module("rc1_f07_opaque")
    # When: the spec is read and the processing module is generated
    parameter = template_registry.get_template("rc1_f07_opaque.Rc1OpaqueTemplate").slots[0].parameters[0]
    output = tmp_path / "generated"
    generate_processing_template("rc1_f07_opaque.Rc1OpaqueTemplate", ["rc1_f07_opaque"], output)
    source = (output / "processing.py").read_text(encoding="utf-8")
    # Then: the spec shows the object-level repr, is non-literal, and generation defers to the skeleton default
    assert parameter.default is not None
    assert parameter.default.startswith("<rc1_f07_opaque.Opaque object at ")
    assert parameter.default_literal is False
    assert "    def read(self, value: object = _skeleton_default('read', 'value')) -> object:\n" in source
