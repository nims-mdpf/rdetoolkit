from pathlib import Path

class TileOutputPaths:
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
    temp: Path
    invoice_patch: Path
    def __init__(
        self,
        struct: Path,
        meta: Path,
        main_image: Path,
        other_image: Path,
        thumbnail: Path,
        attachment: Path,
        nonshared_raw: Path,
        raw: Path,
        invoice: Path,
        logs: Path,
        temp: Path,
        invoice_patch: Path,
    ) -> None: ...

def resolve_data_root(root: Path) -> Path: ...
def resolve_tile_paths(base_dir: Path, idx: int) -> TileOutputPaths: ...
