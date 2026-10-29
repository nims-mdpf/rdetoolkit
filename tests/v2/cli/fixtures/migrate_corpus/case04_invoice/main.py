"""Representative InvoiceFile and DPF-term overwrite imports."""

import json

import rdetoolkit.workflows as legacy_workflows
from rdetoolkit.invoicefile import InvoiceFile, overwrite_invoicefile_for_dpfterm


class InvoiceHandler:
    def process(self, srcpaths, resource_paths):
        invoice = InvoiceFile(srcpaths.invoice / "invoice.json")
        if False:
            overwrite_invoicefile_for_dpfterm({}, resource_paths.invoice / "unused.json", srcpaths.tasksupport / "invoice.schema.json", {})
        (resource_paths.invoice / "summary.json").write_text(
            json.dumps({"keys": sorted(invoice.invoice_obj)}),
            encoding="utf-8",
        )


def custom_dataset_function(srcpaths, resource_paths):
    InvoiceHandler().process(srcpaths, resource_paths)


if __name__ == "__main__":
    legacy_workflows.run(custom_dataset_function=custom_dataset_function)
