"""Coding-agent readiness gate (#676): the public author-test-debug-fix loop on all five modes.

For each mode the gate builds a project with the public CLI (``corpus``) and
drives the documented command sequence in separate processes, the way an agent
following the shipped Skills does:

    new config / new invoice / new excelinvoice  ->  nodes lint --json, flows list --json
    ->  doctor --format json  ->  run (failing input)  ->  run report + events
    ->  report diagnose --json / report explain --format json  ->  repair
    ->  run (same project)  ->  artifact assertions  ->  re-diagnose the old report

The doctor, run, diagnose, lint and discovery commands are taken verbatim from
the Skill text of a separately installed, version-matched Skills pack, never
from a copy in this file. Nothing under ``src/`` and no rdetoolkit module is
imported (only this package, ``scripts/agent_readiness_gate.py`` and
third-party libraries): every rdetoolkit call is a subprocess of the installed
interpreter. No model call or network access is involved.

Independent oracles: expected tile order, tile names and values come from the
corpus definition (and, for SmartTable's row order, the frozen v1 contract);
codes come from the user code's ``ecode``; JSON shapes come from the published
schemas under ``docs/usage``. Nothing is compared with an earlier v2 run except
where the v1 callback smoke compares the two entry points with each other.

EP table:

| ID | Partition | Expected |
|----|-----------|----------|
| ARG-PACK | installed Skills pack | receipt version == installed runtime, five Skills, runtime outside the checkout when required |
| ARG-NEW-{MODE} | new-code workflow files | no v1 entry point (``custom_dataset_function``, ``--legacy``, v1 path types) |
| ARG-DISCOVER-{MODE} | lint / flows / Skill discovery | lint passed, ``processing.pipeline`` listed, every discovery command emits JSON |
| ARG-DOCTOR-{MODE} | doctor preflight | passed, detected mode, flow not executed, nothing written |
| ARG-FAIL-{MODE} | failing input (fail_fast) | exit 1, failed at the broken tile, code 1, job.failed, events and diagnosis name the same call |
| ARG-REPAIR-{MODE} | repaired input, same project | exit 0, every tile's structured / metadata (units, variable rows) / invoice / raw artifact |
| ARG-STALE-{MODE} | old report after the rerun | still the old run's failure; overwritten iteration details flagged mismatched, never borrowed |
| ARG-PRIVACY-{MODE} | fake secret in input and environment | present in job.failed and the run report, absent from every agent-facing JSON view |
| ARG-CONTRACT-{MODE} | JSON outputs | stdout is exactly one document; envelopes validate against the published schemas |
| ARG-PARTIAL | MultiDataTile, ``continue``, healthy tile after the broken one | exit 2, partial, only the broken tile failed, the later tile completed and published; ``diagnose --fail-on-error`` exits 1 |
| ARG-V1-{MODE} | ``run --legacy`` v1 callback | same structured / invoice / raw artifacts and job.failed as the v2 flow |
| ARG-MIGRATE | migration Skill worked example | v1 entry, converted flow and artifact-node flow agree (installed Skill copy) |

BV table:

| ID | Boundary | Expected |
|----|----------|----------|
| ARG-FAIL-INV | single-tile mode, its only tile broken | zero completed tiles, one failed iteration |
| ARG-FAIL-SMT | broken row runs first (last row is tile 0) | exactly one iteration recorded |
| ARG-FAIL-{XLS,MDT,RDF} | broken second tile | tile 0 completed and published (read before the repair rerun), tile 1 failed |
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from scripts.agent_readiness_gate import REQUIRE_INSTALLED_ENV, SKILLS_ENV, install_pack
from tests.v2.acceptance import corpus

ROOT = Path(__file__).resolve().parents[3]
DOCS = ROOT / "docs" / "usage"
SKILL_NAMES = tuple(f"rdetoolkit-{name}" for name in ("flow-authoring", "metadata", "debugging", "testing", "v1-migration"))
EXAMPLE = re.compile(r"<!-- example: ([\w-]+) -->\n```(?:python|console)\n(.*?)```", re.DOTALL)
#: v1 entry points that must not appear in code generated or written by the new-code workflow.
V1_ENTRY_POINTS = (
    r"custom_dataset_function",
    r"--legacy",
    r"\bRdeDatasetPaths\b",
    r"\bRdeInputDirPaths\b",
    r"\bRdeOutputResourcePath\b",
    r"rdetoolkit\.processing\b",
)
MODE_IDS = {"invoice": "INV", "excelinvoice": "XLS", "multidatatile": "MDT", "rdeformat": "RDF", "smarttable": "SMT"}
MODE_PARAMS = [pytest.param(mode, id=MODE_IDS[mode]) for mode in corpus.MODES]
#: Prints the installed distribution version, the module's __version__ and its file.
PROBE = (
    "import importlib.metadata, json, rdetoolkit; "
    "print(json.dumps([importlib.metadata.version('rdetoolkit'), rdetoolkit.__version__, rdetoolkit.__file__]))"
)


# ------------------------------------------------------------ installed pack


def _skill_examples(skills: Path) -> dict[str, str]:
    """Return every marked example of the installed Skills, by id."""
    examples: dict[str, str] = {}
    for path in sorted(skills.glob("rdetoolkit-*/**/*.md")):
        for match in EXAMPLE.finditer(path.read_text(encoding="utf-8")):
            assert match[1] not in examples, f"duplicate Skill example {match[1]}"
            examples[match[1]] = match[2]
    return examples


@dataclass(frozen=True)
class Pack:
    """The installed Skills pack and the runtime it was installed against."""

    skills: Path
    examples: dict[str, str]
    runtime_version: str
    runtime_origin: Path

    def command(self, example_id: str) -> list[str]:
        """Return a one-line ``python -m rdetoolkit`` Skill example as CLI arguments."""
        (command,) = self.commands(example_id)
        return command

    def commands(self, example_id: str) -> list[list[str]]:
        """Return every ``python -m rdetoolkit`` line of a console Skill example."""
        result = []
        for line in self.examples[example_id].strip().splitlines():
            words = shlex.split(line)
            assert words[:3] == ["python", "-m", "rdetoolkit"], line
            result.append(words[3:])
        return result


@pytest.fixture(scope="session")
def pack(tmp_path_factory: pytest.TempPathFactory) -> Pack:
    """The version-matched Skills pack the gate takes its commands from."""
    configured = os.environ.get(SKILLS_ENV)
    # Without CI's pack, build and install one the same way scripts/agent_readiness_gate.py does.
    skills = Path(configured) if configured else install_pack(sys.executable, tmp_path_factory.mktemp("skills-pack"))
    probe = subprocess.run(  # noqa: S603
        [sys.executable, "-c", PROBE],
        capture_output=True, text=True, timeout=120, check=False, env=corpus.cli_env(tmp_path_factory.getbasetemp()),
    )
    assert probe.returncode == 0, probe.stderr
    distribution, runtime, origin = json.loads(probe.stdout)
    assert distribution == runtime, (distribution, runtime)
    return Pack(skills=skills, examples=_skill_examples(skills), runtime_version=runtime, runtime_origin=Path(origin).resolve())


def test_skills_pack_matches_the_installed_runtime__arg_pack(pack: Pack) -> None:
    """ARG-PACK: the commands below come from a pack installed for exactly this runtime."""
    # Given: the installed pack's receipt and the runtime the CLI imports
    receipt = json.loads((pack.skills / ".rdetoolkit-skills.json").read_text(encoding="utf-8"))
    # Then: versions match exactly and the five Skills carry the examples the gate executes
    assert receipt["version"] == pack.runtime_version
    assert sorted(path.name for path in pack.skills.iterdir() if path.is_dir()) == sorted(SKILL_NAMES)
    assert {"authoring-discovery", "authoring-doctor", "authoring-run", "debugging-diagnose", "testing-lint", "migration-exercise"} <= set(pack.examples)
    # And: in CI the runtime is the installed wheel, not this checkout's src/
    if os.environ.get(REQUIRE_INSTALLED_ENV) == "1":
        assert ROOT / "src" not in pack.runtime_origin.parents, pack.runtime_origin
        assert "site-packages" in pack.runtime_origin.parts, pack.runtime_origin


# --------------------------------------------------------------- scenario


def _json(result: subprocess.CompletedProcess[str]) -> Any:
    """Parse a command's whole stdout as one JSON document (clean stdout)."""
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:  # pragma: no cover -- failure message only
        msg = f"{result.args}: stdout is not exactly one JSON document ({error})\n{result.stdout[:2000]}\n{result.stderr[-2000:]}"
        raise AssertionError(msg) from error


def _run_report(project: Path, result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    """Return the run report printed on stdout, checking it equals the saved file."""
    printed: dict[str, Any] = _json(result)
    saved = project / "data" / "logs" / f"run_report_{printed['run_id']}.json"
    assert json.loads(saved.read_text(encoding="utf-8")) == printed
    return printed


@dataclass
class Scenario:
    """Every command result of one mode's author-test-debug-fix loop."""

    mode: str
    project: Path
    spec: corpus.ModeSpec
    outputs: dict[str, subprocess.CompletedProcess[str]] = field(default_factory=dict)
    failed: dict[str, Any] = field(default_factory=dict)
    repaired: dict[str, Any] = field(default_factory=dict)
    failed_events: list[dict[str, Any]] = field(default_factory=list)
    failed_job: str = ""
    #: Each earlier tile's ``structured/measurement.txt`` (None if absent), read right
    #: after the failing run and before the repair rerun rewrites it.
    failed_tiles: dict[int, str | None] = field(default_factory=dict)
    after_doctor: list[str] = field(default_factory=list)

    @property
    def data(self) -> Path:
        """The project's data root."""
        return self.project / "data"

    def json(self, key: str) -> Any:
        """Parse the stdout of command ``key``."""
        return _json(self.outputs[key])

    def agent_facing(self) -> dict[str, subprocess.CompletedProcess[str]]:
        """The JSON views an agent may read by default (Skill: rdetoolkit-debugging)."""
        return {key: value for key, value in self.outputs.items() if key.startswith(("doctor", "lint", "diagnose", "explain"))}


def _play(mode: str, root: Path, pack: Pack) -> Scenario:
    project = corpus.build(mode, root / "project", bad=True)
    scenario = Scenario(mode=mode, project=project, spec=corpus.MODES[mode])
    out = scenario.outputs

    out["lint"] = corpus.rdetoolkit(project, "nodes", "lint", "--module", "processing", "--json")
    out["lint-skill"] = corpus.rdetoolkit(project, *pack.command("testing-lint"))
    out["flows"] = corpus.rdetoolkit(project, "flows", "list", "--module", "processing", "--json")
    for index, command in enumerate(pack.commands("authoring-discovery")):
        out[f"discovery-{index}"] = corpus.rdetoolkit(project, *command)
    out["doctor"] = corpus.rdetoolkit(project, *pack.command("authoring-doctor"))
    scenario.after_doctor = sorted(path.name for path in scenario.data.iterdir())

    # The failing run, through the Skill's documented run command.
    out["run-failed"] = corpus.rdetoolkit(project, *pack.command("authoring-run"))
    scenario.failed = _run_report(project, out["run-failed"])
    run_id = scenario.failed["run_id"]
    logs = scenario.data / "logs"
    scenario.failed_events = [json.loads(line) for line in (logs / f"events_{run_id}.jsonl").read_text(encoding="utf-8").splitlines()]
    scenario.failed_job = (scenario.data / "job.failed").read_text(encoding="utf-8")
    for index in range(scenario.spec.failing_index):
        published = corpus.tile_dir(scenario.data, index) / "structured" / "measurement.txt"
        scenario.failed_tiles[index] = published.read_text(encoding="utf-8") if published.is_file() else None
    report = logs / f"run_report_{run_id}.json"
    # The debugging Skill diagnoses a copy named failure-report.json, then the original.
    shutil.copyfile(report, project / "failure-report.json")
    out["diagnose-copy"] = corpus.rdetoolkit(project, *pack.command("debugging-diagnose"))
    out["diagnose"] = corpus.rdetoolkit(project, "report", "diagnose", str(report.relative_to(project)), "--json")
    out["explain"] = corpus.rdetoolkit(project, "report", "explain", str(report.relative_to(project)), "--format", "json")

    # Repair: archive the failure marker as the debugging Skill says, fix the input, rerun.
    (scenario.data / "job.failed").rename(scenario.data / "job.failed.previous")
    corpus.repair(mode, project)
    out["run-repaired"] = corpus.rdetoolkit(project, *pack.command("authoring-run"))
    scenario.repaired = _run_report(project, out["run-repaired"])
    out["diagnose-stale"] = corpus.rdetoolkit(project, "report", "diagnose", str(report.relative_to(project)), "--json")
    out["explain-stale"] = corpus.rdetoolkit(project, "report", "explain", str(report.relative_to(project)), "--format", "json")
    new_report = logs / f"run_report_{scenario.repaired['run_id']}.json"
    out["diagnose-repaired"] = corpus.rdetoolkit(project, "report", "diagnose", str(new_report.relative_to(project)), "--json", "--fail-on-error")
    return scenario


@pytest.fixture(scope="module", params=MODE_PARAMS)
def scenario(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory, pack: Pack) -> Scenario:
    """Play one mode's loop once; the tests below each assert one aspect of it."""
    mode: str = request.param
    return _play(mode, tmp_path_factory.mktemp(f"gate-{mode}"), pack)


def _text_files(root: Path) -> list[Path]:
    return [path for path in root.rglob("*") if path.is_file() and path.suffix in {".py", ".yaml", ".json", ".md", ".csv"}]


def test_new_code_workflow_has_no_v1_entry_point__arg_new(scenario: Scenario, pack: Pack) -> None:
    """ARG-NEW-{MODE}: generated and authored project files and the new-code Skills use only v2 entry points."""
    # Given: every text file of the project except Runner output, plus the new-code Skills
    project_files = [path for path in _text_files(scenario.project) if "logs" not in path.parts and path.name != "failure-report.json"]
    skill_files = [path for name in SKILL_NAMES if name != "rdetoolkit-v1-migration" for path in _text_files(pack.skills / name)]
    assert scenario.project / "processing.py" in project_files
    assert scenario.data / "tasksupport" / "rdeconfig.yaml" in project_files
    # Then: none of them names a v1 entry point
    for path in project_files + skill_files:
        text = path.read_text(encoding="utf-8")
        found = [pattern for pattern in V1_ENTRY_POINTS if re.search(pattern, text)]
        assert not found, f"{path}: {found}"


def test_discovery_and_lint_report_the_project__arg_discover(scenario: Scenario) -> None:
    """ARG-DISCOVER-{MODE}: lint passes, the flow is discoverable, every Skill discovery command emits JSON."""
    for key in ("lint", "lint-skill"):
        result = scenario.outputs[key]
        assert result.returncode == 0, result.stdout + result.stderr
        lint = scenario.json(key)
        assert (lint["command"], lint["status"], lint["diagnostics"]) == ("nodes lint", "passed", [])
    flows = scenario.json("flows")
    assert scenario.outputs["flows"].returncode == 0
    assert {"id": "processing.pipeline", "name": "pipeline", "source_location": "processing:pipeline"} in flows
    discovery = [key for key in scenario.outputs if key.startswith("discovery-")]
    assert discovery
    for key in discovery:
        assert scenario.outputs[key].returncode == 0, scenario.outputs[key].stderr
        assert isinstance(scenario.json(key), (list, dict))


def test_doctor_preflight_detects_the_mode_without_running__arg_doctor(scenario: Scenario) -> None:
    """ARG-DOCTOR-{MODE}: doctor passes the bad input (a data defect is not a setup defect) and runs nothing."""
    result = scenario.outputs["doctor"]
    assert result.returncode == 0, result.stdout + result.stderr
    doctor = scenario.json("doctor")
    assert (doctor["command"], doctor["status"], doctor["mode"], doctor["flow_executed"]) == ("doctor", "passed", scenario.mode, False)
    assert doctor["diagnostics"] == []
    assert {check["check_id"] for check in doctor["checks"]} >= {"flow.import", "flow.signature", "runner.preflight"}
    assert scenario.after_doctor == ["inputdata", "invoice", "tasksupport"]


def test_failing_run_is_located_by_report_events_and_diagnosis__arg_fail(scenario: Scenario) -> None:
    """ARG-FAIL-{MODE}: the failure is attributed to the broken tile's actual call, everywhere."""
    spec, failed = scenario.spec, scenario.failed
    # Then: process exit, status, mode and the user's own error code
    assert scenario.outputs["run-failed"].returncode == 1
    assert (failed["schema_version"], failed["status"], failed["mode"]) == ("2", "failed", spec.mode)
    assert failed["error"]["code"] == 1
    # And: fail_fast stops at the broken tile; earlier tiles completed
    assert [iteration["index"] for iteration in failed["iterations"]] == list(range(spec.failing_index + 1))
    assert [iteration["status"] for iteration in failed["iterations"]] == ["completed"] * spec.failing_index + ["failed"]
    broken = failed["iterations"][spec.failing_index]
    (failed_call,) = [call for call in broken["node_calls"] if call["status"] == "failed"]
    assert failed_call["node_id"] == "processing.parse_measurement"
    # (read right after the failing run: the repair rerun would recreate them)
    expected_tiles = {index: f"{float(corpus.GOOD_VALUES[spec.tile_sources[index]])}\n" for index in range(spec.failing_index)}
    assert scenario.failed_tiles == expected_tiles
    # And: job.failed carries the user error
    assert scenario.failed_job.splitlines()[0] == "ErrorCode=1"
    # And: the event log of this run records the same failed call and the run outcome
    assert {event["run_id"] for event in scenario.failed_events} == {failed["run_id"]}
    node_failures = [event for event in scenario.failed_events if event.get("name") == "node.failed"]
    assert [(event["node_id"], event["payload"]["call_id"]) for event in node_failures] == [(failed_call["node_id"], failed_call["call_id"])]
    assert scenario.failed_events[-1]["name"] == "run.completed" and scenario.failed_events[-1]["payload"]["status"] == "failed"
    # And: both diagnoses (the Skill's copy and the original) name exactly that call
    for key, detail_state in (("diagnose-copy", "missing"), ("diagnose", "verified")):
        assert scenario.outputs[key].returncode == 0, scenario.outputs[key].stderr
        diagnosis = scenario.json(key)
        assert (diagnosis["run_id"], diagnosis["run_status"]) == (failed["run_id"], "failed")
        failures = [(item["iteration_index"], item["node_id"], item["call_id"], item["code"]) for item in diagnosis["failures"]]
        assert failures == [(spec.failing_index, failed_call["node_id"], failed_call["call_id"], 1)]
        states = {item["iteration_detail"]["state"] for item in diagnosis["evidence"]["iterations"]}
        assert states == {detail_state}
    # And: explain points at the same call with its evidence verified
    explain = scenario.json("explain")
    assert (explain["run_id"], explain["run_status"], explain["mode"]) == (failed["run_id"], "failed", spec.mode)
    assert [item["subject"] for item in explain["diagnostics"] if item["severity"] == "error"] == [failed_call["call_id"]]


def _expected_metadata(value: float) -> dict[str, Any]:
    return {
        "constant": {"sample_count": {"value": 1}},
        "variable": [{"position": {"value": value, "unit": "nm"}}],
    }


def test_repaired_rerun_publishes_every_tile__arg_repair(scenario: Scenario) -> None:
    """ARG-REPAIR-{MODE}: after the input repair the same project runs clean, with each tile's artifacts."""
    spec, repaired = scenario.spec, scenario.repaired
    assert scenario.outputs["run-repaired"].returncode == 0, scenario.outputs["run-repaired"].stderr
    assert (repaired["status"], repaired["mode"], repaired["error"]) == ("success", spec.mode, None)
    assert [iteration["status"] for iteration in repaired["iterations"]] == ["completed"] * len(spec.tile_sources)
    assert not (scenario.data / "job.failed").exists()
    assert (scenario.data / "job.failed.previous").read_text(encoding="utf-8") == scenario.failed_job
    for index, (source, name) in enumerate(zip(spec.tile_sources, spec.tile_names, strict=True)):
        tile = corpus.tile_dir(scenario.data, index)
        value = float(corpus.GOOD_VALUES[source])
        # v2 path injection: the flow saw this tile's own iteration and input file
        assert json.loads((tile / "structured" / "inputs.json").read_text(encoding="utf-8")) == {"iteration": index, "measurements": [source]}
        assert (tile / "structured" / "measurement.txt").read_text(encoding="utf-8") == f"{value}\n"
        assert json.loads((tile / "meta" / "metadata.json").read_text(encoding="utf-8")) == _expected_metadata(value)
        invoice = json.loads((tile / "invoice" / "invoice.json").read_text(encoding="utf-8"))
        assert (invoice["basic"]["dataName"], invoice["custom"]["operator"]) == (name, "agent")
        assert (tile / spec.raw_dir / source).read_text(encoding="utf-8") == corpus.GOOD_VALUES[source]
    assert not (scenario.data / "divided" / f"{len(spec.tile_sources):04d}").exists()
    if spec.mode == "rdeformat":
        for index in range(len(spec.tile_sources)):
            assert (corpus.tile_dir(scenario.data, index) / "structured" / "prepared.csv").read_text(encoding="utf-8") == f"tile,{index}\n"
    # And: diagnosing the clean run reports no failure, so --fail-on-error passes
    assert scenario.outputs["diagnose-repaired"].returncode == 0, scenario.outputs["diagnose-repaired"].stdout
    assert scenario.json("diagnose-repaired")["failures"] == []


def test_old_report_does_not_borrow_the_rerun__arg_stale(scenario: Scenario) -> None:
    """ARG-STALE-{MODE}: after the rerun, the old report keeps its own failure and flags overwritten details."""
    failed = scenario.failed
    (failed_call,) = [call for call in failed["iterations"][-1]["node_calls"] if call["status"] == "failed"]
    stale = scenario.json("diagnose-stale")
    assert (stale["run_id"], stale["run_status"]) == (failed["run_id"], "failed")
    assert [(item["iteration_index"], item["call_id"]) for item in stale["failures"]] == [(scenario.spec.failing_index, failed_call["call_id"])]
    # The iteration details were rewritten by the rerun: flagged, never used as this run's evidence
    assert [item["iteration_detail"]["state"] for item in stale["evidence"]["iterations"]] == ["mismatched"] * len(failed["iterations"])
    assert stale["evidence"]["events"]["path"] == f"events_{failed['run_id']}.jsonl"
    assert stale["evidence"]["events"]["flags"] == []
    explain = scenario.json("explain-stale")
    assert explain["run_id"] == failed["run_id"]
    assert scenario.repaired["run_id"] not in scenario.outputs["diagnose-stale"].stdout + scenario.outputs["explain-stale"].stdout
    mismatched = [item for item in explain["diagnostics"] if item["name"] == "SupportingEvidenceMismatched"]
    assert len(mismatched) == len(failed["iterations"])


def test_agent_facing_json_omits_the_fake_secret__arg_privacy(scenario: Scenario) -> None:
    """ARG-PRIVACY-{MODE}: the planted secret reached the run's own artifacts but no agent-facing view."""
    # Given (negative control): the secret did reach job.failed and the printed run report
    assert corpus.FAKE_SECRET in scenario.failed_job
    assert corpus.FAKE_SECRET in scenario.outputs["run-failed"].stdout
    # Then: no default agent-facing JSON view carries it, the input path or the environment value
    views = scenario.agent_facing()
    assert {"doctor", "lint", "diagnose", "diagnose-copy", "explain", "diagnose-stale", "explain-stale"} <= set(views)
    # Decoded strings, not raw stdout: JSON escapes a Windows path's backslashes.
    forbidden = (corpus.FAKE_SECRET, corpus.SECRET_ENV, str(scenario.project), scenario.project.as_posix(), str(scenario.project.resolve()))
    for key, result in views.items():
        for text in (result.stdout, *_strings(_json(result))):
            leaked = [value for value in forbidden if value in text]
            assert not leaked, f"{key}: {leaked}"


def _strings(document: Any) -> list[str]:
    """Return every string key and value of a decoded JSON document."""
    if isinstance(document, str):
        return [document]
    if isinstance(document, dict):
        return [text for key, value in document.items() for text in (key, *_strings(value))]
    if isinstance(document, list):
        return [text for item in document for text in _strings(item)]
    return []


def _validator(name: str) -> Draft202012Validator:
    common = json.loads((DOCS / "diagnostics.schema.json").read_text(encoding="utf-8"))
    registry = Registry().with_resource("diagnostics.schema.json", Resource.from_contents(common))
    return Draft202012Validator(json.loads((DOCS / name).read_text(encoding="utf-8")), registry=registry)


def test_json_outputs_follow_the_versioned_contracts__arg_contract(scenario: Scenario, pack: Pack) -> None:
    """ARG-CONTRACT-{MODE}: every envelope validates against the published schema and names this runtime."""
    envelope, diagnosis = _validator("diagnostics.schema.json"), _validator("diagnostics-report.schema.json")
    for key in scenario.agent_facing():
        document = scenario.json(key)
        envelope.validate(document)
        assert document["producer"] == {"name": "rdetoolkit", "version": pack.runtime_version}
        if document["command"] == "report diagnose":
            diagnosis.validate(document)
    for key in ("run-failed", "run-repaired"):
        assert scenario.json(key)["schema_version"] == "2"
    for event in scenario.failed_events:
        assert event["schema_version"] == "1"


# ---------------------------------------------------------- single cases


def test_continue_policy_gives_partial_exit_semantics__arg_partial(tmp_path: Path, pack: Pack) -> None:
    """ARG-PARTIAL: MultiDataTile under ``continue`` runs past the broken tile and exits 2."""
    # Given: the bad MultiDataTile corpus plus a healthy third file after the broken
    # second one (so continuing is observable), and a documented --config override
    project = corpus.build("multidatatile", tmp_path / "project", bad=True)
    (project / "data" / "inputdata" / "m2.txt").write_text("7.5", encoding="utf-8")
    (project / "overrides.yaml").write_text("execution:\n  on_iteration_error: continue\n", encoding="utf-8")
    # When: running with the override
    result = corpus.rdetoolkit(project, *pack.command("authoring-run"), "--config", "overrides.yaml")
    # Then: partial, only the broken tile failed, and the tile after it still ran
    report = _run_report(project, result)
    assert result.returncode == 2
    assert report["status"] == "partial"
    assert [(iteration["index"], iteration["status"]) for iteration in report["iterations"]] == [(0, "completed"), (1, "failed"), (2, "completed")]
    data = project / "data"
    for index, (source, value) in enumerate((("m0.txt", "2.5"), ("m2.txt", "7.5"))):
        tile = corpus.tile_dir(data, 2 * index)
        assert json.loads((tile / "structured" / "inputs.json").read_text(encoding="utf-8")) == {"iteration": 2 * index, "measurements": [source]}
        assert (tile / "structured" / "measurement.txt").read_text(encoding="utf-8") == f"{float(value)}\n"
        assert json.loads((tile / "meta" / "metadata.json").read_text(encoding="utf-8")) == _expected_metadata(float(value))
    path = f"data/logs/run_report_{report['run_id']}.json"
    diagnose = corpus.rdetoolkit(project, "report", "diagnose", path, "--json", "--fail-on-error")
    assert diagnose.returncode == 1
    assert [(item["iteration_index"], item["code"]) for item in _json(diagnose)["failures"]] == [(1, 1)]


def _artifacts(data: Path) -> dict[str, bytes]:
    """Return every tile's structured / invoice / raw files, by data-root-relative path.

    ``meta/`` and ``structured/inputs.json`` are left out: the v1 callback does
    not write them (they come from the v2 artifact nodes).
    """
    files = {}
    for path in sorted(data.rglob("*")):
        relative = path.relative_to(data)
        if not path.is_file() or relative.parts[0] in {"inputdata", "tasksupport", "logs", "temp"}:
            continue
        if path.parent.name in {"structured", "invoice", "raw", "nonshared_raw"} and path.name != "inputs.json":
            files[relative.as_posix()] = path.read_bytes()
    return files


@pytest.mark.parametrize("mode", MODE_PARAMS)
def test_v1_callback_entry_still_matches_the_flow__arg_v1(mode: str, tmp_path: Path, pack: Pack) -> None:
    """ARG-V1-{MODE}: ``run --legacy`` on the same input gives the flow's artifacts and failure."""
    results = {}
    for bad in (False, True):
        for entry in ("flow", "legacy"):
            project = corpus.build(mode, tmp_path / f"{entry}-{bad}" / "project", bad=bad)
            if entry == "flow":
                result = corpus.rdetoolkit(project, *pack.command("authoring-run"))
            else:
                shutil.copyfile(corpus.PROJECT_TEMPLATE / "legacy_dataset.py", project / "legacy_dataset.py")
                result = corpus.rdetoolkit(project, "run", "--legacy", "legacy_dataset.py::dataset")
            assert result.returncode == (1 if bad else 0), f"{entry} bad={bad}: {result.stdout[-2000:]}{result.stderr[-2000:]}"
            job = project / "data" / "job.failed"
            results[entry, bad] = (_artifacts(project / "data"), job.read_text(encoding="utf-8") if job.exists() else None)
    # Then: the v1 callback publishes what the v2 flow publishes, for success and failure
    assert results["legacy", False] == results["flow", False]
    assert results["legacy", False][0]
    assert results["legacy", True] == results["flow", True]
    assert results["legacy", True][1] is not None


def test_migration_skill_worked_example_from_the_installed_pack__arg_migrate(pack: Pack) -> None:
    """ARG-MIGRATE: the migration Skill's exercise passes from the installed copy, outside the checkout."""
    # Given: the project the pack was installed into, which holds .agents/skills/
    project = pack.skills.parent.parent
    words = shlex.split(pack.examples["migration-exercise"].strip())
    assert words[:2] == ["python", ".agents/skills/rdetoolkit-v1-migration/scripts/exercise_migration.py"], words
    # When: running the Skill's exact command with the installed interpreter
    result = subprocess.run(  # noqa: S603
        [sys.executable, *words[1:]], cwd=project, env=corpus.cli_env(project.parent),
        capture_output=True, text=True, timeout=600, check=False,
    )
    # Then: the v1 entry, the converted flow and the artifact-node flow agree on both inputs
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
    summary = json.loads((project / "migration-exercise" / "summary.json").read_text(encoding="utf-8"))
    assert summary["parity"] is True
    assert (summary["success"]["status"], summary["failure"]["status"], summary["failure"]["error_code"]) == ("success", "failed", 999)
