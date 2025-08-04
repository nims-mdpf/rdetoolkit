# Invoice Models API

## Purpose

This module defines data models for invoices and Excel invoices in RDEToolKit. It provides structured invoice management, validation, registry management, and multi-language support through term registries.

## Key Features

### Data Models
- Excel invoice header structure definitions
- Template configuration management
- Multi-language support through term registries

### Configuration Management
- Fixed header management
- General and specific attribute configuration
- Term search and mapping functionality

---

::: src.rdetoolkit.models.invoice.FixedHeaders

---

::: src.rdetoolkit.models.invoice.HeaderRow1

---

::: src.rdetoolkit.models.invoice.HeaderRow2

---

::: src.rdetoolkit.models.invoice.HeaderRow3

---

::: src.rdetoolkit.models.invoice.HeaderRow4

---

::: src.rdetoolkit.models.invoice.TemplateConfig

---

::: src.rdetoolkit.models.invoice.BaseTermRegistry

---

::: src.rdetoolkit.models.invoice.GeneralTermRegistry

---

::: src.rdetoolkit.models.invoice.SpecificTermRegistry

---

::: src.rdetoolkit.models.invoice.GeneralAttributeConfig

---

::: src.rdetoolkit.models.invoice.SpecificAttributeConfig

---

## Practical Usage

### Fixed Header Management

```python title="fixed_headers.py"
from rdetoolkit.models.invoice import FixedHeaders
import pandas as pd

# Create fixed headers
headers = FixedHeaders()

# Generate template DataFrame
template_df = headers.to_template_dataframe()
print(f"Template columns: {len(template_df.columns)}")
print(f"Template rows: {len(template_df)}")

# Display header structure
print("Header structure:")
for i, column in enumerate(template_df.columns):
    print(f"  Column {i+1}: {column}")
```

### Term Registry Usage

```python title="term_registry.py"
from rdetoolkit.models.invoice import GeneralTermRegistry, SpecificTermRegistry

# General term registry usage
general_registry = GeneralTermRegistry()

# Search terms
search_results = general_registry.search("temperature")
print(f"Search results: {search_results}")

# Search by term ID
term_by_id = general_registry.by_term_id("TEMP001")
if term_by_id:
    print(f"Term ID TEMP001: {term_by_id}")

# Search by Japanese term
term_by_ja = general_registry.by_ja("温度")
if term_by_ja:
    print(f"Japanese '温度': {term_by_ja}")

# Search by English term
term_by_en = general_registry.by_en("temperature")
if term_by_en:
    print(f"English 'temperature': {term_by_en}")

# Specific term registry usage
specific_registry = SpecificTermRegistry()

# Search by term and class ID
specific_term = specific_registry.by_term_and_class_id("material", "MAT001")
if specific_term:
    print(f"Specific term: {specific_term}")
```

### Attribute Configuration Management

```python title="attribute_config.py"
from rdetoolkit.models.invoice import GeneralAttributeConfig, SpecificAttributeConfig

# General attribute configuration
general_config = GeneralAttributeConfig(
    term_id="TEMP001",
    name_ja="温度",
    name_en="Temperature",
    unit="℃",
    data_type="float",
    required=True
)

print(f"General attribute: {general_config.name_ja} ({general_config.name_en})")
print(f"Unit: {general_config.unit}")
print(f"Data type: {general_config.data_type}")
print(f"Required: {general_config.required}")

# Specific attribute configuration
specific_config = SpecificAttributeConfig(
    class_id="MAT001",
    term_id="DENSITY001",
    name_ja="密度",
    name_en="Density",
    unit="g/cm³",
    data_type="float",
    required=False,
    default_value=1.0
)

print(f"Specific attribute: {specific_config.name_ja} ({specific_config.name_en})")
print(f"Class ID: {specific_config.class_id}")
print(f"Default value: {specific_config.default_value}")
```

### Template Configuration Usage

```python title="template_config.py"
from rdetoolkit.models.invoice import TemplateConfig

# Create template configuration
template_config = TemplateConfig(
    name="Experiment Data Template",
    version="1.0",
    description="Template for temperature measurement experiments",
    author="John Doe",
    created_date="2024-01-01"
)

print(f"Template name: {template_config.name}")
print(f"Version: {template_config.version}")
print(f"Description: {template_config.description}")
print(f"Author: {template_config.author}")
print(f"Created date: {template_config.created_date}")

# Validate template configuration
if template_config.validate():
    print("✓ Template configuration is valid")
else:
    print("✗ Template configuration has issues")
```
