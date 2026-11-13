# Runner

The Runner owns the RDE lifecycle: configuration, mode resolution,
validation, data tile iteration, `job.failed` and the run report. Most
programs reach it through `rdetoolkit.workflows.run(flow=...)` or
`rdetoolkit run --flow`; see [Runner](../../concepts/runner.md).

---

::: src.rdetoolkit.runner.config_loader.load_run_config

---

::: src.rdetoolkit.runner.config_loader.load_config

---

::: src.rdetoolkit.runner.lifecycle.Runner
