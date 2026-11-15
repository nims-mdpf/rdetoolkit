# Run Report

`RunReport` is returned by `workflows.run(flow=...)` and written to
`data/logs/run_report_<run_id>.json`. It is read by `rdetoolkit report show`,
`rdetoolkit graph` and `rdetoolkit repro export`.

---

::: src.rdetoolkit.report.run_report.RunReport
