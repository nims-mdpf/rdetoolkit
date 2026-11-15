# v2 Errors

Every error raised by the v2 framework is an `RdeError` carrying an integer
`code`, a `name` and a `remediation`. The code ranges are: 1xxx configuration,
2xxx registration and declaration, 3xxx execution, 4xxx validation, 5xxx
internal. The full list is in the [Error Catalog](../error_catalog.md).

---

::: src.rdetoolkit.errors.RdeError

---

::: src.rdetoolkit.errors.RdeConfigError

---

::: src.rdetoolkit.errors.RdeRegistryError

---

::: src.rdetoolkit.errors.RdeExecutionError

---

::: src.rdetoolkit.errors.RdeValidationError

---

::: src.rdetoolkit.errors.RdeInternalError
