"""Excel invoice template generation.

This module provides classes for generating Excel invoice templates
from RDE invoice schema definitions.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias

from rdetoolkit import __version__
from rdetoolkit.exceptions import InvoiceSchemaValidationError, StructuredError
from rdetoolkit.fileops import readf_json
from rdetoolkit.invoicefile._helpers import (
    _ensure_openpyxl_styles,
    _ensure_openpyxl_utils,
    _ensure_pandas,
    _ensure_validation_error,
    logger,
)
from rdetoolkit.models.invoice_schema import InvoiceSchemaJson

if TYPE_CHECKING:
    import pandas as pd

    from rdetoolkit.models.invoice import (
        FixedHeaders,
        GeneralAttributeConfig,
        GeneralTermRegistry,
        SpecificAttributeConfig,
        SpecificTermRegistry,
        TemplateConfig,
    )
    from rdetoolkit.models.invoice_schema import SampleField, SpecificProperty

    AttributeConfig: TypeAlias = GeneralAttributeConfig | SpecificAttributeConfig
else:
    # Runtime imports are required for isinstance checks in _add_sample_field.
    from rdetoolkit.models.invoice import (
        GeneralAttributeConfig,
        GeneralTermRegistry,
        SpecificAttributeConfig,
        SpecificTermRegistry,
    )
    from rdetoolkit.models.invoice_schema import SpecificProperty

    AttributeConfig = Any


class TemplateGenerator(Protocol):
    """Protocol for template generators.

    Defines the interface for generating invoice templates from configurations.
    """

    def generate(self, config: TemplateConfig) -> pd.DataFrame:
        """Generates a template based on the provided configuration.

        Args:
            config (TemplateConfig): The configuration object.

        Returns:
            pd.DataFrame: A DataFrame representing the generated template.
        """
        ...


class ExcelInvoiceTemplateGenerator:
    """Generator for Excel invoice templates.

    This class generates Excel invoice templates based on RDE invoice schema
    definitions, including support for general and specific terms.

    Attributes:
        fixed_header (FixedHeaders): Fixed header configuration for the template.

    Args:
        fixed_header (FixedHeaders): The fixed headers configuration.

    Example:
        from rdetoolkit.models.invoice import FixedHeaders, TemplateConfig

        headers = FixedHeaders()
        generator = ExcelInvoiceTemplateGenerator(headers)
        config = TemplateConfig(
            schema_path="invoice.schema.json",
            general_term_path="generalterm.csv",
            specific_term_path="specificterm.csv",
            inputfile_mode="file"
        )
        template_df, general_df, specific_df, version_df = generator.generate(config)
    """

    GENERAL_PREFIX = "sample.general"
    SPECIFIC_PREFIX = "sample.specific"
    CUSTOM_PREFIX = "custom"

    def __init__(self, fixed_header: FixedHeaders):
        self.fixed_header = fixed_header

    def _version_info(self) -> pd.DataFrame:
        pd = _ensure_pandas()
        return pd.DataFrame({
            "items": ["version"],
            "values": [__version__],
        })

    def generate(self, config: TemplateConfig) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Generate Excel invoice template from configuration.

        Args:
            config: Template configuration containing schema and term paths.

        Returns:
            Tuple of (template_df, general_df, specific_df, version_df).

        Raises:
            InvoiceSchemaValidationError: If the invoice schema validation fails.
        """
        pd = _ensure_pandas()

        base_df = self.fixed_header.to_template_dataframe().to_pandas()
        invoice_schema_obj = readf_json(config.schema_path)
        try:
            validation_error = _ensure_validation_error()
            invoice_schema = InvoiceSchemaJson(**invoice_schema_obj)
        except validation_error as e:
            raise InvoiceSchemaValidationError(str(e)) from e
        prefixes = {
            "general": self.GENERAL_PREFIX,
            "specific": self.SPECIFIC_PREFIX,
            "custom": self.CUSTOM_PREFIX,
        }

        # Sample field
        sample_field = invoice_schema.properties.sample
        if sample_field is not None:
            _, general_term_df, specific_term_df = self._add_sample_field(base_df, config, sample_field, prefixes)

        # Custom field
        custom_field = invoice_schema.properties.custom
        if custom_field is not None:
            custom_dict = custom_field.properties.root
            for key, meta_prop in custom_dict.items():
                base_df[key] = pd.Series([None, prefixes["custom"], key, meta_prop.label.ja], index=base_df.index)

        # Select Mode: folder/file
        if config.inputfile_mode == "folder":
            first_col = base_df.columns[0]
            base_df.loc[1, first_col] = ""
            base_df.loc[2, first_col] = "data_folder"

        # Version
        version_df = self._version_info()

        logger.info("Template generation complete")
        return base_df, general_term_df, specific_term_df, version_df

    def _add_sample_field(self, base_df: pd.DataFrame, config: TemplateConfig, sample_field: SampleField, prefixes: Mapping[str, str]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        pd = _ensure_pandas()
        attribute_configs: list[AttributeConfig] = [
            GeneralAttributeConfig(
                type="general",
                registry=GeneralTermRegistry(str(config.general_term_path)),
                prefix=prefixes["general"],
                attributes=sample_field.properties.generalAttributes,
                requires_class_id=False,
            ),
            SpecificAttributeConfig(
                type="specific",
                registry=SpecificTermRegistry(str(config.specific_term_path)),
                prefix=prefixes["specific"],
                attributes=sample_field.properties.specificAttributes,
                requires_class_id=True,
            ),
        ]
        registered_general_terms: list[dict[str, Any]] = []
        registered_specific_terms: list[dict[str, Any]] = []
        for attr_config in attribute_configs:
            attrs = attr_config.attributes
            if not attrs or not attrs.items.root:
                if isinstance(attr_config, GeneralAttributeConfig):
                    registered_general_terms = []
                elif isinstance(attr_config, SpecificAttributeConfig):
                    registered_specific_terms = []
                continue

            for prop in attrs.items.root:
                term_id = prop.properties.term_id.const
                class_id = ""
                if isinstance(prop, SpecificProperty):
                    class_id = prop.properties.class_id.const

                try:
                    emsg = "Could not find a result corresponding to the specified term_id or class_id."
                    if isinstance(attr_config, SpecificAttributeConfig):
                        emsg = f"Could not find a result corresponding to term_id {term_id} and class_id {class_id}."
                        term = attr_config.registry.by_term_and_class_id(term_id, class_id)[0]
                        registered_specific_terms.append({
                            "sample_class_id": class_id,
                            "term_id": term_id,
                            "key_name": term["key_name"],
                        })
                    else:
                        emsg = f"Could not find a result corresponding to term_id {term_id}."
                        term = attr_config.registry.by_term_id(term_id)[0]
                        registered_general_terms.append({
                            "term_id": term_id,
                            "key_name": term["key_name"],
                        })
                except (IndexError, KeyError) as e:
                    raise StructuredError(emsg) from e

                ja_name = term["ja"]
                key_name = term["key_name"]
                name = key_name.replace(f"{attr_config.prefix}.", "")
                base_df[key_name] = [None, attr_config.prefix, name, ja_name]

        df_registered_general = pd.DataFrame(
            registered_general_terms,
            columns=["term_id", "key_name"] if not registered_general_terms else None,
        )
        df_registered_specific = pd.DataFrame(
            registered_specific_terms,
            columns=["sample_class_id", "term_id", "key_name"] if not registered_specific_terms else None,
        )

        return base_df, df_registered_general, df_registered_specific

    def save(self, dataframes: Mapping[str, pd.DataFrame], save_path: str) -> None:
        """Save generated templates to an Excel file with styling.

        Args:
            dataframes: Dictionary mapping sheet names to DataFrames.
            save_path: Path where Excel file will be saved.

        Note:
            The method performs the following operations:
            - Writes the DataFrame to an Excel file starting from the 5th row without headers.
            - Sets the height of the 5th row to 40.
            - Adjusts the width of all columns to 20.
            - Applies a thin border to all cells in the range from row 5 to row 40.
            - Applies a thick top border and a double bottom border to the cells in the 5th row.

        Example:
            dataframes = {
                "invoice_form": template_df,
                "generalTerm": general_df,
                "specificTerm": specific_df,
                "_version": version_df,
            }
            generator.save(dataframes, "template.xlsx")
        """
        pd = _ensure_pandas()
        with pd.ExcelWriter(save_path, engine="openpyxl") as writer:
            for sheet_name, df in dataframes.items():
                if sheet_name != "invoice_form":
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                    self._style_sub_sheet(writer, df, sheet_name)
                else:
                    df.to_excel(writer, sheet_name=sheet_name, index=False, header=False)
                    self._style_main_sheet(writer, df, sheet_name)

    def _style_main_sheet(self, writer: pd.ExcelWriter, df: pd.DataFrame, sheet_name: str) -> None:
        """Apply styling to main invoice sheet.

        Args:
            writer: pandas ExcelWriter instance.
            df: DataFrame being written.
            sheet_name: Name of the sheet.
        """
        border_cls, _, side_cls = _ensure_openpyxl_styles()
        get_column_letter = _ensure_openpyxl_utils()
        default_row_height: int = 40
        default_column_width: int = 20
        default_start_row: int = 4
        default_end_row: int = 41
        default_start_col: int = 1

        _ = writer.book
        worksheet = writer.sheets[sheet_name]
        worksheet.row_dimensions[4].height = default_row_height
        max_col = df.shape[1]

        for col in range(1, max_col + 1):
            col_letter = get_column_letter(col)
            worksheet.column_dimensions[col_letter].width = default_column_width

        # settings cell border
        thin = side_cls(border_style="thin", color="000000")
        thick = side_cls(border_style="thick", color="000000")
        double = side_cls(border_style="double", color="000000")
        grid_border = border_cls(top=thin, left=thin, right=thin, bottom=thin)

        for row in range(default_start_row, default_end_row):
            for col in range(default_start_col, max_col + 1):
                cell = worksheet.cell(row=row, column=col)
                cell.border = grid_border

        for col in range(1, max_col + 1):
            cell = worksheet.cell(row=4, column=col)
            cell.border = border_cls(left=cell.border.left, right=cell.border.right, top=thick, bottom=double)

    def _style_sub_sheet(self, writer: pd.ExcelWriter, df: pd.DataFrame, sheet_name: str) -> None:
        """Apply styling to sub-sheets (general/specific term sheets).

        Args:
            writer: pandas ExcelWriter instance.
            df: DataFrame being written.
            sheet_name: Name of the sheet.
        """
        _, font_cls, _ = _ensure_openpyxl_styles()
        default_cell_style = "Normal"
        _ = writer.book
        worksheet = writer.sheets[sheet_name]
        for row in worksheet.iter_rows():
            for cell in row:
                cell.style = default_cell_style
                cell.font = font_cls(bold=False)
