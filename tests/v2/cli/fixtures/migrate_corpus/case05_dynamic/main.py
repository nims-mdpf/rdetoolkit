"""Representative callback containing unconvertible dynamic dispatch."""

import rdetoolkit.workflows as legacy_workflows


class DynamicHandler:
    def process(self, srcpaths, resource_paths):
        source = next(srcpaths.inputdata.glob("*.txt"))
        (resource_paths.struct / "dynamic.txt").write_text(source.stem, encoding="utf-8")


HANDLER_NAME = "DynamicHandler"


def custom_dataset_function(srcpaths, resource_paths):
    handler_class = globals()[HANDLER_NAME]
    handler_class().process(srcpaths, resource_paths)


if __name__ == "__main__":
    legacy_workflows.run(custom_dataset_function=custom_dataset_function)
