from __future__ import annotations

import os
import pathlib
from datetime import datetime
from uuid import uuid4

import click
import pytz

from rdetoolkit.artifact.report import TemplateMarkdownReportGenerator, get_scanner
from rdetoolkit.impl.compressed_controller import get_artifact_archiver
from rdetoolkit.models.reports import CodeSnippet, ReportItem


class CreateArtifactCommand:
    MARK_SUCCESS = "✅"
    MARK_WARNING = "⚠️"
    MARK_ERROR = "🔥"
    MARK_INFO = "📌"
    MARK_SCAN = "🔍"
    MARK_ARCHIVE = "📦"

    def __init__(self, source_dir: pathlib.Path, *, output_archive_path: pathlib.Path | None = None, exclude_patterns: list[str] | None = None) -> None:
        self.source_dir = source_dir
        if output_archive_path is None:
            default_zip_filename = f"{datetime.now(tz=pytz.UTC).strftime('%Y%m%d')}_{uuid4().hex}_rde_artifact.zip"
            self.output_archive_path = source_dir.parent / default_zip_filename
        else:
            self.output_archive_path = output_archive_path
        self.exclude_patterns = exclude_patterns if exclude_patterns else ['.*', 'venv', '.venv', 'site-packages']
        self.template_report_generator = TemplateMarkdownReportGenerator()

    def invoke(self) -> None:
        """Invoke the command to create an archive and generate a report."""
        click.echo(f"{self.MARK_ARCHIVE} Archiving project files...")
        click.echo(f"{self.MARK_INFO} - Source Directory: {self.source_dir}")
        click.echo(f"{self.MARK_INFO} - Output Archive: {self.output_archive_path}")

        dockerfile_path = self._check_file("Dockerfile", logo="🐳")
        requirements_path = self._check_file("requirements.txt", logo="🐍")

        fmt = self._check_extention_type()
        result_conn = self._scan_external_conn()
        result_code_security = self._scan_code_security()
        result_dirs = self._archive_target_dir(fmt)

        item = ReportItem(
            exec_date=datetime.now(tz=pytz.UTC).strftime("%Y-%m-%d %H:%M:%S"),
            dockerfile_path=dockerfile_path,
            requirements_path=requirements_path,
            include_dirs=[self._safe_relative(pathlib.Path(d)) for d in result_dirs] if result_dirs else [],
            code_security_scan_results=result_code_security,
            code_ext_requests_scan_results=result_conn,
        )

        self._generate_report(item)

    def _generate_report(self, item: ReportItem) -> None:
        try:
            report_path = self.output_archive_path.with_suffix(".md")
            self.template_report_generator.generate(item)
            self.template_report_generator.save(report_path)
            click.echo(f"{self.MARK_SUCCESS} Archive and report generation completed successfully.: {report_path}")
        except Exception as e:
            click.echo(click.style(f"{self.MARK_ERROR} Error: {e}", fg="red"))
            raise click.Abort from e

    def _check_file(self, target_filename: str, *, logo: str | None = None) -> str:
        _result = f"{target_filename} not found"
        result_message = f"{logo} {target_filename}" if logo else target_filename
        _target_path = None

        for root, dirs, files in os.walk(self.source_dir):
            dirs[:] = [d for d in dirs if d not in ("venv", "site-packages")]
            if target_filename in files:
                _target_path = pathlib.Path(root) / pathlib.Path(target_filename)
                try:
                    _result = str(_target_path.relative_to(self.source_dir))
                except ValueError:
                    continue

        if _target_path is not None:
            click.echo(click.style(f"{self.MARK_SUCCESS} {result_message} found!: {_target_path}"))
        else:
            click.echo(click.style(f"{self.MARK_WARNING} {result_message} not found.", fg="yellow"))

        return _result

    def _check_extention_type(self) -> str:
        output_archive_ext = self.output_archive_path.suffix
        if output_archive_ext.lower() not in ['.zip']:
            click.echo(click.style(f"{self.MARK_ERROR} The output archive file must have a .zip extension.", fg="red"))
            raise click.Abort
        return output_archive_ext.lstrip(".")

    def _archive_target_dir(self, fmt: str) -> list[pathlib.Path] | None:
        result_dirs = []
        try:
            archiver = get_artifact_archiver(fmt, self.source_dir, self.exclude_patterns)
            result_dirs = archiver.archive(str(self.output_archive_path))
            click.echo(click.style(f"{self.MARK_SUCCESS} Archive created successfully: {self.output_archive_path}"))
            return result_dirs
        except Exception as e:
            click.echo(click.style(f"{self.MARK_ERROR} Archive Error: {e}", fg="red"))
            raise click.Abort from e

    def _scan_external_conn(self) -> list[CodeSnippet]:
        try:
            click.echo(f"{self.MARK_SCAN} Scanning for external connections...", nl=False)
            scanner = get_scanner('external', self.source_dir)
            results = scanner.scan()
            if results:
                click.echo(click.style(f" found {len(results)} reference(s).", fg="yellow"))
            else:
                click.echo(click.style("OK", fg="green"))
            return results
        except Exception as e:
            click.echo(click.style(f"{self.MARK_ERROR} Error", fg="red"))
            click.echo(click.style(f"{e}", fg="red"))
            raise click.Abort from e

    def _scan_code_security(self) -> list[CodeSnippet]:
        try:
            click.echo(f"{self.MARK_SCAN} Scanning for code security vulnerabilities...", nl=False)
            scanner = get_scanner('vulnerability', self.source_dir)
            results = scanner.scan()
            if results:
                click.echo(click.style(f" found {len(results)} reference(s).", fg="yellow"))
            else:
                click.echo(click.style("OK", fg="green"))
            return results
        except Exception as e:
            click.echo(click.style(f"{self.MARK_ERROR} Error", fg="red"))
            click.echo(click.style(f"{e}", fg="red"))
            raise click.Abort from e

    def _safe_relative(self, p: pathlib.Path) -> str:
        try:
            if p.is_absolute():
                return str(p.relative_to(self.source_dir))
            return str(p)
        except ValueError:
            return str(p)
