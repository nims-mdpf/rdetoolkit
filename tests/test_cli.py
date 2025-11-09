"""Test design tables for csv2graph CLI.

Equivalence Partitioning

| API | Input/State Partition | Rationale | Expected Outcome | Test ID |
| --- | --- | --- | --- | --- |
| `cli.csv2graph` | Single-series CSV, flag omitted | Auto suppression should remove per-series PNGs | Only overlay PNG exists | `TC-EP-CLI-001` |
| `cli.csv2graph` | Single-series CSV, `--individual` specified | User override must force individual PNG creation | Overlay + individual PNGs exist | `TC-EP-CLI-002` |
| `cli.csv2graph` | Multi-series CSV, flag omitted | Default behavior should emit both overlay and per-series PNGs | Overlay + >=1 individual PNG | `TC-EP-CLI-003` |
| `cli.csv2graph` | Multi-series CSV, `--no-individual` specified | Explicit skip must remove per-series PNGs even w/ multiple series | Overlay PNG only | `TC-EP-CLI-004` |

Boundary Value

| API | Boundary | Rationale | Expected Outcome | Test ID |
| --- | --- | --- | --- | --- |
| `cli.csv2graph` | `len(y_cols)=1` vs `len(y_cols)=2` | Auto suppression applies only when at most one series is valid | `len=1`: overlay only, `len=2`: overlay + individual | `TC-BV-CLI-001` |
| `cli.csv2graph` | `mode="overlay"` vs `mode="individual"` | Individual mode should bypass overlay generation regardless of flags | Overlay absent, individual PNGs exist | `TC-BV-CLI-002` |
"""

import json
import os
import platform
import shutil
from distutils.version import StrictVersion
from pathlib import Path
import textwrap
from unittest.mock import patch


import click
import pytest
from click.testing import CliRunner
from rdetoolkit.cli import (
    init,
    version,
    make_excelinvoice,
    csv2graph,
)
from rdetoolkit.cmd.command import (
    DockerfileGenerator,
    MainScriptGenerator,
    RequirementsTxtGenerator,
    InvoiceJsonGenerator,
    InvoiceSchemaJsonGenerator,
    MetadataDefJsonGenerator,
)

from rdetoolkit.cmd.archive import CreateArtifactCommand


def test_make_main_py():
    test_path = Path("test_main.py")
    gen = MainScriptGenerator(test_path)
    gen.generate()

    with open(test_path, encoding="utf-8") as f:
        content = f.read()

    expected_content = """# The following script is a template for the source code.

import rdetoolkit

rdetoolkit.workflows.run()
"""
    assert content == expected_content
    test_path.unlink()

    if os.path.exists("container"):
        shutil.rmtree("container")


def test_make_dockerfile():
    test_path = Path("Dockerfile")
    gen = DockerfileGenerator(test_path)
    gen.generate()

    with open(test_path, encoding="utf-8") as f:
        content = f.read()

    expected_content = """FROM python:3.11.9

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY main.py /app
COPY modules/ /app/modules/
"""
    assert content == expected_content
    test_path.unlink()

    if os.path.exists("container"):
        shutil.rmtree("container")


def test_make_requirements_txt():
    test_path = Path("test_requirements.txt")
    gen = RequirementsTxtGenerator(test_path)
    gen.generate()

    with open(test_path, encoding="utf-8") as f:
        content = f.read()

    expected_content = """# ----------------------------------------------------
# Please add the desired packages and install the libraries after that.
# Then, run
#
# pip install -r requirements.txt
#
# on the terminal to install the required packages.
# ----------------------------------------------------
# ex.
# pandas==2.0.3
# numpy
rdetoolkit==1.4.2
"""
    assert content == expected_content
    test_path.unlink()

    if os.path.exists("container"):
        shutil.rmtree("container")

    if os.path.exists("test_requirements.txt"):
        os.remove("test_requirements.txt")


def test_make_template_json():
    test_path = Path("test_template.json")
    gen = InvoiceJsonGenerator(test_path)
    gen.generate()

    assert test_path.exists()
    test_path.unlink()

    if os.path.exists("container"):
        shutil.rmtree("container")


def test_make_schema_json():
    test_path = Path("test_template.json")
    gen = InvoiceSchemaJsonGenerator(test_path)
    _ = gen.generate()

    assert test_path.exists()

    # Verify the content of generated JSON has correct keys
    with open(test_path, encoding="utf-8") as f:
        generated_json = json.load(f)

    # Check that the correct keys are present
    assert "$schema" in generated_json
    assert generated_json["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert "$id" in generated_json
    assert generated_json["$id"] == "https://rde.nims.go.jp/rde/dataset-templates/dataset_template_custom_sample/invoice.schema.json"
    assert "type" in generated_json
    assert generated_json["type"] == "object"

    # Ensure old keys are not present
    assert "version" not in generated_json
    assert "schema_id" not in generated_json
    assert "value_type" not in generated_json

    test_path.unlink()

    if os.path.exists("container"):
        shutil.rmtree("container")


def test_make_metadata_def_json():
    test_path = Path("test_template.json")
    gen = MetadataDefJsonGenerator(test_path)
    gen.generate()

    with open(test_path, encoding="utf-8") as f:
        contents = json.load(f)

    assert contents == {}
    assert test_path.exists()
    test_path.unlink()

    if os.path.exists("container"):
        shutil.rmtree("container")


def test_init_creation():
    runner = CliRunner()

    result = runner.invoke(init)

    # 出力メッセージのテスト
    assert "Ready to develop a structured program for RDE." in result.output
    assert "Done!" in result.output

    dirs = [
        Path("container/modules"),
        Path("container/data/inputdata"),
        Path("container/data/invoice"),
        Path("container/data/tasksupport"),
        Path("input/invoice"),
        Path("input/inputdata"),
        Path("templates/tasksupport"),
    ]
    for d in dirs:
        assert d.exists()

    files = [
        Path("container/main.py"),
        Path("container/requirements.txt"),
        Path("container/data/invoice/invoice.json"),
        Path("container/data/tasksupport/invoice.schema.json"),
        Path("container/data/tasksupport/metadata-def.json"),
        Path("input/invoice/invoice.json"),
        Path("templates/tasksupport/invoice.schema.json"),
        Path("templates/tasksupport/metadata-def.json"),
    ]
    for file in files:
        assert file.exists()

    # Test for files not created
    assert not Path("container/modules/modules.py").exists()

    if os.path.exists("container"):
        shutil.rmtree("container")

    if os.path.exists("input"):
        shutil.rmtree("input")

    if os.path.exists("templates"):
        shutil.rmtree("templates")


def test_init_no_overwrite():
    """initを実行して既存のファイルが上書きされないことをテスト"""
    runner = CliRunner()

    with runner.isolated_filesystem():
        runner.invoke(init)

        with open(Path("container/main.py"), "a", encoding="utf-8") as f:
            f.write("# Sample test message")

        runner.invoke(init)

        with open(Path("container/main.py"), encoding="utf-8") as f:
            content = f.read()
            assert "# Sample test message" in content


@pytest.fixture
def get_version_from_pyprojecttoml_py39_py310():
    import toml

    path = Path(os.path.dirname(os.path.dirname(__file__)), "pyproject.toml")
    with open(path, encoding="utf-8") as f:
        parse_toml = toml.loads(f.read())
    return parse_toml["project"]["version"]


@pytest.fixture
def get_version_from_pyprojecttoml_py311():
    py_version = platform.python_version_tuple()
    if StrictVersion(f"{py_version[0]}.{py_version[1]}") >= StrictVersion("3.11"):
        import tomllib

        path = Path(os.path.dirname(os.path.dirname(__file__)), "pyproject.toml")
        with open(path, encoding="utf-8") as f:
            parse_toml = tomllib.loads(f.read())
        return parse_toml["project"]["version"]
    return ""


def test_version(get_version_from_pyprojecttoml_py39_py310, get_version_from_pyprojecttoml_py311):
    py_version = platform.python_version_tuple()
    if StrictVersion(f"{py_version[0]}.{py_version[1]}") >= StrictVersion("3.11"):
        v = get_version_from_pyprojecttoml_py311 + "\n"
    else:
        v = get_version_from_pyprojecttoml_py39_py310 + "\n"

    runner = CliRunner()

    result = runner.invoke(version)

    assert v == result.output


@pytest.fixture
def temp_output_path(tmp_path):
    yield tmp_path / "output_excel_invoice.xlsx"


@pytest.fixture
def temp_invalid_output_path(tmp_path):
    yield tmp_path / "output_invalid_invoice.xlsx"


@pytest.fixture
def temp_output_folder(tmp_path):
    output_folder = tmp_path / "invoices"
    yield output_folder


def test_make_excelinvoice_file_mode_success(ivnoice_schema_json_with_full_sample_info, temp_output_path):
    """'file' モードでの正常な実行をテスト"""
    runner = CliRunner()
    result = runner.invoke(
        make_excelinvoice,
        [
            str(ivnoice_schema_json_with_full_sample_info),
            '-o',
            str(temp_output_path),
        ],
    )

    assert result.exit_code == 0
    assert temp_output_path.exists()
    assert "📄 Generating ExcelInvoice template..." in result.output
    assert f"- Schema: {Path(ivnoice_schema_json_with_full_sample_info).resolve()}" in result.output
    assert f"- Output: {temp_output_path}" in result.output
    assert "- Mode: file" in result.output
    assert f"✨ ExcelInvoice template generated successfully! : {temp_output_path}" in result.output


def test_make_excelinvoice_folder_mode_success(ivnoice_schema_json_with_full_sample_info, temp_output_path):
    """'file' モードでの正常な実行をテスト"""
    runner = CliRunner()
    result = runner.invoke(
        make_excelinvoice,
        [
            str(ivnoice_schema_json_with_full_sample_info),
            '-o',
            str(temp_output_path),
            "-m",
            "folder",
        ],
    )

    assert result.exit_code == 0
    assert temp_output_path.exists()
    assert "📄 Generating ExcelInvoice template..." in result.output
    assert f"- Schema: {Path(ivnoice_schema_json_with_full_sample_info).resolve()}" in result.output
    assert f"- Output: {temp_output_path}" in result.output
    assert "- Mode: folder" in result.output
    assert f"✨ ExcelInvoice template generated successfully! : {temp_output_path}" in result.output


def test_generate_excelinvoice_command_schema_error(invalid_ivnoice_schema_json, temp_output_path):
    """スキーマエラーテスト"""
    runner = CliRunner()
    result = runner.invoke(
        make_excelinvoice,
        [
            str(invalid_ivnoice_schema_json),
            '-o',
            str(temp_output_path),
        ],
    )

    assert "📄 Generating ExcelInvoice template..." in result.output
    assert f"- Schema: {Path(invalid_ivnoice_schema_json).resolve()}" in result.output
    assert f"- Output: {temp_output_path}" in result.output
    assert "- Mode: file" in result.output
    assert "🔥 Schema Error" in result.output


def test_generate_excelinvoice_command_unexpected_error(ivnoice_schema_json_with_full_sample_info, temp_output_path):
    """エラーテスト"""
    with patch('rdetoolkit.invoicefile.ExcelInvoiceFile.generate_template') as mock_generate:
        mock_generate.side_effect = Exception("Unexpected test error")
        runner = CliRunner()
        result = runner.invoke(
            make_excelinvoice,
            [
                str(ivnoice_schema_json_with_full_sample_info),
                '-o',
                str(temp_output_path),
            ],
        )

        assert "📄 Generating ExcelInvoice template..." in result.output
        assert f"- Schema: {Path(ivnoice_schema_json_with_full_sample_info).resolve()}" in result.output
        assert f"- Output: {temp_output_path}" in result.output
        assert "- Mode: file" in result.output
        assert "🔥 Error: An unexpected error occurred: Unexpected test error" in result.output
        assert result.exit_code != 0


def test_generate_excelinvoice_command_unexpected_output_format(ivnoice_schema_json_with_full_sample_info, temp_invalid_output_path):
    """ファイルの拡張子テスト"""
    runner = CliRunner()
    result = runner.invoke(
        make_excelinvoice,
        [
            str(ivnoice_schema_json_with_full_sample_info),
            '-o',
            str(temp_invalid_output_path),
        ],
    )

    assert "📄 Generating ExcelInvoice template..." in result.output
    assert f"- Schema: {Path(ivnoice_schema_json_with_full_sample_info).resolve()}" in result.output
    assert "- Mode: file" in result.output
    assert f"- Output: {temp_invalid_output_path}" in result.output
    assert f"🔥 Warning: The output file name '{Path(temp_invalid_output_path).name}' must end with '_excel_invoice.xlsx'." in result.output
    assert result.exit_code != 0


def test_make_excelinvoice_help():
    """make-excelinvoiceコマンドのヘルプメッセージをテストする"""
    runner = CliRunner()
    result = runner.invoke(make_excelinvoice, ['--help'])

    assert result.exit_code == 0
    assert "Usage: make-excelinvoice [OPTIONS] <invoice.schema.json file path>" in result.output
    assert "Generate an Excel invoice based on the provided schema and save it to the\n  specified output path." in result.output
    assert "-o, --output" in result.output
    assert "-m, --mode" in result.output
    assert "select the registration mode" in result.output


def test_json_file_validation(tmp_path, ivnoice_schema_json_with_full_sample_info):
    runner = CliRunner()

    invalid_ext_file = tmp_path / "invalid_file.txt"
    invalid_ext_file.write_text("{}")
    result = runner.invoke(
        make_excelinvoice,
        [
            str(invalid_ext_file),
            '-o',
            str(tmp_path / "output_excel_invoice.xlsx"),
        ],
    )
    assert result.exit_code != 0
    assert "The schema file must be a JSON file." in result.output

    invalid_json_file = tmp_path / "invalid_json.json"
    invalid_json_file.write_text("Invalid JSON content")
    result = runner.invoke(
        make_excelinvoice,
        [
            str(invalid_json_file),
            '-o',
            str(tmp_path / "output_excel_invoice.xlsx"),
        ],
    )
    assert result.exit_code != 0
    assert "The schema file must be a valid JSON file." in result.output

    valid_json_file = ivnoice_schema_json_with_full_sample_info
    result = runner.invoke(
        make_excelinvoice,
        [
            str(valid_json_file),
            '-o',
            str(tmp_path / "output_excel_invoice.xlsx"),
        ],
    )
    assert result.exit_code == 0


@pytest.fixture
def temp_source_dir(tmp_path: Path) -> Path:
    """Create a temporary source directory for testing.
    - Includes Dockerfile and requirements.txt
    - Contains a Python file with a vulnerability (vuln.py) using eval
    - Contains a Python file with external communication (external.py) using requests.get
    """
    src_dir = tmp_path / "source"
    src_dir.mkdir()
    sub_dir = src_dir / "container"
    sub_dir.mkdir()

    # Required files
    (sub_dir / "Dockerfile").write_text("FROM python:3.8")
    (sub_dir / "requirements.txt").write_text("click\npytz")

    # Vulnerable file
    vuln_file = sub_dir / "vuln.py"
    vuln_file.write_text(textwrap.dedent("""
        def insecure():
            value = eval("1+2")
            print(value)
    """))
    # File with external communication
    ext_file = sub_dir / "external.py"
    ext_file.write_text(textwrap.dedent("""
        import requests
        def fetch():
            response = requests.get("https://example.com")
            return response.text
    """))
    return src_dir


@pytest.fixture
def temp_output_archive(tmp_path: Path) -> Path:
    """Temporary file path to be used as the output archive (with a .zip extension).
    """
    return tmp_path / "output.zip"


def test_invoke_with_default_values(temp_source_dir, capsys):
    """Uses default values for the output archive path and exclude_patterns."""
    command = CreateArtifactCommand(
        source_dir=temp_source_dir,
    )

    command.invoke()

    # Check that the default output file is generated
    report_files = list(temp_source_dir.parent.glob("*_rde_artifact.md"))
    assert len(report_files) == 1, "Default named report file was not generated"

    report_content = report_files[0].read_text(encoding="utf-8")
    assert "Execution Report" in report_content

    # Verify standard output
    captured = capsys.readouterr().out
    assert "Archiving project files" in captured


def test_invoke_creates_report(temp_source_dir, temp_output_archive, capsys):
    """Execute CreateArtifactCommand.invoke() and verify:
    - The process runs correctly when the required files exist in the source directory.
    - After invoking, a Markdown report (.md file) is generated in the same location as the output_archive.
    - The generated report contains information such as Dockerfile and requirements.txt details.
    - The output of click.echo includes the expected strings.
    """
    # Initially, the output_archive (.zip file) does not need to exist.
    if temp_output_archive.exists():
        temp_output_archive.unlink()

    exclude_patterns = ["venv", "site-packages"]
    command = CreateArtifactCommand(temp_source_dir, output_archive_path=temp_output_archive, exclude_patterns=exclude_patterns)

    # Directly call invoke() (internally performs archiving, scanning, and report generation).
    command.invoke()

    # The generated report file should have the same name as output_archive but with a .md extension.
    report_path = temp_output_archive.with_suffix(".md")

    assert report_path.exists(), "The report file was not generated."

    report_content = report_path.read_text(encoding="utf-8")
    # Verify that the expected items exist in the template (contents depend on the implementation).
    assert "Execution Report" in report_content or "Execution Date:" in report_content
    assert "Dockerfile" in report_content, "Dockerfile information is missing in the report."
    assert "requirements.txt" in report_content, "requirements.txt information is missing in the report."

    # Also, check the content echoed to standard output.
    captured = capsys.readouterr().out
    assert "Archiving project files" in captured
    assert "Source Directory:" in captured
    assert "Output Archive:" in captured


def test_report_generation_failure(temp_source_dir, temp_output_archive, capsys):
    """Test that an exception (click.Abort) is raised when the report output path
    is a directory during report generation.
    """
    report_path = temp_output_archive.with_suffix(".md")
    report_path.mkdir(exist_ok=True)
    with pytest.raises(click.Abort):
        command = CreateArtifactCommand(
            source_dir=temp_source_dir,
            output_archive_path=temp_output_archive,
            exclude_patterns=["venv", "site-packages"],
        )
        command.invoke()
    captured = capsys.readouterr().out
    assert "Error:" in captured


@pytest.fixture
def sample_csv_file(tmp_path: Path) -> Path:
    """Create a simple CSV file for testing csv2graph command."""
    csv_file = tmp_path / "test_data.csv"
    csv_content = """X,Y1,Y2
1.0,10.5,20.3
2.0,15.2,25.8
3.0,12.8,22.1
4.0,18.5,28.9
5.0,16.3,24.5
"""
    csv_file.write_text(csv_content)
    return csv_file


@pytest.fixture
def single_series_csv_file(tmp_path: Path) -> Path:
    """Create a CSV file with a single Y series."""
    csv_file = tmp_path / "single_series.csv"
    csv_file.write_text(
        """X,Y1
0,1
1,2
2,3
""",
        encoding="utf-8",
    )
    return csv_file


@pytest.fixture
def csv_output_dir(tmp_path: Path) -> Path:
    """Create a temporary output directory for graph files."""
    output_dir = tmp_path / "graphs"
    output_dir.mkdir()
    return output_dir


def test_csv2graph_cli_auto_suppresses_single_series__tc_ep_cli_001(single_series_csv_file: Path, csv_output_dir: Path) -> None:
    """Auto detection skips individual PNGs for single-series overlay inputs."""
    runner = CliRunner()

    # Given: a single-series CSV without explicit flags
    # When: invoking csv2graph in overlay mode
    result = runner.invoke(
        csv2graph,
        [
            str(single_series_csv_file),
            "--output-dir", str(csv_output_dir),
        ],
    )

    # Then: only the overlay PNG is present
    assert result.exit_code == 0, result.output
    overlay = csv_output_dir / f"{single_series_csv_file.stem}.png"
    assert overlay.exists()
    individual_files = list(csv_output_dir.glob(f"{single_series_csv_file.stem}_*.png"))
    assert not individual_files


def test_csv2graph_cli_individual_flag_restores_output__tc_ep_cli_002(single_series_csv_file: Path, csv_output_dir: Path) -> None:
    """Explicit --individual should re-enable per-series PNGs."""
    runner = CliRunner()

    # Given: a single-series CSV
    # When: invoking csv2graph with --individual
    result = runner.invoke(
        csv2graph,
        [
            str(single_series_csv_file),
            "--output-dir", str(csv_output_dir),
            "--individual",
        ],
    )

    # Then: both overlay and individual PNGs exist
    assert result.exit_code == 0, result.output
    overlay = csv_output_dir / f"{single_series_csv_file.stem}.png"
    assert overlay.exists()
    individual_files = list(csv_output_dir.glob(f"{single_series_csv_file.stem}_*.png"))
    assert individual_files


def test_csv2graph_cli_multiple_series_keeps_individuals__tc_ep_cli_003(sample_csv_file: Path, csv_output_dir: Path) -> None:
    """Multi-series CSVs should still emit individual PNGs by default."""
    runner = CliRunner()

    # Given: a CSV with multiple Y columns
    # When: invoking csv2graph without overriding flags
    result = runner.invoke(
        csv2graph,
        [
            str(sample_csv_file),
            "--output-dir", str(csv_output_dir),
        ],
    )

    # Then: overlay and per-series PNGs exist
    assert result.exit_code == 0, result.output
    overlay = csv_output_dir / f"{sample_csv_file.stem}.png"
    assert overlay.exists()
    individual_files = list(csv_output_dir.glob(f"{sample_csv_file.stem}_*.png"))
    assert individual_files


def test_csv2graph_cli_explicit_no_individual_skips_outputs__tc_ep_cli_004(sample_csv_file: Path, csv_output_dir: Path) -> None:
    """Explicit --no-individual suppresses per-series PNGs even with multiple series."""
    runner = CliRunner()

    # Given: a multi-series CSV
    # When: invoking csv2graph with --no-individual
    result = runner.invoke(
        csv2graph,
        [
            str(sample_csv_file),
            "--output-dir", str(csv_output_dir),
            "--no-individual",
        ],
    )

    # Then: only the overlay PNG remains
    assert result.exit_code == 0, result.output
    overlay = csv_output_dir / f"{sample_csv_file.stem}.png"
    assert overlay.exists()
    individual_files = list(csv_output_dir.glob(f"{sample_csv_file.stem}_*.png"))
    assert not individual_files


def test_csv2graph_cli_series_count_boundary__tc_bv_cli_001(
    single_series_csv_file: Path,
    sample_csv_file: Path,
    tmp_path: Path,
) -> None:
    """Validate the transition between single- and multi-series CSV handling."""
    runner = CliRunner()

    single_output = tmp_path / "single_out"
    single_output.mkdir()
    multi_output = tmp_path / "multi_out"
    multi_output.mkdir()

    # Given: a single-series CSV without overrides
    # When: invoking csv2graph
    result_single = runner.invoke(
        csv2graph,
        [
            str(single_series_csv_file),
            "--output-dir", str(single_output),
        ],
    )

    # Then: the overlay PNG exists and no per-series PNG is produced
    assert result_single.exit_code == 0, result_single.output
    assert (single_output / f"{single_series_csv_file.stem}.png").exists()
    assert not list(single_output.glob(f"{single_series_csv_file.stem}_*.png"))

    # Given: a multi-series CSV without overrides
    # When: invoking csv2graph
    result_multi = runner.invoke(
        csv2graph,
        [
            str(sample_csv_file),
            "--output-dir", str(multi_output),
        ],
    )

    # Then: overlay and per-series PNGs exist
    assert result_multi.exit_code == 0, result_multi.output
    assert (multi_output / f"{sample_csv_file.stem}.png").exists()
    assert list(multi_output.glob(f"{sample_csv_file.stem}_*.png"))


def test_csv2graph_cli_mode_boundary__tc_bv_cli_002(sample_csv_file: Path, tmp_path: Path) -> None:
    """Ensure mode transitions keep expected overlay/individual combinations."""
    runner = CliRunner()

    overlay_output = tmp_path / "overlay_out"
    overlay_output.mkdir()
    individual_output = tmp_path / "individual_out"
    individual_output.mkdir()

    # Given: overlay mode on a multi-series CSV
    # When: invoking csv2graph
    overlay_result = runner.invoke(
        csv2graph,
        [
            str(sample_csv_file),
            "--output-dir", str(overlay_output),
        ],
    )

    # Then: overlay and per-series PNGs exist
    assert overlay_result.exit_code == 0, overlay_result.output
    assert (overlay_output / f"{sample_csv_file.stem}.png").exists()
    assert list(overlay_output.glob(f"{sample_csv_file.stem}_*.png"))

    # Given: individual mode on the same CSV
    # When: invoking csv2graph with --mode individual
    individual_result = runner.invoke(
        csv2graph,
        [
            str(sample_csv_file),
            "--output-dir", str(individual_output),
            "--mode", "individual",
        ],
    )

    # Then: overlay PNG is absent while per-series PNGs are generated
    assert individual_result.exit_code == 0, individual_result.output
    assert not (individual_output / f"{sample_csv_file.stem}.png").exists()
    assert list(individual_output.glob(f"{sample_csv_file.stem}_*.png"))


def test_csv2graph_basic_success(sample_csv_file, csv_output_dir):
    """Test basic csv2graph command execution with minimal options."""
    runner = CliRunner()
    result = runner.invoke(
        csv2graph,
        [
            str(sample_csv_file),
            "--output-dir", str(csv_output_dir),
        ],
    )

    assert result.exit_code == 0
    assert "📊 Generating graphs from CSV..." in result.output
    assert f"- CSV file: {sample_csv_file}" in result.output
    assert f"- Output: {csv_output_dir}" in result.output
    assert "- Mode: overlay" in result.output
    assert "✨ Graphs generated successfully" in result.output

    # Check that output file was created
    output_files = list(csv_output_dir.glob("*.png"))
    assert len(output_files) > 0, "No PNG files were generated"


def test_csv2graph_with_options(sample_csv_file, csv_output_dir):
    """Test csv2graph command with various options."""
    runner = CliRunner()
    result = runner.invoke(
        csv2graph,
        [
            str(sample_csv_file),
            "--output-dir", str(csv_output_dir),
            "--title", "Test Plot",
            "--grid",
            "--invert-x",
            "--logy",
        ],
    )

    assert result.exit_code == 0
    assert "📊 Generating graphs from CSV..." in result.output
    assert "✨ Graphs generated successfully" in result.output


def test_csv2graph_individual_mode(sample_csv_file, csv_output_dir):
    """Test csv2graph command in individual plotting mode."""
    runner = CliRunner()
    result = runner.invoke(
        csv2graph,
        [
            str(sample_csv_file),
            "--output-dir", str(csv_output_dir),
            "--mode", "individual",
        ],
    )

    assert result.exit_code == 0
    assert "- Mode: individual" in result.output

    # Individual mode should create multiple PNG files
    output_files = list(csv_output_dir.glob("*.png"))
    assert len(output_files) > 0, "No PNG files were generated in individual mode"


def test_csv2graph_main_image_dir(sample_csv_file, csv_output_dir, tmp_path: Path):
    """Ensure combined plots are routed to the main image directory."""
    main_image_dir = tmp_path / "main_images"
    main_image_dir.mkdir()

    runner = CliRunner()
    result = runner.invoke(
        csv2graph,
        [
            str(sample_csv_file),
            "--output-dir", str(csv_output_dir),
            "--main-image-dir", str(main_image_dir),
        ],
    )

    assert result.exit_code == 0
    assert "- Main images:" in result.output

    combined_name = sample_csv_file.stem + ".png"
    assert (main_image_dir / combined_name).exists()
    assert not (csv_output_dir / combined_name).exists()

    individual_files = list(csv_output_dir.glob(f"{sample_csv_file.stem}_*.png"))
    assert individual_files, "Individual plots were not written to output directory"


def test_csv2graph_file_not_found():
    """Test csv2graph command with non-existent CSV file."""
    runner = CliRunner()
    non_existent = Path("/tmp/non_existent_file.csv")

    result = runner.invoke(
        csv2graph,
        [str(non_existent)],
    )

    assert result.exit_code != 0
    assert "🔥 File Error" in result.output


def test_csv2graph_help():
    """Test csv2graph command help message."""
    runner = CliRunner()
    result = runner.invoke(csv2graph, ["--help"])

    assert result.exit_code == 0
    assert "Usage: csv2graph [OPTIONS] CSV_PATH" in result.output
    assert "Generate graphs from CSV files." in result.output
    assert "--output-dir" in result.output
    assert "--main-image-dir" in result.output
    assert "--mode" in result.output
    assert "--title" in result.output
