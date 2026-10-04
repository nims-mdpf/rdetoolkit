"""One derivation for ``flow_id`` and one flow-stack helper (Session J1, ruling #1).

Authority: ``local/develop/v2/tasks/session_j1.md`` ruling #1 (which corrects
PhaseJ ruling #5a), ``PhaseJ_prompts.md`` §Phase J 契約裁定 #5(a), Design.md §3.4
addendum. The invariant being protected is

    every ``NodeCallRecord.parent_flow`` equals ``RunReport.flow_id``

for **both** entry points. ``parent_flow`` comes from the flow stack, which
``@flow`` fills with ``FlowSpec.id``; therefore ``RunReport.flow_id`` must be
derived the same way — ``FlowSpec.id`` when the callable carries a spec
(honouring an explicit ``@flow(id=...)``), otherwise ``module.qualname``.
Colon-izing either side would split the invariant, which is why ruling #1
rejected it.

EP table:

| API | Partition | Expected | Test ID |
| --- | --- | --- | --- |
| ``derive_flow_id`` | ``@flow`` without an explicit id | ``module.qualname`` == ``FlowSpec.id`` | TC-J1-FID-EP-001 |
| ``derive_flow_id`` | ``@flow(id=...)`` | the explicit id, not ``module.qualname`` | TC-J1-FID-EP-002 |
| ``derive_flow_id`` | undecorated plain function | ``module.qualname`` | TC-J1-FID-EP-003 |
| ``callback_flow_id`` | v1 dataset callback | ``module.qualname`` of the callback | TC-J1-FID-EP-004 |
| ``push_flow`` | inside the context | ``current_flow_id()`` is the pushed id | TC-J1-PUSH-EP-001 |
| ``push_flow`` | nested contexts | innermost id wins, outer restored | TC-J1-PUSH-EP-002 |

BV table:

| API | Boundary | Expected | Test ID |
| --- | --- | --- | --- |
| ``callback_flow_id`` | ``None`` callback | dotted sentinel, never colon-ized | TC-J1-FID-BV-001 |
| ``derive_flow_id`` | callable without ``__qualname__`` | falls back, never raises | TC-J1-FID-BV-002 |
| ``derive_flow_id`` | callable without ``__module__`` | bare qualname, no leading dot | TC-J1-FID-BV-003 |
| ``derive_flow_id`` | ``__flow_spec__`` present but id empty | positional fallback | TC-J1-FID-BV-004 |
| ``_flow_id`` | explicit-id ``@flow`` | reports the explicit id (was: qualname) | TC-J1-FID-EV-001 |
| ``_target_flow_id`` | callback target with ``None`` function | the dotted sentinel | TC-J1-FID-EV-002 |
| ``_target_flow_id`` | template wrapper without ``__flow_spec__`` | concrete ``module.qualname`` | TC-J1-FID-EV-003 |
| ``push_flow`` | body raises | stack restored, id not leaked | TC-J1-PUSH-BV-001 |
| ``@flow`` wrapper | shares the helper | flow id visible to a nested ``push_flow`` | TC-J1-PUSH-EV-001 |
"""

from __future__ import annotations

from functools import wraps
from typing import Any

import pytest

from rdetoolkit.api.request import FlowTarget, LegacyCallbackTarget
from rdetoolkit.compat.v1.callback import NO_CALLBACK_FLOW_ID, callback_flow_id
from rdetoolkit.core.flow import current_flow_id, derive_flow_id, flow, push_flow
from rdetoolkit.runner.lifecycle import _flow_id, _target_flow_id

_MODULE = "tests.v2.core.test_flow_id_derivation_j1"


@flow
def _fid_default_flow() -> None:
    """Flow without an explicit id."""
    return None


@flow(id="tests.j1.explicit-flow-id")
def _fid_explicit_flow() -> None:
    """Flow whose id was chosen by the author."""
    return None


def _fid_plain_function() -> None:
    """Undecorated callable, as a v1 callback is."""
    return None


def _fid_legacy_callback(srcpaths: object, resource_paths: object) -> None:
    """v1 two-argument dataset callback."""
    del srcpaths, resource_paths


def test_default_flow_id_equals_the_flow_spec_id__tc_j1_fid_ep_001() -> None:
    """TC-J1-FID-EP-001: the default derivation is exactly ``FlowSpec.id``."""
    # Given: a @flow registered without an explicit id
    spec_id = _fid_default_flow.__flow_spec__.id  # type: ignore[attr-defined]

    # When: deriving the reporting flow_id from the decorated callable
    actual = derive_flow_id(_fid_default_flow)

    # Then: the two are the same dotted reference, so parent_flow can equal flow_id
    assert actual == spec_id
    assert actual == f"{_MODULE}._fid_default_flow"
    assert ":" not in actual


def test_explicit_flow_id_wins_over_qualname__tc_j1_fid_ep_002() -> None:
    """TC-J1-FID-EP-002: ``@flow(id=...)`` is the stable reference, not the qualname."""
    # Given: a @flow whose author pinned its id
    # When: deriving the reporting flow_id
    actual = derive_flow_id(_fid_explicit_flow)

    # Then: the explicit id is reported and the qualname form is not
    assert actual == "tests.j1.explicit-flow-id"
    assert actual != f"{_MODULE}._fid_explicit_flow"


def test_plain_function_uses_module_qualname__tc_j1_fid_ep_003() -> None:
    """TC-J1-FID-EP-003: a callable with no spec keeps the dotted qualname form."""
    # Given / When: deriving from an undecorated function
    actual = derive_flow_id(_fid_plain_function)

    # Then: the dotted module.qualname reference is used
    assert actual == f"{_MODULE}._fid_plain_function"


def test_callback_flow_id_uses_the_same_derivation__tc_j1_fid_ep_004() -> None:
    """TC-J1-FID-EP-004: a v1 callback is identified by the shared derivation."""
    # Given / When: deriving the flow_id a v1 dataset callback is recorded under
    actual = callback_flow_id(_fid_legacy_callback)

    # Then: it is the same value ``derive_flow_id`` produces — one authority
    assert actual == derive_flow_id(_fid_legacy_callback)
    assert actual == f"{_MODULE}._fid_legacy_callback"


def test_absent_callback_reports_the_dotted_sentinel__tc_j1_fid_bv_001() -> None:
    """TC-J1-FID-BV-001: the callback-free sentinel is dotted like every other id."""
    # Given / When: a v1 run with no ``custom_dataset_function`` at all
    actual = callback_flow_id(None)

    # Then: the sentinel is reported in dotted form (the colon spelling is retired)
    assert actual == "rdetoolkit.compat.v1.callback.none"
    assert actual == NO_CALLBACK_FLOW_ID
    assert ":" not in actual


def test_callable_without_qualname_does_not_raise__tc_j1_fid_bv_002() -> None:
    """TC-J1-FID-BV-002: an exotic callable degrades instead of crashing."""

    # Given: a callable object that has neither __qualname__ nor __name__
    class _Callable:
        def __call__(self) -> None:
            return None

    instance = _Callable()
    assert not hasattr(instance, "__qualname__")

    # When: deriving its flow_id
    actual = derive_flow_id(instance)

    # Then: a non-empty reference is produced instead of an exception
    assert isinstance(actual, str)
    assert actual


def test_module_less_callable_has_no_leading_dot__tc_j1_fid_bv_003() -> None:
    """TC-J1-FID-BV-003: an empty module never produces a ``.qualname`` id."""

    # Given: a callable whose __module__ was cleared
    def _orphan() -> None:
        return None

    _orphan.__module__ = ""

    # When: deriving its flow_id
    actual = derive_flow_id(_orphan)

    # Then: the bare qualname is used, with no leading separator
    assert actual == _orphan.__qualname__
    assert not actual.startswith(".")


def test_blank_spec_id_falls_back_to_qualname__tc_j1_fid_bv_004() -> None:
    """TC-J1-FID-BV-004: a spec carrying no usable id must not blank the report."""

    # Given: a callable carrying a malformed flow spec
    def _spec_less() -> None:
        return None

    class _BlankSpec:
        id = ""

    _spec_less.__flow_spec__ = _BlankSpec()  # type: ignore[attr-defined]

    # When: deriving its flow_id
    actual = derive_flow_id(_spec_less)

    # Then: the qualname form is used rather than an empty identifier
    assert actual == f"{_MODULE}.{_spec_less.__qualname__}"


def test_lifecycle_flow_id_honours_the_explicit_id__tc_j1_fid_ev_001() -> None:
    """TC-J1-FID-EV-001 (UPDATE): the report no longer disagrees with ``parent_flow``.

    Before J1, ``_flow_id`` recomputed ``module.qualname`` and ignored
    ``__flow_spec__``, so a flow declared as ``@flow(id="...")`` produced
    ``parent_flow != flow_id`` on every one of its node records.
    """
    # Given: a @flow with an explicit id
    # When: the Runner derives the report's flow_id from it
    actual = _flow_id(_fid_explicit_flow)

    # Then: it matches what the flow stack pushes, i.e. FlowSpec.id
    assert actual == _fid_explicit_flow.__flow_spec__.id  # type: ignore[attr-defined]
    assert _target_flow_id(FlowTarget(function=_fid_explicit_flow)) == "tests.j1.explicit-flow-id"


def test_callback_free_target_reports_the_sentinel__tc_j1_fid_ev_002() -> None:
    """TC-J1-FID-EV-002: the target-level sentinel is the callback adapter's."""
    # Given / When: the v1 callback-free target
    actual = _target_flow_id(LegacyCallbackTarget(function=None))

    # Then: the one sentinel constant is reported, in dotted form. The retired
    # colon spelling is asserted away structurally rather than by quoting it, so
    # the session's "no colon-ized flow id anywhere" grep stays clean.
    assert actual == NO_CALLBACK_FLOW_ID
    assert ":" not in actual


def test_template_wrapper_keeps_the_concrete_identity__tc_j1_fid_ev_003() -> None:
    """TC-J1-FID-EV-003: ``flow_from_template``-style wrappers are unaffected.

    ``templates/base.py`` builds a wrapper whose ``__qualname__`` is the
    *concrete* class, and ``tests/v2/cli/test_cli_run.py`` pins that identity.
    Spec-first derivation must not hijack it.
    """

    # Given: a wrapper shaped like flow_from_template's (no __flow_spec__)
    def _skeleton(paths: object) -> None:
        del paths

    @wraps(_skeleton)
    def _wrapper(*args: Any, **kwargs: Any) -> None:
        return _skeleton(*args, **kwargs)

    _wrapper.__qualname__ = "ConcreteTemplate"
    assert not hasattr(_wrapper, "__flow_spec__")

    # When: deriving the report's flow_id
    actual = derive_flow_id(_wrapper)

    # Then: the concrete identity survives
    assert actual.endswith("ConcreteTemplate")


def test_push_flow_exposes_the_current_flow_id__tc_j1_push_ep_001() -> None:
    """TC-J1-PUSH-EP-001: the helper is what makes a flow id observable."""
    # Given: no active flow
    assert current_flow_id() is None

    # When: pushing one id
    with push_flow("tests.j1.pushed"):
        inside = current_flow_id()

    # Then: the id was visible inside and removed afterwards
    assert inside == "tests.j1.pushed"
    assert current_flow_id() is None


def test_nested_push_restores_the_outer_flow__tc_j1_push_ep_002() -> None:
    """TC-J1-PUSH-EP-002: the stack is a stack, not a single slot."""
    # Given / When: two nested pushes
    with push_flow("outer"):
        outer_before = current_flow_id()
        with push_flow("inner"):
            inner = current_flow_id()
        outer_after = current_flow_id()

    # Then: the innermost id wins and the outer one is restored
    assert (outer_before, inner, outer_after) == ("outer", "inner", "outer")
    assert current_flow_id() is None


def test_push_flow_restores_on_exception__tc_j1_push_bv_001() -> None:
    """TC-J1-PUSH-BV-001: a failing body must not leak its flow id."""
    # Given: a body that raises inside the context
    message = "flow body exploded"

    # When / Then: the exception propagates unchanged
    with pytest.raises(RuntimeError, match=message), push_flow("tests.j1.leaky"):
        raise RuntimeError(message)

    # And: the stack was restored, so a later node cannot inherit a dead flow
    assert current_flow_id() is None


def test_flow_decorator_uses_the_shared_helper__tc_j1_push_ev_001() -> None:
    """TC-J1-PUSH-EV-001: ``@flow`` and the callback adapter share one stack.

    Duplicating the ``_flow_stack_var`` push inside the callback adapter is
    forbidden by ruling #2; this seat proves the decorator observes the helper's
    stack and vice versa.
    """
    # Given: a flow that records what the stack looks like while it runs
    observed: list[str | None] = []

    @flow
    def _observing_flow() -> None:
        observed.append(current_flow_id())

    # When: calling it from inside an outer push
    with push_flow("tests.j1.outer-adapter"):
        _observing_flow()
        after_flow = current_flow_id()

    # Then: the flow's own id was on top, and the adapter's id came back
    assert observed == [_observing_flow.__flow_spec__.id]  # type: ignore[attr-defined]
    assert after_flow == "tests.j1.outer-adapter"
