"""Test RDE type docstring quality and completeness."""

from rdetoolkit.models.rde2types import RdeInputDirPaths, RdeOutputResourcePath


class TestRde2TypesDocstrings:
    """Test RDE type docstring quality and completeness."""

    def test_rde_input_dir_paths_has_docstring(self):
        """Test: RdeInputDirPaths has docstring."""
        # Given: RdeInputDirPaths class
        # When: Checking docstring
        # Then: Should have non-empty docstring
        assert RdeInputDirPaths.__doc__ is not None
        assert len(RdeInputDirPaths.__doc__) > 100

    def test_rde_output_resource_path_has_docstring(self):
        """Test: RdeOutputResourcePath has docstring."""
        # Given: RdeOutputResourcePath class
        # When: Checking docstring
        # Then: Should have non-empty docstring
        assert RdeOutputResourcePath.__doc__ is not None
        assert len(RdeOutputResourcePath.__doc__) > 100

    def test_input_paths_docstring_documents_attributes(self):
        """Test: RdeInputDirPaths docstring documents key attributes."""
        # Given: RdeInputDirPaths docstring
        docstring = RdeInputDirPaths.__doc__

        # When: Checking for attribute documentation
        # Then: Should document key attributes
        assert "inputdata" in docstring
        assert "invoice" in docstring
        assert "tasksupport" in docstring
        assert "config" in docstring

    def test_output_paths_docstring_documents_attributes(self):
        """Test: RdeOutputResourcePath docstring documents key attributes."""
        # Given: RdeOutputResourcePath docstring
        docstring = RdeOutputResourcePath.__doc__

        # When: Checking for attribute documentation
        # Then: Should document key attributes
        assert "struct" in docstring
        assert "main_image" in docstring
        assert "other_image" in docstring
        assert "meta" in docstring
        assert "raw" in docstring

    def test_docstrings_include_examples(self):
        """Test: Path class docstrings include usage examples."""
        # Given: Path class docstrings
        input_doc = RdeInputDirPaths.__doc__
        output_doc = RdeOutputResourcePath.__doc__

        # When: Checking for examples
        # Then: Should contain code examples
        assert "Examples:" in input_doc or ">>>" in input_doc
        assert "Examples:" in output_doc or ">>>" in output_doc

    def test_docstrings_follow_google_style(self):
        """Test: Docstrings follow Google Style format."""
        # Given: Path class docstrings
        input_doc = RdeInputDirPaths.__doc__
        output_doc = RdeOutputResourcePath.__doc__

        # When: Checking format
        # Then: Should have standard sections
        for doc in [input_doc, output_doc]:
            assert "Attributes:" in doc
            # Should have proper indentation and structure
            assert len(doc.split("\n")) > 5

    def test_docstrings_reference_related_classes(self):
        """Test: Docstrings reference related classes."""
        # Given: Path class docstrings
        input_doc = RdeInputDirPaths.__doc__
        output_doc = RdeOutputResourcePath.__doc__

        # When: Checking for cross-references
        # Then: Should reference related classes
        assert "RdeOutputResourcePath" in input_doc or "output" in input_doc.lower()
        assert "RdeInputDirPaths" in output_doc or "input" in output_doc.lower()

    def test_input_paths_docstring_describes_directory_structure(self):
        """Test: RdeInputDirPaths docstring describes directory structure."""
        # Given: RdeInputDirPaths docstring
        docstring = RdeInputDirPaths.__doc__

        # When: Checking for structure documentation
        # Then: Should describe directory layout
        assert "directory structure" in docstring.lower() or "container/data/" in docstring

    def test_output_paths_docstring_describes_directory_structure(self):
        """Test: RdeOutputResourcePath docstring describes directory structure."""
        # Given: RdeOutputResourcePath docstring
        docstring = RdeOutputResourcePath.__doc__

        # When: Checking for structure documentation
        # Then: Should describe directory layout
        assert "directory structure" in docstring.lower() or "container/data/invoice/" in docstring

    def test_docstrings_include_notes_section(self):
        """Test: Docstrings include Notes section with important details."""
        # Given: Path class docstrings
        input_doc = RdeInputDirPaths.__doc__
        output_doc = RdeOutputResourcePath.__doc__

        # When: Checking for Notes section
        # Then: Should have Notes section
        assert "Notes:" in input_doc
        assert "Notes:" in output_doc

    def test_docstrings_include_see_also_section(self):
        """Test: Docstrings include See Also section with cross-references."""
        # Given: Path class docstrings
        input_doc = RdeInputDirPaths.__doc__
        output_doc = RdeOutputResourcePath.__doc__

        # When: Checking for See Also section
        # Then: Should have See Also section
        assert "See Also:" in input_doc
        assert "See Also:" in output_doc
