# SmartTableInvoiceモードとは

## 目的

テーブルファイル（Excel/CSV/TSV）からメタデータを読み取り、自動的にinvoice.jsonファイルを生成するモードです。

## 特徴

- 多形式対応: Excel (.xlsx)、CSV、TSVファイルの読み込み
- 2行ヘッダー形式: 1行目に表示名、2行目にマッピングキーを配置
- 自動メタデータマッピング: `basic/`、`custom/`、`sample/`プレフィックスによる構造化データ生成
- zipファイル統合: データファイルを含むzipとテーブルファイルの自動関連付け

## 使用場面

- 複数のファイルを関連づけて複数データ登録したい場合

## 設定方法

設定ファイルの変更は不要です。ただし、入力データに、`smarttable_`という接頭辞がついたExcel/CSV/TSVファイルを配置する必要があります。

- `smarttable_tabledata.xlsx`
- `smarttable_imagedata.csv`
- `smarttable_20250101.tsv`

## テーブルデータのフォーマット

### 全体像

```csv
# 1行目: 表示名（ユーザー向けの説明）
データ名,入力ファイル1,サイクル,厚さ,温度,試料名,試料ID,一般項目

# 2行目: マッピングキー（実際の処理で使用）
basic/dataName,inputdata1,custom/cycle,custom/thickness,custom/temperature,sample/names,sample/sampleId,sample/generalAttributes.3adf9874-7bcb-e5f8-99cb-3d6fd9d7b55e

# 3行目以降: データ
実験1,file1.txt,1,2mm,25,sample001,S001,value1
実験2,file2.txt,2,3mm,30,sample002,S002,value2
```

![smarttable_excel_sample](../../img/smarttable_excel_sample.png)

### 1行目：　表示名（ユーザー向けの説明）

ここはデータ登録には関係ないですが、このテーブルデータを管理するときにどのようなデータかをわかりやすくするために、表示名を記載します。

```csv
データ名,入力ファイル1,サイクル,厚さ,温度,試料名,試料ID,一般項目
```

### 2行目: マッピングキー

#### メタデータのマッピングと展開

この行を読み取って、invocie.jsonやメタデータ等に自動でマッピングされます。マッピングされるルールは以下のとおりです。

- `basic/<invoice.jsonのキー名>`: invoice.jsonのbasicセクションにマッピングされます。
- `custom/<invoice.jsonのキー名>`: invoice.jsonのcustomセクションにマッピングされます。
- `sample/<invoice.jsonのキー名>`: invoice.jsonのsampleセクションにマッピングされます。
- `sample/generalAttributes.<termId>`: `generalAttributes`配列内の該当する`termId`の`value`にマッピング
- `sample/specificAttributes.<classId>.<termId>`: `specificAttributes`配列内の該当する`classId`と`termId`の`value`にマッピング
- `meta/<metadata-defのキー>`: `metadata-def.json`の定義に従って`metadata.json`の`constant`セクションへ書き込み（`schema.type`で型変換し、`unit`があれば付与）。`variable`定義は現時点では対応しません。`metadata-def.json`が存在しない場合は従来どおり書き込みをスキップします。
- `inputdataX`: zipファイル内のファイルパスを指定（X=1,2,3...）

> 現在自動でテーブルデータの情報が展開される先は、invoice.json と metadata.json（`meta/`列）です。それ以外のデータは、構造化処理で使用できるように展開されます。

#### 入力ファイルの取り扱いについて

`inputdata[数値]`というキーは、1データタイルに含めたいファイルパスを入力します。zipファイル内のパスを指定します。

- 例えば、`inputdata1`に`data1/file1.txt`と記載した場合、zipファイル内に`file1.txt`が存在する必要があります。
- `inputdata1`と`inputdata2`に`data1/file1.txt`を`data1/file2.txt`と記載した場合、構造化処理内で、2つのファイルを読み取ることができるようにグルーピングされます。

### 3行目以降

実際に登録するデータを記載します。1行1データタイルとして登録されます。

```csv
実験1,file1.txt,1,2mm,25,sample001,S001,value1
実験2,file2.txt,2,3mm,30,sample002,S002,value2
```

### 拡張子

テーブルデータファイルの拡張子は、`.csv`、`.xlsx`、`.tsv`のいずれかである必要があります。

## 入力ファイルについて

SmartTableInvoiceモードでは、特定の形式の入力ファイルが必要です。これらのファイルは、テーブルデータを含むExcel/CSV/TSVファイルと、関連するデータファイルを含むzipファイルです。

- `smarttable_imagedata.csv`
- `inputdata.zip`

## ディレクトリ構造

`inputdata`ディレクトリに、Excelファイルとzipファイルを配置します。

```bash
data/
├── inputdata/
│   ├── inputdata.zip
│   └── smarttable_imagedata.csv
├── invoice/
├── tasksupport/
```

```bash
data/
├── inputdata/
│   ├── smarttable_imagedata.csv
│   └── inputdata.zip
├── invoice/
├── tasksupport/
├── divided/
│   ├── 0001/
│   │   ├── invoice/
│   │   │   └── invoice.json  # smarttableの1行目から生成
│   │   ├── raw/
│   │   │   ├── file1.txt
│   │   │   └── file2.txt
│   │   └── (その他の標準フォルダ)
│   └── 0002/
│       ├── invoice/
│       │   └── invoice.json  # smarttableの2行目から生成
│       └── (その他の標準フォルダ)
└── temp/
    ├── fsmarttable_experiment_0001.csv
    └── fsmarttable_experiment_0002.csv
```

## テーブルデータの1行分のデータを構造化処理で取得する

構造化処理を以下のように定義した場合、`RdeOutputResourcePath.rawfiles`からcsvのパスを取得できます。上記のディレクトリ構造の例では、`temp/fsmarttable_experiment_0001.csv`等になります。

```python
def custom_module(srcpaths: RdeInputDirPaths, resource_paths: RdeOutputResourcePath) -> None:
    """Execute structured text processing, metadata extraction, and visualization.

    It handles structured text processing, metadata extraction, and graphing.
    Other processing required for structuring may be implemented as needed.

    Args:
        srcpaths (RdeInputDirPaths): Paths to input resources for processing.
        resource_paths (RdeOutputResourcePath): Paths to output resources for saving results.

    Returns:
        None

    Note:
        The actual function names and processing details may vary depending on the project.
    """
    ...
```

## テーブルデータファイルをRDEに登録する場合

デフォルトでは、SmartTableInvoiceモードで使用したテーブルデータは、RDEに登録されません。設定ファイル`rdeconfig.yml`に、以下のように設定することで、テーブルデータをRDEに登録することができます。

```yaml
smarttable:
    save_table_file: true
```
