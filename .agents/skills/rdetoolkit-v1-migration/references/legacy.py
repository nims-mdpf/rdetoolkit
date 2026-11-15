"""Representative bare v1 init callback with one handler class."""

import rdetoolkit.workflows as legacy_workflows


class TextHandler:
    def process(self, srcpaths, resource_paths):
        source = next(srcpaths.inputdata.glob("*.txt"))
        destination = resource_paths.struct / "structured.txt"
        destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def custom_dataset_function(srcpaths, resource_paths):
    TextHandler().process(srcpaths, resource_paths)


if __name__ == "__main__":
    legacy_workflows.run(custom_dataset_function=custom_dataset_function)
