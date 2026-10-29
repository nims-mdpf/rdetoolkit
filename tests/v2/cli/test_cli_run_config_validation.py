"""Additional boundary coverage for ``run --config``.

EP table:
    API: ``run --config``
    Partition: YAML document with a non-mapping root
    Rationale: overrides must be keyword mappings
    Expected: usage error, exit code 3
    Test ID: TC-CLI-RUN-EP-013
"""

from pathlib import Path

from typer.testing import CliRunner

from rdetoolkit.cli.app import app


def test_config_non_mapping_exits_3__tc_cli_run_ep_013(tmp_path: Path) -> None:
    """TC-CLI-RUN-EP-013: Reject a YAML sequence as config overrides."""
    # Given: a syntactically valid YAML document whose root is not a mapping
    config_path = tmp_path / "override.yaml"
    config_path.write_text("- not\n- a\n- mapping\n", encoding="utf-8")

    # When: passing the document as v2 flow configuration
    result = CliRunner().invoke(
        app,
        [
            "run",
            "--flow",
            "tests.v2.cli.fixtures.run_flows:success_pipeline",
            "--config",
            str(config_path),
        ],
    )

    # Then: the CLI rejects it before attempting execution
    assert result.exit_code == 3
    assert "top-level yaml mapping" in result.output.lower()
