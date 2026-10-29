"""Real, dotted-importable fixture package for tests/v2/cli/test_cli_run.py.

``rdetoolkit run --flow`` resolves its target via ``importlib.import_module``
on a dotted module path (Conflict #11 in session_e1.md: no file-path
support, unlike the legacy ``target::attr`` syntax). Fixture flows therefore
cannot be defined inline inside a test function -- they must live in an
actual importable package. This package plays that role for Session E1
only; it is not general-purpose test infrastructure.
"""
