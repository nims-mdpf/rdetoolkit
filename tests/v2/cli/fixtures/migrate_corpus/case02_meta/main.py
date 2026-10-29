"""Representative metadata-definition and rde2util usage."""

import json

import rdetoolkit.workflows as legacy_workflows
from rdetoolkit.rde2util import CharDecEncoding, Meta, read_from_json_file


class MetadataHandler:
    def process(self, srcpaths, resource_paths):
        source = next(srcpaths.inputdata.glob("*.txt"))
        encoding = CharDecEncoding.detect_text_file_encoding(source)
        invoice = read_from_json_file(srcpaths.invoice / "invoice.json")
        metadata = Meta("")
        payload = {"encoding": encoding, "invoice": bool(invoice), "actions": metadata.actions}
        (resource_paths.meta / "metadata.json").write_text(json.dumps(payload), encoding="utf-8")


def custom_dataset_function(srcpaths, resource_paths):
    MetadataHandler().process(srcpaths, resource_paths)


if __name__ == "__main__":
    legacy_workflows.run(custom_dataset_function=custom_dataset_function)
