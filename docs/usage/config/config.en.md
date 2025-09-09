
**# How to Create a Configuration File**

**## Purpose**

This document explains how to create and configure the `rdeconfig.yaml` configuration file that custom‑defines the structured‑processing behavior of **RDEToolKit**. You can learn everything from basic settings to advanced options step‑by‑step.

**## Prerequisites**

- Familiarity with the basic usage of RDEToolKit
- Basic knowledge of the YAML file format
- Understanding of the directory structure used for structured processing

**## Configuration‑File Requirements**

| Item          | Requirement                                                                                           |
| ------------- | ----------------------------------------------------------------------------------------------------- |
| **File name** | `rdeconfig.yml`, `rdeconfig.yaml` or `pyproject.toml` can be used                                     |
| **Location**  | *YAML format*: inside the `data/tasksupport/` directory  <br> *`pyproject.toml`*: at the project root |
| **Format**    | YAML (or TOML)                                                                                        |

**## Procedure**

---

### **1. Place the configuration file**

Put the file in the correct location:

```text
data/
└── tasksupport/
    └── rdeconfig.yaml   # ← place it here
```

---

### **2. Create a basic configuration**

A minimal configuration file looks like this:

```yaml
system:
  save_raw: true
  magic_variable: false
  save_thumbnail_image: true
  extended_mode: null
```

---

### **3. Set each configuration item**

#### **save_raw**

Controls whether input data are copied to the `raw` directory.

- **type:** `bool`
- **default:** `false`

```yaml
system:
  save_raw: true   # copy input data to the raw directory
  save_raw: false  # do not copy input data
```

> **💡 Tip – Save Raw Data**
> If you set `save_raw` to **true**, make sure `save_nonshared_raw` is **false**. Enabling both will copy the data to both `raw` **and** `nonshared_raw` directories.

---

#### **save_nonshared_raw**

Controls whether input data are copied to the `save_nonshared_raw` directory (a non‑shared location).

- **type:** `bool`
- **default:** `false`

```yaml
system:
  save_nonshared_raw: true   # copy input data to save_nonshared_raw (recommended)
  save_nonshared_raw: false  # do not copy input data
```

> **💡 Tip – Save Raw Data**
> If you set `save_nonshared_raw` to **true**, make sure `save_raw` is **false**. Enabling both will copy the data to both `raw` **and** `nonshared_raw` directories.

---

#### **magic_variable**

Enables dynamic filename substitution. When active, magic variables such as `${filename}` can be used in an invoice, and the data tile name is automatically replaced with the actual file name.

- **type:** `bool`
- **default:** `false`

```yaml
system:
  magic_variable: true   # enable ${filename} etc.
  magic_variable: false  # disable substitution (default)
```

**Example** – Using a magic variable in an invoice:

*Invoice before processing* (`20250101_sample_data.dat` is the file being registered)

```json
{
  "datasetId": "e66233bf-821a-404c-a584-083ff36bb825",
  "basic": {
    "dateSubmitted": "2025-01-01",
    "dataOwnerId": "010z27x4095x7fx10x5614428108ce53e5628a0b3830987098664533",
    "dataName": "${filename}",
    "instrumentId": "409ada22-108f-42e2-8ba0-e53e5628a0b383098",
    "experimentId": null,
    "description": "",
    "dataset_title": "xrd",
    "dataOwner": "Sample,Username"
  }
  /* … */
}
```

*After structured processing*

```json
{
  "datasetId": "e66233bf-821a-404c-a584-083ff36bb825",
  "basic": {
    "dateSubmitted": "2025-01-01",
    "dataOwnerId": "010z27x4095x7fx10x5614428108ce53e5628a0b3830987098664533",
    "dataName": "20250101_sample_data.dat",
    "instrumentId": "409ada22-108f-42e2-8ba0-e53e5628a0b383098",
    "experimentId": null,
    "description": "",
    "dataset_title": "xrd",
    "dataOwner": "Sample,Username"
  }
  /* … */
}
```

---

#### **save_thumbnail_image**

Controls automatic generation of thumbnail images from the main image (`main_image` directory).

- **type:** `bool`
- **default:** `false`

```yaml
system:
  save_thumbnail_image: true   # generate thumbnails automatically (recommended)
  save_thumbnail_image: false  # disable thumbnail generation
```

---

#### **extended_mode**

Specifies an extended data‑registration mode.

- **type:** `str` | `null`
- **default:** `null`
- **Available options:**
  - `null` → Standard mode
  - `"rdeformat"` → RDE format mode
  - `"MultiDataTile"` → Multi‑data‑tile mode

```yaml
system:
  extended_mode: null               # standard mode
  extended_mode: "rdeformat"        # RDE format mode
  extended_mode: "MultiDataTile"    # Multi‑data‑tile mode
```

For details on each mode, see the **[Data Registration Modes](../mode/mode.md)** documentation.

---

### **4. Add mode‑specific settings**

#### **Ignore errors in MultiDataTile**

> *Only effective when `extended_mode: "MultiDataTile"` is set.*

Continues processing even if an error occurs for a particular data tile (the faulty tile is simply not registered).

- **type:** `bool`
- **default:** `false`

```yaml
multidatatile:
  ignore_errors: true   # or false
```

#### **SmartTable**

> *Only effective when the SmartTable feature is enabled.*

When enabled, table data files that are uploaded are saved as data tiles.

- **type:** `bool`
- **default:** `false`

```yaml
smarttable:
  save_table_file: true
```

---

### **5. Add logging / stack‑trace settings**

#### **Traceback**

Controls an LLM/AI‑friendly stack‑trace feature.

- **type:** `bool`
- **default:** `false`

```yaml
traceback:
  enabled: true   # turn the traceback feature on or off
```

When `enabled: true`, the following additional options become available:

| Option                 | Description                                         | Type        | Default    |
| ---------------------- | --------------------------------------------------- | ----------- | ---------- |
| **format**             | Output format (`"compact"`, `"python"`, `"duplex"`) | `str`       | `"duplex"` |
| **include_context**    | Show source‑code lines                              | `bool`      | `true`     |
| **include_locals**     | Show local variables (may expose sensitive data)    | `bool`      | `false`    |
| **include_env**        | Show environment information                        | `bool`      | `true`     |
| **max_locals_size**    | Maximum size (bytes) for variable output            | `int`       | `512`      |
| **sensitive_patterns** | Custom patterns that should be redacted             | `list[str]` | `[]`       |

```yaml
traceback:
  enabled: true
  format: "duplex"                 # output: compact, python, or duplex
  include_context: true            # show source lines
  include_locals: false            # hide locals for security
  include_env: true                # show environment info
  max_locals_size: 512             # limit size of variable dump
  sensitive_patterns:              # custom redaction patterns
    - "database_url"
    - "private_key"
    - "connection_string"
```

---

## **Configuration Example Collection**

Use the following examples as a starting point and adapt them to your needs.

### **Standard (Invoice‑Registration) Settings**

```yaml
system:
  save_raw: true
  magic_variable: false
  save_thumbnail_image: true
```

### **Register Raw Data to a Non‑Shared Directory**

```yaml
system:
  save_nonshared_raw: true
  magic_variable: false
  save_thumbnail_image: true
```

### **Multi‑Data‑Tile Registration Mode**

```yaml
system:
  save_raw: true
  magic_variable: true
  save_thumbnail_image: true
  extended_mode: "MultiDataTile"
```

### **System‑wide Integration (RDEFormat Mode)**

```yaml
system:
  extended_mode: "rdeformat"
```

### **AI‑Agent Integration**

```yaml
system:
  save_raw: true
  magic_variable: false
  save_thumbnail_image: true

traceback:
  enabled: true
  format: "compact"            # machine‑readable only
  include_context: true        # source code for AI analysis
  include_locals: false        # security‑first
  include_env: false           # minimal info
  max_locals_size: 0           # no variables in production
  sensitive_patterns:
    - "database_url"
    - "private_key"
    - "connection_string"
    - "encryption_key"
```

---

## **Related Information**

To learn more about configuration files, consult the following documents:

- **[Processing Modes](../mode/mode.ja.md)** – details on each `extended_mode`
- **[Magic Variable Feature](magic_variable.ja.md)** – how dynamic substitution works
- **[Concept of Structured Processing](../structured_process/structured.ja.md)** – how configuration influences the processing flow
- **[LLM/AI‑Friendly Traceback Settings](../structured_process/traceback.ja.md)** – deep dive into stack‑trace customization
