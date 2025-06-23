# Invoice File Module

The `rdetoolkit.invoicefile` module provides comprehensive functionality for handling various types of invoice files in RDE (Research Data Exchange) processing workflows. This module supports standard JSON invoices, Excel-based invoices, template generation, and advanced file processing with rule-based transformations.

## Overview

The invoicefile module offers extensive capabilities for invoice processing:

- **Invoice File Management**: Reading, writing, and manipulation of JSON-based invoice files
- **Excel Invoice Processing**: Specialized handling of Excel-based invoice files with multiple sheets
- **Template Generation**: Automated creation of Excel invoice templates based on schemas
- **SmartTable Integration**: Processing of SmartTable files for automated invoice generation
- **Rule-Based Replacement**: Flexible file naming and content transformation rules
- **Magic Variable Processing**: Dynamic variable substitution in invoice content
- **Backup and Recovery**: Automated backup of invoice files during processing
- **Validation and Error Handling**: Comprehensive validation with detailed error reporting

## Classes

### InvoiceFile

A class representing standard JSON invoice files with utilities for reading and writing.

#### Constructor

```python
InvoiceFile(invoice_path: Path)
```

**Parameters:**
- `invoice_path` (Path): Path to the invoice JSON file

**Attributes:**
- `invoice_path` (Path): Path to the invoice file
- `invoice_obj` (dict[str, Any]): Dictionary representation of the invoice JSON

#### Methods

##### read

Read the content of the invoice file and return as a dictionary.

```python
def read(self, *, target_path: Path | None = None) -> dict
```

**Parameters:**
- `target_path` (Path | None): Alternative path to read from (optional)

**Returns:**
- `dict`: Dictionary representation of the invoice JSON file

##### overwrite

Overwrite the contents of the destination file with invoice JSON data.

```python
def overwrite(self, dst_file_path: Path, *, src_obj: Path | None = None) -> None
```

**Parameters:**
- `dst_file_path` (Path): Destination file path
- `src_obj` (Path | None): Source object path (optional)

**Returns:**
- `None`

**Raises:**
- `StructuredError`: If the destination file cannot be created

##### copy_original_invoice

Copy the original invoice file from source to destination.

```python
@classmethod
def copy_original_invoice(cls, src_file_path: Path, dst_file_path: Path) -> None
```

**Parameters:**
- `src_file_path` (Path): Source file path
- `dst_file_path` (Path): Destination file path

**Raises:**
- `StructuredError`: If the source file does not exist

**Example:**

```python
from rdetoolkit.invoicefile import InvoiceFile
from pathlib import Path

# Create and manipulate invoice file
invoice_path = Path("data/invoice/invoice.json")
invoice = InvoiceFile(invoice_path)

# Access and modify invoice data
print(f"Original data name: {invoice.invoice_obj['basic']['dataName']}")
invoice.invoice_obj["basic"]["dataName"] = "Updated Dataset Name"
invoice.invoice_obj["basic"]["description"] = "Updated description"

# Save changes
output_path = Path("data/invoice/invoice_updated.json")
invoice.overwrite(output_path)

# Copy original invoice
backup_path = Path("data/backup/invoice_backup.json")
InvoiceFile.copy_original_invoice(invoice_path, backup_path)

# Read from different file
invoice.read(target_path=backup_path)
print(f"Backup data name: {invoice.invoice_obj['basic']['dataName']}")
```

### ExcelInvoiceFile

A comprehensive class for handling Excel-based invoice files with multiple sheets.

#### Constructor

```python
ExcelInvoiceFile(invoice_path: Path)
```

**Parameters:**
- `invoice_path` (Path): Path to the Excel invoice file (.xlsx)

**Attributes:**
- `invoice_path` (Path): Path to the Excel invoice file
- `dfexcelinvoice` (pd.DataFrame): DataFrame of the invoice data
- `df_general` (pd.DataFrame): DataFrame of general terms
- `df_specific` (pd.DataFrame): DataFrame of specific terms
- `template_generator` (ExcelInvoiceTemplateGenerator): Template generator instance

#### Methods

##### read

Read the Excel invoice file and return three DataFrames.

```python
def read(self, *, target_path: Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]
```

**Parameters:**
- `target_path` (Path | None): Path to the Excel invoice file (optional)

**Returns:**
- `tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]`: Invoice, general terms, and specific terms DataFrames

**Raises:**
- `StructuredError`: If file not found or multiple/no invoice sheets exist

##### generate_template

Generate Excel invoice template based on schema.

```python
@classmethod
def generate_template(
    cls,
    invoice_schema_path: str | Path,
    save_path: str | Path,
    file_mode: Literal["file", "folder"] = "file"
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]
```

**Parameters:**
- `invoice_schema_path` (str | Path): Path to invoice schema file
- `save_path` (str | Path): Path to save the generated template
- `file_mode` (Literal["file", "folder"]): Input mode specification

**Returns:**
- `tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]`: Template, general terms, and specific terms DataFrames

##### overwrite

Overwrite original invoice file based on Excel invoice data.

```python
def overwrite(self, invoice_org: Path, dist_path: Path, invoice_schema_path: Path, idx: int) -> None
```

**Parameters:**
- `invoice_org` (Path): Path to original invoice file
- `dist_path` (Path): Path for output invoice file
- `invoice_schema_path` (Path): Path to invoice schema
- `idx` (int): Row index in the invoice DataFrame

##### save

Save the invoice DataFrame to an Excel file.

```python
def save(
    self,
    save_path: str | Path,
    *,
    invoice: pd.DataFrame | None = None,
    sheet_name: str = "invoice_form",
    index: list[str] | None = None,
    header: list[str] | None = None
) -> None
```

**Parameters:**
- `save_path` (str | Path): Path to save the Excel file
- `invoice` (pd.DataFrame | None): DataFrame to save (optional)
- `sheet_name` (str): Sheet name in Excel file
- `index` (list[str] | None): Index labels (optional)
- `header` (list[str] | None): Column headers (optional)

##### check_intermittent_empty_rows

Detect empty rows between data rows in Excel invoice.

```python
@staticmethod
def check_intermittent_empty_rows(df: pd.DataFrame) -> None
```

**Parameters:**
- `df` (pd.DataFrame): DataFrame to check

**Raises:**
- `StructuredError`: If empty rows exist between data rows

**Example:**

```python
from rdetoolkit.invoicefile import ExcelInvoiceFile
from pathlib import Path
import pandas as pd

# Read Excel invoice
excel_path = Path("data/input/sample_excel_invoice.xlsx")
excel_invoice = ExcelInvoiceFile(excel_path)

print(f"Invoice data shape: {excel_invoice.dfexcelinvoice.shape}")
print(f"General terms: {len(excel_invoice.df_general)}")
print(f"Specific terms: {len(excel_invoice.df_specific)}")

# Generate template
schema_path = Path("data/tasksupport/invoice.schema.json")
template_path = Path("data/templates/new_template.xlsx")

template_df, general_df, specific_df = ExcelInvoiceFile.generate_template(
    invoice_schema_path=schema_path,
    save_path=template_path,
    file_mode="file"
)

print(f"Generated template with {template_df.shape[1]} columns")

# Process Excel invoice data
original_invoice = Path("data/invoice/invoice.json")
output_invoice = Path("data/processed/invoice_processed.json")

# Process each row in the Excel invoice
for idx in range(len(excel_invoice.dfexcelinvoice)):
    row_output = Path(f"data/processed/invoice_{idx:04d}.json")
    excel_invoice.overwrite(
        invoice_org=original_invoice,
        dist_path=row_output,
        invoice_schema_path=schema_path,
        idx=idx
    )
    print(f"Processed row {idx} -> {row_output}")

# Save modified invoice data
modified_path = Path("data/output/modified_invoice.xlsx")
excel_invoice.save(
    save_path=modified_path,
    sheet_name="processed_invoice"
)
```

### ExcelInvoiceTemplateGenerator

A specialized class for generating Excel invoice templates with proper formatting.

#### Constructor

```python
ExcelInvoiceTemplateGenerator(fixed_header: FixedHeaders)
```

**Parameters:**
- `fixed_header` (FixedHeaders): Fixed header configuration

#### Methods

##### generate

Generate template based on configuration.

```python
def generate(self, config: TemplateConfig) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]
```

**Parameters:**
- `config` (TemplateConfig): Template configuration

**Returns:**
- `tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]`: Template, general terms, specific terms, and version DataFrames

##### save

Save DataFrames to Excel file with formatting.

```python
def save(self, dataframes: dict[str, pd.DataFrame], save_path: str) -> None
```

**Parameters:**
- `dataframes` (dict[str, pd.DataFrame]): DataFrames to save
- `save_path` (str): Output file path

**Example:**

```python
from rdetoolkit.invoicefile import ExcelInvoiceTemplateGenerator, FixedHeaders
from rdetoolkit.models.invoice import TemplateConfig
from pathlib import Path

# Create template generator
fixed_headers = FixedHeaders()
generator = ExcelInvoiceTemplateGenerator(fixed_headers)

# Setup configuration
config = TemplateConfig(
    schema_path=Path("data/tasksupport/invoice.schema.json"),
    general_term_path=Path("data/terms/general_terms.csv"),
    specific_term_path=Path("data/terms/specific_terms.csv"),
    inputfile_mode="file"
)

# Generate template
template_df, general_df, specific_df, version_df = generator.generate(config)

# Prepare DataFrames for saving
dataframes = {
    "invoice_form": template_df,
    "generalTerm": general_df,
    "specificTerm": specific_df,
    "_version": version_df
}

# Save with formatting
output_path = "data/templates/formatted_template.xlsx"
generator.save(dataframes, output_path)

print(f"Template saved to: {output_path}")
print(f"Template dimensions: {template_df.shape}")
```

### RuleBasedReplacer

A flexible class for managing file name mapping and content transformation rules.

#### Constructor

```python
RuleBasedReplacer(*, rule_file_path: str | Path | None = None)
```

**Parameters:**
- `rule_file_path` (str | Path | None): Path to rule file (optional)

**Attributes:**
- `rules` (dict[str, str]): Dictionary holding mapping rules
- `last_apply_result` (dict[str, Any]): Result of last applied rules

#### Methods

##### load_rules

Load file mapping rules from JSON file.

```python
def load_rules(self, filepath: str | Path) -> None
```

**Parameters:**
- `filepath` (str | Path): Path to JSON file containing mapping rules

**Raises:**
- `StructuredError`: If file extension is not .json

##### set_rule

Set a new mapping rule.

```python
def set_rule(self, path: str, variable: str) -> None
```

**Parameters:**
- `path` (str): Target path for replacement
- `variable` (str): Replacement variable

##### get_apply_rules_obj

Convert file mapping rules into JSON format.

```python
def get_apply_rules_obj(
    self,
    replacements: dict[str, Any],
    source_json_obj: dict[str, Any] | None,
    *,
    mapping_rules: dict[str, str] | None = None,
) -> dict[str, Any]
```

**Parameters:**
- `replacements` (dict[str, Any]): Object containing mapping rules
- `source_json_obj` (dict[str, Any] | None): Source JSON object for rule application
- `mapping_rules` (dict[str, str] | None): Rules for mapping (optional)

**Returns:**
- `dict[str, Any]`: Dictionary after rule conversion

##### write_rule

Write file mapping rules to target JSON file.

```python
def write_rule(self, replacements_rule: dict[str, Any], save_file_path: str | Path) -> str
```

**Parameters:**
- `replacements_rule` (dict[str, Any]): Object containing mapping rules
- `save_file_path` (str | Path): File path for saving

**Returns:**
- `str`: Result of writing to target JSON

**Raises:**
- `StructuredError`: If file extension is not .json or writing fails

**Example:**

```python
from rdetoolkit.invoicefile import RuleBasedReplacer
from pathlib import Path
import json

# Create replacer with rules file
rules_path = Path("data/config/mapping_rules.json")
replacer = RuleBasedReplacer(rule_file_path=rules_path)

# Set custom rules
replacer.set_rule("basic.dataName", "${filename}")
replacer.set_rule("basic.description", "${description}")
replacer.set_rule("sample.names", ["${sample_name}"])

# Prepare replacement values
replacements = {
    "${filename}": "experiment_data.csv",
    "${description}": "Experimental measurement data",
    "${sample_name}": "Sample A"
}

# Apply rules to create new JSON structure
source_obj = {
    "basic": {
        "title": "Original Title"
    }
}

result = replacer.get_apply_rules_obj(replacements, source_obj)
print("Applied rules result:")
print(json.dumps(result, indent=2))

# Write rules to file
output_path = Path("data/output/processed_data.json")
written_content = replacer.write_rule(replacements, output_path)
print(f"Rules written to: {output_path}")

# Load existing rules
if rules_path.exists():
    replacer.load_rules(rules_path)
    print(f"Loaded {len(replacer.rules)} rules from file")
```

### SmartTableFile

A class for handling SmartTable files (Excel/CSV/TSV) for automated invoice generation.

#### Constructor

```python
SmartTableFile(smarttable_path: Path)
```

**Parameters:**
- `smarttable_path` (Path): Path to SmartTable file (.xlsx, .csv, .tsv)

**Raises:**
- `StructuredError`: If file format unsupported or file doesn't exist

#### Methods

##### read_table

Read the SmartTable file and return as DataFrame.

```python
def read_table(self) -> pd.DataFrame
```

**Returns:**
- `pd.DataFrame`: Table data with mapping key headers

**Raises:**
- `StructuredError`: If file reading fails or format is invalid

##### generate_row_csvs_with_file_mapping

Generate individual CSV files for each row with file mapping.

```python
def generate_row_csvs_with_file_mapping(
    self,
    output_dir: Path,
    extracted_files: list[Path] | None = None,
) -> list[tuple[Path, tuple[Path, ...]]]
```

**Parameters:**
- `output_dir` (Path): Directory to save individual CSV files
- `extracted_files` (list[Path] | None): List of extracted files from zip (optional)

**Returns:**
- `list[tuple[Path, tuple[Path, ...]]]`: List of tuples with CSV paths and related file paths

**Raises:**
- `StructuredError`: If CSV generation or file mapping fails

**Example:**

```python
from rdetoolkit.invoicefile import SmartTableFile
from pathlib import Path
import pandas as pd

# Create SmartTable file
smarttable_path = Path("data/input/smarttable_metadata.xlsx")
smarttable = SmartTableFile(smarttable_path)

# Read table data
table_data = smarttable.read_table()
print(f"SmartTable data shape: {table_data.shape}")
print(f"Columns: {list(table_data.columns)}")

# Display mapping columns
mapping_columns = [col for col in table_data.columns
                  if any(col.startswith(prefix) for prefix in ["basic/", "custom/", "sample/", "meta/"])]
print(f"Mapping columns: {mapping_columns}")

# Generate individual CSV files with file mapping
output_dir = Path("data/processed/smarttable_rows")
extracted_files = [
    Path("data/temp/file1.csv"),
    Path("data/temp/file2.txt"),
    Path("data/temp/subdir/file3.json")
]

csv_mappings = smarttable.generate_row_csvs_with_file_mapping(
    output_dir=output_dir,
    extracted_files=extracted_files
)

print(f"Generated {len(csv_mappings)} CSV files:")
for csv_path, related_files in csv_mappings:
    print(f"  {csv_path.name} -> {len(related_files)} related files")
    for file_path in related_files:
        print(f"    - {file_path}")
```

## Functions

### read_excelinvoice

Read an Excel invoice and process each sheet into DataFrames.

```python
def read_excelinvoice(excelinvoice_filepath: RdeFsPath) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]
```

**Parameters:**
- `excelinvoice_filepath` (RdeFsPath): Path to Excel invoice file

**Returns:**
- `tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]`: Invoice list, general terms, and specific terms DataFrames

**Raises:**
- `StructuredError`: If multiple invoice sheets exist or no sheets are present

**Sheet Requirements:**
- One sheet with 'invoiceList_format_id' in cell A1
- One sheet named 'generalTerm'
- One sheet named 'specificTerm'

### check_exist_rawfiles

Check existence of raw file paths listed in DataFrame against file list.

```python
def check_exist_rawfiles(dfexcelinvoice: pd.DataFrame, excel_rawfiles: list[Path]) -> list[Path]
```

**Parameters:**
- `dfexcelinvoice` (pd.DataFrame): DataFrame with file names in 'data_file_names/name' column
- `excel_rawfiles` (list[Path]): List of file paths

**Returns:**
- `list[Path]`: List of Path objects ordered as they appear in DataFrame

**Raises:**
- `StructuredError`: If any file name in DataFrame is not found in file list

### backup_invoice_json_files

Backup invoice files and retrieve paths based on processing mode.

```python
def backup_invoice_json_files(excel_invoice_file: Path | None, mode: str | None) -> Path
```

**Parameters:**
- `excel_invoice_file` (Path | None): Excel invoice file path (optional)
- `mode` (str | None): Processing mode flags

**Returns:**
- `Path`: Path to backed up invoice_org.json file

### update_description_with_features

Write metadata features to the description field in invoice.json.

```python
def update_description_with_features(
    rde_resource: RdeOutputResourcePath,
    dst_invoice_json: Path,
    metadata_def_json: Path,
) -> None
```

**Parameters:**
- `rde_resource` (RdeOutputResourcePath): Resource paths for RDE processing
- `dst_invoice_json` (Path): Path to target invoice.json file
- `metadata_def_json` (Path): Path to metadata definition JSON file

**Returns:**
- `None`

### apply_magic_variable

Convert magic variables like ${filename} in invoice content.

```python
def apply_magic_variable(
    invoice_path: str | Path,
    rawfile_path: str | Path,
    *,
    save_filepath: str | Path | None = None
) -> dict[str, Any]
```

**Parameters:**
- `invoice_path` (str | Path): Path to invoice.json file
- `rawfile_path` (str | Path): Path to input data file
- `save_filepath` (str | Path | None): Path to save processed file (optional)

**Returns:**
- `dict[str, Any]`: Invoice content after variable replacement

### apply_default_filename_mapping_rule

Apply default filename mapping rule based on save file path.

```python
def apply_default_filename_mapping_rule(
    replacement_rule: dict[str, Any],
    save_file_path: str | Path
) -> dict[str, Any]
```

**Parameters:**
- `replacement_rule` (dict[str, Any]): Replacement rules to apply
- `save_file_path` (str | Path): File path for saving rules

**Returns:**
- `dict[str, Any]`: Result of applied replacement rules

## Complete Usage Examples

### Comprehensive Excel Invoice Processing Pipeline

```python
from rdetoolkit.invoicefile import ExcelInvoiceFile, RuleBasedReplacer, apply_magic_variable
from pathlib import Path
import pandas as pd
import json
from typing import List, Dict, Any

class ExcelInvoiceProcessor:
    """Comprehensive Excel invoice processing pipeline."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.input_dir = base_dir / "input"
        self.output_dir = base_dir / "output"
        self.config_dir = base_dir / "config"
        self.templates_dir = base_dir / "templates"

        # Ensure directories exist
        for directory in [self.output_dir, self.config_dir, self.templates_dir]:
            directory.mkdir(parents=True, exist_ok=True)

    def generate_template_from_schema(
        self,
        schema_path: Path,
        template_path: Path,
        mode: str = "file"
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Generate Excel invoice template from schema."""

        print(f"Generating template from schema: {schema_path}")

        try:
            template_df, general_df, specific_df = ExcelInvoiceFile.generate_template(
                invoice_schema_path=schema_path,
                save_path=template_path,
                file_mode=mode
            )

            print(f"Template generated successfully:")
            print(f"  Template columns: {template_df.shape[1]}")
            print(f"  General terms: {len(general_df)}")
            print(f"  Specific terms: {len(specific_df)}")
            print(f"  Saved to: {template_path}")

            return template_df, general_df, specific_df

        except Exception as e:
            print(f"Template generation failed: {e}")
            raise

    def process_excel_invoice_batch(
        self,
        excel_invoice_path: Path,
        original_invoice_path: Path,
        schema_path: Path,
        raw_files_dir: Path
    ) -> List[Dict[str, Any]]:
        """Process Excel invoice in batch mode."""

        print(f"Processing Excel invoice: {excel_invoice_path}")

        try:
            # Read Excel invoice
            excel_invoice = ExcelInvoiceFile(excel_invoice_path)

            print(f"Excel invoice loaded:")
            print(f"  Rows: {len(excel_invoice.dfexcelinvoice)}")
            print(f"  Columns: {excel_invoice.dfexcelinvoice.shape[1]}")

            # Process each row
            results = []

            for idx, row in excel_invoice.dfexcelinvoice.iterrows():
                try:
                    result = self._process_single_row(
                        excel_invoice=excel_invoice,
                        row_index=idx,
                        original_invoice_path=original_invoice_path,
                        schema_path=schema_path,
                        raw_files_dir=raw_files_dir
                    )
                    results.append(result)
                    print(f"✓ Processed row {idx}: {result['output_file']}")

                except Exception as e:
                    error_result = {
                        "row_index": idx,
                        "status": "failed",
                        "error": str(e),
                        "output_file": None
                    }
                    results.append(error_result)
                    print(f"✗ Failed to process row {idx}: {e}")

            # Summary
            successful = sum(1 for r in results if r["status"] == "success")
            print(f"\nBatch processing summary:")
            print(f"  Total rows: {len(results)}")
            print(f"  Successful: {successful}")
            print(f"  Failed: {len(results) - successful}")

            return results

        except Exception as e:
            print(f"Batch processing failed: {e}")
            raise

    def _process_single_row(
        self,
        excel_invoice: ExcelInvoiceFile,
        row_index: int,
        original_invoice_path: Path,
        schema_path: Path,
        raw_files_dir: Path
    ) -> Dict[str, Any]:
        """Process a single row from Excel invoice."""

        # Generate output filename
        output_filename = f"invoice_{row_index:04d}.json"
        output_path = self.output_dir / output_filename

        # Get data filename for this row
        row_data = excel_invoice.dfexcelinvoice.iloc[row_index]
        data_filename = row_data.get("data_file_names/name", f"data_{row_index}")

        # Process invoice
        excel_invoice.overwrite(
            invoice_org=original_invoice_path,
            dist_path=output_path,
            invoice_schema_path=schema_path,
            idx=row_index
        )

        # Apply magic variables if needed
        raw_file_path = raw_files_dir / data_filename
        if raw_file_path.exists():
            apply_magic_variable(
                invoice_path=output_path,
                rawfile_path=raw_file_path,
                save_filepath=output_path
            )

        return {
            "row_index": row_index,
            "status": "success",
            "output_file": output_path,
            "data_file": data_filename,
            "processed_at": pd.Timestamp.now().isoformat()
        }

    def setup_custom_rules(self, rules_config: Dict[str, str]) -> RuleBasedReplacer:
        """Setup custom replacement rules."""

        rules_file = self.config_dir / "custom_rules.json"
        replacer = RuleBasedReplacer()

        # Set custom rules
        for path, variable in rules_config.items():
            replacer.set_rule(path, variable)

        print(f"Setup {len(rules_config)} custom rules:")
        for path, variable in rules_config.items():
            print(f"  {path} -> {variable}")

        return replacer

    def apply_bulk_transformations(
        self,
        invoice_files: List[Path],
        transformation_rules: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Apply transformations to multiple invoice files."""

        replacer = RuleBasedReplacer()
        results = []

        for invoice_path in invoice_files:
            try:
                # Load invoice
                with open(invoice_path, 'r', encoding='utf-8') as f:
                    invoice_data = json.load(f)

                # Apply rules
                transformed_data = replacer.get_apply_rules_obj(
                    replacements=transformation_rules,
                    source_json_obj=invoice_data
                )

                # Save transformed invoice
                output_path = self.output_dir / f"transformed_{invoice_path.name}"
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(transformed_data, f, indent=2, ensure_ascii=False)

                results.append({
                    "input_file": invoice_path,
                    "output_file": output_path,
                    "status": "success"
                })

            except Exception as e:
                results.append({
                    "input_file": invoice_path,
                    "output_file": None,
                    "status": "failed",
                    "error": str(e)
                })

        return results

# Usage example
def main():
    """Main processing example."""

    # Setup processor
    base_dir = Path("data/invoice_processing")
    processor = ExcelInvoiceProcessor(base_dir)

    # File paths
    schema_path = Path("data/tasksupport/invoice.schema.json")
    excel_invoice_path = Path("data/input/batch_invoice.xlsx")
    original_invoice_path = Path("data/invoice/invoice.json")
    raw_files_dir = Path("data/raw_files")

    try:
        # Step 1: Generate template from schema
        template_path = processor.templates_dir / "generated_template.xlsx"
        template_df, general_df, specific_df = processor.generate_template_from_schema(
            schema_path=schema_path,
            template_path=template_path,
            mode="file"
        )

        # Step 2: Process Excel invoice batch
        if excel_invoice_path.exists():
            batch_results = processor.process_excel_invoice_batch(
                excel_invoice_path=excel_invoice_path,
                original_invoice_path=original_invoice_path,
                schema_path=schema_path,
                raw_files_dir=raw_files_dir
            )

            # Step 3: Setup and apply custom rules
            custom_rules = {
                "basic.creator": "${creator_name}",
                "basic.organization": "${organization}",
                "sample.location": "${sample_location}"
            }

            replacer = processor.setup_custom_rules(custom_rules)

            # Step 4: Apply bulk transformations
            processed_invoices = [r["output_file"] for r in batch_results
                                if r["status"] == "success" and r["output_file"]]

            transformation_rules = {
                "${creator_name}": "Research Team Alpha",
                "${organization}": "Advanced Research Institute",
                "${sample_location}": "Laboratory Building A"
            }

            transformation_results = processor.apply_bulk_transformations(
                invoice_files=processed_invoices,
                transformation_rules=transformation_rules
            )

            print(f"\nTransformation results:")
            successful_transforms = sum(1 for r in transformation_results if r["status"] == "success")
            print(f"  Successful transformations: {successful_transforms}/{len(transformation_results)}")

        print("\n✅ Invoice processing pipeline completed successfully")

    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        raise

if __name__ == "__main__":
    main()
```

### SmartTable Processing with File Mapping

```python
from rdetoolkit.invoicefile import SmartTableFile
from pathlib import Path
import pandas as pd
import zipfile
import tempfile
import shutil
from typing import List, Tuple, Dict, Any

class SmartTableProcessor:
    """Advanced SmartTable processing with file mapping capabilities."""

    def __init__(self, working_dir: Path):
        self.working_dir = working_dir
        self.temp_dir = working_dir / "temp"
        self.output_dir = working_dir / "output"
        self.processed_dir = working_dir / "processed"

        # Create directories
        for directory in [self.temp_dir, self.output_dir, self.processed_dir]:
            directory.mkdir(parents=True, exist_ok=True)

    def extract_zip_file(self, zip_path: Path) -> List[Path]:
        """Extract ZIP file and return list of extracted files."""

        print(f"Extracting ZIP file: {zip_path}")

        try:
            extracted_files = []

            with zipfile.ZipFile(zip_path, 'r') as zip_file:
                # Extract all files
                zip_file.extractall(self.temp_dir)

                # Get list of extracted files
                for file_info in zip_file.filelist:
                    if not file_info.is_dir():
                        extracted_path = self.temp_dir / file_info.filename
                        if extracted_path.exists():
                            extracted_files.append(extracted_path)

            print(f"Extracted {len(extracted_files)} files")
            return extracted_files

        except Exception as e:
            print(f"ZIP extraction failed: {e}")
            raise

    def process_smarttable_with_zip(
        self,
        smarttable_path: Path,
        zip_path: Path | None = None
    ) -> Dict[str, Any]:
        """Process SmartTable with optional ZIP file containing data files."""

        print(f"Processing SmartTable: {smarttable_path}")

        try:
            # Extract ZIP file if provided
            extracted_files = []
            if zip_path and zip_path.exists():
                extracted_files = self.extract_zip_file(zip_path)

            # Create SmartTable processor
            smarttable = SmartTableFile(smarttable_path)

            # Read table data
            table_data = smarttable.read_table()
            print(f"SmartTable data: {table_data.shape[0]} rows, {table_data.shape[1]} columns")

            # Analyze mapping columns
            mapping_analysis = self._analyze_mapping_columns(table_data)
            print(f"Mapping analysis: {mapping_analysis}")

            # Generate CSV files with file mapping
            csv_output_dir = self.processed_dir / "smarttable_csvs"
            csv_mappings = smarttable.generate_row_csvs_with_file_mapping(
                output_dir=csv_output_dir,
                extracted_files=extracted_files
            )

            # Process each generated CSV
            processing_results = []
            for csv_path, related_files in csv_mappings:
                result = self._process_single_csv(csv_path, related_files, table_data)
                processing_results.append(result)

            # Create summary
            summary = {
                "smarttable_file": str(smarttable_path),
                "zip_file": str(zip_path) if zip_path else None,
                "total_rows": len(table_data),
                "total_csvs": len(csv_mappings),
                "extracted_files": len(extracted_files),
                "mapping_analysis": mapping_analysis,
                "processing_results": processing_results,
                "successful_processing": sum(1 for r in processing_results if r["status"] == "success")
            }

            # Save summary
            summary_path = self.output_dir / "smarttable_processing_summary.json"
            import json
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, default=str, ensure_ascii=False)

            print(f"Processing completed: {summary['successful_processing']}/{summary['total_csvs']} successful")
            return summary

        except Exception as e:
            print(f"SmartTable processing failed: {e}")
            raise

    def _analyze_mapping_columns(self, table_data: pd.DataFrame) -> Dict[str, Any]:
        """Analyze mapping columns in SmartTable data."""

        mapping_prefixes = ["basic/", "custom/", "sample/", "meta/"]
        inputdata_pattern = "inputdata"

        analysis = {
            "total_columns": len(table_data.columns),
            "mapping_columns": {},
            "inputdata_columns": [],
            "other_columns": []
        }

        for column in table_data.columns:
            # Check for mapping columns
            mapped = False
            for prefix in mapping_prefixes:
                if column.startswith(prefix):
                    if prefix not in analysis["mapping_columns"]:
                        analysis["mapping_columns"][prefix] = []
                    analysis["mapping_columns"][prefix].append(column)
                    mapped = True
                    break

            # Check for inputdata columns
            if inputdata_pattern in column.lower():
                analysis["inputdata_columns"].append(column)
                mapped = True

            # Other columns
            if not mapped:
                analysis["other_columns"].append(column)

        return analysis

    def _process_single_csv(
        self,
        csv_path: Path,
        related_files: Tuple[Path, ...],
        original_table_data: pd.DataFrame
    ) -> Dict[str, Any]:
        """Process a single CSV file generated from SmartTable row."""

        try:
            # Read CSV data
            csv_data = pd.read_csv(csv_path)
            row_data = csv_data.iloc[0] if len(csv_data) > 0 else None

            if row_data is None:
                return {
                    "csv_file": str(csv_path),
                    "status": "failed",
                    "error": "Empty CSV data"
                }

            # Extract metadata from row
            metadata = self._extract_metadata_from_row(row_data)

            # Process related files
            file_processing_results = []
            for file_path in related_files:
                file_result = self._process_related_file(file_path, metadata)
                file_processing_results.append(file_result)

            # Create output structure
            output_data = {
                "metadata": metadata,
                "related_files": [str(f) for f in related_files],
                "file_processing_results": file_processing_results
            }

            # Save individual result
            output_filename = f"processed_{csv_path.stem}.json"
            output_path = self.output_dir / output_filename

            import json
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, default=str, ensure_ascii=False)

            return {
                "csv_file": str(csv_path),
                "output_file": str(output_path),
                "status": "success",
                "metadata_fields": len(metadata),
                "related_files_count": len(related_files),
                "processed_files": len([r for r in file_processing_results if r["status"] == "success"])
            }

        except Exception as e:
            return {
                "csv_file": str(csv_path),
                "status": "failed",
                "error": str(e)
            }

    def _extract_metadata_from_row(self, row_data: pd.Series) -> Dict[str, Any]:
        """Extract metadata from SmartTable row."""

        metadata = {
            "basic": {},
            "custom": {},
            "sample": {},
            "meta": {}
        }

        for column, value in row_data.items():
            if pd.isna(value) or value == "":
                continue

            # Parse mapping columns
            if column.startswith("basic/"):
                key = column.replace("basic/", "")
                metadata["basic"][key] = value
            elif column.startswith("custom/"):
                key = column.replace("custom/", "")
                metadata["custom"][key] = value
            elif column.startswith("sample/"):
                key = column.replace("sample/", "")
                metadata["sample"][key] = value
            elif column.startswith("meta/"):
                key = column.replace("meta/", "")
                metadata["meta"][key] = value

        return metadata

    def _process_related_file(self, file_path: Path, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single related file."""

        try:
            file_info = {
                "file_path": str(file_path),
                "file_name": file_path.name,
                "file_size": file_path.stat().st_size,
                "file_extension": file_path.suffix,
                "status": "success"
            }

            # Add file-specific processing based on extension
            if file_path.suffix.lower() == '.csv':
                # Process CSV file
                csv_data = pd.read_csv(file_path)
                file_info.update({
                    "csv_rows": len(csv_data),
                    "csv_columns": len(csv_data.columns),
                    "csv_headers": list(csv_data.columns)
                })

            elif file_path.suffix.lower() in ['.txt', '.log']:
                # Process text file
                content = file_path.read_text(encoding='utf-8')
                file_info.update({
                    "text_lines": len(content.splitlines()),
                    "text_chars": len(content)
                })

            elif file_path.suffix.lower() in ['.json']:
                # Process JSON file
                import json
                with open(file_path, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                file_info.update({
                    "json_keys": list(json_data.keys()) if isinstance(json_data, dict) else None,
                    "json_type": type(json_data).__name__
                })

            return file_info

        except Exception as e:
            return {
                "file_path": str(file_path),
                "status": "failed",
                "error": str(e)
            }

    def cleanup(self):
        """Clean up temporary files."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
        print("Cleanup completed")

# Usage example
def demonstrate_smarttable_processing():
    """Demonstrate SmartTable processing capabilities."""

    # Setup processor
    working_dir = Path("data/smarttable_processing")
    processor = SmartTableProcessor(working_dir)

    try:
        # Example file paths
        smarttable_path = Path("data/input/smarttable_experiment.xlsx")
        zip_path = Path("data/input/experiment_data.zip")

        # Process SmartTable with ZIP file
        if smarttable_path.exists():
            summary = processor.process_smarttable_with_zip(
                smarttable_path=smarttable_path,
                zip_path=zip_path if zip_path.exists() else None
            )

            print(f"\nSmartTable Processing Summary:")
            print(f"  Total rows processed: {summary['total_rows']}")
            print(f"  Generated CSV files: {summary['total_csvs']}")
            print(f"  Successful processing: {summary['successful_processing']}")
            print(f"  Extracted files: {summary['extracted_files']}")

        else:
            print("SmartTable file not found, creating example...")
            # Create example SmartTable for demonstration
            example_data = pd.DataFrame({
                "Display Name": ["Sample A", "Sample B"],
                "basic/dataName": ["experiment_001", "experiment_002"],
                "basic/description": ["First experiment", "Second experiment"],
                "custom/temperature": ["25.5", "26.1"],
                "sample/location": ["Lab A", "Lab B"],
                "inputdata1": ["data/sample_a.csv", "data/sample_b.csv"],
                "inputdata2": ["data/metadata_a.json", "data/metadata_b.json"]
            })

            example_path = working_dir / "example_smarttable.xlsx"
            example_data.to_excel(example_path, index=False)
            print(f"Created example SmartTable: {example_path}")

    finally:
        # Cleanup
        processor.cleanup()

if __name__ == "__main__":
    demonstrate_smarttable_processing()
```

## Error Handling

### Exception Types

The invoicefile module raises `StructuredError` for various error conditions:

```python
from rdetoolkit.exceptions import StructuredError
from rdetoolkit.invoicefile import InvoiceFile, ExcelInvoiceFile

# Handle invoice file errors
try:
    invoice = InvoiceFile("nonexistent.json")
except StructuredError as e:
    print(f"Invoice file error: {e}")

# Handle Excel invoice errors
try:
    excel_invoice = ExcelInvoiceFile("invalid.xlsx")
except StructuredError as e:
    print(f"Excel invoice error: {e}")
```

### Best Practices for Error Handling

1. **Validate Files Before Processing**:
   ```python
   def safe_invoice_processing(invoice_path: Path) -> bool:
       """Safely process invoice with validation."""
       if not invoice_path.exists():
           print(f"Invoice file not found: {invoice_path}")
           return False

       try:
           invoice = InvoiceFile(invoice_path)
           # Process invoice...
           return True
       except StructuredError as e:
           print(f"Invoice processing failed: {e}")
           return False
   ```

2. **Handle Template Generation Errors**:
   ```python
   def safe_template_generation(schema_path: Path, output_path: Path):
       """Generate template with error handling."""
       try:
           return ExcelInvoiceFile.generate_template(schema_path, output_path)
       except StructuredError as e:
           print(f"Template generation failed: {e}")
           return None, None, None
   ```

## Performance Notes

### Optimization Strategies

1. **Batch Processing**: Process multiple invoice files efficiently
2. **Memory Management**: Use DataFrames efficiently for large Excel files
3. **File I/O Optimization**: Minimize repeated file reading operations
4. **Template Caching**: Cache generated templates for reuse

### Performance Best Practices

```python
# Efficient batch processing
def process_invoices_efficiently(invoice_paths: List[Path]):
    """Process multiple invoices efficiently."""

    # Load schema once
    schema_path = Path("data/tasksupport/invoice.schema.json")

    for invoice_path in invoice_paths:
        try:
            invoice = InvoiceFile(invoice_path)
            # Process with shared schema...
        except Exception as e:
            print(f"Skipping {invoice_path}: {e}")
```

## See Also

- [Core Module](core.md) - For directory operations and file handling
- [File Operations](fileops.md) - For JSON file reading and writing utilities
- [Models - Invoice](models/invoice.md) - For invoice data structure definitions
- [Models - Invoice Schema](models/invoice_schema.md) - For invoice schema definitions
- [Validation](validation.md) - For invoice validation functionality
- [RDE2 Utilities](rde2util.md) - For metadata processing utilities
- [Exceptions](exceptions.md) - For StructuredError and other exception types
- [Usage - CLI](../usage/cli.md) - For command-line invoice processing
- [Usage - Structured Process](../usage/structured_process/structured.md) - For invoice processing in workflows
