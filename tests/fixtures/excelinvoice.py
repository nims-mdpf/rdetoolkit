import os
import pathlib
import shutil
from collections.abc import Generator

import pandas as pd
import pytest


# ExcelInvoice (file mode): Register multiple files + multiple tiles in zip
# Data for writing to sheet
EXCELINVOICE_ENTRYDATA_SHEET1_MULTI = [
    [
        "data_file_names",
        "",
        "",
        "basic",
        "basic",
        "basic",
        "basic",
        "sample",
        "sample",
        "sample",
        "sample",
        "sample",
        "sample",
        "sample.general",
        "sample.general",
        "sample.general",
        "sample.general",
        "custom",
        "custom",
    ],
    [
        "name",
        "dataset_title",
        "dataOwner",
        "dataOwnerId",
        "dataName",
        "experimentId",
        "referenceUrl",
        "description",
        "names",
        "sampleId",
        "ownerId",
        "composition",
        "description",
        "general-name",
        "chemical-composition",
        "sample-type",
        "cas-number",
        "key1",
        "key2",
    ],
    [
        "ファイル名\n(拡張子も含め入力)\n(入力例:○○.txt)",
        "データセット名\n(必須)",
        "データ所有者\n(NIMS User ID)",
        "NIMS user UUID\n(必須)",
        "データ名\n(必須)",
        "実験ID",
        "参考URL",
        "説明",
        "試料名\n(ローカルID)",
        "試料UUID\n(必須)",
        "試料管理者UUID",
        "化学式・組成式・分子式など",
        "試料の説明",
        "一般名称\n(General name)",
        "化学組成\n(Chemical composition)",
        "試料分類\n(Sample type)",
        "CAS番号\n(CAS Number)",
        "key1",
        "key2",
    ],
    [
        "test_child1.txt",
        "N_TEST_1",
        "test_user",
        "f30812c3-14bc-4274-809f-afcfaa2e4047",
        "test1",
        "test_230606_1",
        "desc1",
        "sample1",
        "cbf194ea-813f-4e05-b288",
        "1111",
        "sample1",
        "test_ref",
        "desc3",
        "testname",
        "Fe",
        "magnet",
        "7439-89-6",
        "AAA",
        "CCC",
    ],
    [
        "test_child2.txt",
        "N_TEST_2",
        "test_user",
        "f30812c3-14bc-4274-809f-afcfaa2e4047",
        "test2",
        "test_230606_2",
        "desc2",
        "sample2",
        "cbf194ea-813f-4e05-b288",
        "1111",
        "sample2",
        "test_ref",
        "desc4",
        "testname",
        "Fe",
        "magnet",
        "7439-89-6",
        "BBB",
        "DDD",
    ],
]

# ExcelInvoice (folder mode): Register multiple folders + multiple tiles in zip
# Data for writing to sheet
EXCELINVOICE_ENTRYDATA_SHEET1_MULTI_FOLDER = [
    [
        "data_folder_names",
        "",
        "",
        "basic",
        "basic",
        "basic",
        "basic",
        "sample",
        "sample",
        "sample",
        "sample",
        "sample",
        "sample",
        "sample.general",
        "sample.general",
        "sample.general",
        "sample.general",
        "custom",
        "custom",
    ],
    [
        "name",
        "dataset_title",
        "dataOwner",
        "dataOwnerId",
        "dataName",
        "experimentId",
        "referenceUrl",
        "description",
        "names",
        "sampleId",
        "ownerId",
        "composition",
        "description",
        "general-name",
        "chemical-composition",
        "sample-type",
        "cas-number",
        "key1",
        "key2",
    ],
    [
        "ファイル名\n(拡張子も含め入力)\n(入力例:○○.txt)",
        "データセット名\n(必須)",
        "データ所有者\n(NIMS User ID)",
        "NIMS user UUID\n(必須)",
        "データ名\n(必須)",
        "実験ID",
        "参考URL",
        "説明",
        "試料名\n(ローカルID)",
        "試料UUID\n(必須)",
        "試料管理者UUID",
        "化学式・組成式・分子式など",
        "試料の説明",
        "一般名称\n(General name)",
        "化学組成\n(Chemical composition)",
        "試料分類\n(Sample type)",
        "CAS番号\n(CAS Number)",
        "key1",
        "key2",
    ],
    [
        "data2",
        "N_TEST_1",
        "test_user",
        "f30812c3-14bc-4274-809f-afcfaa2e4047",
        "test1",
        "test_230606_1",
        "desc1",
        "sample1",
        "cbf194ea-813f-4e05-b288",
        "1111",
        "sample1",
        "test_ref",
        "desc3",
        "testname",
        "Fe",
        "magnet",
        "7439-89-6",
        "AAA",
        "CCC",
    ],
    [
        "data1",
        "N_TEST_2",
        "test_user",
        "f30812c3-14bc-4274-809f-afcfaa2e4047",
        "test2",
        "test_230606_2",
        "desc2",
        "sample2",
        "cbf194ea-813f-4e05-b288",
        "1111",
        "sample2",
        "test_ref",
        "desc4",
        "testname",
        "Fe",
        "magnet",
        "7439-89-6",
        "BBB",
        "DDD",
    ],
]

# ExcelInvoice (file mode): Register only 1 file + 1 tile in zip
# Data for writing to sheet
EXCELINVOICE_ENTRYDATA_SHEET1_SINGLE = [
    [
        "data_file_names",
        "",
        "",
        "basic",
        "basic",
        "basic",
        "basic",
        "basic",
        "basic",
        "sample",
        "sample",
        "sample",
        "sample",
        "sample",
        "sample",
        "sample.general",
        "sample.general",
        "sample.general",
        "sample.general",
        "sample.general",
        "sample.general",
        "sample.general",
        "custom",
        "custom",
    ],
    [
        "name",
        "dataset_title",
        "dataOwner",
        "dataOwnerId",
        "dataName",
        "instrumentId",
        "experimentId",
        "referenceUrl",
        "description",
        "names",
        "sampleId",
        "ownerId",
        "composition",
        "referenceUrl",
        "description",
        "general-name",
        "cas-number",
        "crystal-structure",
        "purchase-date",
        "lot-number-or-product-number-etc",
        "smiles-string",
        "supplier",
        "key1",
        "key2",
    ],
    [
        "ファイル名\n(拡張子も含め入力)\n(入力例:○○.txt)",
        "データセット名\n(必須)",
        "データ所有者\n(NIMS User ID)",
        "NIMS user UUID\n(必須)",
        "データ名\n(必須)",
        "装置ID",
        "実験ID",
        "参考URL",
        "説明",
        "試料名\n(ローカルID)",
        "試料UUID\n(必須)",
        "試料管理者UUID",
        "化学式・組成式・分子式など",
        "参考URL",
        "試料の説明",
        "general-name",
        "cas-number",
        "crystal-structure",
        "purchase-date",
        "lot-number-or-product-number-etc",
        "smiles-string",
        "supplier",
        "key1",
        "key2",
    ],
    [
        "test_child1.txt",
        "N_TEST_1",
        "test_user",
        "de17c7b3f0ff5126831c2d519f481055ba466ddb6238666132316439",
        "test1",
        "ee17c7b3-f0ff-5126-831c-2d519f481055",
        "test_230606_1",
        "https://sample.com",
        "desc1",
        "sample1",
        "de17c7b3-f0ff-5126-831c-2d519f481055",
        "de17c7b3f0ff5126831c2d519f481055ba466ddb6238666132316439",
        "sample1",
        "https://sample.com",
        "desc3",
        "testname",
        "Fe",
        "magnet",
        "7439-89-6",
        "7439-89-6",
        "7439-89-6",
        "7439-89-6",
        "AAA",
        "CCC",
    ],
]

# ExcelInvoice (file mode): Register only 1 file + multiple tiles in zip
EXCELINVOICE_ENTRYDATA_SHEET1_SINGLE_MULTILINE = [
    [
        "data_file_names",
        "",
        "",
        "basic",
        "basic",
        "basic",
        "basic",
        "sample",
        "sample",
        "sample",
        "sample",
        "sample",
        "sample",
        "sample.general",
        "sample.general",
        "sample.general",
        "sample.general",
        "custom",
        "custom",
    ],
    [
        "name",
        "dataset_title",
        "dataOwner",
        "dataOwnerId",
        "dataName",
        "experimentId",
        "referenceUrl",
        "description",
        "names",
        "sampleId",
        "ownerId",
        "composition",
        "description",
        "general-name",
        "chemical-composition",
        "sample-type",
        "cas-number",
        "key1",
        "key2",
    ],
    [
        "ファイル名\n(拡張子も含め入力)\n(入力例:○○.txt)",
        "データセット名\n(必須)",
        "データ所有者\n(NIMS User ID)",
        "NIMS user UUID\n(必須)",
        "データ名\n(必須)",
        "実験ID",
        "参考URL",
        "説明",
        "試料名\n(ローカルID)",
        "試料UUID\n(必須)",
        "試料管理者UUID",
        "化学式・組成式・分子式など",
        "試料の説明",
        "一般名称\n(General name)",
        "化学組成\n(Chemical composition)",
        "試料分類\n(Sample type)",
        "CAS番号\n(CAS Number)",
        "key1",
        "key2",
    ],
    [
        "test_child1.txt",
        "N_TEST_1",
        "test_user",
        "f30812c3-14bc-4274-809f-afcfaa2e4047",
        "test1",
        "test_230606_1",
        "desc1",
        "sample1",
        "cbf194ea-813f-4e05-b288",
        "1111",
        "sample1",
        "test_ref",
        "desc3",
        "testname",
        "Fe",
        "magnet",
        "7439-89-6",
        "AAA",
        "CCC",
    ],
    [
        "test_child1.txt",
        "N_TEST_1",
        "test_user",
        "f30812c3-14bc-4274-809f-afcfaa2e4047",
        "test1",
        "test_230606_1",
        "desc1",
        "sample1",
        "cbf194ea-813f-4e05-b288",
        "1111",
        "sample1",
        "test_ref",
        "desc3",
        "testname",
        "Fe",
        "magnet",
        "7439-89-6",
        "DDD",
        "FFF",
    ],
    [
        "test_child1.txt",
        "N_TEST_1",
        "test_user",
        "f30812c3-14bc-4274-809f-afcfaa2e4047",
        "test1",
        "test_230606_1",
        "desc1",
        "sample1",
        "cbf194ea-813f-4e05-b288",
        "1111",
        "sample1",
        "test_ref",
        "desc3",
        "testname",
        "Fe",
        "magnet",
        "7439-89-6",
        "DDD",
        "FFF",
    ],
]

# ExcelInvoice (file mode): Register only 1 file + 1 tile in zip, no sample information
EXCELINVOICE_ENTRYDATA_SHEET1_SINGLE_NON_SAMPLE = [
    ["data_file_names", "", "", "basic", "basic", "basic", "basic", "basic", "custom", "custom"],
    ["name", "dataset_title", "dataOwner", "dataOwnerId", "dataName", "experimentId", "referenceUrl", "description", "key1", "key2"],
    [
        "ファイル名\n(拡張子も含め入力)\n(入力例:○○.txt)",
        "データセット名\n(必須)",
        "データ所有者\n(NIMS User ID)",
        "NIMS user UUID\n(必須)",
        "データ名\n(必須)",
        "実験ID",
        "参考URL",
        "説明",
        "key1",
        "key2",
    ],
    [
        "test_child1.txt",
        "DATASETNAME_TEST_1",
        "test_user",
        "f30812c3-14bc-4274-809f-afcfaa2e4047",
        "TEST DATA NAME",
        "exp_id",
        "test_ref_url",
        "desc1",
        "AAA",
        "CCC",
    ],
]

# excelinvoice containing ${filename}
EXCELINVOICE_ENTRYDATA_SHEET1_SINGLE_MAGIC_VARIABLE = [
    [
        "data_file_names",
        "",
        "",
        "basic",
        "basic",
        "basic",
        "basic",
        "basic",
        "custom",
        "custom",
    ],
    [
        "name",
        "dataset_title",
        "dataOwner",
        "dataOwnerId",
        "dataName",
        "experimentId",
        "referenceUrl",
        "description",
        "key1",
        "key2",
    ],
    [
        "ファイル名\n(拡張子も含め入力)\n(入力例:○○.txt)",
        "データセット名\n(必須)",
        "データ所有者\n(NIMS User ID)",
        "NIMS user UUID\n(必須)",
        "データ名\n(必須)",
        "実験ID",
        "参考URL",
        "説明",
        "key1",
        "key2",
    ],
    [
        "test_child1.txt",
        "N_TEST_1",
        "test_user",
        "0c233ef274f28e611de4074638b4dc43e737ab993132343532343430",
        "${filename}",
        "test_230606_1",
        "https://test.com",
        "desc1",
        "AAA",
        "CCC",
    ],
]

# ExcelInvoice (file mode): Register only 1 file + 1 tile in zip, with merged header format
EXCELINVOICE_ENTRYDATA_SHEET1_SINGLE_MERGE = [
    [
        "data_file_names/name",
        "/dataset_title",
        "/dataOwner",
        "basic",
        "basic",
        "basic",
        "basic",
        "sample",
        "sample",
        "sample",
        "sample",
        "sample",
        "sample",
        "sample.general",
        "sample.general",
        "sample.general",
        "sample.general",
        "custom",
        "custom",
    ],
    [
        "name",
        "dataset_title",
        "dataOwner",
        "dataOwnerId",
        "dataName",
        "experimentId",
        "referenceUrl",
        "description",
        "names",
        "sampleId",
        "ownerId",
        "composition",
        "description",
        "general-name",
        "chemical-composition",
        "sample-type",
        "cas-number",
        "key1",
        "key2",
    ],
    [
        "ファイル名\n(拡張子も含め入力)\n(入力例:○○.txt)",
        "データセット名\n(必須)",
        "データ所有者\n(NIMS User ID)",
        "NIMS user UUID\n(必須)",
        "データ名\n(必須)",
        "実験ID",
        "参考URL",
        "説明",
        "試料名\n(ローカルID)",
        "試料UUID\n(必須)",
        "試料管理者UUID",
        "化学式・組成式・分子式など",
        "試料の説明",
        "一般名称\n(General name)",
        "化学組成\n(Chemical composition)",
        "試料分類\n(Sample type)",
        "CAS番号\n(CAS Number)",
        "key1",
        "key2",
    ],
    [
        "test_child1.txt",
        "N_TEST_1",
        "test_user",
        "f30812c3-14bc-4274-809f-afcfaa2e4047",
        "test1",
        "test_230606_1",
        "desc1",
        "sample1",
        "cbf194ea-813f-4e05-b288",
        "1111",
        "sample1",
        "test_ref",
        "desc3",
        "testname",
        "Fe",
        "magnet",
        "7439-89-6",
        "AAA",
        "CCC",
    ],
]

# ExcelInvoice (file mode): Register no file + 1 tile in zip
EXCELINVOICE_ENTRYDATA_SHEET1_NONFILE = [
    [
        "data_file_names",
        "",
        "",
        "basic",
        "basic",
        "basic",
        "basic",
        "sample",
        "sample",
        "sample",
        "sample",
        "sample",
        "sample",
        "sample.general",
        "sample.general",
        "sample.general",
        "sample.general",
        "custom",
        "custom",
    ],
    [
        "name",
        "dataset_title",
        "dataOwner",
        "dataOwnerId",
        "dataName",
        "experimentId",
        "referenceUrl",
        "description",
        "names",
        "sampleId",
        "ownerId",
        "composition",
        "description",
        "general-name",
        "chemical-composition",
        "sample-type",
        "cas-number",
        "key1",
        "key2",
    ],
    [
        "ファイル名\n(拡張子も含め入力)\n(入力例:○○.txt)",
        "データセット名\n(必須)",
        "データ所有者\n(NIMS User ID)",
        "NIMS user UUID\n(必須)",
        "データ名\n(必須)",
        "実験ID",
        "参考URL",
        "説明",
        "試料名\n(ローカルID)",
        "試料UUID\n(必須)",
        "試料管理者UUID",
        "化学式・組成式・分子式など",
        "試料の説明",
        "一般名称\n(General name)",
        "化学組成\n(Chemical composition)",
        "試料分類\n(Sample type)",
        "CAS番号\n(CAS Number)",
        "key1",
        "key2",
    ],
]

# ExcelInvoice (file mode): Register multiple files + multiple tiles in zip, correctly includes blank lines in between
EXCELINVOICE_ENTRYDATA_SHEET1_WITH_BLANKLINE = [
    [
        "data_file_names",
        "",
        "",
        "basic",
        "basic",
        "basic",
        "basic",
        "sample",
        "sample",
        "sample",
        "sample",
        "sample",
        "sample",
        "sample.general",
        "sample.general",
        "sample.general",
        "sample.general",
        "custom",
        "custom",
    ],
    [
        "name",
        "dataset_title",
        "dataOwner",
        "dataOwnerId",
        "dataName",
        "experimentId",
        "referenceUrl",
        "description",
        "names",
        "sampleId",
        "ownerId",
        "composition",
        "description",
        "general-name",
        "chemical-composition",
        "sample-type",
        "cas-number",
        "key1",
        "key2",
    ],
    [
        "ファイル名\n(拡張子も含め入力)\n(入力例:○○.txt)",
        "データセット名\n(必須)",
        "データ所有者\n(NIMS User ID)",
        "NIMS user UUID\n(必須)",
        "データ名\n(必須)",
        "実験ID",
        "参考URL",
        "説明",
        "試料名\n(ローカルID)",
        "試料UUID\n(必須)",
        "試料管理者UUID",
        "化学式・組成式・分子式など",
        "試料の説明",
        "一般名称\n(General name)",
        "化学組成\n(Chemical composition)",
        "試料分類\n(Sample type)",
        "CAS番号\n(CAS Number)",
        "key1",
        "key2",
    ],
    [
        "test_child1.txt",
        "N_TEST_1",
        "test_user",
        "f30812c3-14bc-4274-809f-afcfaa2e4047",
        "test1",
        "test_230606_1",
        "desc1",
        "sample1",
        "cbf194ea-813f-4e05-b288",
        "1111",
        "sample1",
        "test_ref",
        "desc3",
        "testname",
        "Fe",
        "magnet",
        "7439-89-6",
        "AAA",
        "CCC",
    ],
    ["", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
    [
        "test_child2.txt",
        "N_TEST_2",
        "test_user",
        "f30812c3-14bc-4274-809f-afcfaa2e4047",
        "test2",
        "test_230606_2",
        "desc2",
        "sample2",
        "cbf194ea-813f-4e05-b288",
        "1111",
        "sample2",
        "test_ref",
        "desc4",
        "testname",
        "Fe",
        "magnet",
        "7439-89-6",
        "BBB",
        "DDD",
    ],
]

# ExcelInvoice (file mode): Register multiple files + multiple tiles in zip, however, includes a blank line immediately after the header
EXCELINVOICE_ENTRYDATA_SHEET1_WITH_A_SHORT_BLANKLINE_IMMEDIATELY_AFTER_HEADER = [
    [
        "data_file_names",
        "",
        "",
        "basic",
        "basic",
        "basic",
        "basic",
        "sample",
        "sample",
        "sample",
        "sample",
        "sample",
        "sample",
        "sample.general",
        "sample.general",
        "sample.general",
        "sample.general",
        "custom",
        "custom",
    ],
    [
        "name",
        "dataset_title",
        "dataOwner",
        "dataOwnerId",
        "dataName",
        "experimentId",
        "referenceUrl",
        "description",
        "names",
        "sampleId",
        "ownerId",
        "composition",
        "description",
        "general-name",
        "chemical-composition",
        "sample-type",
        "cas-number",
        "key1",
        "key2",
    ],
    [
        "ファイル名\n(拡張子も含め入力)\n(入力例:○○.txt)",
        "データセット名\n(必須)",
        "データ所有者\n(NIMS User ID)",
        "NIMS user UUID\n(必須)",
        "データ名\n(必須)",
        "実験ID",
        "参考URL",
        "説明",
        "試料名\n(ローカルID)",
        "試料UUID\n(必須)",
        "試料管理者UUID",
        "化学式・組成式・分子式など",
        "試料の説明",
        "一般名称\n(General name)",
        "化学組成\n(Chemical composition)",
        "試料分類\n(Sample type)",
        "CAS番号\n(CAS Number)",
        "key1",
        "key2",
    ],
    ["", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
    [
        "test_child1.txt",
        "N_TEST_1",
        "test_user",
        "f30812c3-14bc-4274-809f-afcfaa2e4047",
        "test1",
        "test_230606_1",
        "desc1",
        "sample1",
        "cbf194ea-813f-4e05-b288",
        "1111",
        "sample1",
        "test_ref",
        "desc3",
        "testname",
        "Fe",
        "magnet",
        "7439-89-6",
        "AAA",
        "CCC",
    ],
    [
        "test_child2.txt",
        "N_TEST_2",
        "test_user",
        "f30812c3-14bc-4274-809f-afcfaa2e4047",
        "test2",
        "test_230606_2",
        "desc2",
        "sample2",
        "cbf194ea-813f-4e05-b288",
        "1111",
        "sample2",
        "test_ref",
        "desc4",
        "testname",
        "Fe",
        "magnet",
        "7439-89-6",
        "BBB",
        "DDD",
    ],
]

# ExcelInvoice: Information on the second sheet
EXCELINVOICE_ENTRYDATA_SHEET2 = [
    ["33c6e9dc-5787-0f96-7683-f39281c60419", "sample.general.composiiton"],
    ["f2d5e89e-01f0-66a2-5d8e-623a4fc31698", "sample.general.material-name"],
    ["a7a6fc7b-ed46-88b0-bba8-a1e34857a049", "sample.general.sample-alias"],
    ["e2d20d02-2e38-2cd3-b1b3-66fdb8a11057", "sample.general.cas-number"],
    ["1e70d11d-cbdd-bfd1-9301-9612c29b4060", "sample.general.purchase-date"],
    ["1d3cab05-3eaa-cb9b-9a3f-20eb0ca26963", "sample.general.crystalline-state"],
    ["efcf34e7-4308-c195-6691-6f4d28ffc9bb", "sample.general.crystal-structure"],
    ["e9617207-7f74-ef45-9b05-74eef6e4ecbb", "sample.general.pearson-symbol"],
    ["f63149a4-e57c-4273-4c1e-dffa41356d28", "sample.general.space-group"],
    ["7cc57dfb-8b70-4b3a-5315-fbce4cbf73d0", "sample.general.sample-shape"],
    ["efc6a0d5-313e-1871-190c-baaff7d1bf6c", "sample.general.smiles-string"],
    ["9270879d-d94e-4d3f-2d5c-19568e040004", "sample.general.inchi"],
    ["3edadcff-8a85-51d9-708f-8f76bf055377", "sample.general.inchi-key"],
    ["dc27a956-263e-f920-e574-5beec912a247", "sample.general.molecular-weight"],
    ["0444cf53-db47-b208-7b5f-54429291a140", "sample.general.sample-type"],
    ["fc30c31d-12a3-591a-c837-4f06ab458de0", "sample.general.taxonomy"],
    ["9a23002a-c398-e521-081a-24b6cd32dbbd", "sample.general.cell-line"],
    ["b4ce4016-e2bf-e5a1-7cae-ed496c7a776f", "sample.general.protein-name"],
    ["8c9b1a88-1530-24d3-4b2e-5441eee5c24f", "sample.general.gene-name"],
    ["047e30f3-f294-e58d-cbe4-6bb588bf4cf8", "sample.general.ncbi-accession-number"],
    ["3adf9874-7bcb-e5f8-99cb-3d6fd9d7b55e", "sample.general.general-name"],
    ["0aadfff2-37de-411f-883a-38b62b2abbce", "sample.general.chemical-composition"],
    ["5e166ac4-bfcd-457a-84bc-8626abe9188f", "sample.general.supplier"],
    ["0d0417a3-3c3b-496a-b0fb-5a26f8a74166", "sample.general.lot-number-or-product-number-etc"],
]

# ExcelInvoice: Information on the third sheet
EXCELINVOICE_ENTRYDATA_SHEET3 = [
    ["01cb3c01-37a4-5a43-d8ca-f523ca99a75b", "3250c45d-0ed6-1438-43b5-eb679918604a", "sample.specific.organic.chemical-formula"],
    ["01cb3c01-37a4-5a43-d8ca-f523ca99a75b", "70c2c751-5404-19b7-4a5e-981e6cebbb15", "sample.specific.organic.name"],
    ["01cb3c01-37a4-5a43-d8ca-f523ca99a75b", "e2d20d02-2e38-2cd3-b1b3-66fdb8a11057", "sample.specific.organic.cas-number"],
    ["01cb3c01-37a4-5a43-d8ca-f523ca99a75b", "518e26a0-4262-86f5-3598-80e18e6ff2af", "sample.specific.organic.pubchem"],
    ["01cb3c01-37a4-5a43-d8ca-f523ca99a75b", "3a775d54-5c13-fe66-6405-29c05bc931ce", "sample.specific.organic.viscosity"],
    ["01cb3c01-37a4-5a43-d8ca-f523ca99a75b", "659da80e-c2ee-2986-41ce-68201b3bc4dd", "sample.specific.organic.boiling-point"],
    ["01cb3c01-37a4-5a43-d8ca-f523ca99a75b", "4efc4c3b-727c-c752-cf28-701b55dba1af", "sample.specific.organic.melting-temperature"],
    ["932e4fe1-9724-305f-ffc5-1908c31c83e5", "70c2c751-5404-19b7-4a5e-981e6cebbb15", "sample.specific.inorganic.name"],
    ["932e4fe1-9724-305f-ffc5-1908c31c83e5", "3250c45d-0ed6-1438-43b5-eb679918604a", "sample.specific.inorganic.chemical-formula"],
    ["932e4fe1-9724-305f-ffc5-1908c31c83e5", "f63149a4-e57c-4273-4c1e-dffa41356d28", "sample.specific.inorganic.space-group"],
    ["a674a8ef-efa8-9497-4ed4-74de55fafddb", "3250c45d-0ed6-1438-43b5-eb679918604a", "sample.specific.metals.chemical-formula"],
    ["a674a8ef-efa8-9497-4ed4-74de55fafddb", "70c2c751-5404-19b7-4a5e-981e6cebbb15", "sample.specific.metals.name"],
    ["a674a8ef-efa8-9497-4ed4-74de55fafddb", "e2d20d02-2e38-2cd3-b1b3-66fdb8a11057", "sample.specific.metals.cas-number"],
    ["a674a8ef-efa8-9497-4ed4-74de55fafddb", "f63149a4-e57c-4273-4c1e-dffa41356d28", "sample.specific.metals.space-group"],
    ["a674a8ef-efa8-9497-4ed4-74de55fafddb", "efcf34e7-4308-c195-6691-6f4d28ffc9bb", "sample.specific.metals.crystal-structure"],
    ["a674a8ef-efa8-9497-4ed4-74de55fafddb", "659da80e-c2ee-2986-41ce-68201b3bc4dd", "sample.specific.metals.boiling-point"],
    ["a674a8ef-efa8-9497-4ed4-74de55fafddb", "4efc4c3b-727c-c752-cf28-701b55dba1af", "sample.specific.metals.melting-temperature"],
    ["342ba516-4d02-171c-9bc4-70a3134b47a8", "3250c45d-0ed6-1438-43b5-eb679918604a", "sample.specific.polymers.chemical-formula"],
    ["342ba516-4d02-171c-9bc4-70a3134b47a8", "70c2c751-5404-19b7-4a5e-981e6cebbb15", "sample.specific.polymers.name"],
    ["342ba516-4d02-171c-9bc4-70a3134b47a8", "e2d20d02-2e38-2cd3-b1b3-66fdb8a11057", "sample.specific.polymers.cas-number"],
    ["342ba516-4d02-171c-9bc4-70a3134b47a8", "518e26a0-4262-86f5-3598-80e18e6ff2af", "sample.specific.polymers.pubchem"],
    ["342ba516-4d02-171c-9bc4-70a3134b47a8", "4efc4c3b-727c-c752-cf28-701b55dba1af", "sample.specific.polymers.melting-temperature"],
    ["52148afb-6759-23e8-c8b8-33912ec5bfcf", "70c2c751-5404-19b7-4a5e-981e6cebbb15", "sample.specific.semiconductors.name"],
    ["961c9637-9b83-0e9d-e60e-ffc1e2517afd", "70c2c751-5404-19b7-4a5e-981e6cebbb15", "sample.specific.ceramics.name"],
    ["0dde5969-3039-739b-b33b-97df40450790", "70c2c751-5404-19b7-4a5e-981e6cebbb15", "sample.specific.biological.name"],
    ["01cb3c01-37a4-5a43-d8ca-f523ca99a75b", "dc27a956-263e-f920-e574-5beec912a247", "sample.specific.organic-material.molecular-weight"],
    ["01cb3c01-37a4-5a43-d8ca-f523ca99a75b", "efc6a0d5-313e-1871-190c-baaff7d1bf6c", "sample.specific.organic-material.SMILES-String"],
    ["0dde5969-3039-739b-b33b-97df40450790", "0444cf53-db47-b208-7b5f-54429291a140", "sample.specific.biological.sample-type"],
    ["0dde5969-3039-739b-b33b-97df40450790", "fc30c31d-12a3-591a-c837-4f06ab458de0", "sample.specific.biological.taxonomy"],
    ["0dde5969-3039-739b-b33b-97df40450790", "9a23002a-c398-e521-081a-24b6cd32dbbd", "sample.specific.biological.cell-line"],
    ["0dde5969-3039-739b-b33b-97df40450790", "b4ce4016-e2bf-e5a1-7cae-ed496c7a776f", "sample.specific.biological.protein-name"],
    ["0dde5969-3039-739b-b33b-97df40450790", "8c9b1a88-1530-24d3-4b2e-5441eee5c24f", "sample.specific.biological.gene-name"],
    ["0dde5969-3039-739b-b33b-97df40450790", "047e30f3-f294-e58d-cbe4-6bb588bf4cf8", "sample.specific.biological.ncbi-accession-number"],
    ["01cb3c01-37a4-5a43-d8ca-f523ca99a75b", "9270879d-d94e-4d3f-2d5c-19568e040004", "sample.specific.organic-material.inchi"],
    ["01cb3c01-37a4-5a43-d8ca-f523ca99a75b", "3edadcff-8a85-51d9-708f-8f76bf055377", "sample.specific.organic-material.inchi-key"],
]


@pytest.fixture
def inputfile_single_excelinvoice() -> Generator[str, None, None]:
    """ExcelInvoice / One input file / add empty sheet"""
    input_dir = pathlib.Path("data", "inputdata")
    input_dir.mkdir(parents=True, exist_ok=True)
    test_excel_invoice = pathlib.Path(input_dir, "test_excel_invoice.xlsx")

    df1 = pd.DataFrame(
        EXCELINVOICE_ENTRYDATA_SHEET1_SINGLE,
        columns=["invoiceList_format_id", "Sample_RDE_DataSet", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
    )
    empty_df = pd.DataFrame()
    df2 = pd.DataFrame(EXCELINVOICE_ENTRYDATA_SHEET2, columns=["term_id", "key_name"])
    df3 = pd.DataFrame(EXCELINVOICE_ENTRYDATA_SHEET3, columns=["sample_class_id", "term_id", "key_name"])

    with pd.ExcelWriter(test_excel_invoice) as writer:
        df1.to_excel(writer, sheet_name="invoice_form", index=False)
        empty_df.to_excel(writer, sheet_name="empty_sheet", index=False)
        df2.to_excel(writer, sheet_name="generalTerm", index=False)
        df3.to_excel(writer, sheet_name="specificTerm", index=False)

    yield str(test_excel_invoice)

    # teardown
    if os.path.exists("data"):
        shutil.rmtree("data")


@pytest.fixture
def inputfile_single_excelinvoice_with_blankline() -> Generator[str, None, None]:
    """Invalid ExcelInvoice containing blank lines"""
    input_dir = pathlib.Path("data", "inputdata")
    input_dir.mkdir(parents=True, exist_ok=True)
    test_excel_invoice = pathlib.Path(input_dir, "test_excel_invoice.xlsx")

    df1 = pd.DataFrame(
        EXCELINVOICE_ENTRYDATA_SHEET1_WITH_BLANKLINE,
        columns=["invoiceList_format_id", "Sample_RDE_DataSet", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
    )
    df2 = pd.DataFrame(EXCELINVOICE_ENTRYDATA_SHEET2, columns=["term_id", "key_name"])
    df3 = pd.DataFrame(EXCELINVOICE_ENTRYDATA_SHEET3, columns=["sample_class_id", "term_id", "key_name"])

    with pd.ExcelWriter(test_excel_invoice) as writer:
        df1.to_excel(writer, sheet_name="invoice_form", index=False)
        df2.to_excel(writer, sheet_name="generalTerm", index=False)
        df3.to_excel(writer, sheet_name="specificTerm", index=False)

    yield str(test_excel_invoice)

    # teardown
    if os.path.exists("data"):
        shutil.rmtree("data")


@pytest.fixture
def inputfile_single_header_merge_excelinvoice() -> Generator[str, None, None]:
    """ExcelInvoice / One input file with merged header"""
    input_dir = pathlib.Path("data", "inputdata")
    input_dir.mkdir(parents=True, exist_ok=True)
    test_excel_invoice = pathlib.Path(input_dir, "test_excel_invoice.xlsx")

    df1 = pd.DataFrame(
        EXCELINVOICE_ENTRYDATA_SHEET1_SINGLE_MERGE,
        columns=["invoiceList_format_id", "Sample_RDE_DataSet", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
    )
    df2 = pd.DataFrame(EXCELINVOICE_ENTRYDATA_SHEET2, columns=["term_id", "key_name"])
    df3 = pd.DataFrame(EXCELINVOICE_ENTRYDATA_SHEET3, columns=["sample_class_id", "term_id", "key_name"])

    with pd.ExcelWriter(test_excel_invoice) as writer:
        df1.to_excel(writer, sheet_name="invoice_form", index=False)
        df2.to_excel(writer, sheet_name="generalTerm", index=False)
        df3.to_excel(writer, sheet_name="specificTerm", index=False)

    yield str(test_excel_invoice)

    # teardown
    if os.path.exists("data"):
        shutil.rmtree("data")


@pytest.fixture
def inputfile_multi_excelinvoice() -> Generator[str, None, None]:
    """ExcelInvoice / Multiple input files"""
    input_dir = pathlib.Path("data", "inputdata")
    input_dir.mkdir(parents=True, exist_ok=True)
    test_excel_invoice = pathlib.Path(input_dir, "test_excel_invoice.xlsx")

    df1 = pd.DataFrame(
        EXCELINVOICE_ENTRYDATA_SHEET1_MULTI,
        columns=["invoiceList_format_id", "Sample_RDE_DataSet", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
    )
    df2 = pd.DataFrame(EXCELINVOICE_ENTRYDATA_SHEET2, columns=["term_id", "key_name"])
    df3 = pd.DataFrame(EXCELINVOICE_ENTRYDATA_SHEET3, columns=["sample_class_id", "term_id", "key_name"])

    with pd.ExcelWriter(test_excel_invoice) as writer:
        df1.to_excel(writer, sheet_name="invoice_form", index=False)
        df2.to_excel(writer, sheet_name="generalTerm", index=False)
        df3.to_excel(writer, sheet_name="specificTerm", index=False)

    yield str(test_excel_invoice)

    # teardown
    if os.path.exists("data"):
        shutil.rmtree("data")


@pytest.fixture
def inputfile_multi_folder_excelinvoice() -> Generator[str, None, None]:
    """ExcelInvoice / Multiple input files in a folder"""
    input_dir = pathlib.Path("data", "inputdata")
    input_dir.mkdir(parents=True, exist_ok=True)
    test_excel_invoice = pathlib.Path(input_dir, "test_excel_invoice.xlsx")

    df1 = pd.DataFrame(
        EXCELINVOICE_ENTRYDATA_SHEET1_MULTI_FOLDER,
        columns=["invoiceList_format_id", "Sample_RDE_DataSet", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
    )
    df2 = pd.DataFrame(EXCELINVOICE_ENTRYDATA_SHEET2, columns=["term_id", "key_name"])
    df3 = pd.DataFrame(EXCELINVOICE_ENTRYDATA_SHEET3, columns=["sample_class_id", "term_id", "key_name"])

    with pd.ExcelWriter(test_excel_invoice) as writer:
        df1.to_excel(writer, sheet_name="invoice_form", index=False)
        df2.to_excel(writer, sheet_name="generalTerm", index=False)
        df3.to_excel(writer, sheet_name="specificTerm", index=False)

    yield str(test_excel_invoice)

    # teardown
    if os.path.exists("data"):
        shutil.rmtree("data")


@pytest.fixture
def inputfile_single_dummy_header_excelinvoice() -> Generator[str, None, None]:
    """ExcelInvoice / One input file with dummy header"""
    input_dir = pathlib.Path("data", "inputdata")
    input_dir.mkdir(parents=True, exist_ok=True)
    test_excel_invoice = pathlib.Path(input_dir, "test_excel_invoice.xlsx")

    df1 = pd.DataFrame(
        EXCELINVOICE_ENTRYDATA_SHEET1_SINGLE,
        columns=[
            "invoiceList_format_id",
            "Sample_RDE_DataSet",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ],
    )
    df2 = pd.DataFrame(EXCELINVOICE_ENTRYDATA_SHEET2, columns=["dummy_id", "dummy_term"])
    df3 = pd.DataFrame(EXCELINVOICE_ENTRYDATA_SHEET3, columns=["dummy1", "dummy2", "dummy3"])

    with pd.ExcelWriter(test_excel_invoice) as writer:
        df1.to_excel(writer, sheet_name="invoice_form", index=False)
        df2.to_excel(writer, sheet_name="generalTerm", index=False)
        df3.to_excel(writer, sheet_name="specificTerm", index=False)

    yield str(test_excel_invoice)

    # teardown
    if os.path.exists("data"):
        shutil.rmtree("data")


@pytest.fixture
def inputfile_single_dummy_header_excelinvoice_with_magic_variable() -> Generator[str, None, None]:
    """ExcelInvoice with magic variable: ${filename}"""
    input_dir = pathlib.Path("data", "inputdata")
    input_dir.mkdir(parents=True, exist_ok=True)
    test_excel_invoice = pathlib.Path(input_dir, "test_excel_invoice.xlsx")

    df1 = pd.DataFrame(
        EXCELINVOICE_ENTRYDATA_SHEET1_SINGLE_MAGIC_VARIABLE,
        columns=[
            "invoiceList_format_id",
            "Sample_RDE_DataSet",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ],
    )
    df2 = pd.DataFrame(EXCELINVOICE_ENTRYDATA_SHEET2, columns=["dummy_id", "dummy_term"])
    df3 = pd.DataFrame(EXCELINVOICE_ENTRYDATA_SHEET3, columns=["dummy1", "dummy2", "dummy3"])

    with pd.ExcelWriter(test_excel_invoice) as writer:
        df1.to_excel(writer, sheet_name="invoice_form", index=False)
        df2.to_excel(writer, sheet_name="generalTerm", index=False)
        df3.to_excel(writer, sheet_name="specificTerm", index=False)

    yield str(test_excel_invoice)

    # teardown
    if os.path.exists("data"):
        shutil.rmtree("data")


@pytest.fixture
def inputfile_empty_excelinvoice() -> Generator[str, None, None]:
    """ExcelInvoice / Empty input file"""
    input_dir = pathlib.Path("data", "inputdata")
    input_dir.mkdir(parents=True, exist_ok=True)
    test_excel_invoice = pathlib.Path(input_dir, "test_excel_invoice.xlsx")
    df2 = pd.DataFrame(EXCELINVOICE_ENTRYDATA_SHEET2, columns=["dummy_id", "dummy_term"])
    df3 = pd.DataFrame(EXCELINVOICE_ENTRYDATA_SHEET3, columns=["dummy1", "dummy2", "dummy3"])

    with pd.ExcelWriter(test_excel_invoice) as writer:
        df2.to_excel(writer, sheet_name="generalTerm", index=False)
        df3.to_excel(writer, sheet_name="specificTerm", index=False)

    yield str(test_excel_invoice)

    # teardown
    if os.path.exists("data"):
        shutil.rmtree("data")


@pytest.fixture
def non_inputfile_excelinvoice() -> Generator[str, None, None]:
    """Invalid ExcelInvoice / Non-existent input file"""
    input_dir = pathlib.Path("data", "inputdata")
    input_dir.mkdir(parents=True, exist_ok=True)
    test_excel_invoice = pathlib.Path(input_dir, "test_excel_invoice.xlsx")

    df1 = pd.DataFrame(
        EXCELINVOICE_ENTRYDATA_SHEET1_NONFILE,
        columns=["invoiceList_format_id", "Sample_RDE_DataSet", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
    )
    df2 = pd.DataFrame(EXCELINVOICE_ENTRYDATA_SHEET2, columns=["term_id", "key_name"])
    df3 = pd.DataFrame(EXCELINVOICE_ENTRYDATA_SHEET3, columns=["sample_class_id", "term_id", "key_name"])

    with pd.ExcelWriter(test_excel_invoice) as writer:
        df1.to_excel(writer, sheet_name="invoice_form", index=False)
        df2.to_excel(writer, sheet_name="generalTerm", index=False)
        df3.to_excel(writer, sheet_name="specificTerm", index=False)

    yield str(test_excel_invoice)

    # teardown
    if os.path.exists("data"):
        shutil.rmtree("data")


@pytest.fixture
def empty_inputfile_excelinvoice() -> Generator[str, None, None]:
    """ExcelInvoice / Empty input file"""
    input_dir = pathlib.Path("data", "inputdata")
    input_dir.mkdir(parents=True, exist_ok=True)
    test_excel_invoice = pathlib.Path(input_dir, "test_excel_invoice.xlsx")

    df = pd.DataFrame([[1, 2, 3, 4]])
    df.to_excel(test_excel_invoice)

    yield str(test_excel_invoice)

    # teardown
    if os.path.exists("data"):
        shutil.rmtree("data")


@pytest.fixture
def inputfile_invalid_samesheet_excelinvoice() -> Generator[str, None, None]:
    """Invalid Excelinvoice / ExcelInvoice with multiple sheets containing the contents of Sheet1"""
    input_dir = pathlib.Path("data", "inputdata")
    input_dir.mkdir(parents=True, exist_ok=True)
    test_excel_invoice = pathlib.Path(input_dir, "test_excel_invoice.xlsx")

    df1 = pd.DataFrame(
        EXCELINVOICE_ENTRYDATA_SHEET1_SINGLE,
        columns=[
            "invoiceList_format_id",
            "Sample_RDE_DataSet",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ],
    )
    df2 = pd.DataFrame(
        EXCELINVOICE_ENTRYDATA_SHEET1_SINGLE,
        columns=[
            "invoiceList_format_id",
            "Sample_RDE_DataSet",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ],
    )
    df3 = pd.DataFrame(EXCELINVOICE_ENTRYDATA_SHEET3, columns=["dummy1", "dummy2", "dummy3"])

    with pd.ExcelWriter(test_excel_invoice) as writer:
        df1.to_excel(writer, sheet_name="invoice_form", index=False)
        df2.to_excel(writer, sheet_name="generalTerm", index=False)
        df3.to_excel(writer, sheet_name="specificTerm", index=False)

    yield str(test_excel_invoice)

    # teardown
    if os.path.exists("data"):
        shutil.rmtree("data")


@pytest.fixture
def excelinvoice_non_sampleinfo() -> Generator[str, None, None]:
    """ExcelInvoice / ExcelInvoice with no sample information"""
    input_dir = pathlib.Path("data", "inputdata")
    input_dir.mkdir(parents=True, exist_ok=True)
    test_excel_invoice = pathlib.Path(input_dir, "test_excel_invoice.xlsx")

    df1 = pd.DataFrame(EXCELINVOICE_ENTRYDATA_SHEET1_SINGLE_NON_SAMPLE, columns=["invoiceList_format_id", "Sample_RDE_DataSet", "", "", "", "", "", "", "", ""])
    df2 = pd.DataFrame(EXCELINVOICE_ENTRYDATA_SHEET2, columns=["term_id", "key_name"])
    df3 = pd.DataFrame(EXCELINVOICE_ENTRYDATA_SHEET3, columns=["sample_class_id", "term_id", "key_name"])

    with pd.ExcelWriter(test_excel_invoice) as writer:
        df1.to_excel(writer, sheet_name="invoice_form", index=False)
        df2.to_excel(writer, sheet_name="generalTerm", index=False)
        df3.to_excel(writer, sheet_name="specificTerm", index=False)

    yield str(test_excel_invoice)

    # teardown
    if os.path.exists("data"):
        shutil.rmtree("data")


@pytest.fixture
def excelinvoice_single_input_multiline() -> Generator[str, None, None]:
    """ExcelInvoice / ExcelInvoice with multiple lines in a single cell"""
    input_dir = pathlib.Path("data", "inputdata")
    input_dir.mkdir(parents=True, exist_ok=True)
    test_excel_invoice = pathlib.Path(input_dir, "test_excel_invoice.xlsx")

    df1 = pd.DataFrame(
        EXCELINVOICE_ENTRYDATA_SHEET1_SINGLE_MULTILINE,
        columns=["invoiceList_format_id", "Sample_RDE_DataSet", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
    )
    df2 = pd.DataFrame(EXCELINVOICE_ENTRYDATA_SHEET2, columns=["term_id", "key_name"])
    df3 = pd.DataFrame(EXCELINVOICE_ENTRYDATA_SHEET3, columns=["sample_class_id", "term_id", "key_name"])

    with pd.ExcelWriter(test_excel_invoice) as writer:
        df1.to_excel(writer, sheet_name="invoice_form", index=False)
        df2.to_excel(writer, sheet_name="generalTerm", index=False)
        df3.to_excel(writer, sheet_name="specificTerm", index=False)

    yield str(test_excel_invoice)

    # teardown
    if os.path.exists("data"):
        shutil.rmtree("data")
