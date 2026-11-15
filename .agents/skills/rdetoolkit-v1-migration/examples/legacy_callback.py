# ruff: noqa: INP001
"""Small source-conversion fixture; its data/error contracts must survive."""
import json

from rdetoolkit import workflows
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath


def dataset(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath) -> None:
    """Write representative artifacts from one measurement."""
    payload = json.loads((srcpaths.inputdata / "measurement.json").read_text(encoding="utf-8"))
    if payload["fail"]:
        msg = "Measurement rejected by the instrument"
        raise StructuredError(msg, ecode=999)
    (resource_paths.meta / "metadata.json").write_text(json.dumps(payload["metadata"], ensure_ascii=False, indent=4), encoding="utf-8")
    (resource_paths.struct / "table.csv").write_text(payload["table"], encoding="utf-8")
    (resource_paths.main_image / "measurement.png").write_bytes((srcpaths.inputdata / "measurement.png").read_bytes())


if __name__ == "__main__":
    # The legacy stub protocol conflates its two supported callback signatures.
    workflows.run(custom_dataset_function=dataset)  # type: ignore[call-overload]
