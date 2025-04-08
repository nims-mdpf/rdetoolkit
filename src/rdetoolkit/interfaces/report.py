from abc import ABC, abstractmethod

from rdetoolkit.models.reports import CodeSnippet, ReportItem


class IReportGenerator(ABC):
    """An abstract base class for generating reports.

    This class defines the structure for generating various types of reports.
    Subclasses should implement the `generate` method to produce specific report formats.
    """

    @abstractmethod
    def generate(self, data: ReportItem) -> str:
        """Generates a report based on the provided data.

        Args:
            data (ReportItem): The data to be included in the report.

        Returns:
            str: The generated report as a string.
        """
        ...


class ICodeScanner(ABC):
    """An abstract base class for code scanners."""

    @abstractmethod
    def scan(self) -> list[CodeSnippet]:
        """A method to scan source code and detect issues."""
        ...
