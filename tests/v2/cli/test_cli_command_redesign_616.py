"""CLI command tree, help contract and v1 aliases after the #616 redesign.

| Test ID | Target | Condition | Expected |
|---|---|---|---|
| TC-616-TREE-001 | registered commands | walk the click tree | exactly the proposed noun-verb tree plus the five v1 aliases |
| TC-616-HELP-001 | every command and group | render ``--help`` | Examples and Exit codes sections present |
| TC-616-HELP-002 | every example line | inspect the help source | starts with ``rdetoolkit``, fits 74 columns, names a real command |
| TC-616-HELP-003 | root ``--help`` | render | panels in workflow order, Deprecated panel last |
| TC-616-OPT-001 | option names | walk every option | no ``--overwrite``/``--out``/``--output-archive`` outside the v1 aliases |
| TC-616-OPT-002 | single-output commands | inspect options | ``-o/--output`` |
| TC-616-ALIAS-001 | ``gen-config`` | invoke in a temp dir | warning naming ``new config`` on stderr, file written, v1 options kept |
| TC-616-ALIAS-002 | ``gen-invoice`` / ``make-excelinvoice`` / ``csv2graph`` / ``artifact`` | invoke with stubbed backends | warning naming the replacement, backend called |
| TC-616-ALIAS-003 | new names | invoke | no deprecation warning |
| TC-616-RC-001 | rc-only names | invoke ``graph`` / ``templates`` / ``nodes describe`` / ``run --flow`` | rejected by the parser (exit 2) |
| TC-616-RUN-001 | ``run`` | ``::`` without ``--legacy`` vs with it | both reach the legacy entry |
| TC-616-MIG-001 | ``migrate check`` | Python string / argv list / shell script using old names | one finding per renamed command naming the replacement |
| TC-616-MIG-002 | ``migrate check`` | current names only, incl. ``--legacy`` after TARGET | no finding |
| TC-616-MIG-003 | ``migrate check`` | argv list mixing literals and variables | old name in the literal part reported |
| TC-616-MIG-004 | ``migrate check`` | shell command continued with a trailing backslash | reported at the first physical line |
| TC-616-PY-001 | ``rdetoolkit.cli.app`` | import the v1.7.1 Python function names | importable with the v1.7.1 parameter names |
| TC-616-PY-002 | v1 Python names | call with v1 keyword arguments | the replacement's backend runs |
| TC-616-REN-001 | ``COMMAND_RENAMES`` | each row | v1 rows still registered, rc rows gone, replacement registered |
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import click
import pytest
import typer
from typer.testing import CliRunner

from rdetoolkit.cli._help import PANEL_DEPRECATED, SECTION_EXAMPLES, SECTION_EXIT_CODES
from rdetoolkit.cli._renames import COMMAND_RENAMES, find_renamed_commands
from rdetoolkit.cli.app import app

V1_ALIASES = {
    "gen-config": "rdetoolkit new config",
    "gen-invoice": "rdetoolkit new invoice",
    "make-excelinvoice": "rdetoolkit new excelinvoice",
    "csv2graph": "rdetoolkit plot",
    "artifact": "rdetoolkit package",
}

EXPECTED_TREE = {
    "init",
    "new",
    "new config",
    "new invoice",
    "new excelinvoice",
    "new processing",
    "plot",
    "validate",
    "validate invoice",
    "validate invoice-schema",
    "validate metadata",
    "validate metadata-def",
    "validate all",
    "run",
    "report",
    "report show",
    "report trace",
    "nodes",
    "nodes list",
    "nodes show",
    "nodes lint",
    "flows",
    "flows list",
    "flows show",
    "skeletons",
    "skeletons list",
    "skeletons show",
    "formats",
    "formats list",
    "package",
    "repro",
    "repro export",
    "repro import",
    "migrate",
    "migrate check",
    "migrate apply",
    "agent-guide",
    "version",
    *V1_ALIASES,
}

ROOT_PANEL_ORDER = ("Scaffold", "Generate", "Validate", "Run", "Inspect", "Package", "Migrate", "Info", PANEL_DEPRECATED)

_MAX_EXAMPLE_WIDTH = 74


def _root() -> click.Group:
    command = typer.main.get_command(app)
    assert isinstance(command, click.Group)
    return command


def _walk(command: click.Command, path: tuple[str, ...] = ()) -> Iterator[tuple[tuple[str, ...], click.Command]]:
    yield path, command
    if isinstance(command, click.Group):
        for name, sub in command.commands.items():
            yield from _walk(sub, (*path, name))


def _all_commands() -> list[tuple[tuple[str, ...], click.Command]]:
    return [(path, command) for path, command in _walk(_root())]


def _plain(text: str) -> str:
    return click.unstyle(text)


def _examples(command: click.Command) -> list[str]:
    match = re.search(r"```\n(.*?)\n```", command.help or "", re.S)
    assert match, f"no Examples block in the help source of {command.name}"
    return match.group(1).splitlines()


def _resolves(argv: list[str]) -> bool:
    """Whether ``argv`` (after ``rdetoolkit``) starts with a registered command path."""
    command: click.Command = _root()
    consumed = 0
    for token in argv:
        if not isinstance(command, click.Group) or token not in command.commands:
            break
        command = command.commands[token]
        consumed += 1
    return consumed > 0 and not isinstance(command, click.Group)


# --------------------------------------------------------------------------
# tree and help contract
# --------------------------------------------------------------------------


def test_command_tree_matches_the_proposal__tc_616_tree_001() -> None:
    # Given/When: every registered command path
    paths = {" ".join(path) for path, _ in _all_commands() if path}

    # Then: the tree is exactly the #616 proposal plus the v1 aliases
    assert paths == EXPECTED_TREE


@pytest.mark.parametrize("path", sorted(" ".join(p) for p, _ in _all_commands()))
def test_every_help_has_examples_and_exit_codes__tc_616_help_001(path: str) -> None:
    # Given: one command or group of the tree (the empty path is the root)
    argv = [*path.split(), "--help"] if path else ["--help"]

    # When: rendering its help the way a user does
    result = CliRunner().invoke(app, argv, env={"COLUMNS": "200", "NO_COLOR": "1"})

    # Then: the help states how to call it and what it returns
    output = _plain(result.output)
    assert result.exit_code == 0, output
    assert SECTION_EXAMPLES in output
    assert SECTION_EXIT_CODES in output


@pytest.mark.parametrize(("path", "command"), [(" ".join(p), c) for p, c in _all_commands()], ids=lambda value: value if isinstance(value, str) else "")
def test_examples_are_copy_pasteable__tc_616_help_002(path: str, command: click.Command) -> None:
    # Given: the example lines of one help text
    examples = _examples(command)

    # Then: at least two, each short enough not to wrap in an 80-column
    # terminal, and each invoking a command that exists
    assert len(examples) >= 2, path
    for line in examples:
        assert len(line) <= _MAX_EXAMPLE_WIDTH, f"{path}: example wraps: {line!r}"
        if line.startswith("    "):
            continue  # continuation of the previous example ('\\' line break)
        assert line.startswith(("rdetoolkit ", "python -m rdetoolkit ")), f"{path}: {line!r}"
        argv = line.split("rdetoolkit ", 1)[1].split()
        if argv[0].startswith("-"):
            continue  # root options such as --help
        assert _resolves(argv), f"{path}: example names no command: {line!r}"


def test_root_help_groups_commands_by_workflow_phase__tc_616_help_003() -> None:
    # When: rendering the root help
    result = CliRunner().invoke(app, ["--help"], env={"COLUMNS": "200", "NO_COLOR": "1"})
    output = _plain(result.output)

    # Then: every panel is present, in workflow order
    positions = [output.find(f"─ {panel} ") for panel in ROOT_PANEL_ORDER]
    assert all(position >= 0 for position in positions), dict(zip(ROOT_PANEL_ORDER, positions, strict=True))
    assert positions == sorted(positions)
    # And: the v1 aliases are listed only in the Deprecated panel
    for alias in V1_ALIASES:
        assert alias in output[positions[-1] :]
        assert alias not in output[: positions[-1]]


# --------------------------------------------------------------------------
# option names
# --------------------------------------------------------------------------


def test_option_names_are_unified__tc_616_opt_001() -> None:
    # Given: every option of every non-alias command
    retired = {"--overwrite", "--out", "--output-archive", "--flow", "--processing-template"}
    offenders = [
        (" ".join(path), option)
        for path, command in _all_commands()
        if path and path[0] not in V1_ALIASES
        for parameter in command.params
        if isinstance(parameter, click.Option)
        for option in parameter.opts
        if option in retired
    ]

    # Then: the retired spellings survive only on the v1 aliases
    assert offenders == []


@pytest.mark.parametrize(
    "path",
    ["new config", "new invoice", "new excelinvoice", "new processing", "package", "repro export", "migrate apply"],
)
def test_single_output_commands_use_dash_o_output__tc_616_opt_002(path: str) -> None:
    command = {" ".join(p): c for p, c in _all_commands()}[path]
    opts = {tuple(sorted(parameter.opts)) for parameter in command.params if isinstance(parameter, click.Option)}
    assert ("--output", "-o") in opts


# --------------------------------------------------------------------------
# v1 aliases
# --------------------------------------------------------------------------


def _warning_lines(result: click.testing.Result) -> str:
    return _plain(result.stderr)


def test_gen_config_alias_warns_and_keeps_v1_options__tc_616_alias_001(tmp_path: Path) -> None:
    # Given: the v1 spelling with its v1-only option names
    target = tmp_path / "cfg"

    # When: running it
    result = CliRunner().invoke(app, ["gen-config", str(target), "--template", "full", "--overwrite"])

    # Then: it warns, names the replacement, and still writes the file
    assert result.exit_code == 0, result.output
    stderr = _warning_lines(result)
    assert "'rdetoolkit gen-config' is deprecated" in stderr
    assert "Remediation: use 'rdetoolkit new config'" in stderr
    assert (target / "rdeconfig.yaml").is_file()


def test_new_config_writes_the_same_file_without_warning__tc_616_alias_003(tmp_path: Path) -> None:
    # Given: the same request through the new name and option spellings
    old_dir, new_dir = tmp_path / "old", tmp_path / "new"
    CliRunner().invoke(app, ["gen-config", str(old_dir), "--template", "multitile"])

    # When: generating with the replacement command
    result = CliRunner().invoke(app, ["new", "config", "-o", str(new_dir), "--preset", "multitile", "--force"])

    # Then: identical output and no deprecation warning
    assert result.exit_code == 0, result.output
    assert "deprecated" not in _plain(result.stderr)
    assert (new_dir / "rdeconfig.yaml").read_text(encoding="utf-8") == (old_dir / "rdeconfig.yaml").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("argv", "backend"),
    [
        (["gen-invoice", "{schema}", "-o", "{out}/invoice.json"], "rdetoolkit.cmd.gen_invoice.GenerateInvoiceCommand.invoke"),
        (["make-excelinvoice", "{schema}", "-o", "{out}/a_excel_invoice.xlsx"], "rdetoolkit.cmd.gen_excelinvoice.GenerateExcelInvoiceCommand.invoke"),
        (["csv2graph", "{csv}", "-o", "{out}"], "rdetoolkit.cmd.csv2graph.Csv2GraphCommand.invoke"),
        (["artifact", "-s", "{out}", "--output-archive", "{out}.zip"], "rdetoolkit.cmd.archive.CreateArtifactCommand.invoke"),
    ],
)
def test_v1_aliases_warn_and_run_the_replacement__tc_616_alias_002(
    argv: list[str],
    backend: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: inputs on disk and the command backend replaced by a recorder
    schema = tmp_path / "invoice.schema.json"
    schema.write_text('{"type": "object", "properties": {}}', encoding="utf-8")
    csv = tmp_path / "data.csv"
    csv.write_text("x,y\n1,2\n", encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()
    calls: list[object] = []
    monkeypatch.setattr(backend, lambda self: calls.append(self))
    rendered = [part.format(schema=schema, csv=csv, out=out) for part in argv]

    # When: invoking the v1 name
    result = CliRunner().invoke(app, rendered)

    # Then: the backend ran once, after a warning naming the replacement
    assert result.exit_code == 0, result.output
    assert len(calls) == 1
    stderr = _warning_lines(result)
    assert f"'rdetoolkit {argv[0]}' is deprecated" in stderr
    assert f"use '{V1_ALIASES[argv[0]]}'" in stderr


@pytest.mark.parametrize(
    "argv",
    [
        ["graph", "report.json"],
        ["templates", "list"],
        ["nodes", "describe", "x"],
        ["flows", "describe", "x"],
        ["run", "--flow", "pkg.mod:pipeline"],
        ["migrate", "apply", ".", "--out", "x"],
    ],
)
def test_rc_only_names_are_removed_without_alias__tc_616_rc_001(argv: list[str]) -> None:
    # When: invoking a name that only existed in v2 release candidates
    result = CliRunner().invoke(app, argv)

    # Then: the parser rejects it
    assert result.exit_code == 2, result.output


@pytest.mark.parametrize("argv_prefix", [[], ["--legacy"]])
def test_legacy_target_runs_with_and_without_flag__tc_616_run_001(
    argv_prefix: list[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a v1 dataset function in a file and a stubbed v1 entry point
    from rdetoolkit import cli as cli_module

    source = tmp_path / "main.py"
    source.write_text("def dataset(srcpaths, resource_paths):\n    return None\n", encoding="utf-8")
    seen: list[str] = []

    def _stub_run(*, custom_dataset_function: object) -> str:
        seen.append(getattr(custom_dataset_function, "__name__", ""))
        return "run-ok"

    monkeypatch.setattr(cli_module.workflows, "run", _stub_run)

    # When: running the '::' form, with and without --legacy
    result = CliRunner().invoke(app, ["run", *argv_prefix, f"{source}::dataset"])

    # Then: both reach the v1 entry; the output stays exactly the v1 payload
    assert result.exit_code == 0, result.output
    assert result.output.strip() == "run-ok"
    assert seen == ["dataset"]


# --------------------------------------------------------------------------
# migrate check
# --------------------------------------------------------------------------


def test_migrate_check_reports_renamed_commands__tc_616_mig_001(tmp_path: Path) -> None:
    # Given: a project that calls old command names from Python and from shell
    (tmp_path / "build.py").write_text(
        "import subprocess\n"
        'subprocess.run(["rdetoolkit", "gen-config", "."])\n'
        'CMD = "python -m rdetoolkit csv2graph data.csv"\n',
        encoding="utf-8",
    )
    (tmp_path / "ci.sh").write_text(
        "#!/bin/sh\nrdetoolkit run --flow modules.processing:pipeline\nrdetoolkit artifact -s container\n",
        encoding="utf-8",
    )

    # When: checking the project
    result = CliRunner().invoke(app, ["migrate", "check", str(tmp_path)])

    # Then: each use is reported with its line and replacement
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert f"{tmp_path / 'build.py'}:2: renamed CLI command 'rdetoolkit gen-config [--template X] [--overwrite]' -> use 'rdetoolkit new config [--preset X] [--force]'" in lines
    assert any(line.startswith(f"{tmp_path / 'build.py'}:3: renamed CLI command 'rdetoolkit csv2graph'") for line in lines)
    assert f"{tmp_path / 'ci.sh'}:2: renamed CLI command 'rdetoolkit run --flow X' -> use 'rdetoolkit run X'" in lines
    assert any(line.startswith(f"{tmp_path / 'ci.sh'}:3: renamed CLI command 'rdetoolkit artifact") for line in lines)
    assert len(lines) == 4


def test_migrate_check_is_silent_for_current_names__tc_616_mig_002(tmp_path: Path) -> None:
    # Given: scripts that already use the v2.0 names
    (tmp_path / "ci.sh").write_text(
        "rdetoolkit new config --preset full\nrdetoolkit run modules.processing:pipeline\n"
        "rdetoolkit run --legacy main.py::dataset\nrdetoolkit run main.py::dataset --legacy\n"
        "rdetoolkit report trace r.json\nrdetoolkit plot a.csv\n"
        "rdetoolkit run \\\n  modules.processing:pipeline \\\n  --config c.yaml\n",
        encoding="utf-8",
    )
    (tmp_path / "build.py").write_text(
        "import subprocess\n"
        'subprocess.run(["rdetoolkit", "run", "main.py::dataset", "--legacy"])\n'
        'subprocess.run(["rdetoolkit", "run", flow_ref, "--config", config_path])\n',
        encoding="utf-8",
    )

    # When/Then: nothing to report
    result = CliRunner().invoke(app, ["migrate", "check", str(tmp_path)])
    assert result.exit_code == 0
    assert result.output == ""


def test_migrate_check_reads_argv_lists_with_variables__tc_616_mig_003(tmp_path: Path) -> None:
    # Given: argv lists whose command part is literal but whose arguments are variables
    (tmp_path / "build.py").write_text(
        "import subprocess, sys\n"
        'subprocess.run(["rdetoolkit", "run", "--flow", flow_ref])\n'
        'subprocess.run([sys.executable, "-m", "rdetoolkit", "templates", "list", *extra])\n'
        'subprocess.run(["rdetoolkit", "run", f"{module}::dataset"])\n',
        encoding="utf-8",
    )

    # When: checking the project
    result = CliRunner().invoke(app, ["migrate", "check", str(tmp_path)])

    # Then: the literal command names are reported
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert f"{tmp_path / 'build.py'}:2: renamed CLI command 'rdetoolkit run --flow X' -> use 'rdetoolkit run X'" in lines
    assert any(line.startswith(f"{tmp_path / 'build.py'}:3: renamed CLI command 'rdetoolkit templates") for line in lines)
    assert any(line.startswith(f"{tmp_path / 'build.py'}:4: renamed CLI command 'rdetoolkit run TARGET'") for line in lines)
    assert len(lines) == 3


def test_migrate_check_joins_shell_line_continuations__tc_616_mig_004(tmp_path: Path) -> None:
    # Given: an old option on a continuation line
    (tmp_path / "ci.sh").write_text(
        "#!/bin/sh\nrdetoolkit run \\\n  --flow modules.processing:pipeline\necho done\n",
        encoding="utf-8",
    )

    # When: checking the project
    result = CliRunner().invoke(app, ["migrate", "check", str(tmp_path)])

    # Then: the command is reported once, at the line where it starts
    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        f"{tmp_path / 'ci.sh'}:2: renamed CLI command 'rdetoolkit run --flow X' -> use 'rdetoolkit run X'",
    ]


#: Parameter names of the CLI functions in rdetoolkit 1.7.1 ``rdetoolkit/cli/app.pyi``.
_V1_PYTHON_SIGNATURES = {
    "init": ["template", "entry_point", "modules", "tasksupport", "inputdata", "other"],
    "version": [],
    "run": ["target"],
    "gen_config": ["output_dir", "template_name", "overwrite", "lang"],
    "artifact": ["source_dir", "output_archive", "exclude"],
    "gen_invoice": ["schema_path", "output_path", "fill_defaults", "required_only", "output_format"],
    "make_excelinvoice": ["invoice_schema_json_path", "output_path", "mode"],
    "csv2graph": [
        "csv_path", "output_dir", "main_image_dir", "html_output_dir", "csv_format", "logy", "logx", "html", "mode",
        "x_col", "y_cols", "direction_cols", "direction_filter", "direction_colors", "title", "legend_info",
        "legend_loc", "xlim", "ylim", "grid", "invert_x", "invert_y", "no_individual", "max_legend_items",
        "legend_policy", "legend_outside_threshold", "legend_bottom_threshold", "legend_ncol",
        "x_tick_format", "y_tick_format",
    ],
    "parse_column": ["col"],
    "validate_json_file": ["value"],
}


@pytest.mark.parametrize("name", sorted(_V1_PYTHON_SIGNATURES))
def test_v1_python_names_stay_importable__tc_616_py_001(name: str) -> None:
    import importlib
    import inspect

    app_module = importlib.import_module("rdetoolkit.cli.app")

    # When: importing a v1.7.1 function name from rdetoolkit.cli.app
    function = getattr(app_module, name)

    # Then: it keeps the v1.7.1 parameter names (v2 may add keyword parameters after them)
    parameters = list(inspect.signature(function).parameters)
    assert parameters[: len(_V1_PYTHON_SIGNATURES[name])] == _V1_PYTHON_SIGNATURES[name]


def test_v1_python_names_accept_v1_keywords__tc_616_py_002(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from rdetoolkit import cli as cli_module
    from rdetoolkit.cli.app import csv2graph, gen_invoice, make_excelinvoice, run

    # Given: inputs on disk and every backend replaced by a recorder
    schema = tmp_path / "invoice.schema.json"
    schema.write_text('{"type": "object", "properties": {}}', encoding="utf-8")
    csv = tmp_path / "data.csv"
    csv.write_text("x,y\n1,2\n", encoding="utf-8")
    source = tmp_path / "main.py"
    source.write_text("def dataset(srcpaths, resource_paths):\n    return None\n", encoding="utf-8")
    calls: list[str] = []
    for backend in (
        "rdetoolkit.cmd.gen_invoice.GenerateInvoiceCommand.invoke",
        "rdetoolkit.cmd.gen_excelinvoice.GenerateExcelInvoiceCommand.invoke",
        "rdetoolkit.cmd.csv2graph.Csv2GraphCommand.invoke",
    ):
        monkeypatch.setattr(backend, lambda self, backend=backend: calls.append(backend.split(".")[2]))
    monkeypatch.setattr(cli_module.workflows, "run", lambda *, custom_dataset_function: calls.append("workflows.run"))

    # When: calling them the v1 way, with v1 keyword arguments
    gen_invoice(schema_path=schema, output_path=tmp_path / "invoice.json")
    make_excelinvoice(invoice_schema_json_path=schema, output_path=tmp_path / "a_excel_invoice.xlsx", mode="file")
    csv2graph(csv_path=csv, output_dir=tmp_path)
    run(target=f"{source}::dataset")

    # Then: each reached its backend
    assert calls == ["gen_invoice", "gen_excelinvoice", "csv2graph", "workflows.run"]


@pytest.mark.parametrize("rename", COMMAND_RENAMES, ids=lambda rename: rename.old)
def test_rename_table_matches_the_tree__tc_616_ren_001(rename: object) -> None:
    from rdetoolkit.cli._renames import CommandRename

    assert isinstance(rename, CommandRename)
    root = _root()
    old_command = rename.old.split()[1]
    new_argv = [token.split("|")[0] for token in rename.new.split()[1:] if not token.startswith(("-", "[")) and token.upper() != token]
    # Then: v1 command names are still registered; rc-only ones are gone
    if rename.alias_kept and old_command != "run":
        assert old_command in root.commands
    if not rename.alias_kept and old_command in {"graph", "templates"}:
        assert old_command not in root.commands
    # And: the replacement exists, and the old spelling is what the pattern finds
    assert _resolves(new_argv), rename.new
    assert rename in find_renamed_commands(rename.old.replace(" X", " x").replace("TARGET", "main.py::f").replace("REPORT", "r.json"))
