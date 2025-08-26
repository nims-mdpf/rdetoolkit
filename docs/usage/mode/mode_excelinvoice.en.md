# What Is ExcelInvoice Mode?

## Purpose

A mode for efficiently registering multiple datasets in bulk using an Excel file. It bundles together multiple Invoice-mode registrations. If `invoice.schema.json` has been created, you can easily generate the Excel format used by ExcelInvoice mode.

## Features

- By describing multiple invoices in a single Excel file, you can register data in bulk.
- You can register data with different sample information and experimental conditions all at once.

## When to Use

- When you have conducted a large number of experiments of the same type.

## How to Configure

Simply place the ExcelInvoice file (`*_excel_invoice.xlsx`) in `inputdata`, and it will be automatically detected. No changes to configuration files are required.

## About the Excel File Format

ExcelInvoice mode is designed on the premise that `invoice.schema.json` has been created.

Run the following commands to create a template ExcelInvoice file.

\=== "Unix/macOS"

```shell
python3 -m rdetoolkit make-excelinvoice <invoice.schema.json path> -o <save file path> -m <file or folder>

# Example
python3 -m rdetoolkit make-excelinvoice template/invoice.schema.json
```

\=== "Windows"

```powershell
py -m rdetoolkit make-excelinvoice <invoice.schema.json path> -o <save file path> -m <file or folder>

# Example
py -m rdetoolkit make-excelinvoice template/invoice.schema.json
```

An Excel file like the one below will be generated. This Excel file is registered on a “`1 row` = `1 dataset tile`” basis. Therefore, please fill in each row with the information you want to register as a dataset tile.

![excelinvoice\_format](../../img/excelinvoice_format.png)

!!! Warning
If the data registrant UUID (NIMS user UUID) or the UUID used to reference existing sample information is not specified correctly, a registration error may occur.

### How to Check Your User UUID in RDE

Access [https://rde.nims.go.jp/rde/datasets](https://rde.nims.go.jp/rde/datasets). After logging in, click your username at the top right of the screen. Once your user information is displayed, the string in the URL after `users/` is your UUID.

![UserUUID](../../img/rde_user_uuid.png)

### How to Check a Sample UUID in RDE

You can check the UUID on the sample information page.

![SampleUUID](../../img/rde_sample_uuid.png)

## Preparing Input Files

In ExcelInvoice mode, create a zip file alongside the Excel file above.
Include in the zip the files specified in column A of the Excel sheet.

> The files below are example outputs. They vary depending on how the structuring process is defined.

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

#### Directory Structure

Place the Excel file and the zip file in the `inputdata` directory.

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

## Common Errors

### --UUID Not Specified Correctly--

If the data registrant UUID or sample UUID is not specified correctly, a registration error will occur. You can check these UUIDs in RDE.

### --File Not Found--

ExcelInvoice mode requires an Excel file that follows a specific format. If the format is invalid, an error will occur.

- The file name does not end with `_excel_invoice.xlsx`.
- The file name contains spaces or special characters.
- Unnecessary strings are appended to the end of the file name, such as `_excel_invoice(1).xlsx`, `_excel_invoice copy.xlsx`, etc.

### Unnecessary Files Included in the Zip

If macOS-specific files such as `.DS_Store` are included, they may cause errors. Exclude unnecessary files when creating the zip.
