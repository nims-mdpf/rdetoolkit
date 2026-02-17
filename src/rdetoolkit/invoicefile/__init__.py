"""Invoice file handling package.

This package provides utilities for working with RDE invoice files
in JSON and Excel formats.

Backward Compatibility:
    All imports from the original `rdetoolkit.invoicefile` module are preserved:
    - from rdetoolkit.invoicefile import InvoiceFile
    - from rdetoolkit.invoicefile import ExcelInvoiceFile
    - from rdetoolkit.invoicefile import SmartTableFile
    - from rdetoolkit.invoicefile import apply_magic_variable
    - etc.
"""

from __future__ import annotations

# Re-export all public and internal components for backward compatibility

# From _helpers
from rdetoolkit.invoicefile._helpers import (
    EX_GENERALTERM,
    EX_SPECIFICTERM,
    MAGIC_VARIABLE_PATTERN,
    STATIC_DIR,
    _ensure_chardet,
    _ensure_logger,
    _ensure_openpyxl_styles,
    _ensure_openpyxl_utils,
    _ensure_pandas,
    _ensure_validation_error,
    logger,
)

# From _sheet_processing
from rdetoolkit.invoicefile._sheet_processing import (
    SheetType,
    _SHEET_PROCESSORS,
    _identify_sheet_type,
    _process_general_term_sheet,
    _process_invoice_sheet,
    _process_specific_term_sheet,
    check_exist_rawfiles,
    check_exist_rawfiles_for_folder,
    read_excelinvoice,
)

# From _invoice
from rdetoolkit.invoicefile._invoice import (
    InvoiceFile,
    _assign_invoice_val,
    overwrite_invoicefile_for_dpfterm,
)

# From _template
from rdetoolkit.invoicefile._template import (
    ExcelInvoiceTemplateGenerator,
    TemplateGenerator,
)

# From _excelinvoice
from rdetoolkit.invoicefile._excelinvoice import ExcelInvoiceFile

# From _description
from rdetoolkit.invoicefile._description import (
    backup_invoice_json_files,
    update_description_with_features,
)

# From _rule_replacer
from rdetoolkit.invoicefile._rule_replacer import (
    RuleBasedReplacer,
    apply_default_filename_mapping_rule,
)

# From _magic_variable
from rdetoolkit.invoicefile._magic_variable import (
    MagicVariableResolver,
    _load_metadata,
    apply_magic_variable,
)

# From _smarttable
from rdetoolkit.invoicefile._smarttable import SmartTableFile

__all__ = [
    # Constants and helpers
    "STATIC_DIR",
    "EX_GENERALTERM",
    "EX_SPECIFICTERM",
    "MAGIC_VARIABLE_PATTERN",
    "logger",
    "_ensure_pandas",
    "_ensure_openpyxl_styles",
    "_ensure_openpyxl_utils",
    "_ensure_chardet",
    "_ensure_validation_error",
    "_ensure_logger",
    # Sheet processing
    "SheetType",
    "read_excelinvoice",
    "_process_invoice_sheet",
    "_process_general_term_sheet",
    "_process_specific_term_sheet",
    "_identify_sheet_type",
    "_SHEET_PROCESSORS",
    "check_exist_rawfiles",
    "check_exist_rawfiles_for_folder",
    # Invoice file handling
    "InvoiceFile",
    "_assign_invoice_val",
    "overwrite_invoicefile_for_dpfterm",
    # Template generation
    "TemplateGenerator",
    "ExcelInvoiceTemplateGenerator",
    # Excel invoice
    "ExcelInvoiceFile",
    # Description updates
    "backup_invoice_json_files",
    "update_description_with_features",
    # Rule-based replacement
    "RuleBasedReplacer",
    "apply_default_filename_mapping_rule",
    # Magic variables
    "MagicVariableResolver",
    "_load_metadata",
    "apply_magic_variable",
    # SmartTable
    "SmartTableFile",
]
