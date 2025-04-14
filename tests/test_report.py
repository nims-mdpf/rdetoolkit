from datetime import datetime
import textwrap
import pytest
import pytz
from rdetoolkit.artifact.report import (
    TemplateMarkdownReportGenerator,
    CodeSecurityScanner,
    ExternalConnScanner,
    get_scanner,
)
from rdetoolkit.models.reports import ReportItem, CodeSnippet


def test_get_scanner_vulnerability():
    scanner = get_scanner("vulnerability", "/path/to/source")
    assert isinstance(scanner, CodeSecurityScanner)


def test_get_scanner_external():
    scanner = get_scanner("external", "/path/to/source")
    assert isinstance(scanner, ExternalConnScanner)


def test_get_scanner_unknown():
    with pytest.raises(ValueError):
        get_scanner("unknown", "/path/to/source")


@pytest.fixture
def sample_report_item():
    """Generate a ReportItem with sample data"""
    return ReportItem(
        exec_date=datetime.now(tz=pytz.UTC).strftime("%Y-%m-%d %H:%M:%S"),
        dockerfile_path="Dockerfile",
        requirements_path="requirements.txt",
        include_dirs=["src", "tests"],
        code_security_scan_results=[
            CodeSnippet(
                file_path="src/example.py",
                snippet="1: eval('1+2')\n2: print('vuln')",
                description="Usage of eval() poses the risk of arbitrary code execution.",
            ),
        ],
        code_ext_requests_scan_results=[
            CodeSnippet(
                file_path="src/api.py",
                snippet="1: import requests\n2: requests.get('https://example.com')",
                description=None,
            ),
        ],
    )


def test_generate_report(sample_report_item):
    """TemplateMarkdownReportGenerator.generate generates a report based on the contents of ReportItem"""
    generator = TemplateMarkdownReportGenerator()
    report_text = generator.generate(sample_report_item)

    assert "Execution Report" in report_text
    assert sample_report_item.exec_date in report_text
    assert sample_report_item.dockerfile_path in report_text
    assert sample_report_item.requirements_path in report_text
    for d in sample_report_item.include_dirs:
        assert f"- {d}" in report_text
    assert "eval(" in report_text or "vuln" in report_text
    assert "import requests" in report_text or "requests.get" in report_text


def test_save_report(tmp_path, sample_report_item):
    """Test if TemplateMarkdownReportGenerator.save can output to a file"""
    generator = TemplateMarkdownReportGenerator()
    _ = generator.generate(sample_report_item)
    report_file = tmp_path / "report.md"
    generator.save(report_file)

    assert report_file.exists()
    content = report_file.read_text(encoding="utf-8")
    assert sample_report_item.exec_date in content
    assert "Dockerfile" in content
    assert "requirements.txt" in content


@pytest.fixture
def temp_vuln_file(tmp_path):
    """Create a test Python file containing vulnerabilities"""
    file_path = tmp_path / "vuln_test.py"
    file_path.write_text(textwrap.dedent("""
        def insecure():
            value = eval("1+2")
            print(value)
    """))
    return tmp_path


def test_code_security_scanner(temp_vuln_file):
    """Test if CodeSecurityScanner can detect vulnerability patterns"""
    scanner = CodeSecurityScanner(temp_vuln_file)
    results = scanner.scan()
    assert len(results) >= 1
    assert any("vuln_test.py" in r.file_path for r in results)
    assert any("eval(" in r.snippet for r in results)


@pytest.fixture
def temp_external_file(tmp_path):
    """Create a test file containing external communication code"""
    file_path = tmp_path / "external_test.py"
    file_path.write_text(textwrap.dedent("""
        import requests

        def get_data():
            response = requests.get('https://example.com')
            return response.text
    """))
    return tmp_path


def test_external_conn_scanner(temp_external_file):
    """Test if ExternalConnScanner can detect external communication code"""
    scanner = ExternalConnScanner(temp_external_file)
    results = scanner.scan()
    assert len(results) >= 1
    assert any("external_test.py" in r.file_path for r in results)
    assert any("requests.get" in r.snippet for r in results)


def test_get_scanner():
    """Test if the get_scanner function returns the correct instance"""
    vuln_scanner = get_scanner("vulnerability", "/tmp")
    assert isinstance(vuln_scanner, CodeSecurityScanner)

    external_scanner = get_scanner("external", "/tmp")
    assert isinstance(external_scanner, ExternalConnScanner)

    with pytest.raises(ValueError) as excinfo:
        get_scanner("unknown", "/tmp")
    assert "Unknown scanner type" in str(excinfo.value)
