from __future__ import annotations

import os
import re
from pathlib import Path
from string import Template
from typing import Literal

from rdetoolkit.interfaces.report import ICodeScanner, IReportGenerator
from rdetoolkit.models.reports import CodeSnippet, ReportItem
from rdetoolkit.rdelogger import get_logger

logger = get_logger(__name__)


class TemplateMarkdownReportGenerator(IReportGenerator):
    """TemplateMarkdownReportGenerator is a class that generates a markdown report for the given template and data."""

    def __init__(self, template_str: str | None = None) -> None:
        self.template_str = template_str or (
            "# Execution Report\n\n"
            "**Execution Date:** $exec_date\n\n"
            "- **Dockerfile:** $dockerfile_status\n"
            "- **Requirements:** $requirements_status\n\n"
            "## Included Directories\n\n"
            "$included_dirs\n\n"
            "## Code Scan Results\n\n"
            "$vuln_results\n\n"
            "## External Communication Check Results\n\n"
            "$ext_comm_results\n"
        )
        self.template = Template(self.template_str)
        self.text = ""

    def generate(self, data: ReportItem) -> str:
        """Generates a report string based on the provided detail data.

        Args:
            data (ReportItem): An object containing the details required to generate the report.

        Returns:
            str: The generated report as a string.

        The report includes:
            - Dockerfile status (OK or N/A based on the presence of a Dockerfile path).
            - Requirements file status (OK or N/A based on the presence of a requirements file path).
            - A list of included directories/files.
            - Bandit analysis results in JSON format.
            - External requests code snippets with file paths and code snippets formatted.

        The generated report is created by substituting the provided data into a predefined template.
        """
        dockerfile_status = f"[Exists]: 🐳　{data.dockerfile_path}" if data.dockerfile_path else "[Not Found] 🐳 N/A"
        requirements_status = f"[Exists]: 🐍 {data.requirements_path}" if data.requirements_path else "[Not Found]: 🐍 N/A"

        included_dirs = "\n".join(
            f"- {d}"
            for d in data.include_dirs
        )

        vuln_results = []
        for item in data.code_security_scan_results:
            snippet_cleaned = item.snippet.strip("\n")
            vuln_results.append(
                f"### {item.file_path}\n\n"
                f"**Description**: {item.description}\n\n"
                f"```python\n{snippet_cleaned}\n```\n\n",
            )
        ext_requests_code = []
        for item in data.code_ext_requests_scan_results:
            snippet_cleaned = item.snippet.strip("\n")
            ext_requests_code.append(
                f"### **{item.file_path}**\n\n```python\n{snippet_cleaned}\n```\n\n",
            )
        ext_comm_results_text = "\n".join(ext_requests_code) if ext_requests_code else "No external communication issues were detected."
        vuln_results_text = "\n".join(vuln_results) if vuln_results else "No security issues were detected."

        self.text = self.template.substitute(
            exec_date=data.exec_date,
            dockerfile_status=dockerfile_status,
            requirements_status=requirements_status,
            included_dirs=included_dirs,
            vuln_results=vuln_results_text,
            ext_comm_results=ext_comm_results_text,
        )

        return self.text

    def save(self, output_path: str | Path) -> None:
        """Saves the generated report to the specified output path.

        Args:
            output_path (str | Path): The path where the report will be saved.
        """
        if not self.text:
            emsg = "Report text is empty. Please generate the report before saving."
            raise FileNotFoundError(emsg)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(self.text)


class CodeSecurityScanner(ICodeScanner):
    _vuln_patterns = (
        {
            "pattern": r'\beval\s*\(',
            "description": "Usage of eval() poses the risk of arbitrary code execution.",
        },
        {
            "pattern": r'\bos\.system\s*\(',
            "description": "Usage of os.system() can lead to command injection vulnerabilities.",
        },
        {
            "pattern": r'\bsubprocess\.(Popen|call)\s*\(',
            "description": "Usage of subprocess.Popen() can lead to command injection vulnerabilities.",
        },
        {
            "pattern": r'\bsubprocess\.run\s*\(',
            "description": "Usage of subprocess.run() can lead to command injection vulnerabilities.",
        },
        {
            "pattern": r'\bpickle\.load(s)?\s*\(',
            "description": "Using pickle.load or pickle.loads is risky when handling untrusted data.",
        },
        {
            "pattern": r'\bmktemp\s*\(',
            "description": "mktemp() usage is not recommended due to race condition risks.",
        },
        {
            "pattern": r'\bexecute\s*\(.*%.*\)',
            "description": "Formatting SQL queries via string formatting may expose the code to SQL injection.",
        },
    )

    def __init__(self, source_dir: str | Path):
        self.source_dir = Path(source_dir) if isinstance(source_dir, str) else source_dir
        self.results: list[CodeSnippet] = []

    def scan_file(self, file_path: Path) -> None:
        """Scans a file for vulnerabilities based on predefined patterns and stores the results.

        Args:
            file_path (Path): The path to the file to be scanned.

        Behavior:
            - Reads the file line by line.
            - Searches each line for matches against vulnerability patterns.
            - If a match is found, extracts a snippet of surrounding lines for context.
            - Appends the result, including the file path, snippet, and vulnerability description, to the results list.

        Error Handling:
            - Logs an error and exits the function if the file cannot be read.

        Note:
            - The file path in the results is relative to the source directory.
            - The snippet includes up to 3 lines before and 4 lines after the matched line.
        """
        try:
            with file_path.open("r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return

        for idx, line in enumerate(lines):
            for vuln in self._vuln_patterns:
                if re.search(vuln["pattern"], line):
                    start = max(idx - 3, 0)
                    end = min(idx + 4, len(lines))
                    snippet = "\n".join(lines[start:end])

                    self.results.append(
                        CodeSnippet(
                            file_path=str(file_path.relative_to(self.source_dir)),
                            snippet=snippet,
                            description=vuln["description"],
                        ),
                    )

    def scan(self) -> list[CodeSnippet]:
        """Scans the source directory for Python files, excluding specific directories, and processes each Python file found.

        This method traverses the directory tree starting from `self.source_dir`,
        skipping directories named "venv" and "site-packages". For each Python file
        (files with a ".py" extension) encountered, it calls the `scan_file` method
        with the file's path.

        Returns:
            None
        """
        for root, dirs, files in os.walk(self.source_dir):
            dirs[:] = [d for d in dirs if d not in ("venv", "site-packages")]
            for file in files:
                if file.endswith(".py"):
                    self.scan_file(Path(root) / file)

        return self.get_results()

    def get_results(self) -> list[CodeSnippet]:
        """Retrieve the list of code snippets stored in the results.

        Returns:
            list[CodeSnippet]: A list of CodeSnippet objects representing the results.
        """
        return self.results


class ExternalConnScanner(ICodeScanner):
    def __init__(self, source_dir: str | Path):
        self.source_dir = Path(source_dir) if isinstance(source_dir, str) else source_dir
        self.external_comm_packages = [
            "requests",
            "urllib",
            "urllib3",
            "httplib",
            "http.client",
            "socket",
            "ftplib",
            "telnetlib",
            "smtplib",
            "aiohttp",
            "httpx",
            "pycurl",
        ]

    def _build_pattern(self) -> re.Pattern:
        import_patterns = [
            r"import\s+({0})",
            r"from\s+({0})(\.\w+)?\s+import",
            r"import\s({0})\s+as\s+\w+",
            r"\s+import\s+({0})",
            r"\s+from\s+({0})(\.\w+)?\s+import",
            r"\s+import\s+({0})\s+as\s+\w+",
        ]
        usage_patterns = [
            r"({0})\.\w+\(",
        ]

        patterns = []
        for pkg in self.external_comm_packages:
            for pattern in import_patterns + usage_patterns:
                patterns.append(pattern.format(pkg))

        return re.compile("|".join(patterns), re.MULTILINE)

    def _is_excluded_path(self, path: Path) -> bool:
        path_str = str(path)
        return "site-packages" in path_str or "venv" in path_str

    def _extract_snippet(self, content: str, match: re.Match, lines: list[str]) -> str:
        match_pos = match.start()
        line_number = content[: match_pos].count('\n')
        start_line = max(0, line_number - 5)
        end_line = min(len(lines), line_number + 6)

        snippet_lines = [f"{i+1}: {lines[i]}" for i in range(start_line, end_line)]
        snippet = "\n".join(snippet_lines)
        return snippet.strip("\n")

    def _process_file(self, path: Path, pattern: re.Pattern) -> list[CodeSnippet]:
        """Scans the given file using the provided regex pattern, extracts matching code snippets, and returns them as a list of CodeSnippet objects.

        Args:
            path (Path): Path to the Python file to scan.
            pattern (re.Pattern): Compiled regex pattern to detect external communication usage.

        Returns:
            list[CodeSnippet]: List of CodeSnippet objects found in the file.
        """
        snippets = []

        try:
            with open(path, encoding="utf-8") as file:
                content = file.read()

            matches = list(pattern.finditer(content))
            if not matches:
                return []

            lines = content.splitlines()
            for match in matches:
                snippet_cleaned = self._extract_snippet(content, match, lines)
                try:
                    rel_path = path.relative_to(self.source_dir)
                except ValueError:
                    rel_path = path

                snippets.append(
                    CodeSnippet(
                        file_path=str(rel_path),
                        snippet=snippet_cleaned,
                        description=None,
                    ),
                )
                break
        except Exception as e:
            logger.error(f"An error occurred while processing file {path}: {e}")

        return snippets

    def scan(self) -> list[CodeSnippet]:
        """Scans the source directory for Python files and extracts code snippets that match specified patterns for external communication package usage.

        Returns:
            list[CodeSnippet]: A list of `CodeSnippet` objects containing the file
            path and the relevant code snippet for each match.
        """
        if not self.source_dir.exists() or not self.source_dir.is_dir():
            emsg = "Error: The provided source directory does not exist or is not a directory."
            logger.error(emsg)
            return []

        pattern = self._build_pattern()
        collected_snippets: list[CodeSnippet] = []
        for path in self.source_dir.rglob("*.py"):
            if self._is_excluded_path(path):
                continue

            file_snippets = self._process_file(path, pattern)
            collected_snippets.extend(file_snippets)

        return collected_snippets


def get_scanner(scanner_type: Literal["vulnerability", "external"], source_dir: str | Path) -> ICodeScanner:
    """A method to switch the type of scanner (vulnerability or external).

    Args:
        scanner_type (Literal["vulnerability", "external"]): Expected to be either "vulnerability" or "external".
        source_dir (str | Path): The directory to be scanned.

    Returns:
        ICodeScanner: An instance of the corresponding scanner.
    """
    if scanner_type == "vulnerability":
        return CodeSecurityScanner(source_dir)
    if scanner_type == "external":
        return ExternalConnScanner(source_dir)
    emsg = f"Unknown scanner type: {scanner_type}"
    raise ValueError(emsg)
