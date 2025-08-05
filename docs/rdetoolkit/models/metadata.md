# Metadata Models API

## Purpose

This module defines validation models for metadata (metadata.json) used in RDEToolKit. It provides functionality for metadata structure validation, type safety assurance, and data integrity verification.

## Key Features

### Metadata Models
- Structure definition of metadata items
- Management of validatable items
- Processing of meta values and variables

### Data Validation
- Pydantic-based type safety
- Metadata validity verification
- Detailed error messages

---

::: src.rdetoolkit.models.metadata.MetadataItem

---

::: src.rdetoolkit.models.metadata.ValidableItems

---

::: src.rdetoolkit.models.metadata.MetaValue

---

::: src.rdetoolkit.models.metadata.Variable

---

## Practical Usage

### Basic Metadata Item

```python title="basic_metadata_item.py"
from rdetoolkit.models.metadata import MetadataItem, MetaValue

# Create meta value
meta_value = MetaValue(
    value=25.0,
    unit="℃",
    uncertainty=0.1,
    description="Measurement at room temperature"
)

# Create metadata item
metadata_item = MetadataItem(
    name="temperature",
    meta_value=meta_value,
    required=True,
    category="measurement"
)

print(f"Metadata item: {metadata_item.name}")
print(f"Value: {metadata_item.meta_value.value} {metadata_item.meta_value.unit}")
print(f"Uncertainty: ±{metadata_item.meta_value.uncertainty}")
print(f"Required: {metadata_item.required}")
```

### Managing Validatable Items

```python title="validable_items.py"
from rdetoolkit.models.metadata import ValidableItems, MetadataItem

# Create multiple metadata items
temperature_item = MetadataItem(
    name="temperature",
    meta_value={"value": 25.0, "unit": "℃"},
    required=True
)

pressure_item = MetadataItem(
    name="pressure",
    meta_value={"value": 1013.25, "unit": "hPa"},
    required=True
)

humidity_item = MetadataItem(
    name="humidity",
    meta_value={"value": 60, "unit": "%"},
    required=False
)

# Manage as validatable items
validable_items = ValidableItems(
    items=[temperature_item, pressure_item, humidity_item],
    validation_rules={
        "temperature": {"min": -50, "max": 100},
        "pressure": {"min": 800, "max": 1200},
        "humidity": {"min": 0, "max": 100}
    }
)

print(f"Number of validatable items: {len(validable_items.items)}")
print(f"Validation rules: {validable_items.validation_rules}")

# Validate each item
for item in validable_items.items:
    print(f"Item {item.name}: {item.meta_value}")
```

### Variable Processing

```python title="variable_processing.py"
from rdetoolkit.models.metadata import Variable

# Create variables
temperature_var = Variable(
    name="T",
    full_name="Temperature",
    data_type="float",
    unit="℃",
    description="Measured temperature",
    default_value=25.0
)

pressure_var = Variable(
    name="P",
    full_name="Pressure",
    data_type="float",
    unit="hPa",
    description="Atmospheric pressure",
    default_value=1013.25
)

print(f"Variable {temperature_var.name}: {temperature_var.full_name}")
print(f"Data type: {temperature_var.data_type}")
print(f"Unit: {temperature_var.unit}")
print(f"Default value: {temperature_var.default_value}")

print(f"Variable {pressure_var.name}: {pressure_var.full_name}")
print(f"Data type: {pressure_var.data_type}")
print(f"Unit: {pressure_var.unit}")
print(f"Default value: {pressure_var.default_value}")
```

### Metadata Validation System

```python title="metadata_validation_system.py"
from rdetoolkit.models.metadata import MetadataItem, ValidableItems, Variable
from typing import List, Dict

class MetadataValidator:
    """Metadata validation system"""
    
    def __init__(self):
        self.variables: List[Variable] = []
        self.validation_results: Dict[str, bool] = {}
    
    def add_variable(self, variable: Variable):
        """Add variable"""
        self.variables.append(variable)
        print(f"Added variable '{variable.name}'")
    
    def validate_metadata_items(self, items: ValidableItems) -> Dict[str, bool]:
        """Validate metadata items"""
        results = {}
        
        for item in items.items:
            try:
                # Basic validation
                if item.required and not item.meta_value:
                    results[item.name] = False
                    print(f"✗ {item.name}: Required item not set")
                    continue
                
                # Value range validation
                if item.name in items.validation_rules:
                    rules = items.validation_rules[item.name]
                    value = item.meta_value.get("value") if isinstance(item.meta_value, dict) else item.meta_value.value
                    
                    if "min" in rules and value < rules["min"]:
                        results[item.name] = False
                        print(f"✗ {item.name}: Value below minimum ({value} < {rules['min']})")
                        continue
                    
                    if "max" in rules and value > rules["max"]:
                        results[item.name] = False
                        print(f"✗ {item.name}: Value exceeds maximum ({value} > {rules['max']})")
                        continue
                
                results[item.name] = True
                print(f"✓ {item.name}: Validation successful")
                
            except Exception as e:
                results[item.name] = False
                print(f"✗ {item.name}: Validation error - {e}")
        
        self.validation_results = results
        return results
    
    def get_validation_summary(self) -> Dict[str, int]:
        """Validation results summary"""
        total = len(self.validation_results)
        passed = sum(1 for result in self.validation_results.values() if result)
        failed = total - passed
        
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "success_rate": passed / total if total > 0 else 0
        }

# Usage example
validator = MetadataValidator()

# Add variables
temp_var = Variable(name="T", full_name="Temperature", data_type="float", unit="℃")
press_var = Variable(name="P", full_name="Pressure", data_type="float", unit="hPa")

validator.add_variable(temp_var)
validator.add_variable(press_var)

# Create metadata items
items = ValidableItems(
    items=[
        MetadataItem(name="temperature", meta_value={"value": 25.0}, required=True),
        MetadataItem(name="pressure", meta_value={"value": 1013.25}, required=True),
        MetadataItem(name="humidity", meta_value={"value": 150}, required=False)  # Invalid value
    ],
    validation_rules={
        "temperature": {"min": -50, "max": 100},
        "pressure": {"min": 800, "max": 1200},
        "humidity": {"min": 0, "max": 100}
    }
)

# Execute validation
validation_results = validator.validate_metadata_items(items)

# Display summary
summary = validator.get_validation_summary()
print(f"\n=== Validation Summary ===")
print(f"Total items: {summary['total']}")
print(f"Passed: {summary['passed']}")
print(f"Failed: {summary['failed']}")
print(f"Success rate: {summary['success_rate']:.2%}")
```
