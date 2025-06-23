# Reports Module

The `rdetoolkit.models.reports` module provides Pydantic models for generating and managing security scan reports and code analysis results. This module implements structured data models for documenting security vulnerabilities, external request activities, and code quality assessments in RDE systems.

## Overview

The reports module implements a comprehensive reporting system with the following capabilities:

- **Security Scan Reports**: Structured reporting of code security vulnerabilities
- **External Request Tracking**: Documentation of external API calls and network requests
- **Code Quality Analysis**: Integration with code scanning and analysis tools
- **Standardized Documentation**: Consistent format for audit trails and compliance reporting
- **Flexible Description Fields**: Optional detailed descriptions for findings

## Core Classes

### CodeSnippet

Model for representing code snippets found during security or quality scans.

#### CodeSnippet Constructor

```python
CodeSnippet(
    file_path: str,
    snippet: str,
    description: str | None = None
)
```

**Parameters:**

- `file_path` (str): Path to the file containing the code snippet
- `snippet` (str): The actual code snippet that was identified
- `description` (str | None): Optional description explaining the significance of the snippet

#### CodeSnippet Example

```python
from rdetoolkit.models.reports import CodeSnippet

# Security vulnerability example
security_issue = CodeSnippet(
    file_path="src/auth/login.py",
    snippet="password = request.form['password']  # Plain text password",
    description="Password handled in plain text without encryption"
)

# External request example
external_call = CodeSnippet(
    file_path="src/api/data_fetcher.py",
    snippet="response = requests.get('https://api.external.com/data')",
    description="External API call to third-party service"
)

# Code quality issue
quality_issue = CodeSnippet(
    file_path="src/utils/helpers.py",
    snippet="def calculate(x, y): return x/y",
    description="Division by zero not handled"
)

print(security_issue.file_path)    # src/auth/login.py
print(external_call.snippet)      # response = requests.get('https://api.external.com/data')
print(quality_issue.description)  # Division by zero not handled
```

### ReportItem

Comprehensive model for security and code analysis reports.

#### Constructor

```python
ReportItem(
    exec_date: str,
    dockerfile_path: str,
    requirements_path: str,
    include_dirs: list[str],
    code_security_scan_results: list[CodeSnippet],
    code_ext_requests_scan_results: list[CodeSnippet]
)
```

**Parameters:**

- `exec_date` (str): Date when the scan was executed (ISO format recommended)
- `dockerfile_path` (str): Path to the Dockerfile used for the environment
- `requirements_path` (str): Path to the requirements file (e.g., requirements.txt)
- `include_dirs` (list[str]): List of directories included in the scan
- `code_security_scan_results` (list[CodeSnippet]): Security vulnerability findings
- `code_ext_requests_scan_results` (list[CodeSnippet]): External request findings

#### Example

```python
from rdetoolkit.models.reports import ReportItem, CodeSnippet
from datetime import datetime

# Create security findings
security_findings = [
    CodeSnippet(
        file_path="src/auth/session.py",
        snippet="session['user_id'] = user.id",
        description="Session data stored without encryption"
    ),
    CodeSnippet(
        file_path="src/database/connection.py",
        snippet="cursor.execute(f'SELECT * FROM users WHERE id = {user_id}')",
        description="SQL injection vulnerability - unparameterized query"
    )
]

# Create external request findings
external_requests = [
    CodeSnippet(
        file_path="src/services/weather.py",
        snippet="requests.get('http://api.openweathermap.org/data/2.5/weather')",
        description="External weather API call"
    ),
    CodeSnippet(
        file_path="src/integrations/analytics.py",
        snippet="requests.post('https://analytics.service.com/track')",
        description="Analytics tracking service call"
    )
]

# Create comprehensive report
report = ReportItem(
    exec_date="2025-01-15T10:30:00Z",
    dockerfile_path="docker/Dockerfile.prod",
    requirements_path="requirements/production.txt",
    include_dirs=["src/", "tests/", "scripts/"],
    code_security_scan_results=security_findings,
    code_ext_requests_scan_results=external_requests
)

# Access report data
print(f"Scan executed on: {report.exec_date}")
print(f"Found {len(report.code_security_scan_results)} security issues")
print(f"Found {len(report.code_ext_requests_scan_results)} external requests")
print(f"Scanned directories: {', '.join(report.include_dirs)}")
```

## Complete Usage Examples

### Security Scan Report Generation

```python
from rdetoolkit.models.reports import ReportItem, CodeSnippet
from datetime import datetime
from pathlib import Path
import json

class SecurityScanner:
    """Example security scanner that generates reports."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.security_patterns = [
            ("password", "Potential password in plain text"),
            ("SECRET", "Hardcoded secret detected"),
            ("eval(", "Dangerous eval() usage"),
            ("exec(", "Dangerous exec() usage"),
            ("subprocess.call", "Subprocess call - review for command injection")
        ]
        self.external_patterns = [
            ("requests.get", "HTTP GET request"),
            ("requests.post", "HTTP POST request"),
            ("urllib.request", "urllib request"),
            ("httpx.", "HTTPX client request"),
            ("aiohttp.", "Aiohttp request")
        ]

    def scan_file(self, file_path: Path) -> tuple[list[CodeSnippet], list[CodeSnippet]]:
        """Scan a single file for security issues and external requests."""

        security_findings = []
        external_findings = []

        try:
            content = file_path.read_text(encoding='utf-8')
            lines = content.splitlines()

            for line_num, line in enumerate(lines, 1):
                line_stripped = line.strip()

                # Check for security patterns
                for pattern, description in self.security_patterns:
                    if pattern in line_stripped:
                        security_findings.append(CodeSnippet(
                            file_path=str(file_path.relative_to(self.project_root)),
                            snippet=f"Line {line_num}: {line_stripped}",
                            description=f"{description} (Line {line_num})"
                        ))

                # Check for external request patterns
                for pattern, description in self.external_patterns:
                    if pattern in line_stripped:
                        external_findings.append(CodeSnippet(
                            file_path=str(file_path.relative_to(self.project_root)),
                            snippet=f"Line {line_num}: {line_stripped}",
                            description=f"{description} (Line {line_num})"
                        ))

        except Exception as e:
            # Handle encoding or other errors
            print(f"Error scanning {file_path}: {e}")

        return security_findings, external_findings

    def scan_directory(self, scan_dirs: list[str]) -> ReportItem:
        """Scan multiple directories and generate a report."""

        all_security_findings = []
        all_external_findings = []

        for scan_dir in scan_dirs:
            dir_path = self.project_root / scan_dir
            if not dir_path.exists():
                continue

            # Scan Python files
            for py_file in dir_path.rglob("*.py"):
                security, external = self.scan_file(py_file)
                all_security_findings.extend(security)
                all_external_findings.extend(external)

        # Create report
        report = ReportItem(
            exec_date=datetime.now().isoformat(),
            dockerfile_path="Dockerfile",
            requirements_path="requirements.txt",
            include_dirs=scan_dirs,
            code_security_scan_results=all_security_findings,
            code_ext_requests_scan_results=all_external_findings
        )

        return report

# Usage example
scanner = SecurityScanner(Path("project_root"))
report = scanner.scan_directory(["src/", "tests/", "scripts/"])

print(f"Security scan completed at {report.exec_date}")
print(f"Scanned directories: {report.include_dirs}")
print(f"Security issues found: {len(report.code_security_scan_results)}")
print(f"External requests found: {len(report.code_ext_requests_scan_results)}")
```

### Report Serialization and Storage

```python
from rdetoolkit.models.reports import ReportItem, CodeSnippet
import json
from pathlib import Path
from datetime import datetime

def save_report_to_json(report: ReportItem, output_path: Path) -> None:
    """Save a report to a JSON file."""

    # Serialize to dictionary
    report_dict = report.model_dump()

    # Save to file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report_dict, f, indent=2, ensure_ascii=False)

    print(f"Report saved to {output_path}")

def load_report_from_json(file_path: Path) -> ReportItem:
    """Load a report from a JSON file."""

    with open(file_path, 'r', encoding='utf-8') as f:
        report_dict = json.load(f)

    # Reconstruct the report
    return ReportItem(**report_dict)

def generate_html_report(report: ReportItem, output_path: Path) -> None:
    """Generate an HTML report from a ReportItem."""

    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Security Scan Report</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .header { background-color: #f0f0f0; padding: 10px; border-radius: 5px; }
            .section { margin: 20px 0; }
            .finding { background-color: #fff3cd; padding: 10px; margin: 5px 0; border-left: 4px solid #ffc107; }
            .external { background-color: #d1ecf1; padding: 10px; margin: 5px 0; border-left: 4px solid #17a2b8; }
            .code { background-color: #f8f9fa; padding: 5px; font-family: monospace; border-radius: 3px; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Security Scan Report</h1>
            <p><strong>Execution Date:</strong> {exec_date}</p>
            <p><strong>Dockerfile:</strong> {dockerfile_path}</p>
            <p><strong>Requirements:</strong> {requirements_path}</p>
            <p><strong>Scanned Directories:</strong> {include_dirs}</p>
        </div>

        <div class="section">
            <h2>Security Issues ({security_count})</h2>
            {security_findings}
        </div>

        <div class="section">
            <h2>External Requests ({external_count})</h2>
            {external_findings}
        </div>
    </body>
    </html>
    """

    # Generate security findings HTML
    security_html = ""
    for finding in report.code_security_scan_results:
        security_html += f"""
        <div class="finding">
            <strong>File:</strong> {finding.file_path}<br>
            <strong>Code:</strong> <code class="code">{finding.snippet}</code><br>
            <strong>Description:</strong> {finding.description or 'No description'}
        </div>
        """

    # Generate external request findings HTML
    external_html = ""
    for finding in report.code_ext_requests_scan_results:
        external_html += f"""
        <div class="external">
            <strong>File:</strong> {finding.file_path}<br>
            <strong>Code:</strong> <code class="code">{finding.snippet}</code><br>
            <strong>Description:</strong> {finding.description or 'No description'}
        </div>
        """

    # Fill template
    html_content = html_template.format(
        exec_date=report.exec_date,
        dockerfile_path=report.dockerfile_path,
        requirements_path=report.requirements_path,
        include_dirs=", ".join(report.include_dirs),
        security_count=len(report.code_security_scan_results),
        external_count=len(report.code_ext_requests_scan_results),
        security_findings=security_html,
        external_findings=external_html
    )

    # Save HTML file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"HTML report saved to {output_path}")

# Example usage
report = ReportItem(
    exec_date="2025-01-15T14:30:00Z",
    dockerfile_path="docker/Dockerfile.prod",
    requirements_path="requirements/production.txt",
    include_dirs=["src/", "tests/"],
    code_security_scan_results=[
        CodeSnippet(
            file_path="src/auth.py",
            snippet="password = 'hardcoded_secret'",
            description="Hardcoded password detected"
        )
    ],
    code_ext_requests_scan_results=[
        CodeSnippet(
            file_path="src/api.py",
            snippet="requests.get('https://api.example.com')",
            description="External API call"
        )
    ]
)

# Save in different formats
save_report_to_json(report, Path("security_report.json"))
generate_html_report(report, Path("security_report.html"))

# Load and verify
loaded_report = load_report_from_json(Path("security_report.json"))
assert loaded_report.exec_date == report.exec_date
print("Report successfully saved and loaded!")
```

### Integration with CI/CD Pipeline

```python
from rdetoolkit.models.reports import ReportItem, CodeSnippet
import subprocess
import json
from pathlib import Path
from datetime import datetime

class CICDSecurityIntegration:
    """Integration class for CI/CD security scanning."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.report_dir = project_root / "security_reports"
        self.report_dir.mkdir(exist_ok=True)

    def run_bandit_scan(self, scan_dirs: list[str]) -> list[CodeSnippet]:
        """Run Bandit security scanner and parse results."""

        findings = []

        try:
            # Run bandit with JSON output
            cmd = ["bandit", "-r", "-f", "json"] + scan_dirs
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.project_root)

            if result.returncode == 0 or result.stdout:
                bandit_data = json.loads(result.stdout)

                for issue in bandit_data.get("results", []):
                    findings.append(CodeSnippet(
                        file_path=issue["filename"],
                        snippet=issue["code"],
                        description=f"{issue['test_name']}: {issue['issue_text']}"
                    ))

        except Exception as e:
            print(f"Error running Bandit: {e}")

        return findings

    def scan_for_external_requests(self, scan_dirs: list[str]) -> list[CodeSnippet]:
        """Scan for external HTTP requests in code."""

        findings = []
        request_patterns = [
            "requests.",
            "urllib.request",
            "httpx.",
            "aiohttp.",
            "fetch(",
            "axios."
        ]

        for scan_dir in scan_dirs:
            dir_path = self.project_root / scan_dir
            if not dir_path.exists():
                continue

            for file_path in dir_path.rglob("*"):
                if file_path.suffix in [".py", ".js", ".ts"]:
                    try:
                        content = file_path.read_text(encoding='utf-8')
                        lines = content.splitlines()

                        for line_num, line in enumerate(lines, 1):
                            for pattern in request_patterns:
                                if pattern in line:
                                    findings.append(CodeSnippet(
                                        file_path=str(file_path.relative_to(self.project_root)),
                                        snippet=line.strip(),
                                        description=f"External request detected at line {line_num}"
                                    ))
                    except Exception as e:
                        print(f"Error scanning {file_path}: {e}")

        return findings

    def generate_comprehensive_report(self, scan_dirs: list[str]) -> ReportItem:
        """Generate comprehensive security and external request report."""

        # Run security scan
        security_findings = self.run_bandit_scan(scan_dirs)

        # Scan for external requests
        external_findings = self.scan_for_external_requests(scan_dirs)

        # Create report
        report = ReportItem(
            exec_date=datetime.now().isoformat(),
            dockerfile_path=str(self.project_root / "Dockerfile"),
            requirements_path=str(self.project_root / "requirements.txt"),
            include_dirs=scan_dirs,
            code_security_scan_results=security_findings,
            code_ext_requests_scan_results=external_findings
        )

        return report

    def save_report_with_timestamp(self, report: ReportItem) -> Path:
        """Save report with timestamp in filename."""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.report_dir / f"security_report_{timestamp}.json"

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report.model_dump_json(indent=2))

        return report_path

    def check_security_thresholds(self, report: ReportItem) -> bool:
        """Check if security findings exceed acceptable thresholds."""

        # Define thresholds
        max_high_severity = 0
        max_medium_severity = 5
        max_total_findings = 10

        # Count severity levels (simplified - in real scenario, parse from descriptions)
        high_severity = sum(1 for finding in report.code_security_scan_results
                          if "high" in finding.description.lower())
        medium_severity = sum(1 for finding in report.code_security_scan_results
                            if "medium" in finding.description.lower())
        total_findings = len(report.code_security_scan_results)

        # Check thresholds
        if high_severity > max_high_severity:
            print(f"❌ High severity issues: {high_severity} (max: {max_high_severity})")
            return False

        if medium_severity > max_medium_severity:
            print(f"❌ Medium severity issues: {medium_severity} (max: {max_medium_severity})")
            return False

        if total_findings > max_total_findings:
            print(f"❌ Total security issues: {total_findings} (max: {max_total_findings})")
            return False

        print("✅ Security scan passed all thresholds")
        return True

# Usage in CI/CD
def ci_security_check():
    """Main function for CI/CD security checking."""

    scanner = CICDSecurityIntegration(Path("."))

    # Generate report
    report = scanner.generate_comprehensive_report(["src/", "tests/"])

    # Save report
    report_path = scanner.save_report_with_timestamp(report)
    print(f"Report saved: {report_path}")

    # Check thresholds
    passed = scanner.check_security_thresholds(report)

    # Print summary
    print(f"""
Security Scan Summary:
- Execution Date: {report.exec_date}
- Security Issues: {len(report.code_security_scan_results)}
- External Requests: {len(report.code_ext_requests_scan_results)}
- Directories Scanned: {', '.join(report.include_dirs)}
- Threshold Check: {'PASSED' if passed else 'FAILED'}
    """)

    # Exit with appropriate code for CI/CD
    return 0 if passed else 1

# Example usage
if __name__ == "__main__":
    exit_code = ci_security_check()
    exit(exit_code)
```

### Report Analysis and Aggregation

```python
from rdetoolkit.models.reports import ReportItem, CodeSnippet
from pathlib import Path
import json
from datetime import datetime, timedelta
from collections import defaultdict

class ReportAnalyzer:
    """Analyzer for aggregating and analyzing multiple security reports."""

    def __init__(self, reports_dir: Path):
        self.reports_dir = reports_dir

    def load_all_reports(self, days_back: int = 30) -> list[ReportItem]:
        """Load all reports from the last N days."""

        cutoff_date = datetime.now() - timedelta(days=days_back)
        reports = []

        for report_file in self.reports_dir.glob("*.json"):
            try:
                with open(report_file, 'r', encoding='utf-8') as f:
                    report_data = json.load(f)

                report = ReportItem(**report_data)
                report_date = datetime.fromisoformat(report.exec_date.replace('Z', '+00:00'))

                if report_date >= cutoff_date:
                    reports.append(report)

            except Exception as e:
                print(f"Error loading report {report_file}: {e}")

        return reports

    def analyze_security_trends(self, reports: list[ReportItem]) -> dict:
        """Analyze security vulnerability trends over time."""

        trends = {
            "total_scans": len(reports),
            "average_security_issues": 0,
            "average_external_requests": 0,
            "most_common_security_patterns": defaultdict(int),
            "most_affected_files": defaultdict(int),
            "severity_distribution": defaultdict(int)
        }

        if not reports:
            return trends

        total_security = 0
        total_external = 0

        for report in reports:
            total_security += len(report.code_security_scan_results)
            total_external += len(report.code_ext_requests_scan_results)

            # Analyze security patterns
            for finding in report.code_security_scan_results:
                if finding.description:
                    # Extract pattern (simplified)
                    pattern = finding.description.split(':')[0] if ':' in finding.description else finding.description
                    trends["most_common_security_patterns"][pattern] += 1

                # Track affected files
                trends["most_affected_files"][finding.file_path] += 1

                # Analyze severity (simplified)
                if finding.description:
                    desc_lower = finding.description.lower()
                    if "high" in desc_lower:
                        trends["severity_distribution"]["high"] += 1
                    elif "medium" in desc_lower:
                        trends["severity_distribution"]["medium"] += 1
                    elif "low" in desc_lower:
                        trends["severity_distribution"]["low"] += 1
                    else:
                        trends["severity_distribution"]["unknown"] += 1

        trends["average_security_issues"] = total_security / len(reports)
        trends["average_external_requests"] = total_external / len(reports)

        return trends

    def generate_executive_summary(self, trends: dict) -> str:
        """Generate executive summary from trends analysis."""

        summary = f"""
SECURITY ANALYSIS EXECUTIVE SUMMARY
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

OVERVIEW:
- Total scans analyzed: {trends['total_scans']}
- Average security issues per scan: {trends['average_security_issues']:.1f}
- Average external requests per scan: {trends['average_external_requests']:.1f}

SEVERITY DISTRIBUTION:
"""

        for severity, count in trends['severity_distribution'].items():
            summary += f"- {severity.title()}: {count} issues\n"

        summary += "\nMOST COMMON SECURITY PATTERNS:\n"
        for pattern, count in sorted(trends['most_common_security_patterns'].items(),
                                   key=lambda x: x[1], reverse=True)[:5]:
            summary += f"- {pattern}: {count} occurrences\n"

        summary += "\nMOST AFFECTED FILES:\n"
        for file_path, count in sorted(trends['most_affected_files'].items(),
                                     key=lambda x: x[1], reverse=True)[:5]:
            summary += f"- {file_path}: {count} issues\n"

        return summary

# Usage example
analyzer = ReportAnalyzer(Path("security_reports"))
reports = analyzer.load_all_reports(days_back=30)
trends = analyzer.analyze_security_trends(reports)
summary = analyzer.generate_executive_summary(trends)

print(summary)

# Save summary to file
with open("security_summary.txt", "w") as f:
    f.write(summary)
```

## Error Handling and Validation

### Input Validation

```python
from rdetoolkit.models.reports import ReportItem, CodeSnippet
from pydantic import ValidationError
from datetime import datetime

def create_safe_code_snippet(file_path: str, snippet: str, description: str = None) -> CodeSnippet | None:
    """Safely create a CodeSnippet with validation."""

    try:
        return CodeSnippet(
            file_path=file_path,
            snippet=snippet,
            description=description
        )
    except ValidationError as e:
        print(f"Invalid CodeSnippet data: {e}")
        return None

def create_safe_report(
    exec_date: str,
    dockerfile_path: str,
    requirements_path: str,
    include_dirs: list[str],
    security_findings: list[CodeSnippet],
    external_findings: list[CodeSnippet]
) -> ReportItem | None:
    """Safely create a ReportItem with validation."""

    try:
        return ReportItem(
            exec_date=exec_date,
            dockerfile_path=dockerfile_path,
            requirements_path=requirements_path,
            include_dirs=include_dirs,
            code_security_scan_results=security_findings,
            code_ext_requests_scan_results=external_findings
        )
    except ValidationError as e:
        print(f"Invalid ReportItem data: {e}")
        return None

# Example with validation
valid_snippet = create_safe_code_snippet(
    "src/main.py",
    "print('Hello World')",
    "Simple print statement"
)

invalid_snippet = create_safe_code_snippet(
    None,  # Invalid: missing file_path
    "code",
    "description"
)

print(f"Valid snippet created: {valid_snippet is not None}")    # True
print(f"Invalid snippet created: {invalid_snippet is not None}") # False
```

## Best Practices

1. **Use ISO Date Formats**: Always use ISO 8601 format for dates:

   ```python
   exec_date = datetime.now().isoformat()  # "2025-01-15T10:30:00.123456"
   ```

2. **Provide Meaningful Descriptions**: Include context in code snippet descriptions:

   ```python
   CodeSnippet(
       file_path="auth.py",
       snippet="password = input('Enter password: ')",
       description="Password input without encryption - Line 45"
   )
   ```

3. **Use Relative Paths**: Store relative paths for portability:

   ```python
   # Good
   file_path = str(Path(absolute_path).relative_to(project_root))

   # Avoi
   file_path = "/home/user/project/src/file.py"
   ```

4. **Validate Input Data**: Always validate data before creating reports:

   ```python
   if not Path(dockerfile_path).exists():
       dockerfile_path = "Dockerfile.default"
   ```

5. **Handle Encoding Issues**: Use proper encoding when reading files:

   ```python
   try:
       content = file_path.read_text(encoding='utf-8')
   except UnicodeDecodeError:
       content = file_path.read_text(encoding='latin-1')
   ```

## Integration Examples

### Integration with Popular Security Tools

```python
# Integration with different security scanners
def integrate_with_semgrep(project_path: Path) -> list[CodeSnippet]:
    """Integrate with Semgrep security scanner."""

    cmd = ["semgrep", "--config=auto", "--json", str(project_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)

    findings = []
    if result.returncode == 0:
        data = json.loads(result.stdout)
        for finding in data.get("results", []):
            findings.append(CodeSnippet(
                file_path=finding["path"],
                snippet=finding["extra"]["lines"],
                description=f"{finding['check_id']}: {finding['message']}"
            ))

    return findings

def integrate_with_safety(requirements_path: Path) -> list[CodeSnippet]:
    """Integrate with Safety package vulnerability scanner."""

    cmd = ["safety", "check", "--json", "-r", str(requirements_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)

    findings = []
    if result.stdout:
        try:
            data = json.loads(result.stdout)
            for vuln in data:
                findings.append(CodeSnippet(
                    file_path=str(requirements_path),
                    snippet=f"{vuln['package']}=={vuln['installed_version']}",
                    description=f"Vulnerability: {vuln['vulnerability_id']} - {vuln['advisory']}"
                ))
        except json.JSONDecodeError:
            pass

    return findings
```

## See Also

- [Pydantic Documentation](https://docs.pydantic.dev/) - For model validation and serialization
- [Security Scanning Tools](https://bandit.readthedocs.io/) - For integration with security scanners
- [CI/CD Integration](https://docs.github.com/en/actions) - For automated security scanning in pipelines
- [JSON Schema](https://json-schema.org/) - For report format validation
