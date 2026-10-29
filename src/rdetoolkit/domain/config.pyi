from rdetoolkit.models.config import Config as Config
from rdetoolkit.models.rde2types import RdeFsPath as RdeFsPath

def load_domain_config(tasksupport_path: RdeFsPath, *, config: Config | None = None) -> Config: ...
