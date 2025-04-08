import abc
from abc import ABC, abstractmethod
from rdetoolkit.models.reports import CodeSnippet as CodeSnippet, ReportItem as ReportItem

class IReportGenerator(ABC, metaclass=abc.ABCMeta):
    @abstractmethod
    def generate(self, data: ReportItem) -> str: ...

class ICodeScanner(ABC, metaclass=abc.ABCMeta):
    @abstractmethod
    def scan(self) -> list[CodeSnippet]: ...
