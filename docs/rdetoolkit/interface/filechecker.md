# FileChecker Interface API

## Purpose

This module defines the interfaces for file validation processes in RDEToolKit. It provides features such as existence checks, size validation, format checks, and content verification for files.

## Key Features

### File Validation Interfaces
- Helper interface for input file operations
- Interface for file validation
- Interface for compressed file structure parsing

### Abstraction Layer
- Unified file operation interfaces
- Extensible validation system
- Plugin-based architecture

---

::: src.rdetoolkit.interfaces.filechecker.IInputFileHelper

---

::: src.rdetoolkit.interfaces.filechecker.IInputFileChecker

---

::: src.rdetoolkit.interfaces.filechecker.ICompressedFileStructParser

---

## Practical Usage

### Implementing a Custom File Helper
```python title="custom_file_helper.py"
from rdetoolkit.interfaces.filechecker import IInputFileHelper
from pathlib import Path
from typing import List

class CustomInputFileHelper(IInputFileHelper):
    """Custom implementation of the input file helper"""

    def get_zipfiles(self, directory: Path) -> List[Path]:
        """Retrieve ZIP files in a directory"""
        zip_files = []

        # Basic ZIP file search
        zip_files.extend(directory.glob("*.zip"))
        zip_files.extend(directory.glob("*.ZIP"))

        # Recursive search
        zip_files.extend(directory.rglob("*.zip"))

        # Remove duplicates
        unique_zip_files = list(set(zip_files))

        print(f"Found {len(unique_zip_files)} ZIP files:")
        for zip_file in unique_zip_files:
            print(f"  - {zip_file}")

        return unique_zip_files

    def unpacked(self, zip_file: Path) -> List[Path]:
        """Extract contents of a ZIP file"""
        import zipfile

        extracted_files = []
        extract_dir = zip_file.parent / f"{zip_file.stem}_extracted"
        extract_dir.mkdir(exist_ok=True)

        try:
            with zipfile.ZipFile(zip_file, 'r') as zf:
                zf.extractall(extract_dir)

                # List extracted files
                for file in extract_dir.rglob("*"):
                    if file.is_file():
                        extracted_files.append(file)

            print(f"✓ Extraction complete: {len(extracted_files)} files")
            return extracted_files

        except Exception as e:
            print(f"✗ Extraction error: {e}")
            return []
```

### Implementing a Custom File Checker
```python title="custom_file_checker.py"
from rdetoolkit.interfaces.filechecker import IInputFileChecker
from pathlib import Path
from typing import Dict, Any

class CustomInputFileChecker(IInputFileChecker):
    """Custom implementation of the input file checker"""

    def __init__(self):
        self.validation_rules = {
            ".csv": {"max_size": 10 * 1024 * 1024, "encoding": "utf-8"},
            ".json": {"max_size": 1 * 1024 * 1024, "required_keys": ["basic"]},
            ".xlsx": {"max_size": 20 * 1024 * 1024},
            ".zip": {"max_size": 100 * 1024 * 1024}
        }

    def parse(self, file_path: Path) -> Dict[str, Any]:
        """Validate and parse a file according to its extension and rules"""
        result = {
            "file_path": str(file_path),
            "exists": file_path.exists(),
            "size": 0,
            "extension": file_path.suffix.lower(),
            "valid": False,
            "errors": []
        }

        if not result["exists"]:
            result["errors"].append("File does not exist")
            return result

        # Get file size
        result["size"] = file_path.stat().st_size

        # Validate based on extension
        ext = result["extension"]
        if ext in self.validation_rules:
            rules = self.validation_rules[ext]

            # Size check
            if result["size"] > rules["max_size"]:
                result["errors"].append("File size exceeds the maximum limit")

            # Extension-specific checks
            if ext == ".json":
                result.update(self._validate_json(file_path, rules))
            elif ext == ".csv":
                result.update(self._validate_csv(file_path, rules))
            elif ext == ".xlsx":
                result.update(self._validate_excel(file_path, rules))

        result["valid"] = len(result["errors"]) == 0
        return result

    def _validate_json(self, file_path: Path, rules: Dict) -> Dict:
        """Validate JSON file structure and required keys"""
        import json

        validation_result = {"json_valid": False, "errors": []}

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            validation_result["json_valid"] = True

            # Check required keys
            if "required_keys" in rules:
                missing = [k for k in rules["required_keys"] if k not in data]
                if missing:
                    validation_result["errors"] = [f"Missing required keys: {missing}"]

        except json.JSONDecodeError as e:
            validation_result["errors"] = [f"JSON format error: {e}"]
        except Exception as e:
            validation_result["errors"] = [f"File read error: {e}"]

        return validation_result

    def _validate_csv(self, file_path: Path, rules: Dict) -> Dict:
        """Validate CSV file format and count rows"""
        import csv

        validation_result = {"csv_valid": False, "row_count": 0, "errors": []}

        try:
            with open(file_path, 'r', encoding=rules.get("encoding", "utf-8")) as f:
                reader = csv.reader(f)
                rows = list(reader)
                validation_result["row_count"] = len(rows)
                validation_result["csv_valid"] = True

        except Exception as e:
            validation_result["errors"] = [f"CSV read error: {e}"]

        return validation_result

    def _validate_excel(self, file_path: Path, rules: Dict) -> Dict:
        """Validate basic Excel file format"""
        validation_result = {"excel_valid": False, "errors": []}

        try:
            if file_path.suffix.lower() in ['.xlsx', '.xls']:
                validation_result["excel_valid"] = True
            else:
                validation_result["errors"] = ["Not an Excel file"]

        except Exception as e:
            validation_result["errors"] = [f"Excel validation error: {e}"]

        return validation_result
```

### Example Usage of File Checker
```python title="filechecker_example.py"
from pathlib import Path
from custom_file_checker import CustomInputFileChecker

checker = CustomInputFileChecker()

test_files = [
    Path("data/input/data.csv"),
    Path("data/invoice/invoice.json"),
    Path("data/templates/template.xlsx"),
    Path("data/archives/data.zip")
]

print("=== File Validation Results ===")
for fp in test_files:
    result = checker.parse(fp)
    status = "✓" if result["valid"] else "✗"
    print(f"{status} {fp.name}")
    print(f"   Size: {result['size']:,} bytes")
    print(f"   Extension: {result['extension']}")

    if result["errors"]:
        print(f"   Errors: {', '.join(result['errors'])}")
    print()
```

### Implementing a Custom Compressed File Structure Parser
```python title="compressed_struct_parser.py"
from rdetoolkit.interfaces.filechecker import ICompressedFileStructParser
from pathlib import Path
from typing import Dict, List, Any
import zipfile
import tarfile

class CustomCompressedFileStructParser(ICompressedFileStructParser):
    """カスタム圧縮ファイル構造パーサーの実装"""

    def read(self, archive_path: Path) -> Dict[str, Any]:
        """圧縮ファイルの構造読み込み"""

        result = {
            "archive_path": str(archive_path),
            "archive_type": self._detect_archive_type(archive_path),
            "file_count": 0,
            "directory_count": 0,
            "total_size": 0,
            "files": [],
            "directories": [],
            "structure": {},
            "errors": []
        }

        try:
            if result["archive_type"] == "zip":
                result.update(self._read_zip_structure(archive_path))
            elif result["archive_type"] == "tar":
                result.update(self._read_tar_structure(archive_path))
            else:
                result["errors"].append(f"未対応の圧縮形式: {result['archive_type']}")

        except Exception as e:
            result["errors"].append(f"構造読み込みエラー: {e}")

        return result

    def _detect_archive_type(self, archive_path: Path) -> str:
        """圧縮ファイルタイプの検出"""
        suffix = archive_path.suffix.lower()

        if suffix == ".zip":
            return "zip"
        elif suffix in [".tar", ".tar.gz", ".tgz", ".tar.bz2"]:
            return "tar"
        else:
            return "unknown"

    def _read_zip_structure(self, archive_path: Path) -> Dict:
        """ZIP ファイル構造の読み込み"""
        structure_data = {
            "files": [],
            "directories": [],
            "file_count": 0,
            "directory_count": 0,
            "total_size": 0
        }

        with zipfile.ZipFile(archive_path, 'r') as zf:
            for info in zf.infolist():
                item_data = {
                    "name": info.filename,
                    "size": info.file_size,
                    "compressed_size": info.compress_size,
                    "is_directory": info.is_dir(),
                    "date_time": info.date_time
                }

                if info.is_dir():
                    structure_data["directories"].append(item_data)
                    structure_data["directory_count"] += 1
                else:
                    structure_data["files"].append(item_data)
                    structure_data["file_count"] += 1
                    structure_data["total_size"] += info.file_size

        return structure_data

    def _read_tar_structure(self, archive_path: Path) -> Dict:
        """TAR ファイル構造の読み込み"""
        structure_data = {
            "files": [],
            "directories": [],
            "file_count": 0,
            "directory_count": 0,
            "total_size": 0
        }

        with tarfile.open(archive_path, 'r') as tf:
            for member in tf.getmembers():
                item_data = {
                    "name": member.name,
                    "size": member.size,
                    "is_directory": member.isdir(),
                    "mode": member.mode,
                    "mtime": member.mtime
                }

                if member.isdir():
                    structure_data["directories"].append(item_data)
                    structure_data["directory_count"] += 1
                else:
                    structure_data["files"].append(item_data)
                    structure_data["file_count"] += 1
                    structure_data["total_size"] += member.size

        return structure_data

# 使用例
parser = CustomCompressedFileStructParser()

archive_files = [
    Path("data/archives/experiment1.zip"),
    Path("data/archives/backup.tar.gz"),
    Path("data/archives/images.zip")
]

print("=== 圧縮ファイル構造解析 ===")
for archive_path in archive_files:
    if archive_path.exists():
        result = parser.read(archive_path)

        print(f"\n--- {archive_path.name} ---")
        print(f"タイプ: {result['archive_type']}")
        print(f"ファイル数: {result['file_count']}")
        print(f"ディレクトリ数: {result['directory_count']}")
        print(f"総サイズ: {result['total_size']:,} bytes")

        if result["errors"]:
            print(f"エラー: {', '.join(result['errors'])}")

        # ファイル一覧の表示（最初の5個まで）
        if result["files"]:
            print("ファイル一覧（最初の5個）:")
            for file_info in result["files"][:5]:
                print(f"  - {file_info['name']} ({file_info['size']} bytes)")
    else:
        print(f"✗ ファイルが存在しません: {archive_path}")
```
