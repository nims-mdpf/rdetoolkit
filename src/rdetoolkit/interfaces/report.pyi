import abc
from abc import ABC, abstractmethod
from rdetoolkit.models.reports import ReportItem as ReportItem

class IReportGenerator(ABC, metaclass=abc.ABCMeta):
    @abstractmethod
    def generate(self, data: ReportItem) -> str: ...
