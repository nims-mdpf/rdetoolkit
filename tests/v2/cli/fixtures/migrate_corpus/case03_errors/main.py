"""Representative StructuredError and legacy exception decorator usage."""

import rdetoolkit.workflows as legacy_workflows
from rdetoolkit.errors import catch_exception_with_message
from rdetoolkit.exceptions import StructuredError


@catch_exception_with_message(error_message="conversion failed", error_code=1)
def normalize(value):
    if value is None:
        raise StructuredError("missing value")
    return str(value).upper()


class ErrorAwareHandler:
    def process(self, srcpaths, resource_paths):
        value = normalize(next(srcpaths.inputdata.glob("*.txt")).stem)
        (resource_paths.struct / "normalized.txt").write_text(value, encoding="utf-8")


def custom_dataset_function(srcpaths, resource_paths):
    ErrorAwareHandler().process(srcpaths, resource_paths)


if __name__ == "__main__":
    legacy_workflows.run(custom_dataset_function=custom_dataset_function)
