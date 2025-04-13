import json
import os
import pathlib
import shutil
from collections.abc import Generator

import pytest


@pytest.fixture()
def metadata_def_json_with_feature() -> Generator[str, None, None]:
    """特徴量書き込み用のmetadata-def.json"""
    tasksupport_dir = pathlib.Path("data", "tasksupport")
    invoice_json_path = pathlib.Path(str(tasksupport_dir), "metadata-def.json")
    data = {
        "test_feature_meta1": {"name": {"ja": "特徴量1", "en": "feature1"}, "schema": {"type": "string"}, "_feature": 1},
        "test_feature_meta2": {"name": {"ja": "特徴量2", "en": "feature2"}, "schema": {"type": "string"}, "unit": "V", "_feature": 1},
        "test_feature_meta3": {"name": {"ja": "特徴量3", "en": "feature3"}, "schema": {"type": "string"}, "unit": "V", "_feature": True, "variable": 1},
    }

    # setup
    tasksupport_dir.mkdir(parents=True, exist_ok=True)
    with open(invoice_json_path, mode="w", encoding="utf-8") as f:
        json.dump(data, f)

    yield str(invoice_json_path)

    # teardown
    if os.path.exists("data"):
        shutil.rmtree("data")


@pytest.fixture()
def metadata_def_json_none_feature() -> Generator[str, None, None]:
    """特徴量書き込み用のmetadata-def.json"""
    tasksupport_dir = pathlib.Path("data", "tasksupport")
    invoice_json_path = pathlib.Path(str(tasksupport_dir), "metadata-def.json")
    data = {
        "test_feature_meta1": {
            "name": {"ja": "特徴量1", "en": "feature1"},
            "schema": {"type": "string"},
        },
        "test_feature_meta2": {
            "name": {"ja": "特徴量2", "en": "feature2"},
            "schema": {"type": "string"},
            "unit": "V",
        },
        "test_feature_meta3": {
            "name": {"ja": "特徴量3", "en": "feature3"},
            "schema": {"type": "string"},
            "unit": "V",
        },
    }

    # setup
    tasksupport_dir.mkdir(parents=True, exist_ok=True)
    with open(invoice_json_path, mode="w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    yield str(invoice_json_path)

    # teardown
    if os.path.exists("data"):
        shutil.rmtree("data")


@pytest.fixture()
def metadata_json() -> Generator[str, None, None]:
    """test用のmetadata.json"""
    tasksupport_dir = pathlib.Path("data", "meta")
    invoice_json_path = pathlib.Path(str(tasksupport_dir), "metadata.json")
    data = {
        "constant": {"test_feature_meta1": {"value": "test-value1"}, "test_feature_meta2": {"value": "test-value2", "unit": "V"}},
        "variable": [{"test_feature_meta3": {"value": "test-value3", "unit": "V"}}],
    }

    # setup
    tasksupport_dir.mkdir(parents=True, exist_ok=True)
    with open(invoice_json_path, mode="w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    yield str(invoice_json_path)

    # teardown
    if os.path.exists("data"):
        shutil.rmtree("data")


@pytest.fixture()
def metadata_json_non_variable() -> Generator[str, None, None]:
    """test用のmetadata.json
    variableの内容を全て削除したもの
    """
    tasksupport_dir = pathlib.Path("data", "meta")
    invoice_json_path = pathlib.Path(str(tasksupport_dir), "metadata.json")
    data = {
        "constant": {
            "test_feature_meta1": {"value": "test-value1"},
            "test_feature_meta2": {"value": "test-value2", "unit": "V"},
            "test_feature_meta3": {"value": "test-value3", "unit": "V"},
        },
        "variable": [],
    }

    # setup
    tasksupport_dir.mkdir(parents=True, exist_ok=True)
    with open(invoice_json_path, mode="w", encoding="utf-8") as f:
        json.dump(data, f)

    yield str(invoice_json_path)

    # teardown
    if os.path.exists("data"):
        shutil.rmtree("data")


@pytest.fixture()
def metadata_json_non_constat() -> Generator[str, None, None]:
    """test用のmetadata.json
    variableの内容を全て削除したもの
    """
    tasksupport_dir = pathlib.Path("data", "meta")
    invoice_json_path = pathlib.Path(str(tasksupport_dir), "metadata.json")
    data = {
        "constant": {},
        "variable": [
            {
                "test_feature_meta1": {"value": "test-value1"},
                "test_feature_meta2": {"value": "test-value2", "unit": "V"},
                "test_feature_meta3": {"value": "test-value3", "unit": "V"},
            },
        ],
    }

    # setup
    tasksupport_dir.mkdir(parents=True, exist_ok=True)
    with open(invoice_json_path, mode="w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    yield str(invoice_json_path)

    # teardown
    if os.path.exists("data"):
        shutil.rmtree("data")


@pytest.fixture()
def metadata_json_missing_value() -> Generator[str, None, None]:
    """test用のmetadata.json
    variable test_feature_meta2を欠損させたもの
    """
    tasksupport_dir = pathlib.Path("data", "meta")
    invoice_json_path = pathlib.Path(str(tasksupport_dir), "metadata.json")
    data = {"constant": {"test_feature_meta1": {"value": "test-value1"}}, "variable": [{"test_feature_meta3": {"value": "test-value3", "unit": "V"}}]}

    # setup
    tasksupport_dir.mkdir(parents=True, exist_ok=True)
    with open(invoice_json_path, mode="w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    yield str(invoice_json_path)

    # teardown
    if os.path.exists("data"):
        shutil.rmtree("data")
