import inspect

import pytest

from rdetoolkit.workflows import run


class TestWorkflowsDocstring:
    """Test workflows.run() docstring quality and completeness."""

    def test_run_has_docstring(self):
        """Test: run() function has docstring."""
        # Given: workflows.run function
        # When: Checking docstring
        # Then: Should have non-empty docstring
        assert run.__doc__ is not None
        assert len(run.__doc__) > 0

    def test_docstring_contains_required_sections(self):
        """Test: Docstring contains all required Google Style sections."""
        # Given: run() function docstring
        docstring = run.__doc__

        # When: Checking for required sections
        # Then: Should contain standard sections
        assert "Args:" in docstring
        assert "Returns:" in docstring
        assert "Raises:" in docstring
        assert "Examples:" in docstring
        assert "Notes:" in docstring

    def test_docstring_documents_all_parameters(self):
        """Test: Docstring documents all function parameters."""
        # Given: Function signature
        sig = inspect.signature(run)
        params = [p for p in sig.parameters.keys() if p != "kwargs"]

        # When: Checking docstring
        docstring = run.__doc__

        # Then: All parameters should be documented
        for param in params:
            assert param in docstring, f"Parameter '{param}' not documented"

    def test_docstring_has_practical_examples(self):
        """Test: Docstring includes practical usage examples."""
        # Given: run() function docstring
        docstring = run.__doc__

        # When: Checking for code examples
        # Then: Should contain code blocks (>>>, code syntax)
        assert ">>>" in docstring or "```python" in docstring
        assert "custom_dataset_function" in docstring

    def test_docstring_mentions_processing_modes(self):
        """Test: Docstring mentions processing modes."""
        # Given: run() function docstring
        docstring = run.__doc__

        # When: Checking for mode documentation
        # Then: Should mention key processing modes
        assert "MultiDataTile" in docstring
        assert "SmartTable" in docstring
        assert "invoice" in docstring.lower()

    def test_docstring_references_agent_guide(self):
        """Test: Docstring references agent guide for more info."""
        # Given: run() function docstring
        docstring = run.__doc__

        # When: Checking for agent guide reference
        # Then: Should mention get_agent_guide or agent-guide command
        assert "get_agent_guide" in docstring or "agent-guide" in docstring
