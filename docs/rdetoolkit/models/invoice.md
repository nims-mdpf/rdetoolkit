# Invoice Module

The `rdetoolkit.models.invoice` module provides comprehensive functionality for managing Excel-based invoice templates and term registries in RDE systems. This module handles the creation, validation, and manipulation of invoice data structures with support for both general and specific term management.

## Overview

The invoice module implements a complete system for managing RDE invoice data with the following capabilities:

- **Excel Template Generation**: Structured creation of Excel invoice templates with predefined headers
- **Term Registry Management**: Efficient searching and retrieval of general and specific terms
- **Multi-language Support**: Support for Japanese and English term descriptions
- **Data Validation**: Integration with Pydantic models for robust data validation
- **Flexible Configuration**: Configurable template generation with various input modes

## Header Classes

The module provides a hierarchical structure of header classes that define the standard Excel invoice template format.

### HeaderRow1

Represents the first header row containing format identification.

#### Constructor

```python
HeaderRow1(A1: str = "invoiceList_format_id")
```

**Parameters:**
- `A1` (str): Format identifier (default: "invoiceList_format_id")

#### Example

```python
from rdetoolkit.models.invoice import HeaderRow1

header1 = HeaderRow1()
print(header1.A1)  # "invoiceList_format_id"

# Custom format ID
custom_header1 = HeaderRow1(A1="custom_format_v2")
```

### HeaderRow2

Represents the second header row defining column groupings.

#### Constructor

```python
HeaderRow2(
    A2: str = "data_file_names",
    D2_G2: list[str] = ["basic"] * 4,
    H2_M2: list[str] = ["sample"] * 6
)
```

**Parameters:**
- `A2` (str): Data file names identifier (default: "data_file_names")
- `D2_G2` (list[str]): Basic data column labels (default: ["basic"] * 4)
- `H2_M2` (list[str]): Sample data column labels (default: ["sample"] * 6)

#### Example

```python
from rdetoolkit.models.invoice import HeaderRow2

header2 = HeaderRow2()
print(header2.D2_G2)  # ["basic", "basic", "basic", "basic"]
print(header2.H2_M2)  # ["sample", "sample", "sample", "sample", "sample", "sample"]

# Custom groupings
custom_header2 = HeaderRow2(
    D2_G2=["metadata"] * 4,
    H2_M2=["specimen"] * 6
)
```

### HeaderRow3

Represents the third header row with English column names.

#### Constructor

```python
HeaderRow3(
    A3: str = "name",
    B3: str = "dataset_title",
    C3: str = "dataOwner",
    D3: str = "dataOwnerId",
    E3: str = "dataName",
    F3: str = "experimentId",
    G3: str = "description",
    H3: str = "names",
    I3: str = "sampleId",
    J3: str = "ownerId",
    K3: str = "composition",
    L3: str = "referenceUrl",
    M3: str = "description"
)
```

**Parameters:**
All parameters are column name identifiers with their respective defaults.

#### Example

```python
from rdetoolkit.models.invoice import HeaderRow3

header3 = HeaderRow3()
print(header3.A3)  # "name"
print(header3.I3)  # "sampleId"
```

### HeaderRow4

Represents the fourth header row with Japanese column descriptions.

#### Constructor

```python
HeaderRow4(
    A4: str = "ファイル名\n(拡張子も含め入力)\n(入力例:○○.txt)",
    B4: str = "データセット名\n(必須)",
    C4: str = "データ所有者\n(NIMS User ID)",
    D4: str = "NIMS user UUID\n(必須)",
    E4: str = "データ名\n(必須)",
    F4: str = "実験ID",
    G4: str = "説明",
    H4: str = "試料名\n(ローカルID)",
    I4: str = "試料UUID\n(必須)",
    J4: str = "試料管理者UUID",
    K4: str = "化学式・組成式・分子式など",
    L4: str = "参考URL",
    M4: str = "試料の説明"
)
```

**Parameters:**
All parameters are Japanese column descriptions with their respective defaults.

#### Example

```python
from rdetoolkit.models.invoice import HeaderRow4

header4 = HeaderRow4()
print(header4.B4)  # "データセット名\n(必須)"
print(header4.I4)  # "試料UUID\n(必須)"
```

### FixedHeaders

Container class that combines all header rows and provides template generation functionality.

#### Constructor

```python
FixedHeaders(
    row1: HeaderRow1 = HeaderRow1(),
    row2: HeaderRow2 = HeaderRow2(),
    row3: HeaderRow3 = HeaderRow3(),
    row4: HeaderRow4 = HeaderRow4()
)
```

**Parameters:**
- `row1` (HeaderRow1): First header row
- `row2` (HeaderRow2): Second header row
- `row3` (HeaderRow3): Third header row
- `row4` (HeaderRow4): Fourth header row

#### Methods

##### to_template_dataframe()

Converts the header data to a Polars DataFrame formatted for Excel template generation.

```python
def to_template_dataframe() -> pl.DataFrame
```

**Returns:**
- `pl.DataFrame`: A Polars DataFrame with 13 columns (A-M) and 4 rows containing the formatted header data

**Example:**

```python
from rdetoolkit.models.invoice import FixedHeaders
import polars as pl

headers = FixedHeaders()
df = headers.to_template_dataframe()

print(df.shape)  # (4, 13)
print(df.columns)  # ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M']

# Access specific cells
print(df[0, 0])  # "invoiceList_format_id"
print(df[2, 1])  # "dataset_title"
```

## Configuration Classes

### TemplateConfig

Configuration dataclass for generating Excel invoice templates.

#### Constructor

```python
TemplateConfig(
    schema_path: str | Path,
    general_term_path: str | Path,
    specific_term_path: str | Path,
    inputfile_mode: Literal["file", "folder"] = "file"
)
```

**Parameters:**
- `schema_path` (str | Path): Path to the invoice schema file
- `general_term_path` (str | Path): Path to the general terms CSV file
- `specific_term_path` (str | Path): Path to the specific terms CSV file
- `inputfile_mode` (Literal["file", "folder"]): Input processing mode (default: "file")

#### Example

```python
from rdetoolkit.models.invoice import TemplateConfig
from pathlib import Path

config = TemplateConfig(
    schema_path="schemas/invoice_schema.json",
    general_term_path="terms/general_terms.csv",
    specific_term_path="terms/specific_terms.csv",
    inputfile_mode="folder"
)

# Using Path objects
config = TemplateConfig(
    schema_path=Path("schemas") / "invoice_schema.json",
    general_term_path=Path("terms") / "general_terms.csv",
    specific_term_path=Path("terms") / "specific_terms.csv"
)
```

## Term Registry Classes

### BaseTermRegistry

Abstract base class providing common functionality for term registries.

#### Attributes

- `base_schema` (dict): Base schema definition for term data validation

```python
base_schema = {
    "term_id": pl.Utf8,
    "key_name": pl.Utf8,
    "ja": pl.Utf8,
    "en": pl.Utf8,
}
```

### GeneralTermRegistry

Registry for managing general terms with search capabilities.

#### Constructor

```python
GeneralTermRegistry(csv_path: str)
```

**Parameters:**
- `csv_path` (str): Path to the CSV file containing general terms data

#### Attributes

- `df` (pl.DataFrame): Polars DataFrame containing the loaded term data

#### Methods

##### search(column, value, out_cols)

Generic search method for finding terms based on column values.

```python
def search(column: str, value: str, out_cols: list[str]) -> list[dict[str, Any]]
```

**Parameters:**
- `column` (str): Column name to search in
- `value` (str): Value to search for
- `out_cols` (list[str]): List of columns to include in the output

**Returns:**
- `list[dict[str, Any]]`: List of dictionaries containing matching rows with specified columns

**Example:**

```python
from rdetoolkit.models.invoice import GeneralTermRegistry

registry = GeneralTermRegistry("general_terms.csv")

# Search for terms by key_name
results = registry.search("key_name", "temperature", ["term_id", "ja", "en"])
print(results)
# [{"term_id": "T001", "ja": "温度", "en": "Temperature"}]
```

##### by_term_id(term_id)

Retrieve term details by term ID.

```python
def by_term_id(term_id: str) -> list[dict[str, Any]]
```

**Parameters:**
- `term_id` (str): The term ID to search for

**Returns:**
- `list[dict[str, Any]]`: List of dictionaries with keys "term_id", "key_name", "ja", "en"

**Example:**

```python
registry = GeneralTermRegistry("general_terms.csv")

result = registry.by_term_id("T001")
print(result)
# [{"term_id": "T001", "key_name": "temperature", "ja": "温度", "en": "Temperature"}]
```

##### by_ja(ja_text)

Search for terms using Japanese text.

```python
def by_ja(ja_text: str) -> list[dict[str, Any]]
```

**Parameters:**
- `ja_text` (str): Japanese text to search for

**Returns:**
- `list[dict[str, Any]]`: List of dictionaries with keys "term_id", "key_name", "en"

**Example:**

```python
registry = GeneralTermRegistry("general_terms.csv")

results = registry.by_ja("温度")
print(results)
# [{"term_id": "T001", "key_name": "temperature", "en": "Temperature"}]
```

##### by_en(en_text)

Search for terms using English text.

```python
def by_en(en_text: str) -> list[dict[str, Any]]
```

**Parameters:**
- `en_text` (str): English text to search for

**Returns:**
- `list[dict[str, Any]]`: List of dictionaries with keys "term_id", "key_name", "ja"

**Example:**

```python
registry = GeneralTermRegistry("general_terms.csv")

results = registry.by_en("Temperature")
print(results)
# [{"term_id": "T001", "key_name": "temperature", "ja": "温度"}]
```

### SpecificTermRegistry

Registry for managing specific terms with enhanced search capabilities including sample class support.

#### Constructor

```python
SpecificTermRegistry(csv_path: str)
```

**Parameters:**
- `csv_path` (str): Path to the CSV file containing specific terms data

#### Attributes

- `df` (pl.DataFrame): Polars DataFrame with extended schema including sample_class_id

#### Methods

##### search(columns, values, out_cols)

Multi-column search method for complex term queries.

```python
def search(columns: list[str], values: list[str], out_cols: list[str]) -> list[dict[str, Any]]
```

**Parameters:**
- `columns` (list[str]): List of column names to search in
- `values` (list[str]): List of values to search for (must match columns length)
- `out_cols` (list[str]): List of columns to include in the output

**Returns:**
- `list[dict[str, Any]]`: List of dictionaries containing matching rows

**Raises:**
- `ValueError`: If columns and values lists have different lengths
- `DataRetrievalError`: If data retrieval fails
- `InvalidSearchParametersError`: If search parameters are invalid

**Example:**

```python
from rdetoolkit.models.invoice import SpecificTermRegistry

registry = SpecificTermRegistry("specific_terms.csv")

# Search by multiple criteria
results = registry.search(
    columns=["sample_class_id", "key_name"],
    values=["C001", "hardness"],
    out_cols=["term_id", "ja", "en"]
)
print(results)
# [{"term_id": "S001", "ja": "硬度", "en": "Hardness"}]
```

##### by_term_and_class_id(term_id, sample_class_id)

Search for specific terms by both term ID and sample class ID.

```python
def by_term_and_class_id(term_id: str, sample_class_id: str) -> list[dict[str, Any]]
```

**Parameters:**
- `term_id` (str): Term ID to search for
- `sample_class_id` (str): Sample class ID to search for

**Returns:**
- `list[dict[str, Any]]`: List with keys "sample_class_id", "term_id", "key_name", "ja", "en"

**Example:**

```python
registry = SpecificTermRegistry("specific_terms.csv")

results = registry.by_term_and_class_id("S001", "C001")
print(results)
# [{"sample_class_id": "C001", "term_id": "S001", "key_name": "hardness", "ja": "硬度", "en": "Hardness"}]
```

##### by_key_name(key_name)

Search for terms by key name.

```python
def by_key_name(key_name: list[str]) -> list[dict[str, Any]]
```

**Parameters:**
- `key_name` (list[str]): List containing the key name to search for

**Returns:**
- `list[dict[str, Any]]`: List with keys "sample_class_id", "term_id", "key_name", "ja", "en"

**Example:**

```python
registry = SpecificTermRegistry("specific_terms.csv")

results = registry.by_key_name(["hardness"])
print(results)
# [{"sample_class_id": "C001", "term_id": "S001", "key_name": "hardness", "ja": "硬度", "en": "Hardness"}]
```

##### by_ja(ja_text)

Search for specific terms using Japanese text.

```python
def by_ja(ja_text: list[str]) -> list[dict[str, Any]]
```

**Parameters:**
- `ja_text` (list[str]): List containing Japanese text to search for

**Returns:**
- `list[dict[str, Any]]`: List with keys "sample_class_id", "term_id", "key_name", "en"

##### by_en(en_text)

Search for specific terms using English text.

```python
def by_en(en_text: list[str]) -> list[dict[str, Any]]
```

**Parameters:**
- `en_text` (list[str]): List containing English text to search for

**Returns:**
- `list[dict[str, Any]]`: List with keys "sample_class_id", "term_id", "key_name", "ja"

## Attribute Configuration Classes

### GeneralAttributeConfig

Configuration dataclass for general attribute handling.

#### Constructor

```python
GeneralAttributeConfig(
    type: str,
    registry: GeneralTermRegistry,
    prefix: str,
    attributes: GeneralAttribute | None,
    requires_class_id: Literal[False]
)
```

**Parameters:**
- `type` (str): Attribute type identifier
- `registry` (GeneralTermRegistry): General term registry instance
- `prefix` (str): Column prefix for the attributes
- `attributes` (GeneralAttribute | None): General attribute schema definition
- `requires_class_id` (Literal[False]): Always False for general attributes

#### Example

```python
from rdetoolkit.models.invoice import GeneralAttributeConfig, GeneralTermRegistry
from rdetoolkit.models.invoice_schema import GeneralAttribute

registry = GeneralTermRegistry("general_terms.csv")
config = GeneralAttributeConfig(
    type="general",
    registry=registry,
    prefix="gen_",
    attributes=None,  # or GeneralAttribute instance
    requires_class_id=False
)
```

### SpecificAttributeConfig

Configuration dataclass for specific attribute handling.

#### Constructor

```python
SpecificAttributeConfig(
    type: str,
    registry: SpecificTermRegistry,
    prefix: str,
    attributes: SpecificAttribute | None,
    requires_class_id: Literal[True]
)
```

**Parameters:**
- `type` (str): Attribute type identifier
- `registry` (SpecificTermRegistry): Specific term registry instance
- `prefix` (str): Column prefix for the attributes
- `attributes` (SpecificAttribute | None): Specific attribute schema definition
- `requires_class_id` (Literal[True]): Always True for specific attributes

#### Example

```python
from rdetoolkit.models.invoice import SpecificAttributeConfig, SpecificTermRegistry
from rdetoolkit.models.invoice_schema import SpecificAttribute

registry = SpecificTermRegistry("specific_terms.csv")
config = SpecificAttributeConfig(
    type="specific",
    registry=registry,
    prefix="spec_",
    attributes=None,  # or SpecificAttribute instance
    requires_class_id=True
)
```

## Complete Usage Examples

### Creating an Excel Invoice Template

```python
from rdetoolkit.models.invoice import FixedHeaders, TemplateConfig
from pathlib import Path
import polars as pl

# Create headers
headers = FixedHeaders()

# Generate template DataFrame
template_df = headers.to_template_dataframe()

# Save to Excel
template_df.write_excel("invoice_template.xlsx", position="A1")

print("Excel template created successfully!")
```

### Working with Term Registries

```python
from rdetoolkit.models.invoice import GeneralTermRegistry, SpecificTermRegistry

# Initialize registries
general_registry = GeneralTermRegistry("data/general_terms.csv")
specific_registry = SpecificTermRegistry("data/specific_terms.csv")

# Search general terms
temp_terms = general_registry.by_en("Temperature")
print("Temperature terms:", temp_terms)

# Search specific terms by class and term ID
hardness_terms = specific_registry.by_term_and_class_id("S001", "C001")
print("Hardness terms:", hardness_terms)

# Multi-language search
ja_results = general_registry.by_ja("温度")
en_results = specific_registry.by_en(["Hardness"])

print("Japanese search results:", ja_results)
print("English search results:", en_results)
```

### Complete Template Generation Workflow

```python
from rdetoolkit.models.invoice import (
    TemplateConfig, FixedHeaders, GeneralTermRegistry, SpecificTermRegistry,
    GeneralAttributeConfig, SpecificAttributeConfig
)
from pathlib import Path
import polars as pl

# Setup configuration
config = TemplateConfig(
    schema_path="schemas/invoice_schema.json",
    general_term_path="terms/general_terms.csv",
    specific_term_path="terms/specific_terms.csv",
    inputfile_mode="folder"
)

# Initialize registries
general_registry = GeneralTermRegistry(str(config.general_term_path))
specific_registry = SpecificTermRegistry(str(config.specific_term_path))

# Create attribute configurations
general_config = GeneralAttributeConfig(
    type="general",
    registry=general_registry,
    prefix="gen_",
    attributes=None,
    requires_class_id=False
)

specific_config = SpecificAttributeConfig(
    type="specific",
    registry=specific_registry,
    prefix="spec_",
    attributes=None,
    requires_class_id=True
)

# Generate template
headers = FixedHeaders()
template_df = headers.to_template_dataframe()

# Add sample data rows
sample_data = [
    ["sample1.txt", "Dataset 1", "user123", "uuid-123", "Data 1", "exp1", "Description",
     "Sample A", "sample-uuid-1", "owner-uuid-1", "H2O", "http://ref.url", "Water sample"],
    ["sample2.txt", "Dataset 2", "user456", "uuid-456", "Data 2", "exp2", "Description",
     "Sample B", "sample-uuid-2", "owner-uuid-2", "NaCl", "http://ref2.url", "Salt sample"]
]

# Convert to DataFrame and append
sample_df = pl.DataFrame(sample_data, schema=template_df.columns)
final_df = pl.concat([template_df, sample_df])

# Save complete template
final_df.write_excel("complete_invoice_template.xlsx", position="A1")

print(f"Complete template saved with {len(final_df)} rows")
```

### Advanced Term Searching

```python
from rdetoolkit.models.invoice import GeneralTermRegistry, SpecificTermRegistry
from rdetoolkit.exceptions import DataRetrievalError, InvalidSearchParametersError

def search_terms_safely(registry, search_func, *args):
    """Safely search terms with error handling."""
    try:
        results = search_func(*args)
        return results
    except (DataRetrievalError, InvalidSearchParametersError) as e:
        print(f"Search error: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error: {e}")
        return []

# Initialize registries
general_registry = GeneralTermRegistry("general_terms.csv")
specific_registry = SpecificTermRegistry("specific_terms.csv")

# Safe searching
general_results = search_terms_safely(
    general_registry,
    general_registry.by_en,
    "Temperature"
)

specific_results = search_terms_safely(
    specific_registry,
    specific_registry.by_term_and_class_id,
    "S001", "C001"
)

print("General results:", general_results)
print("Specific results:", specific_results)

# Batch term lookup
term_ids = ["T001", "T002", "T003"]
all_general_terms = []

for term_id in term_ids:
    terms = search_terms_safely(
        general_registry,
        general_registry.by_term_id,
        term_id
    )
    all_general_terms.extend(terms)

print(f"Found {len(all_general_terms)} general terms")
```

### Custom Header Configuration

```python
from rdetoolkit.models.invoice import (
    HeaderRow1, HeaderRow2, HeaderRow3, HeaderRow4, FixedHeaders
)

# Create custom headers for a specific use case
custom_row2 = HeaderRow2(
    A2="file_list",
    D2_G2=["metadata"] * 4,
    H2_M2=["specimen"] * 6
)

custom_row3 = HeaderRow3(
    A3="filename",
    B3="title",
    # ... other customizations
)

custom_row4 = HeaderRow4(
    A4="ファイル名を入力",
    B4="タイトルを入力",
    # ... other Japanese descriptions
)

# Combine into custom headers
custom_headers = FixedHeaders(
    row1=HeaderRow1(),  # Use default
    row2=custom_row2,
    row3=custom_row3,
    row4=custom_row4
)

# Generate custom template
custom_template = custom_headers.to_template_dataframe()
print("Custom template shape:", custom_template.shape)
print("First row data:", custom_template.row(0))
```

## Error Handling

### Common Exceptions

The invoice module may raise several types of exceptions during operation:

#### ValueError
Raised when search parameters are invalid:

```python
try:
    registry = SpecificTermRegistry("terms.csv")
    # This will raise ValueError if columns and values have different lengths
    results = registry.search(["col1", "col2"], ["val1"], ["output"])
except ValueError as e:
    print(f"Parameter error: {e}")
```

#### DataRetrievalError
Raised when data retrieval operations fail:

```python
from rdetoolkit.exceptions import DataRetrievalError

try:
    registry = SpecificTermRegistry("terms.csv")
    results = registry.by_term_and_class_id("invalid_term", "invalid_class")
except DataRetrievalError as e:
    print(f"Data retrieval failed: {e}")
```

#### InvalidSearchParametersError
Raised when search parameters are structurally invalid:

```python
from rdetoolkit.exceptions import InvalidSearchParametersError

try:
    registry = SpecificTermRegistry("terms.csv")
    # Some operation that causes invalid parameters
    results = registry.search([], [], ["output"])
except InvalidSearchParametersError as e:
    print(f"Invalid search parameters: {e}")
```

### Best Practices

1. **Always Validate File Paths**: Ensure CSV files exist before creating registries:
   ```python
   from pathlib import Path

   csv_path = Path("terms.csv")
   if csv_path.exists():
       registry = GeneralTermRegistry(str(csv_path))
   else:
       print(f"File not found: {csv_path}")
   ```

2. **Handle Empty Results Gracefully**: Check for empty results before processing:
   ```python
   results = registry.by_en("NonexistentTerm")
   if results:
       # Process results
       for result in results:
           print(result)
   else:
       print("No results found")
   ```

3. **Use Type Hints**: Leverage type hints for better code clarity:
   ```python
   from typing import List, Dict, Any

   def process_terms(registry: GeneralTermRegistry) -> List[Dict[str, Any]]:
       return registry.by_en("Temperature")
   ```

4. **Validate DataFrame Structure**: Ensure DataFrames have expected columns:
   ```python
   headers = FixedHeaders()
   df = headers.to_template_dataframe()

   expected_cols = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M"]
   assert df.columns == expected_cols, "Template structure mismatch"
   ```

5. **Use Configuration Objects**: Centralize configuration for better maintainability:
   ```python
   config = TemplateConfig(
       schema_path="config/schema.json",
       general_term_path="data/general.csv",
       specific_term_path="data/specific.csv",
       inputfile_mode="folder"
   )

   # Pass config to other functions
   def setup_registries(config: TemplateConfig):
       general_reg = GeneralTermRegistry(str(config.general_term_path))
       specific_reg = SpecificTermRegistry(str(config.specific_term_path))
       return general_reg, specific_reg
   ```

## Performance Notes

- Term registries use Polars DataFrames for efficient data operations
- Search operations are optimized for large datasets with proper indexing
- DataFrame operations leverage Polars' lazy evaluation when possible
- Memory usage is optimized through schema validation and type specification
- Batch operations are recommended for processing multiple terms

## Integration with Schema Models

The invoice module integrates seamlessly with the `invoice_schema` module:

```python
from rdetoolkit.models.invoice import SpecificAttributeConfig
from rdetoolkit.models.invoice_schema import SpecificAttribute, SampleSpecificItems

# Create schema-defined attributes
specific_attr = SpecificAttribute(
    obj_type="array",
    items=SampleSpecificItems(root=[...])
)

# Use in configuration
config = SpecificAttributeConfig(
    type="specific",
    registry=specific_registry,
    prefix="spec_",
    attributes=specific_attr,  # Schema-validated attributes
    requires_class_id=True
)
```

## See Also

- [Invoice Schema Module](invoice_schema.md) - For schema validation and structure definitions
- [Core Module](../core.md) - For file operations and directory management
- [Polars Documentation](https://pola.rs/) - For DataFrame operations and optimization
- [Pydantic Documentation](https://docs.pydantic.dev/) - For data validation patterns
