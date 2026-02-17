# rdetoolkit - Detailed Guide

Technical reference for AI coding assistants working with rdetoolkit.

## Architecture

**Hybrid Python/Rust:**
- Python: API, workflow, models (`src/rdetoolkit/`)
- Rust: Image processing, charset detection, file ops (`rdetoolkit-core/`)
- Build: Maturin → `core.cpython-*.so`

**Pipeline:** `run()` → Mode Detection → Processors → Output
Processors: Validation → Files → Invoice → Thumbnails → Description → Variables → Dataset

## Path Objects

### RdeInputDirPaths
- `inputdata: Path` - container/data/inputdata
- `invoice: Path` - container/data/invoice
- `tasksupport: Path` - container/data/tasksupport
- `config: Config` - Configuration
- `default_csv: Path` - tasksupport/default_value.csv (property)

### RdeOutputResourcePath
**Core:**
- `raw/nonshared_raw: Path` - Raw data outputs
- `rawfiles: tuple[Path, ...]` - Current tile inputs
- `struct/main_image/other_image/meta/thumbnail/logs: Path` - Output dirs
- `invoice/invoice_schema_json/invoice_org: Path` - Invoice paths

**Optional:**
- `smarttable_rowfile/smarttable_row_data: Path | dict | None`
- `temp/invoice_patch/attachment: Path | None`

### RdeDatasetPaths
Unified interface combining input/output. Properties mirror both classes.
Method: `as_legacy_args() -> tuple[RdeInputDirPaths, RdeOutputResourcePath]`

## Processing Modes

Priority: extended_mode → excelinvoice → invoice

**Invoice:** `extended_mode = ""`, uses invoice.json
**Excel Invoice:** `extended_mode = ""`, uses invoice.xlsx (no .json)
**MultiDataTile:** `extended_mode = "MultiDataTile"`, multiple tiles/dataset
**SmartTable:** `extended_mode = "SmartTable"`, row-based processing

### MultiDataTile Config
```toml
[multidatatile]
ignore_errors = false  # Continue on errors
```

### SmartTable Access
```python
row = resource_paths.smarttable_row_data
if row:
    sample = row.get("sample/name", "")
    temp = row.get("condition/temperature", "")
```

```toml
[smarttable]
save_table_file = false
```

## Common Patterns

**Multi-File Aggregation:**
```python
import pandas as pd
all_data = [pd.read_csv(f) for f in srcpaths.inputdata.glob("*.csv")]
pd.concat(all_data).to_csv(resource_paths.struct / "combined.csv", index=False)
```

**Image Processing (Rust):**
```python
from rdetoolkit import resize_image_aspect_ratio
for img in resource_paths.rawfiles:
    if img.suffix.lower() in {'.png', '.jpg'}:
        resize_image_aspect_ratio(str(img), str(resource_paths.thumbnail / f"thumb_{img.name}"), 200, 200)
```

**Config-Driven:**
```python
if srcpaths.config.system.save_raw:
    import shutil
    for f in resource_paths.rawfiles:
        shutil.copy2(f, resource_paths.raw / f.name)
```

**SmartTable:**
```python
row = resource_paths.smarttable_row_data
if row:
    process_by_type(resource_paths.rawfiles, row.get("sample/id"), row.get("measurement/type"), resource_paths)
```

## Error Handling

**Result Pattern:**
```python
from rdetoolkit.result import Success, Failure
if (result := process_data(srcpaths)).is_success():
    data = result.unwrap()
else:
    (resource_paths.logs / "error.log").write_text(str(result.error))
```

**Graceful Degradation:**
```python
successful, failed = [], []
for f in resource_paths.rawfiles:
    try: successful.append(process_file(f))
    except Exception as e: failed.append((f, str(e)))
if failed:
    (resource_paths.logs / "failed.log").write_text("\n".join(f"{f}: {e}" for f, e in failed))
```

**Validation:**
```python
if not resource_paths.rawfiles:
    raise ValueError("No input files")
for f in resource_paths.rawfiles:
    if f.suffix.lower() not in {'.csv', '.txt'}:
        raise ValueError(f"Unsupported: {f.suffix}")
```

**StructuredError:**
```python
from rdetoolkit.exceptions import StructuredError
raise StructuredError(emsg="Not found", ecode=404, details={"file": str(e)})
```

## Configuration

### System
```toml
[system]
extended_mode = ""  # "", "MultiDataTile", "SmartTable"
save_raw = false
save_nonshared_raw = true
save_thumbnail_image = false
magic_variable = false  # ${filename} substitution
save_invoice_to_structured = false
feature_description = true
```

### Traceback
```toml
[traceback]
enabled = false
format = "duplex"  # "compact", "python", "duplex"
include_context = false
include_locals = false
max_locals_size = 512
```

## Testing

**Basic Test:**
```python
def test_custom_dataset(tmp_path):
    (tmp_path/"input").mkdir()
    (tmp_path/"input"/"test.csv").write_text("col1,col2\n1,2")
    srcpaths = RdeInputDirPaths(inputdata=tmp_path/"input", invoice=tmp_path/"invoice",
                                  tasksupport=tmp_path/"ts", config=Config(system=SystemSettings()))
    resource_paths = RdeOutputResourcePath(raw=tmp_path/"raw", nonshared_raw=tmp_path/"ns",
        rawfiles=(tmp_path/"input"/"test.csv",), struct=tmp_path/"struct", main_image=tmp_path/"img",
        other_image=tmp_path/"other", meta=tmp_path/"meta", thumbnail=tmp_path/"thumb",
        logs=tmp_path/"logs", invoice=tmp_path/"inv", invoice_schema_json=tmp_path/"schema.json",
        invoice_org=tmp_path/"inv_org")
    custom_dataset(srcpaths, resource_paths)
    assert (tmp_path/"struct"/"result.csv").exists()
```

**Parametrized:**
```python
@pytest.mark.parametrize("save_raw,expected", [(True, ["result.csv", "test.csv"]), (False, ["result.csv"])])
def test_config(tmp_path, save_raw, expected):
    config = Config(system=SystemSettings(save_raw=save_raw))
    # ... test with config
```

**Error:**
```python
def test_error(tmp_path):
    with pytest.raises(ValueError, match="No input"):
        custom_dataset(srcpaths, RdeOutputResourcePath(rawfiles=(), ...))
```

## Processor Development

```python
from rdetoolkit.processing import Processor, ProcessingContext

class MyProcessor(Processor):
    def process(self, context: ProcessingContext) -> None:
        for f in context.paths.rawfiles:
            self._process(f, context.paths.struct, context.config)

    def _process(self, file, output, config):
        pass  # Implementation
```

Test:
```python
def test_processor(tmp_path):
    context = ProcessingContext(config=cfg, paths=paths)
    MyProcessor().process(context)
    assert (tmp_path / "result.csv").exists()
```

## API Reference

```python
# Workflow
from rdetoolkit.workflows import run
run(custom_dataset_function=my_func)

# Invoice
from rdetoolkit.invoice_generator import generate_invoice_from_schema
generate_invoice_from_schema("schema.json", "invoice.json")

# Config
from rdetoolkit.config import parse_config_file
config = parse_config_file("config.toml")

# Types
from rdetoolkit.models.rde2types import ZipFile, ExcelFile, CsvFile
from rdetoolkit.result import Success, Failure

# Exceptions
from rdetoolkit.exceptions import StructuredError
```

## Resources

- Docs: https://nims-mdpf.github.io/rdetoolkit/
- GitHub: https://github.com/nims-dpfc/rdetoolkit
- Issues: https://github.com/nims-dpfc/rdetoolkit/issues
- AGENTS.md: Development rules
- CLAUDE.md: Agent patterns
