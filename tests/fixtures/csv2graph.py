"""Fixtures and utilities for csv2graph regression tests."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import matplotlib
import pandas as pd
import pytest
import yaml

from rdetoolkit.graph.textutils import sanitize_filename

matplotlib.use("Agg")  # Ensure headless backend for image comparison tests

try:  # Python 3.11+
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parents[2]
TEST_GRAPH_ROOT = REPO_ROOT / "local" / "test_graph"
FIXTURE_DIR = TEST_GRAPH_ROOT / "fixtures"
BASELINE_DIR = TEST_GRAPH_ROOT / "baseline"
CONFIG_EXTENSIONS = (".yaml", ".yml", ".json", ".toml")


@dataclass(frozen=True)
class GraphOutputCheck:
    """Expectation for a single rendered artifact."""

    artifact: str
    baseline: Path


@dataclass(frozen=True)
class GraphCase:
    """Definition of a regression test case for csv2graph."""

    name: str
    csv_path: Path
    plot_kwargs: dict[str, Any] = field(default_factory=dict)
    outputs: list[GraphOutputCheck] = field(default_factory=list)

    @property
    def default_output(self) -> GraphOutputCheck:
        return self.outputs[0]


def _load_config(case_name: str) -> dict[str, Any]:
    """Load an optional configuration file for a given case."""

    for suffix in CONFIG_EXTENSIONS:
        config_path = FIXTURE_DIR / f"{case_name}{suffix}"
        if not config_path.exists():
            continue

        text = config_path.read_text(encoding="utf-8")
        if config_path.suffix in {".yaml", ".yml"}:
            return yaml.safe_load(text) or {}
        if config_path.suffix == ".json":
            return json.loads(text)
        if config_path.suffix == ".toml":
            if tomllib is not None:
                return tomllib.loads(text)
            try:  # pragma: no cover - optional dependency path
                import toml

                return toml.loads(text)
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(
                    "TOML configuration present but tomllib/toml is unavailable"
                ) from exc
    return {}


def _collect_cases() -> list[GraphCase]:
    cases: list[GraphCase] = []
    if not FIXTURE_DIR.exists() or not BASELINE_DIR.exists():
        return cases

    for csv_file in sorted(FIXTURE_DIR.glob("*.csv")):
        case_name = csv_file.stem
        config = _load_config(case_name)
        if config and not isinstance(config, dict):
            raise TypeError(f"Invalid config structure for {case_name}: {type(config)}")

        plot_kwargs: dict[str, Any] = (config or {}).get("plot_kwargs", {}) or {}

        outputs: list[GraphOutputCheck] = []
        outputs_config = (config or {}).get("outputs")

        if outputs_config:
            if not isinstance(outputs_config, list):
                raise TypeError(f"'outputs' must be a list in {case_name}.yaml")
            for entry in outputs_config:
                if not isinstance(entry, dict):
                    raise TypeError(f"Each output entry must be a mapping in {case_name}")
                artifact_name = entry.get("artifact")
                if not artifact_name:
                    raise ValueError(f"Missing 'artifact' key for case {case_name}")
                baseline_name = entry.get("baseline", artifact_name)
                baseline_path = BASELINE_DIR / baseline_name
                if not baseline_path.exists():
                    raise FileNotFoundError(
                        f"Baseline image not found for case {case_name}: {baseline_path}"
                    )
                outputs.append(GraphOutputCheck(artifact=artifact_name, baseline=baseline_path))
        else:
            baseline_name = (config or {}).get("baseline", f"{case_name}.png")
            baseline_path = BASELINE_DIR / baseline_name
            if not baseline_path.exists():
                # Skip if default baseline missing
                continue
            artifact_name = plot_kwargs.get("name", case_name)
            sanitized_artifact = f"{sanitize_filename(str(artifact_name))}.png"
            outputs.append(GraphOutputCheck(artifact=sanitized_artifact, baseline=baseline_path))

        if not outputs:
            continue

        cases.append(
            GraphCase(
                name=case_name,
                csv_path=csv_file,
                plot_kwargs=plot_kwargs,
                outputs=outputs,
            )
        )
    return cases


GRAPH_CASES: list[GraphCase] = _collect_cases()


@pytest.fixture(scope="session")
def load_graph_case() -> Callable[[str], pd.DataFrame]:
    """Return a loader that reads a CSV case into a DataFrame."""

    def _load(case_name: str) -> pd.DataFrame:
        csv_path = FIXTURE_DIR / f"{case_name}.csv"
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV fixture not found: {csv_path}")
        return pd.read_csv(csv_path)

    return _load


def baseline_directory() -> Path:
    """Expose the baseline directory path for pytest-mpl decorators."""

    return BASELINE_DIR


__all__ = [
    "GraphCase",
    "GraphOutputCheck",
    "GRAPH_CASES",
    "baseline_directory",
    "load_graph_case",
]
