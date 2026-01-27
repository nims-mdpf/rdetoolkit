"""Common Hypothesis strategies for RDEToolKit property-based tests.

This module provides reusable strategies for generating test data
across different modules.

Note: This module requires hypothesis to be installed. If hypothesis is not
available, importing this module will raise ImportError.
"""

try:
    from hypothesis import strategies as st

    # File path strategies
    safe_filename_chars = st.text(
        alphabet=st.characters(
            categories=("Lu", "Ll", "Nd"),
            exclude_characters='\\/:*?"<>|',
        ),
        min_size=1,
        max_size=255,
    )

    # Text strategies
    ascii_text = st.text(
        alphabet=st.characters(min_codepoint=32, max_codepoint=126),
        min_size=0,
        max_size=1000,
    )

    unicode_text = st.text(
        alphabet=st.characters(exclude_categories=["Cs"]),  # Exclude surrogates
        min_size=0,
        max_size=1000,
    )

    # Numeric strategies
    finite_floats = st.floats(
        allow_nan=False,
        allow_infinity=False,
        min_value=-1e308,
        max_value=1e308,
    )

    # Column name strategies
    valid_column_names = st.text(
        alphabet=st.characters(
            categories=("Lu", "Ll", "Nd"),
            include_characters="_-",
        ),
        min_size=1,
        max_size=100,
    )

except ImportError:
    # Hypothesis not installed - strategies will not be available
    # Tests using these strategies will be skipped via pytest.importorskip
    pass
