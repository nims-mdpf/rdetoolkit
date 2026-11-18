from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True, slots=True)
class OutputLayout:
    struct: Path
    meta: Path
    main_image: Path
    other_image: Path
    thumbnail: Path
    attachment: Path
    nonshared_raw: Path
    raw: Path
    invoice: Path
    logs: Path

class OutputLayoutResolver:
    def resolve(self, base_dir: Path, index: int) -> OutputLayout: ...
