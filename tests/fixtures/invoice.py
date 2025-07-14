import json
import os
import pathlib
import shutil
from collections.abc import Generator

import pytest


@pytest.fixture()
def invoice_json_with_sample_info() -> Generator[str, None, None]:
    """試料情報ありのinvoice.json"""
    invoice_dir = pathlib.Path("data", "invoice")
    invoice_json_path = pathlib.Path(str(invoice_dir), "invoice.json")
    data = {
        "datasetId": "0c233ef274f28e611de4074638b4dc43e737ab993132343532343430",
        "basic": {
            "dateSubmitted": "2023-03-14",
            "dataOwnerId": "0c233ef274f28e611de4074638b4dc43e737ab993132343532343430",
            "dataName": "test1",
            "experimentId": "test_230606_1",
            "description": "desc1",
        },
        "custom": {"key1": "test1", "key2": "test2"},
        "sample": {
            "sampleId": "cbf194ea-813f-4e05-b288",
            "names": ["sample1"],
            "composition": "sample1",
            "referenceUrl": "test_ref",
            "description": "desc3",
            "generalAttributes": [
                {"termId": "3adf9874-7bcb-e5f8-99cb-3d6fd9d7b55e", "value": "testname"},
                {"termId": "e2d20d02-2e38-2cd3-b1b3-66fdb8a11057", "value": "7439-89-6"},
                {"termId": "efcf34e7-4308-c195-6691-6f4d28ffc9bb", "value": "sample1"},
                {"termId": "1e70d11d-cbdd-bfd1-9301-9612c29b4060", "value": "magnet"},
                {"termId": "5e166ac4-bfcd-457a-84bc-8626abe9188f", "value": "magnet"},
                {"termId": "0d0417a3-3c3b-496a-b0fb-5a26f8a74166", "value": "magnet"},
                {"termId": "efc6a0d5-313e-1871-190c-baaff7d1bf6c", "value": ""},
            ],
            "ownerId": "0c233ef274f28e611de4074638b4dc43e737ab993132343532343430",
        },
    }

    # setup
    invoice_dir.mkdir(parents=True, exist_ok=True)
    with open(invoice_json_path, mode="w", encoding="utf-8") as f:
        json.dump(data, f)

    yield str(invoice_json_path)

    # teardown
    if os.path.exists("data"):
        shutil.rmtree("data")


@pytest.fixture()
def ivnoice_schema_json_with_full_sample_info() -> Generator[str, None, None]:
    """試料情報ありのinvoice.json"""
    invoice_dir = pathlib.Path("data", "tasksupport")
    invoice_json_path = pathlib.Path(str(invoice_dir), "invoice.schema.json")
    data = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://rde.nims.go.jp/rde/dataset-templates/dataset_template_custom_sample/invoice.schema.json",
        "description": "RDEデータセットテンプレートサンプル固有情報invoice",
        "type": "object",
        "required": [
            "custom",
            "sample",
        ],
        "properties": {
            "custom": {
                "type": "object",
                "label": {
                    "ja": "固有情報",
                    "en": "Custom Information",
                },
                "required": [
                    "sample1",
                    "sample2",
                ],
                "properties": {
                    "sample1": {
                        "label": {
                            "ja": "サンプル1",
                            "en": "sample1",
                        },
                        "type": "string",
                        "format": "date",
                        "options": {
                            "unit": "A",
                        },
                    },
                    "sample2": {
                        "label": {
                            "ja": "サンプル2",
                            "en": "sample2",
                        },
                        "type": "number",
                        "options": {
                            "unit": "b",
                        },
                    },
                    "sample3": {
                        "label": {
                            "ja": "サンプル3",
                            "en": "sample3",
                        },
                        "type": "integer",
                        "options": {
                            "unit": "c",
                            "placeholder": {
                                "ja": "Please Enter text",
                                "en": "Please Enter text",
                            },
                        },
                    },
                },
            },
            "sample": {
                "type": "object",
                "label": {
                    "ja": "試料情報",
                    "en": "Sample Information",
                },
                "properties": {
                    "generalAttributes": {
                        "type": "array",
                        "items": [
                            {
                                "type": "object",
                                "required": [
                                    "termId",
                                ],
                                "properties": {
                                    "termId": {
                                        "const": "3adf9874-7bcb-e5f8-99cb-3d6fd9d7b55e",
                                    },
                                },
                            },
                            {
                                "type": "object",
                                "required": [
                                    "termId",
                                ],
                                "properties": {
                                    "termId": {
                                        "const": "e2d20d02-2e38-2cd3-b1b3-66fdb8a11057",
                                    },
                                },
                            },
                            {
                                "type": "object",
                                "required": [
                                    "termId",
                                ],
                                "properties": {
                                    "termId": {
                                        "const": "efcf34e7-4308-c195-6691-6f4d28ffc9bb",
                                    },
                                },
                            },
                            {
                                "type": "object",
                                "required": [
                                    "termId",
                                ],
                                "properties": {
                                    "termId": {
                                        "const": "1e70d11d-cbdd-bfd1-9301-9612c29b4060",
                                    },
                                },
                            },
                            {
                                "type": "object",
                                "required": [
                                    "termId",
                                ],
                                "properties": {
                                    "termId": {
                                        "const": "5e166ac4-bfcd-457a-84bc-8626abe9188f",
                                    },
                                },
                            },
                            {
                                "type": "object",
                                "required": [
                                    "termId",
                                ],
                                "properties": {
                                    "termId": {
                                        "const": "0d0417a3-3c3b-496a-b0fb-5a26f8a74166",
                                    },
                                },
                            },
                        ],
                    },
                    "specificAttributes": {
                        "type": "array",
                        "items": [
                            {
                                "type": "object",
                                "required": [
                                    "classId",
                                    "termId",
                                ],
                                "properties": {
                                    "classId": {
                                        "const": "01cb3c01-37a4-5a43-d8ca-f523ca99a75b",
                                    },
                                    "termId": {
                                        "const": "3250c45d-0ed6-1438-43b5-eb679918604a",
                                    },
                                },
                            },
                            {
                                "type": "object",
                                "required": [
                                    "classId",
                                    "termId",
                                ],
                                "properties": {
                                    "classId": {
                                        "const": "01cb3c01-37a4-5a43-d8ca-f523ca99a75b",
                                    },
                                    "termId": {
                                        "const": "70c2c751-5404-19b7-4a5e-981e6cebbb15",
                                    },
                                },
                            },
                            {
                                "type": "object",
                                "required": [
                                    "classId",
                                    "termId",
                                ],
                                "properties": {
                                    "classId": {
                                        "const": "01cb3c01-37a4-5a43-d8ca-f523ca99a75b",
                                    },
                                    "termId": {
                                        "const": "e2d20d02-2e38-2cd3-b1b3-66fdb8a11057",
                                    },
                                },
                            },
                            {
                                "type": "object",
                                "required": [
                                    "classId",
                                    "termId",
                                ],
                                "properties": {
                                    "classId": {
                                        "const": "342ba516-4d02-171c-9bc4-70a3134b47a8",
                                    },
                                    "termId": {
                                        "const": "518e26a0-4262-86f5-3598-80e18e6ff2af",
                                    },
                                },
                            },
                        ],
                    },
                },
            },
        },
    }
    # setup
    invoice_dir.mkdir(parents=True, exist_ok=True)
    with open(invoice_json_path, mode="w", encoding="utf-8") as f:
        json.dump(data, f)

    yield str(invoice_json_path)

    # teardown
    if os.path.exists("data"):
        shutil.rmtree("data")


@pytest.fixture()
def ivnoice_json_none_sample_info() -> Generator[str, None, None]:
    """試料情報なしのinvoice.json"""
    invoice_dir = pathlib.Path("data", "invoice")
    invoice_json_path = pathlib.Path(str(invoice_dir), "invoice.json")
    data = {
        "datasetId": "1s1199df4-0d1v-41b0-1dea-23bf4dh09g12",
        "basic": {
            "dateSubmitted": "2023-03-14",
            "dataOwnerId": "0c233ef274f28e611de4074638b4dc43e737ab993132343532343430",
            "dataName": "test1",
            "experimentId": "test_230606_1",
            "description": "desc1",
        },
        "custom": {"key1": "test1", "key2": "test2"},
    }

    # setup
    invoice_dir.mkdir(parents=True, exist_ok=True)
    with open(invoice_json_path, mode="w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    yield str(invoice_json_path)

    # teardown
    if os.path.exists("data"):
        shutil.rmtree("data")


@pytest.fixture()
def ivnoice_json_magic_filename_variable() -> Generator[str, None, None]:
    """${filename}をdataNameに追加したinvoice.json"""
    invoice_dir = pathlib.Path("data", "invoice")
    invoice_json_path = pathlib.Path(str(invoice_dir), "invoice.json")
    data = {
        "datasetId": "1s1199df4-0d1v-41b0-1dea-23bf4dh09g12",
        "basic": {
            "dateSubmitted": "2023-03-14",
            "dataOwnerId": "0c233ef274f28e611de4074638b4dc43e737ab993132343532343430",
            "dataName": "${filename}",
            "experimentId": "test_230606_1",
            "description": "desc1",
        },
        "custom": {
            "sample1": "2023-01-01",
            "sample2": 1.0,
            "sample3": 1,
            "sample4": "20:20:39",
            "sample5": "https://sample.co",
            "sample6": "1d8008a5-b8f0-410b-a230-d058129822df",
            "sample7": "#h1",
            "sample8": "itemA",
            "sample9": "II",
            "sample10": "S10",
        },
        "sample": {
            "sampleId": "",
            "names": ["test"],
            "composition": None,
            "referenceUrl": None,
            "description": None,
            "generalAttributes": [
                {
                    "termId": "3adf9874-7bcb-e5f8-99cb-3d6fd9d7b55e",
                    "value": None,
                },
                {
                    "termId": "e2d20d02-2e38-2cd3-b1b3-66fdb8a11057",
                    "value": None,
                },
                {
                    "termId": "efcf34e7-4308-c195-6691-6f4d28ffc9bb",
                    "value": None,
                },
                {
                    "termId": "1e70d11d-cbdd-bfd1-9301-9612c29b4060",
                    "value": None,
                },
                {
                    "termId": "5e166ac4-bfcd-457a-84bc-8626abe9188f",
                    "value": None,
                },
                {
                    "termId": "0d0417a3-3c3b-496a-b0fb-5a26f8a74166",
                    "value": None,
                },
                {
                    "termId": "efc6a0d5-313e-1871-190c-baaff7d1bf6c",
                    "value": None,
                },
            ],
            "specificAttributes": [
                {
                    "classId": "01cb3c01-37a4-5a43-d8ca-f523ca99a75b",
                    "termId": "3250c45d-0ed6-1438-43b5-eb679918604a",
                    "value": None,
                },
                {
                    "classId": "01cb3c01-37a4-5a43-d8ca-f523ca99a75b",
                    "termId": "70c2c751-5404-19b7-4a5e-981e6cebbb15",
                    "value": None,
                },
                {
                    "classId": "01cb3c01-37a4-5a43-d8ca-f523ca99a75b",
                    "termId": "e2d20d02-2e38-2cd3-b1b3-66fdb8a11057",
                    "value": None,
                },
                {
                    "classId": "01cb3c01-37a4-5a43-d8ca-f523ca99a75b",
                    "termId": "518e26a0-4262-86f5-3598-80e18e6ff2af",
                    "value": None,
                },
            ],
            "ownerId": "de17c7b3f0ff5126831c2d519f481055ba466ddb6238666132316439",
        },
    }

    # setup
    invoice_dir.mkdir(parents=True, exist_ok=True)
    with open(invoice_json_path, mode="w", encoding="utf-8") as f:
        json.dump(data, f)

    yield str(invoice_json_path)

    # teardown
    if os.path.exists("data"):
        shutil.rmtree("data")


@pytest.fixture
def empty_attributes_schema(tmp_path):
    """スキーマファイル（generalAttributes、specificAttributesが空）を作成."""
    schema_content = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "test_empty_attributes",
        "type": "object",
        "required": ["custom", "sample"],
        "properties": {
            "custom": {
                "type": "object",
                "label": {"ja": "固有情報", "en": "Custom Information"},
                "required": [],
                "properties": {
                    "test_field": {
                        "label": {"ja": "テストフィールド", "en": "Test Field"},
                        "type": "string"
                    }
                }
            },
            "sample": {
                "type": "object",
                "label": {"ja": "試料情報", "en": "Sample Information"},
                "properties": {}
            }
        }
    }
    schema_file = tmp_path / "empty_attributes.schema.json"
    with open(schema_file, "w", encoding="utf-8") as f:
        json.dump(schema_content, f, ensure_ascii=False, indent=2)

    return schema_file


@pytest.fixture
def empty_general_attributes_schema(tmp_path):
    """スキーマファイル（generalAttributesのみ空）を作成."""
    schema_content = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "test_empty_general_attributes",
        "type": "object",
        "required": [
            "custom",
            "sample"
        ],
        "properties": {
            "custom": {
                "type": "object",
                "label": {"ja": "固有情報", "en": "Custom Information"},
                "required": [],
                "properties": {
                    "test_field": {
                        "label": {"ja": "テストフィールド", "en": "Test Field"},
                        "type": "string"
                    }
                }
            },
            "sample": {
                "type": "object",
                "label": {"ja": "試料情報", "en": "Sample Information"},
                "properties": {
                    "specificAttributes": {
                        "type": "array",
                        "items": [
                            {
                                "type": "object",
                                "required": ["classId", "termId"],
                                "properties": {
                                    "classId": {"const": "01cb3c01-37a4-5a43-d8ca-f523ca99a75b"},
                                    "termId": {"const": "3250c45d-0ed6-1438-43b5-eb679918604a"}
                                }
                            }
                        ]
                    }
                }
            }
        }
    }

    schema_file = tmp_path / "empty_general_attributes.schema.json"
    with open(schema_file, "w", encoding="utf-8") as f:
        json.dump(schema_content, f, ensure_ascii=False, indent=2)

    return schema_file
