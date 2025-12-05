"""Test design for boolean handling in castval.

Equivalence Partitioning
| API | Input/State Partition | Rationale | Expected Outcome | Test ID |
| --- | --- | --- | --- | --- |
| `castval` | Recognized true strings (`"true"` variants) | Valid boolean tokens | Returns `True` | `TC-EP-001` |
| `castval` | Recognized false strings (`"false"` variants) | Valid boolean tokens | Returns `False` | `TC-EP-002` |
| `castval` | Non-string truthy values (e.g., `1`) | Valid non-string inputs | Returns `True` | `TC-EP-003` |
| `castval` | Non-string falsy values (e.g., `0`, `None`) | Valid non-string inputs | Returns `False` | `TC-EP-004` |
| `castval` | Unrecognized strings (`"yes"`, `"no"`, `"1"`, `"0"`, `""`, `"maybe"`, `"true-ish"`, `"falsey"`, `"N/A"`, `"on"`, `"off"`) | Invalid domain | Raises `StructuredError` | `TC-EP-005` |

Boundary Value
| API | Boundary | Rationale | Expected Outcome | Test ID |
| --- | --- | --- | --- | --- |
| `castval` | `" true "` | Leading/trailing whitespace | Returns `True` | `TC-BV-001` |
| `castval` | `" false "` | Leading/trailing whitespace | Returns `False` | `TC-BV-002` |
| `castval` | `""` | Smallest length string | Raises `StructuredError` | `TC-BV-003` |
| `castval` | `1` | Truthy non-string boundary | Returns `True` | `TC-BV-004` |
| `castval` | `0` | Falsy non-string boundary | Returns `False` | `TC-BV-005` |

Execution
- Direct: `pytest -q --maxfail=1 --cov=rdetoolkit --cov-branch --cov-report=term-missing --cov-report=html tests/test_castval_boolean.py`
- Via tox: `tox`
"""

import pytest

from rdetoolkit.exceptions import StructuredError
from rdetoolkit.rde2util import castval


@pytest.mark.parametrize(
    "valstr",
    ["true", "True", " true "],
    ids=["lowercase_true", "capitalized_true", "whitespace_true"],
)
def test_castval_recognized_true_strings__tc_ep_001__tc_bv_001(valstr):
    # Given: recognized true-like string input
    # When: casting the value to boolean
    result = castval(valstr, "boolean", None)
    # Then: the result is True as bool type
    assert result is True
    assert isinstance(result, bool)


@pytest.mark.parametrize(
    "valstr",
    ["false", "FALSE", " false "],
    ids=["lowercase_false", "uppercase_false", "whitespace_false"],
)
def test_castval_recognized_false_strings__tc_ep_002__tc_bv_002(valstr):
    # Given: recognized false-like string input
    # When: casting the value to boolean
    result = castval(valstr, "boolean", None)
    # Then: the result is False as bool type
    assert result is False
    assert isinstance(result, bool)


@pytest.mark.parametrize(
    "valstr",
    [1],
    ids=["int_one_truthy_boundary"],
)
def test_castval_non_string_truthy_values__tc_ep_003__tc_bv_004(valstr):
    # Given: a non-string truthy value
    # When: casting the value to boolean
    result = castval(valstr, "boolean", None)
    # Then: truthy values map to True with bool type
    assert result is True
    assert isinstance(result, bool)


@pytest.mark.parametrize(
    "valstr",
    [0, None],
    ids=["int_zero_falsy_boundary", "none_falsy"],
)
def test_castval_non_string_falsy_values__tc_ep_004__tc_bv_005(valstr):
    # Given: a non-string falsy value
    # When: casting the value to boolean
    result = castval(valstr, "boolean", None)
    # Then: falsy values map to False with bool type
    assert result is False
    assert isinstance(result, bool)


@pytest.mark.parametrize(
    "valstr",
    ["yes", "no", "1", "0", "", "maybe", "true-ish", "falsey", "N/A", "on", "off"],
    ids=[
        "yes_literal",
        "no_literal",
        "string_one",
        "string_zero",
        "empty_string",
        "maybe",
        "true_ish",
        "falsey",
        "n_a",
        "on_literal",
        "off_literal",
    ],
)
def test_castval_invalid_boolean_strings__tc_ep_005__tc_bv_003(valstr):
    # Given: an unrecognized boolean string
    # When: casting the value to boolean
    with pytest.raises(StructuredError) as exc_info:
        castval(valstr, "boolean", None)
    # Then: StructuredError is raised with the invalid value in the message
    assert str(exc_info.value) == f"ERROR: invalid boolean value '{valstr}'"
