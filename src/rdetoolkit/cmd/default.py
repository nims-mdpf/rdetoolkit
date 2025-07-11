CUSTOM_FIELDS = {
    "type": "object",
    "label": {"ja": "固有情報", "en": "Custom Information"},
    "required": [
        "toy_data1",
    ],
    "properties": {"toy_data1": {"label": {"ja": "トイデータ１", "en": "toy_data1"}, "type": "string"}, "sample2": {"label": {"ja": "トイデータ２", "en": "toy_data2"}, "type": "number"}},
}

SAMPLE_FIELDS = {"type": "object", "label": {"ja": "試料情報", "en": "Sample Information"}, "properties": {}}

PROPERTIES = {"custom": CUSTOM_FIELDS, "sample": SAMPLE_FIELDS}


INVOICE_JSON = {
    "datasetId": "3f976089-7b0b-4c66-a035-f48773b018e6",
    "basic": {"dateSubmitted": "", "dataOwnerId": "7e4792d1a8440bcfa08925d35e9d92b234a963449f03df441234569e", "dataName": "toy dataset", "instrumentId": None, "experimentId": None, "description": None},
    "custom": {"toy_data1": "2023-01-01", "toy_data2": 1.0},
    "sample": {
        "sampleId": "",
        "names": ["<Please enter a sample name>"],
        "composition": None,
        "referenceUrl": None,
        "description": None,
        "generalAttributes": [],
        "specificAttributes": [],
        "ownerId": "1234567e4792d1a8440bcfa08925d35e9d92b234a963449f03df449e",
    },
}
