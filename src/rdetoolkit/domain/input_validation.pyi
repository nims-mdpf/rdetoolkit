from pathlib import Path
from rdetoolkit.types import InputPaths

class InputValidator:
    def validate(self, root: Path) -> InputPaths: ...
