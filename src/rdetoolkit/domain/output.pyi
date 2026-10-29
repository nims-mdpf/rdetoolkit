from pathlib import Path
from rdetoolkit.types import OutputContext as OutputContext

def create_output_context(output_root: str | Path, *, create: bool = True) -> OutputContext: ...
