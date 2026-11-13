"""AGGA-002/004: examples are executed from the distributed Skill text.

EP table (written before implementation)
| ID | Partition | Expected |
| AS-01 | five Skill metadata, links and examples | complete, distinct, tracked |
| AS-02 | authoring and metadata examples | real Runner output and units/rows |
| AS-03 | debugging failure and repaired input | failing call, code, job.failed, then success |
| AS-04 | testing example and migration fixture | real outputs and v1/v2 artifact parity |
| AS-05 | CLI discovery examples | successful commands, parseable JSON schemas |
| AS-N1 | old new-code imports/callback/proxy advice | static audit rejects each |
| AS-N2 | untracked or broken example | manifest/fence check rejects |
| AS-N3 | missing API mutation | exact-text execution fails |

BV table
| ID | Boundary | Expected |
| AS-B1 | every Python/console fence in every Skill | exactly one manifest entry |
| AS-B2 | zero/multiple raw inputs | authoring preserves count and eager loop semantics |
| AS-B3 | malformed/empty measurement | debugging reports original node failure |
| AS-B4 | unrelated contributor Skill present | canonical Skills validation unaffected |
"""

from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from typer.testing import CliRunner

from rdetoolkit import workflows
from rdetoolkit.cli.app import app
from rdetoolkit.testing import make_input_paths, make_invoice

ROOT = Path(__file__).resolve().parents[3]
SKILLS = ROOT / ".agents" / "skills"
NAMES = {f"rdetoolkit-{name}" for name in ("flow-authoring", "metadata", "debugging", "testing", "v1-migration")}
EXAMPLE = re.compile(r"<!-- example: ([\w-]+) -->\n```(python|console)\n(.*?)```", re.DOTALL)
COVERED_EXAMPLES = {"authoring-discovery", "authoring-flow", "authoring-run", "metadata-discovery", "metadata-flow", "debugging-flow", "debugging-repair", "debugging-report", "testing-discovery", "testing-roundtrip", "migration-commands"}
OBSOLETE = (r"custom_dataset_function\s*=", r"\bRdeDatasetPaths\b", r"from rdetoolkit\.rde2util import.*\bMeta\b", r"from rdetoolkit\.processing", r"\b(?:Trace|NodeProxy|OutputProxy|RustDAG)\b", r"\bget_agent_guide\b|\bagent-guide\b")


def _manifest() -> list[dict[str, str]]:
    payload = json.loads((SKILLS / "examples.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    return payload["examples"]


def _extract(text: str, source: str) -> dict[str, tuple[str, str]]:
    matches = list(EXAMPLE.finditer(text))
    assert text.count("```") == 2 * len(matches), f"Unmarked or malformed example fence: {source}"
    assert len({match[1] for match in matches}) == len(matches), f"Duplicate example marker: {source}"
    return {match[1]: (match[2], match[3]) for match in matches}


def _code(example_id: str) -> str:
    entries = {entry["id"]: entry for entry in _manifest()}
    assert example_id in entries, f"Untracked example: {example_id}"
    entry = entries[example_id]
    examples = _extract((SKILLS / entry["path"]).read_text(encoding="utf-8"), entry["path"])
    assert example_id in examples, f"Missing example marker: {example_id}"
    language, code = examples[example_id]
    assert language == entry["language"]
    return code


def _namespace(example_id: str, root: Path) -> dict[str, Any]:
    namespace: dict[str, Any] = {"__name__": "skill_" + re.sub(r"\W", "_", example_id + root.name)}
    exec(compile(_code(example_id), f"<skill:{example_id}>", "exec"), namespace)  # noqa: S102
    return namespace


def _tree(root: Path, text: str = "sample\n", files: int = 1) -> Path:
    data = root / "data"
    paths = make_input_paths(data, [f"input-{index}.txt" for index in range(files)])
    for source in paths.rawfiles:
        source.write_text(text, encoding="utf-8")
    invoice = make_invoice({"datasetId": "skill-fixture", "basic": {"dataName": "fixture", "dateSubmitted": "2026-11-12", "dataOwnerId": "0" * 56}})
    (paths.invoice / "invoice.json").write_text(json.dumps(invoice.raw), encoding="utf-8")
    (paths.tasksupport / "invoice.schema.json").write_text('{"properties": {}}', encoding="utf-8")
    (paths.tasksupport / "metadata-def.json").write_text("{}", encoding="utf-8")
    return data


def _run(flow: Any) -> Any:
    return workflows.run(flow=flow, config={"system": {"save_thumbnail_image": False}})


def _audit(text: str) -> list[str]:
    return [pattern for pattern in OBSOLETE if re.search(pattern, text)]


def test_skill_metadata_links_and_manifest__as_01_b1() -> None:
    """AS-01/B1: every distributed example and local reference is validated."""
    # Given: exactly five canonical Skills and one example manifest
    skills = sorted(SKILLS.glob("rdetoolkit-*/SKILL.md"))
    assert {path.parent.name for path in skills} == NAMES
    seen: set[str] = set()
    # When: inspecting the actual distributed Markdown, including references
    for skill in skills:
        text = skill.read_text(encoding="utf-8")
        assert text.startswith("---\nname: " + skill.parent.name + "\ndescription: ")
        assert len(text.split("---", 2)[1].splitlines()) == 3
        for path in [skill, *skill.parent.glob("references/*.md")]:
            content = path.read_text(encoding="utf-8")
            examples = _extract(content, str(path))
            for example_id in examples:
                assert example_id not in seen, f"Duplicate example {example_id}"
                seen.add(example_id)
            if skill.parent.name != "rdetoolkit-v1-migration":
                assert not _audit(content), f"Retired advice in {path}: {_audit(content)}"
            for link in re.findall(r"\]\(([^)]+)\)", content):
                canonical = "https://github.com/nims-mdpf/rdetoolkit/blob/develop/v2/"
                if link.startswith(canonical):
                    assert (ROOT / link.removeprefix(canonical).split("#")[0]).is_file(), f"Broken public v2 reference: {link}"
                elif not link.startswith(("https://", "#")):
                    assert (path.parent / link.split("#")[0]).is_file(), f"Broken Skill link: {path}: {link}"
    # Then: no fence is omitted from execution tracking or points at another file
    assert seen == {entry["id"] for entry in _manifest()}
    assert seen == COVERED_EXAMPLES, "Update execution coverage when adding/removing a shipped example"
    for entry in _manifest():
        assert _code(entry["id"])


def test_unrelated_contributor_skill_is_ignored__as_b4(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AS-B4: contributor Skills do not enter downstream pack validation."""
    # Given: the five canonical Skills alongside a private contributor Skill.
    for name in NAMES:
        shutil.copytree(SKILLS / name, tmp_path / name)
    shutil.copyfile(SKILLS / "examples.json", tmp_path / "examples.json")
    contributor = tmp_path / "contributor-helper"
    contributor.mkdir()
    (contributor / "SKILL.md").write_text("---\nname: contributor-helper\ndescription: A private contributor Skill.\n---\n", encoding="utf-8")
    monkeypatch.setattr(sys.modules[__name__], "SKILLS", tmp_path)
    # When/Then: validating canonical names and examples ignores that extra Skill.
    test_skill_metadata_links_and_manifest__as_01_b1()


@pytest.mark.parametrize("files", [0, 1, 3])
def test_authoring_exact_example__as_02_b2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, files: int) -> None:
    """AS-02/B2: eager loops preserve zero/one/multiple inputs through the Runner."""
    # Given: synthetic public-builder input paths and the shipped flow
    data = _tree(tmp_path, text="  sample  \n", files=files)
    monkeypatch.chdir(tmp_path)
    namespace = _namespace("authoring-flow", tmp_path)
    # When: running the exact Skill example through the public v2 entry
    report = _run(namespace["pipeline"])
    # Then: functional contents match each input and the invoice is finalized
    assert report.status == "success", report.error
    assert report.exit_code == 0
    assert sorted(path.name for path in (data / "structured").glob("*.txt")) == [f"structured-{index}.txt" for index in range(files)]
    for path in (data / "structured").glob("*.txt"):
        assert path.read_text(encoding="utf-8") == "sample\n"
    assert json.loads((data / "invoice" / "invoice.json").read_text(encoding="utf-8"))["basic"]["dataName"] == "fixture"


def test_metadata_exact_example__as_02(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AS-02: metadata example saves typed constants, units, variable rows and image."""
    # Given: an isolated input tree and the shipped metadata flow
    data = _tree(tmp_path)
    monkeypatch.chdir(tmp_path)
    namespace = _namespace("metadata-flow", tmp_path)
    # When: executing real artifact nodes through the Runner
    report = _run(namespace["pipeline"])
    # Then: the promised JSON and image exist with actual scientific values
    assert report.status == "success", report.error
    metadata = json.loads((data / "meta" / "metadata.json").read_text(encoding="utf-8"))
    assert metadata == {"constant": {"temperature": {"value": 300, "unit": "K"}}, "variable": [{"position": {"value": 1.5, "unit": "nm"}}, {"position": {"value": 2.5, "unit": "nm"}}]}
    image_path = data / "other_image" / "positions.png"
    assert image_path.read_bytes().startswith(b"\x89PNG")
    with Image.open(image_path) as image:
        assert image.width > 0 and image.height > 0
        image.verify()


@pytest.mark.parametrize("invalid", ["", "invalid", "-2", "nan", "inf"])
def test_debug_failure_repair_exact_example__as_03_b3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, invalid: str) -> None:
    """AS-03/B3: inspect a real failing node, repair its input, and rerun successfully."""
    # Given: invalid local measurements and the shipped debugging flow
    data = _tree(tmp_path, text=invalid)
    monkeypatch.chdir(tmp_path)
    namespace = _namespace("debugging-flow", tmp_path)
    # When: executing the exact failure example
    failed = _run(namespace["pipeline"])
    # Then: original user error, node, iteration, and job.failed are inspectable
    assert failed.status == "failed"
    assert failed.exit_code == 1
    assert failed.iterations[0]["status"] == "failed"
    assert failed.error["code"] == 1
    assert "positive" in failed.error["message"]
    calls = failed.iterations[0]["node_calls"]
    assert any(call["status"] == "failed" and "positive_measurement" in call["node_id"] for call in calls)
    assert (data / "job.failed").read_text(encoding="utf-8").splitlines()[0] == "ErrorCode=1"
    report_path = data / "logs" / f"run_report_{failed.run_id}.json"
    assert json.loads(report_path.read_text(encoding="utf-8"))["run_id"] == failed.run_id
    shutil.copyfile(report_path, tmp_path / "failure-report.json")
    command = shlex.split(_code("debugging-report"))
    shown = CliRunner().invoke(app, command[3:])
    assert shown.exit_code == 0, shown.output
    assert failed.run_id in shown.output
    assert "positive_measurement" in shown.output
    # When: applying the exact shipped repair and rerunning the same flow
    exec(compile(_code("debugging-repair"), "<skill:debugging-repair>", "exec"), namespace)  # noqa: S102
    repaired = namespace["report"]
    # Then: report and output show the repaired result, with no stale failure marker
    assert repaired.status == "success", repaired.error
    assert repaired.exit_code == 0
    assert (data / "structured" / "measurement.txt").read_text(encoding="utf-8") == "2.5\n"
    assert not (data / "job.failed").exists()
    assert (data / "job.failed.previous").is_file()


def test_testing_exact_example__as_04(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AS-04: the testing Skill builds a complete fixture and keeps Runner outputs."""
    # Given: an empty working directory
    monkeypatch.chdir(tmp_path)
    # When: executing the complete testing recipe, including public run_flow
    namespace = _namespace("testing-roundtrip", tmp_path)
    # Then: assertions in the shipped recipe and independent output checks succeed
    assert namespace["report"].status == "success"
    assert (tmp_path / "scratch" / "data" / "structured" / "result.txt").read_text(encoding="utf-8") == "test\n"


def test_migration_exact_fixture_and_commands__as_04(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AS-04: migrate the real v1 corpus fixture and compare resulting artifact bytes."""
    # Given: the shipped migration-only source, frozen to the real v1 corpus
    source = SKILLS / "rdetoolkit-v1-migration" / "references" / "legacy.py"
    corpus = ROOT / "tests/v2/cli/fixtures/migrate_corpus/case01_init/main.py"
    assert source.read_bytes() == corpus.read_bytes()
    shutil.copyfile(source, tmp_path / "legacy.py")
    v1_data = _tree(tmp_path / "v1")
    v2_data = _tree(tmp_path / "v2")
    monkeypatch.chdir(tmp_path / "v1")
    legacy: dict[str, Any] = {"__name__": "skill_legacy"}
    exec(compile(source.read_text(encoding="utf-8"), str(source), "exec"), legacy)  # noqa: S102
    workflows.run(custom_dataset_function=legacy["custom_dataset_function"], config={"system": {"save_thumbnail_image": False}})
    expected = (v1_data / "structured/structured.txt").read_bytes()
    expected_invoice = json.loads((v1_data / "invoice/invoice.json").read_text(encoding="utf-8"))
    assert not (v2_data / "structured/structured.txt").exists()
    monkeypatch.chdir(tmp_path)
    # When: running the exact documented check/convert commands, then the generated flow
    for line in _code("migration-commands").splitlines():
        command = shlex.split(line)
        assert command[:3] == ["python", "-m", "rdetoolkit"]
        result = CliRunner().invoke(app, command[3:])
        assert result.exit_code == 0, result.output
    migrated: dict[str, Any] = {"__name__": "skill_migrated"}
    target = tmp_path / "migrated" / "legacy.py"
    exec(compile(target.read_text(encoding="utf-8"), str(target), "exec"), migrated)  # noqa: S102
    monkeypatch.chdir(tmp_path / "v2")
    report = _run(migrated["pipeline"])
    # Then: the migration shell preserves the actual v1-produced structured artifact
    assert report.status == "success", report.error
    assert (v2_data / "structured/structured.txt").read_bytes() == expected
    assert json.loads((v2_data / "invoice/invoice.json").read_text(encoding="utf-8")) == expected_invoice


@pytest.mark.parametrize("example_id", ["authoring-discovery", "metadata-discovery", "testing-discovery"])
def test_cli_discovery_examples__as_05(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, example_id: str) -> None:
    """AS-05: every documented discovery command exists and returns parseable schema."""
    # Given: the shipped CLI fence in an isolated downstream directory
    monkeypatch.chdir(tmp_path)
    # When: invoking its exact commands through the public CLI
    for line in _code(example_id).splitlines():
        command = shlex.split(line)
        assert command[:3] == ["python", "-m", "rdetoolkit"]
        result = CliRunner().invoke(app, command[3:])
        # Then: successful machine-readable introspection includes registered identities
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert isinstance(payload, (dict, list))
        if isinstance(payload, list):
            assert all("id" in item for item in payload)
        else:
            assert "id" in payload


@pytest.mark.parametrize(
    "obsolete",
    [
        "workflows.run(custom_dataset_function=callback)", "from rdetoolkit.types import RdeDatasetPaths",
        "from rdetoolkit.rde2util import Meta", "from rdetoolkit.processing import flow",
        "Trace()", "NodeProxy()", "OutputProxy()", "RustDAG()",
        "rdetoolkit.get_agent_guide()", "rdetoolkit agent-guide",
    ],
)
def test_static_audit_rejects_retired_new_code__as_n1(obsolete: str) -> None:
    """AS-N1: a regression to retired new-code advice is rejected explicitly."""
    # Given: an obsolete pattern outside the migration-only Skill
    # When / Then: auditing it identifies a violation
    assert _audit(obsolete)


def test_missing_api_mutation_fails_exact_example__as_n3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AS-N3: deleting a documented public artifact API breaks the exact shipped sample."""
    import rdetoolkit.nodes

    # Given: one deliberate public API deletion, restored by monkeypatch afterwards
    monkeypatch.delattr(rdetoolkit.nodes, "save_text")
    # When / Then: the exact Skill import fails, proving API-drift sensitivity
    with pytest.raises(ImportError, match="save_text"):
        _namespace("authoring-flow", tmp_path)


def test_exact_flow_cli_command__as_05(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AS-05: the exact documented module entry runs in an independent CLI process."""
    # Given: the shipped processing module and a complete local fixture
    data = _tree(tmp_path)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "processing.py").write_text(_code("authoring-flow"), encoding="utf-8")
    command = shlex.split(_code("authoring-run"))
    # When: executing the documented CLI entry using the installed interpreter
    result = subprocess.run([sys.executable, *command[1:]], capture_output=True, text=True, timeout=60, check=False)
    # Then: status, saved versioned report, and structured file all agree
    assert result.returncode == 0, result.stderr
    reports = list((data / "logs").glob("run_report_*.json"))
    assert len(reports) == 1
    payload = json.loads(reports[0].read_text(encoding="utf-8"))
    assert payload["schema_version"] == "2"
    assert payload["status"] == "success"
    assert (data / "structured/structured-0.txt").read_text(encoding="utf-8") == "sample\n"


@pytest.mark.parametrize(
    "text",
    [
        "```python\npass\n```",
        "<!-- example: missing -->\n```pyhton\npass\n```",
        "<!-- example: duplicate -->\n```python\npass\n```\n<!-- example: duplicate -->\n```python\npass\n```",
    ],
)
def test_untracked_or_duplicate_example_rejected__as_n2(text: str) -> None:
    """AS-N2: malformed, unmarked and duplicate fences fail with actionable messages."""
    # Given: a malformed shipped example
    # When / Then: extraction rejects it before example execution
    with pytest.raises(AssertionError, match="example"):
        _extract(text, "broken-skill.md")
