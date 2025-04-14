import json
import os
import pathlib
import shutil
from collections.abc import Generator

import pytest


@pytest.fixture()
def ivnoice_schema_json() -> Generator[str, None, None]:
    """ダミー用invoice.schema.json"""
    tasksupport_dir = pathlib.Path("data", "tasksupport")
    invoice_json_path = pathlib.Path(str(tasksupport_dir), "invoice.schema.json")
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
                            "ja": "サンプル１",
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
                            "ja": "サンプル２",
                            "en": "sample2",
                        },
                        "type": "number",
                        "options": {
                            "unit": "b",
                        },
                    },
                    "sample3": {
                        "label": {
                            "ja": "サンプル３",
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
                    "sample4": {
                        "label": {
                            "ja": "サンプル４",
                            "en": "sample4",
                        },
                        "type": "string",
                        "format": "time",
                    },
                    "sample5": {
                        "label": {
                            "ja": "サンプル５",
                            "en": "sample5",
                        },
                        "type": "string",
                        "format": "uri",
                    },
                    "sample6": {
                        "label": {
                            "ja": "サンプル６",
                            "en": "sample6",
                        },
                        "type": "string",
                        "format": "uuid",
                    },
                    "sample7": {
                        "label": {
                            "ja": "サンプル７",
                            "en": "sample7",
                        },
                        "type": "string",
                        "format": "markdown",
                    },
                    "sample8": {
                        "label": {
                            "ja": "サンプル８",
                            "en": "sample8",
                        },
                        "type": "string",
                        "description": "select item",
                        "examples": ["S8"],
                        "default": "S8",
                        "enum": [
                            "itemA",
                            "itemB",
                            "itemC",
                            "itemD",
                            "itemE",
                        ],
                    },
                    "sample9": {
                        "label": {
                            "ja": "サンプル９",
                            "en": "sample9",
                        },
                        "type": "string",
                    },
                    "sample10": {
                        "label": {
                            "ja": "サンプル１０",
                            "en": "sample10",
                        },
                        "type": "string",
                        "default": "S10",
                        "const": "S10",
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
                            {
                                "type": "object",
                                "required": [
                                    "termId",
                                ],
                                "properties": {
                                    "termId": {
                                        "const": "efc6a0d5-313e-1871-190c-baaff7d1bf6c",
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
                                        "const": "01cb3c01-37a4-5a43-d8ca-f523ca99a75b",
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
    tasksupport_dir.mkdir(parents=True, exist_ok=True)
    with open(invoice_json_path, mode="w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    yield str(invoice_json_path)

    # teardown
    if os.path.exists("data"):
        shutil.rmtree("data")


@pytest.fixture()
def ivnoice_schema_json_none_specificAttributes() -> Generator[str, None, None]:
    """ダミー用invoice.schema.json / sample.specificAttributesなし"""
    tasksupport_dir = pathlib.Path("data", "tasksupport")
    invoice_json_path = pathlib.Path(str(tasksupport_dir), "invoice.schema.json")
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
                    "key1",
                ],
                "properties": {
                    "key1": {
                        "label": {
                            "ja": "キー1",
                            "en": "key1",
                        },
                        "type": "string",
                    },
                    "key2": {
                        "label": {
                            "ja": "キー2",
                            "en": "key2",
                        },
                        "type": "string",
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
                            {
                                "type": "object",
                                "required": [
                                    "termId",
                                ],
                                "properties": {
                                    "termId": {
                                        "const": "efc6a0d5-313e-1871-190c-baaff7d1bf6c",
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
    tasksupport_dir.mkdir(parents=True, exist_ok=True)
    with open(invoice_json_path, mode="w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    yield str(invoice_json_path)

    # teardown
    if os.path.exists("data"):
        shutil.rmtree("data")


@pytest.fixture()
def ivnoice_schema_json_none_sample() -> Generator[str, None, None]:
    """ダミー用invoice.schema.json/試料なし"""
    tasksupport_dir = pathlib.Path("data", "tasksupport")
    invoice_json_path = pathlib.Path(str(tasksupport_dir), "invoice.schema.json")
    data = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://rde.nims.go.jp/rde/dataset-templates/dataset_template_custom_sample/invoice.schema.json",
        "description": "RDEデータセットテンプレートサンプル固有情報invoice",
        "type": "object",
        "required": [
            "custom",
        ],
        "properties": {
            "custom": {
                "type": "object",
                "label": {
                    "ja": "固有情報",
                    "en": "Custom Information",
                },
                "required": [
                    "key1",
                    "key2",
                ],
                "properties": {
                    "key1": {
                        "label": {
                            "ja": "キー1",
                            "en": "key1",
                        },
                        "type": "string",
                    },
                    "key2": {
                        "label": {
                            "ja": "キー2",
                            "en": "key2",
                        },
                        "type": "string",
                    },
                },
            },
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
def invalid_ivnoice_schema_json() -> Generator[str, None, None]:
    """ダミー用invoice.schema.json"""
    tasksupport_dir = pathlib.Path("data", "tasksupport")
    invoice_json_path = pathlib.Path(str(tasksupport_dir), "invoice.schema.json")
    # "requireds"が正しくは、"required"
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
                "requireds": [
                    "sample1",
                    "sample2",
                ],
                "properties": {
                    "sample1": {
                        "label": {
                            "ja": "サンプル１",
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
                            "ja": "サンプル２",
                            "en": "sample2",
                        },
                        "type": "number",
                        "options": {
                            "unit": "b",
                        },
                    },
                    "sample3": {
                        "label": {
                            "ja": "サンプル３",
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
                    "sample4": {
                        "label": {
                            "ja": "サンプル４",
                            "en": "sample4",
                        },
                        "type": "string",
                        "format": "time",
                    },
                    "sample5": {
                        "label": {
                            "ja": "サンプル５",
                            "en": "sample5",
                        },
                        "type": "string",
                        "format": "uri",
                    },
                    "sample6": {
                        "label": {
                            "ja": "サンプル６",
                            "en": "sample6",
                        },
                        "type": "string",
                        "format": "uuid",
                    },
                    "sample7": {
                        "label": {
                            "ja": "サンプル７",
                            "en": "sample7",
                        },
                        "type": "string",
                        "format": "markdown",
                    },
                    "sample8": {
                        "label": {
                            "ja": "サンプル８",
                            "en": "sample8",
                        },
                        "type": "string",
                        "description": "select item",
                        "examples": ["S8"],
                        "default": "S8",
                        "enum": [
                            "itemA",
                            "itemB",
                            "itemC",
                            "itemD",
                            "itemE",
                        ],
                    },
                    "sample9": {
                        "label": {
                            "ja": "サンプル９",
                            "en": "sample9",
                        },
                        "type": "string",
                    },
                    "sample10": {
                        "label": {
                            "ja": "サンプル１０",
                            "en": "sample10",
                        },
                        "type": "string",
                        "default": "S10",
                        "const": "S10",
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
                            {
                                "type": "object",
                                "required": [
                                    "termId",
                                ],
                                "properties": {
                                    "termId": {
                                        "const": "efc6a0d5-313e-1871-190c-baaff7d1bf6c",
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
                                        "const": "01cb3c01-37a4-5a43-d8ca-f523ca99a75b",
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
    tasksupport_dir.mkdir(parents=True, exist_ok=True)
    with open(invoice_json_path, mode="w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    yield str(invoice_json_path)

    # teardown
    if os.path.exists("data"):
        shutil.rmtree("data")
