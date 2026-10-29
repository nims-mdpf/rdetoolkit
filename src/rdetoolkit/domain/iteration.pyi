from pathlib import Path

class IterationFactory:
    def files(self, directory: Path, *, pattern: str = ...) -> tuple[Path, ...]: ...
