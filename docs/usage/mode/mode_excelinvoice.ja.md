# ExcelInvoiceモードとは

## 目的

Excelファイルを使用して複数のデータセットを効率的に一括登録するモードです。複数のInvoiceモード登録を束ねたモードとなります。`invoice.schema.json`が作成されていれば、ExcelInvoiceモードで使用するExcelフォーマットを簡単に作成できます。

## 特徴

- 複数の送り状を一つでExcelで記述することで、一括でデータ登録が可能。
- 異なる試料情報や実験条件のデータを一括で登録可能。

## 使用場面

- 同種の実験を大量に実施した場合

## 設定方法

ExcelInvoiceファイル（`*_excel_invoice.xlsx`）を`inputdata`に配置するだけで自動認識されます。設定ファイルの変更等は不要です。

## Excelファイルのフォーマットについて

ExcelInvoiceモードは、`ivnoice.shcema.json`が作成されていることが前提で設計されています。

以下のコードを実行すると、ExcelInvoiceの雛形ファイルが作成されます。

=== "Unix/macOS"

    ```shell
    python3 -m rdetoolkit make-excelinvoice <invoice.schema.json path> -o <save file path> -m <file or folder>

    # 例
    python3 -m rdetoolkit make-excelinvoice template/invoice.schema.json
    ```

=== "Windows"

    ```powershell
    py -m rdetoolkit make-excelinvoice <invoice.schema.json path> -o <save file path> -m <file or folder>

    # 例
    py -m rdetoolkit make-excelinvoice template/invoice.schema.json
    ```

下記のようなExcelファイルが生成されます。このExcelファイルは、`1行` = `1データセットタイル`で登録されます。そのため、各行でデータセットタイルで登録したい情報を記述してください。

![excelinvoice_format](../../img/excelinvoice_format.png)

!!! Warning
    データ登録者UUID(NIMS user UUID)や、既存試料情報を参照する場合のUUIDが正しく指定されていない場合、登録エラーが発生する可能性があります。

### RDE上からユーザーUUIDを確認する方法

<https://rde.nims.go.jp/rde/datasets> にアクセスし、ログイン後に表示される画面の右上にあるユーザー名をクリックします。ユーザー情報表示後、URLに表示されている`users/`以降の文字列がUUIDになります。

![UserUUID](../../img/rde_user_uuid.png)

### RDE上から試料UUIDを確認する方法

試料情報ページから、UUIDを確認できました。

![SampleUUID](../../img/rde_sample_uuid.png)

## 入力ファイルの作成

ExcelInvoiceモードで、上記のExcelファイルと同時に、zipファイルを作成します。
zipファイルに格納するファイルは、ExcelのA列で指定したファイルを格納してください。

> ファイル等は出力例です。構造化処理の定義によって変化します。

```bash
files.zip
├── sample1.data
├── sample2.data
├── sample3.data
├── sample4.data
├── sample5.data
├── sample6.data
├── sample7.data
└── sample8.data
```

#### ディレクトリ構造

`inputdata`ディレクトリに、Excelファイルとzipファイルを配置します。

```bash
data/
├── inputdata/
│   ├── files.zip
│   └── experiment_excel_invoice.xlsx
├── invoice/
├── tasksupport/
```

```bash
data/
├── inputdata/
│   ├── files.zip
│   └── experiment_excel_invoice.xlsx
├── invoice/
├── tasksupport/
├── divided/
│   ├── 0001/
│   │   ├── structured/
│   │   ├── meta/
│   │   └── raw/
│   └── 0002/
│       ├── structured/
│       ├── meta/
│       └── raw/
└── logs/
```

## よくあるエラーについて

### **UUIDが正しく指定されていない**

データ登録者UUIDや試料UUIDが正しく指定されていない場合、登録エラーが発生します。UUIDはRDE上で確認できます。

### **ファイルが見つからない**

ExcelInvoiceモードでは、特定のフォーマットに従ったExcelファイルが必要です。フォーマットが不正な場合、エラーが発生します。

- ファイルの末尾は、`_excel_invoice.xlsx`でない。
- ファイル名に空白や特殊文字が含まれている。
- ファイルの末尾に、不要な文字列が含まれている。`_excel_invoice(1).xlsx`, `_excel_invoiceのコピー.xlsx`など。

### zipファイルに不要なファイルが含まれている

MacOS特有の`.DS_Store`などの不要なファイルが含まれていると、エラーの原因となる場合があります。zipファイルを作成する際には、不要なファイルを除外してください。
