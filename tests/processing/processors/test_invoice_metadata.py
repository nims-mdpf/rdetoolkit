"""SmartTable metadata mapping tests."""

# Equivalence Partitioning Table
# | API                                 | Input/State Partition                               | Rationale                                   | Expected Outcome                                             | Test ID     |
# | ----------------------------------- | ---------------------------------------------------- | ------------------------------------------- | ------------------------------------------------------------- | ----------- |
# | `SmartTableInvoiceInitializer.process` | 定義済み meta 列                                     | 正常に metadata.json へ書き込めることを確認 | metadata.json の constant に型変換済み値が出力される          | `TC-EP-001` |
# | `SmartTableInvoiceInitializer.process` | 既存 metadata.json に同一キーが存在                  | 上書き時に他の項目を保持できるかを確認       | 対象キーのみ上書きされ、他キーと variable は保持される       | `TC-EP-002` |
# | `SmartTableInvoiceInitializer.process` | metadata-def.json が存在しない                       | 後方互換性としてスキップされるかを確認       | metadata.json は生成されず処理は継続される                   | `TC-EP-003` |
# | `SmartTableInvoiceInitializer.process` | meta 値が空文字/NaN                                  | 無効値の境界動作を確認                       | metadata.json は生成されず値がスキップされる                 | `TC-EP-004` |
# | `SmartTableInvoiceInitializer.process` | metadata-def に定義が無いキー                        | スキーマ不一致の異常系                       | `StructuredError` が送出される                               | `TC-EP-005` |
# | `SmartTableInvoiceInitializer.process` | 型変換できない値                                     | 型バリデーションの異常系                     | `StructuredError` が送出される                               | `TC-EP-006` |
# | `SmartTableInvoiceInitializer.process` | `variable` フラグ付き定義                            | 非対応オプションの異常系                     | `StructuredError` が送出される                               | `TC-EP-007` |
# | `SmartTableInvoiceInitializer.process` | metadata-def がオブジェクト以外                      | ファイル形式異常の検証                       | `StructuredError` が送出される                               | `TC-EP-008` |

# Boundary Value Table
# | API                                 | Boundary                          | Rationale                      | Expected Outcome                                   | Test ID     |
# | ----------------------------------- | --------------------------------- | ------------------------------ | --------------------------------------------------- | ----------- |
# | `SmartTableInvoiceInitializer.process` | 値が空文字/NaN の最小入力境界     | 書き込み条件の下限を確認       | metadata.json が生成されず値がスキップされる       | `TC-BV-001` |
# | `SmartTableInvoiceInitializer.process` | 既存定義の上書き境界              | 上書き時の保持動作を確認       | 対象キーのみ上書きされ他の項目は保持される        | `TC-BV-002` |

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from rdetoolkit.exceptions import StructuredError
from rdetoolkit.processing.processors.invoice import SmartTableInvoiceInitializer


def _write_metadata_def(context, payload: dict[str, dict[str, object]]) -> None:
    context.metadata_def_path.parent.mkdir(parents=True, exist_ok=True)
    with open(context.metadata_def_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)


def _write_smarttable_row(context, columns: list[str], values: list[str]) -> None:
    csv_path = context.resource_paths.rawfiles[0]
    dataframe = pd.DataFrame([values], columns=columns)
    dataframe.to_csv(csv_path, index=False)


def _remove_metadata_files(context) -> None:
    if context.metadata_path.exists():
        context.metadata_path.unlink()


def _read_metadata(context) -> dict[str, object]:
    with open(context.metadata_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def test_process_meta_columns_writes_metadata(smarttable_processing_context) -> None:
    """複数の meta 列が metadata.json に書き込まれることを確認。"""

    processor = SmartTableInvoiceInitializer()
    context = smarttable_processing_context

    # Given: metadata-def と meta 列付き SmartTable 行
    _remove_metadata_files(context)
    _write_metadata_def(
        context,
        {
            "comment": {
                "name": {"ja": "コメント", "en": "Comment"},
                "schema": {"type": "string"},
            },
            "temperature": {
                "name": {"ja": "温度", "en": "Temperature"},
                "schema": {"type": "number"},
                "unit": "C",
            },
        },
    )
    _write_smarttable_row(
        context,
        ["meta/comment", "meta/temperature", "basic/dataName"],
        ["Smart memo", "42.5", "dataset"],
    )

    # When: SmartTable 行を処理
    processor.process(context)

    # Then: metadata.json に型変換・単位付きで記録される
    metadata = _read_metadata(context)
    assert metadata["constant"]["comment"] == {"value": "Smart memo"}
    assert metadata["constant"]["temperature"] == {"value": 42.5, "unit": "C"}
    assert metadata["variable"] == []


def test_process_metadata_overwrites_existing_value(smarttable_processing_context) -> None:
    """既存 metadata.json の定義が上書きされることを確認。"""

    processor = SmartTableInvoiceInitializer()
    context = smarttable_processing_context

    # Given: 既存 metadata.json と更新対象の meta 列
    context.metadata_path.parent.mkdir(parents=True, exist_ok=True)
    with open(context.metadata_path, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "constant": {
                    "comment": {"value": "old", "unit": "note"},
                    "other": {"value": "preserve"},
                },
                "variable": [{"cycle": {"value": "A"}}],
            },
            handle,
        )
    _write_metadata_def(
        context,
        {
            "comment": {
                "name": {"ja": "コメント", "en": "Comment"},
                "schema": {"type": "string"},
                "unit": "updated-unit",
            }
        },
    )
    _write_smarttable_row(
        context,
        ["meta/comment", "basic/dataName"],
        ["new comment", "dataset"],
    )

    # When: SmartTable 行を処理
    processor.process(context)

    # Then: 対象キーのみ更新され他の項目は保持される
    metadata = _read_metadata(context)
    assert metadata["constant"]["comment"] == {
        "value": "new comment",
        "unit": "updated-unit",
    }
    assert metadata["constant"]["other"] == {"value": "preserve"}
    assert metadata["variable"] == [{"cycle": {"value": "A"}}]


def test_process_metadata_def_missing_skips_without_error(smarttable_processing_context) -> None:
    """metadata-def.json が無い場合はスキップされることを確認。"""

    processor = SmartTableInvoiceInitializer()
    context = smarttable_processing_context

    # Given: metadata-def が存在せず meta 列のみ設定
    _remove_metadata_files(context)
    if context.metadata_def_path.exists():
        context.metadata_def_path.unlink()
    _write_smarttable_row(
        context,
        ["meta/comment", "basic/dataName"],
        ["note", "dataset"],
    )

    # When: SmartTable 行を処理
    processor.process(context)

    # Then: metadata.json は生成されず処理は完了する
    assert not context.metadata_path.exists()


def test_process_metadata_skips_empty_values(smarttable_processing_context) -> None:
    """meta 値が空文字の場合は書き込みが行われないことを確認。"""

    processor = SmartTableInvoiceInitializer()
    context = smarttable_processing_context

    # Given: 空文字の meta 値と定義済み metadata-def
    _remove_metadata_files(context)
    _write_metadata_def(
        context,
        {
            "comment": {
                "name": {"ja": "コメント", "en": "Comment"},
                "schema": {"type": "string"},
            }
        },
    )
    _write_smarttable_row(
        context,
        ["meta/comment", "basic/dataName"],
        ["", "dataset"],
    )

    # When: SmartTable 行を処理
    processor.process(context)

    # Then: metadata.json は生成されない
    assert not context.metadata_path.exists()


def test_process_metadata_key_missing_definition_raises(smarttable_processing_context) -> None:
    """定義されていない meta キーはエラーとなることを確認。"""

    processor = SmartTableInvoiceInitializer()
    context = smarttable_processing_context

    # Given: metadata-def に存在しない meta キー
    _remove_metadata_files(context)
    _write_metadata_def(
        context,
        {
            "comment": {
                "name": {"ja": "コメント", "en": "Comment"},
                "schema": {"type": "string"},
            }
        },
    )
    _write_smarttable_row(
        context,
        ["meta/missing", "basic/dataName"],
        ["value", "dataset"],
    )

    # When/Then: 未定義キーのため StructuredError が送出される
    with pytest.raises(StructuredError, match="Metadata definition not found for key: missing"):
        processor.process(context)


def test_process_metadata_type_cast_failure_raises(smarttable_processing_context) -> None:
    """型変換できない値が指定された場合のエラーを確認。"""

    processor = SmartTableInvoiceInitializer()
    context = smarttable_processing_context

    # Given: 整数型定義に非数値を指定
    _remove_metadata_files(context)
    _write_metadata_def(
        context,
        {
            "count": {
                "name": {"ja": "回数", "en": "Count"},
                "schema": {"type": "integer"},
            }
        },
    )
    _write_smarttable_row(
        context,
        ["meta/count", "basic/dataName"],
        ["invalid", "dataset"],
    )

    # When/Then: 型変換失敗で StructuredError が送出される
    with pytest.raises(StructuredError, match="Failed to cast metadata value for key: count"):
        processor.process(context)


def test_process_metadata_variable_definition_raises(smarttable_processing_context) -> None:
    """variable 定義はサポート外であることを確認。"""

    processor = SmartTableInvoiceInitializer()
    context = smarttable_processing_context

    # Given: variable フラグ付き metadata-def
    _remove_metadata_files(context)
    _write_metadata_def(
        context,
        {
            "comment": {
                "name": {"ja": "コメント", "en": "Comment"},
                "schema": {"type": "string"},
                "variable": 1,
            }
        },
    )
    _write_smarttable_row(
        context,
        ["meta/comment", "basic/dataName"],
        ["note", "dataset"],
    )

    # When/Then: variable 定義のため StructuredError が送出される
    with pytest.raises(StructuredError, match="Variable metadata is not supported for SmartTable meta mapping: comment"):
        processor.process(context)


def test_process_metadata_invalid_definition_format_raises(smarttable_processing_context) -> None:
    """metadata-def がオブジェクト以外の場合のエラーを確認。"""

    processor = SmartTableInvoiceInitializer()
    context = smarttable_processing_context

    # Given: 最上位がリストの metadata-def
    context.metadata_def_path.parent.mkdir(parents=True, exist_ok=True)
    with open(context.metadata_def_path, "w", encoding="utf-8") as handle:
        json.dump([{"comment": "invalid"}], handle)
    _write_smarttable_row(
        context,
        ["meta/comment", "basic/dataName"],
        ["note", "dataset"],
    )

    # When/Then: 不正形式のため StructuredError が送出される
    with pytest.raises(StructuredError, match="metadata-def.json must contain an object at the top level"):
        processor.process(context)

