"""Property-based tests for rdetoolkit.rde2util.castval.

Tests type casting functions with various input types and edge cases.
"""

from __future__ import annotations

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import assume, given, strategies as st

from rdetoolkit.exceptions import StructuredError
from rdetoolkit.rde2util import castval
from tests.property.strategies import finite_floats


# Custom strategies for type casting
@st.composite
def numeric_string(draw: st.DrawFn) -> str:
    """Generate string representations of numbers."""
    num = draw(
        st.one_of(
            st.integers(min_value=-(10**10), max_value=10**10),
            st.floats(allow_nan=False, allow_infinity=False, min_value=-1e10, max_value=1e10),
        )
    )
    return str(num)


@st.composite
def boolean_string(draw: st.DrawFn) -> str:
    """Generate string representations of booleans."""
    return draw(
        st.sampled_from(
            [
                "true",
                "True",
                "TRUE",
                "false",
                "False",
                "FALSE",
            ]
        )
    )


@st.composite
def mixed_type_value(draw: st.DrawFn) -> int | float | str | bool | None:
    """Generate values of various types."""
    return draw(
        st.one_of(
            st.integers(min_value=-(10**10), max_value=10**10),
            st.floats(allow_nan=False, allow_infinity=False, min_value=-1e10, max_value=1e10),
            st.text(max_size=100),
            st.booleans(),
            st.none(),
        )
    )


@pytest.mark.property
class TestCastValToIntegerProperties:
    """Property-based tests for casting to integer."""

    @given(value=st.integers(min_value=-(10**10), max_value=10**10))
    def test_int_to_integer_identity(self, value: int) -> None:
        """Property: Casting int to integer is identity."""
        # Given: Integer value
        # When: Casting to integer
        result = castval(value, "integer", None)

        # Then: Result equals input
        assert result == value
        assert isinstance(result, int)

    @given(value=st.integers(min_value=-(10**10), max_value=10**10))
    def test_integer_string_to_integer(self, value: int) -> None:
        """Property: Integer string representations can be cast to integer."""
        # Given: String representation of integer (not float format)
        str_value = str(value)

        # When: Casting to integer
        result = castval(str_value, "integer", None)

        # Then: Result matches expected
        assert result == value
        assert isinstance(result, int)

    @given(value=st.floats(allow_nan=False, allow_infinity=False, min_value=-1e10, max_value=1e10))
    def test_float_string_to_integer_fails(self, value: float) -> None:
        """Property: Float format strings cannot be cast to integer."""
        # Given: String representation of float with decimal point
        str_value = str(value)
        assume("." in str_value)  # Only test float format strings

        # When/Then: Casting to integer raises StructuredError
        with pytest.raises(StructuredError, match="failed to cast"):
            castval(str_value, "integer", None)


@pytest.mark.property
class TestCastValToNumberProperties:
    """Property-based tests for casting to number."""

    @given(value=finite_floats)
    def test_float_to_number(self, value: float) -> None:
        """Property: Casting float to number preserves value."""
        # Given: Float value
        # When: Casting to number
        result = castval(value, "number", None)

        # Then: Result equals input
        assert result == value
        assert isinstance(result, (int, float))

    @given(value=st.integers(min_value=-(10**10), max_value=10**10))
    def test_int_to_number(self, value: int) -> None:
        """Property: Int to number conversion preserves value."""
        # Given: Integer value
        # When: Casting to number
        result = castval(value, "number", None)

        # Then: Result equals input
        assert result == value
        assert isinstance(result, int)

    @given(value=numeric_string())
    def test_numeric_string_to_number(self, value: str) -> None:
        """Property: Numeric strings can be cast to number."""
        # Given: String representation of number
        expected: int | float
        try:
            # Try int first, then float (same logic as _cast_number)
            try:
                expected = int(value)
            except ValueError:
                expected = float(value)
        except (ValueError, OverflowError):
            assume(False)

        # When: Casting to number
        result = castval(value, "number", None)

        # Then: Result matches expected
        if isinstance(expected, float):
            assert abs(float(result) - expected) < 1e-10
        else:
            assert result == expected
        assert isinstance(result, (int, float))


@pytest.mark.property
class TestCastValToStringProperties:
    """Property-based tests for casting to string."""

    @given(value=mixed_type_value())
    def test_any_to_string_without_format(self, value: int | float | str | bool | None) -> None:
        """Property: Any value can be cast to string without format."""
        # Given: Any value
        # When: Casting to string without format
        result = castval(value, "string", None)

        # Then: Result equals original value (no conversion when outfmt is None)
        assert result == value

    @given(value=st.text(max_size=100))
    def test_str_to_string_identity(self, value: str) -> None:
        """Property: Casting str to string is identity."""
        # Given: String value
        # When: Casting to string
        result = castval(value, "string", None)

        # Then: Result equals input
        assert result == value
        assert isinstance(result, str)


@pytest.mark.property
class TestCastValToBooleanProperties:
    """Property-based tests for casting to boolean."""

    @given(value=st.booleans())
    def test_bool_to_boolean_identity(self, value: bool) -> None:
        """Property: Casting bool to boolean is identity."""
        # Given: Boolean value
        # When: Casting to boolean
        result = castval(value, "boolean", None)

        # Then: Result equals input
        assert result == value
        assert isinstance(result, bool)

    @given(value=st.integers(min_value=-(10**10), max_value=10**10))
    def test_int_to_boolean_zero_false(self, value: int) -> None:
        """Property: 0 is False, non-zero is True."""
        # Given: Integer value
        # When: Casting to boolean
        result = castval(value, "boolean", None)

        # Then: 0 is False, others are True
        assert result == (value != 0)
        assert isinstance(result, bool)

    @given(value=boolean_string())
    def test_boolean_string_to_bool(self, value: str) -> None:
        """Property: Boolean strings can be cast to bool."""
        # Given: Boolean string representation
        # When: Casting to boolean
        result = castval(value, "boolean", None)

        # Then: Result is boolean
        assert isinstance(result, bool)
        # 'true', 'True', 'TRUE' -> True
        # 'false', 'False', 'FALSE' -> False
        expected = value.lower().strip() == "true"
        assert result == expected


@pytest.mark.property
class TestCastValUnknownTypeProperties:
    """Property-based tests for unknown type handling."""

    @given(
        value=mixed_type_value(),
        invalid_type=st.text(
            alphabet=st.characters(categories=("Lu", "Ll")),
            min_size=1,
            max_size=20,
        ).filter(lambda x: x not in ["boolean", "integer", "number", "string"]),
    )
    def test_unknown_type_raises_structured_error(
        self,
        value: int | float | str | bool | None,
        invalid_type: str,
    ) -> None:
        """Property: Unknown outtype always raises StructuredError."""
        # Given: Any value and unknown type
        # When/Then: Casting raises StructuredError
        with pytest.raises(StructuredError, match="unknown value type"):
            castval(value, invalid_type, None)

    @given(value=mixed_type_value())
    def test_none_type_raises_structured_error(self, value: int | float | str | bool | None) -> None:
        """Property: None as outtype raises StructuredError."""
        # Given: Any value
        # When/Then: Casting with None type raises StructuredError
        with pytest.raises(StructuredError, match="unknown value type"):
            castval(value, None, None)


@pytest.mark.property
class TestCastValTypePreservationProperties:
    """Property-based tests for type preservation."""

    @given(
        value=mixed_type_value(),
        target_type=st.sampled_from(["boolean", "integer", "number", "string"]),
    )
    def test_result_type_matches_target(
        self,
        value: int | float | str | bool | None,
        target_type: str,
    ) -> None:
        """Property: Result type matches target type (or raises exception)."""
        # Given: Any value and target type
        # When: Casting to target type
        try:
            result = castval(value, target_type, None)
            # Then: Result is of appropriate type
            if target_type == "boolean":
                assert isinstance(result, bool)
            elif target_type == "integer":
                assert isinstance(result, int)
            elif target_type == "number":
                assert isinstance(result, (int, float))
            elif target_type == "string":
                # When outfmt is None, _cast_string returns original value
                pass  # Type may vary
        except StructuredError:
            # Incompatible types should raise StructuredError
            pass

    @given(value=st.one_of(st.integers(min_value=-(10**10), max_value=10**10), finite_floats))
    def test_numeric_cast_idempotent(self, value: float) -> None:
        """Property: Casting numeric type twice gives same result."""
        # Given: Numeric value
        target_type = "integer" if isinstance(value, int) else "number"

        # When: Casting twice
        once = castval(value, target_type, None)
        twice = castval(once, target_type, None)

        # Then: Results are equal
        assert once == twice
