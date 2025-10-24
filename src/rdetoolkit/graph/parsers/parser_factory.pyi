from pathlib import Path
from rdetoolkit.graph.parsers.base import CSVParserProtocol as CSVParserProtocol

class ParserFactory:
    @staticmethod
    def create(format_type: str) -> CSVParserProtocol: ...
    @staticmethod
    def auto_detect(csv_path: Path) -> CSVParserProtocol: ...
