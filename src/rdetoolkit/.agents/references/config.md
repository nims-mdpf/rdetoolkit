# Configuration Files Reference

RDEToolKit supports two configuration file formats: `rdeconfig.yaml` (preferred) and
`pyproject.toml`. Both control processing behavior, mode selection, and output options.

## rdeconfig.yaml (Preferred)

Place at the project root, same level as `main.py`.

### Full example

```yaml
system:
  # Processing mode (omit for default Invoice mode)
  extended_mode: 'MultiDataTile'   # ExcelInvoice | MultiDataTile | RDEFormat | SmartTableInvoice

  # File handling
  save_raw: true                   # Copy original files to raw/ directory
  save_thumbnail_image: true       # Auto-generate thumbnail images

  # Magic variables
  magic_variable: true             # Enable ${variable} substitution in templates

  # Folder/file mode (how inputdata is interpreted)
  # 'file' = each file is one input (default)
  # 'folder' = each subfolder is one input
  folder_mode: 'file'
```

### Minimal example (Invoice mode, defaults)

```yaml
system: {}
```

Or simply omit the file entirely — Invoice mode with defaults will be used.

### Mode-specific configurations

#### ExcelInvoice mode

```yaml
system:
  extended_mode: 'ExcelInvoice'
  save_raw: true
  save_thumbnail_image: true
```

#### MultiDataTile mode

```yaml
system:
  extended_mode: 'MultiDataTile'
  save_raw: true
  magic_variable: true
  save_thumbnail_image: true
```

#### RDEFormat mode

```yaml
system:
  extended_mode: 'RDEFormat'
```

---

## pyproject.toml Alternative

Configuration can also be placed in `pyproject.toml` under the `[tool.rdetoolkit]` section.

```toml
[tool.rdetoolkit.system]
extended_mode = "MultiDataTile"
save_raw = true
magic_variable = true
save_thumbnail_image = true
```

### Priority

If both `rdeconfig.yaml` and `pyproject.toml` exist, `rdeconfig.yaml` takes precedence.

---

## Configuration Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `system.extended_mode` | string | `null` (Invoice) | Processing mode selection |
| `system.save_raw` | bool | `false` | Save original input files to raw/ |
| `system.save_thumbnail_image` | bool | `false` | Auto-generate thumbnail images |
| `system.magic_variable` | bool | `false` | Enable magic variable substitution |
| `system.folder_mode` | string | `file` | Input interpretation: `file` or `folder` |

---

## Magic Variables

When `magic_variable: true`, template files support `${variable}` substitution:

- `${filename}` — Input file name
- `${filename_without_ext}` — Input file name without extension
- `${date}` — Current date
- `${timestamp}` — Current timestamp

These can be used in `invoice.json` and `metadata-def.json` to auto-populate fields.

---

## Common Configuration Mistakes

| Mistake | Effect | Fix |
|---------|--------|-----|
| `extended_mode: 'multidatatile'` | Mode not recognized | Use exact case: `'MultiDataTile'` |
| Config in wrong location | Ignored silently | Place next to `main.py` |
| Both yaml and toml with different values | Confusion | Use only one; yaml takes precedence |
| `save_raw: True` (Python bool) in YAML | May cause issues | Use `true` (YAML bool) |
