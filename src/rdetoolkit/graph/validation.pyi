from typing import Final

SUPPORTED_MODES: Final[tuple[str, ...]]

def validate_plot_request(*, mode: str, no_individual: bool | None) -> None: ...
