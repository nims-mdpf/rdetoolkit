# Changelog

## バージョン一覧

| バージョン | リリース日 | 主な変更点 | 詳細セクション |
| ---------- | ---------- | ---------- | -------------- |
| v1.4.0     | 2025-10-24 | SmartTableの`metadata.json`自動生成 / LLM向けスタックトレース / CSV可視化ユーティリティ / `gen-config` | [v1.4.0](#v140-2025-10-24) |
| v1.3.4     | 2025-08-21 | SmartTable検証の安定化 | [v1.3.4](#v134-2025-08-21) |
| v1.3.3     | 2025-07-29 | `ValidationError`修正 / 再構造化用`sampleWhenRestructured`追加 | [v1.3.3](#v133-2025-07-29) |
| v1.3.2     | 2025-07-22 | SmartTableの必須項目検証の強化 | [v1.3.2](#v132-2025-07-22) |
| v1.3.1     | 2025-07-14 | Excelインボイス空シート生成の修正 / `extended_mode`厳密化 | [v1.3.1](#v131-2025-07-14) |
| v1.2.0     | 2025-04-14 | MinIO対応 / アーカイブ生成 / レポート生成 | [v1.2.0](#v120-2025-04-14) |

# リリース詳細

## v1.4.0 (2025-10-24)

!!! info "参照資料"
    - `local/develop/release_v140.md`
    - `local/develop/PR_v140.md`
    - 主なIssues: [#144](https://github.com/nims-mdpf/rdetoolkit/issues/144), [#188](https://github.com/nims-mdpf/rdetoolkit/issues/188), [#197](https://github.com/nims-mdpf/rdetoolkit/issues/197), [#205](https://github.com/nims-mdpf/rdetoolkit/issues/205), [#236](https://github.com/nims-mdpf/rdetoolkit/issues/236)

#### ハイライト
- SmartTableInvoice で `meta/` 列を `metadata.json` に自動書き込み
- LLM/AI 向けコンパクト・スタックトレース（デュプレックス出力）
- CSV 可視化ユーティリティ `csv2graph`
- 設定ファイル雛形生成コマンド `gen-config`

#### 追加機能 / 改善
- `csv2graph` API を追加。複数CSVフォーマット、方向フィルタ、Plotly HTML 出力、220件超のテストを整備。
- `gen-config` CLI を追加。テンプレート生成、日英対応対話モード、`--overwrite` オプションをサポート。
- SmartTableInvoice で `meta/` プレフィックス列を型変換付きで `metadata.json` の `constant` セクションへ反映。既存値は温存し、`metadata-def.json` がない場合はスキップ。
- 例外処理で `compact` / `python` / `duplex` を選択可能なスタックトレース出力を導入し、センシティブ情報の自動マスキングを実装。
- RDE データセットコールバックを `RdeDatasetPaths` 単一引数に集約し、旧シグネチャには非推奨警告を追加。

#### 不具合修正
- MultiDataTile モードで `ignore_errors=True` 時に `StructuredError` が停止しないバグを修正。
- SmartTable 周辺のエラーハンドリングと型注釈を整理し、処理失敗時の挙動を安定化。

#### 移行ガイド / 互換性
- 旧来の 2 引数コールバックは当面動作するが、`RdeDatasetPaths` 単一引数への移行を推奨。
- SmartTable の `meta/` 列自動書き込みを利用する場合は、各プロジェクトに `metadata-def.json` を配置する。
- スタックトレース形式の切り替えは任意。既存設定に影響はない。

#### 既知の問題
- 現時点で報告されている既知の問題はありません。

---

## v1.3.4 (2025-08-21)

!!! info "参照資料"
    - `local/develop/PR_v134.md`（相当）
    - 主なIssue: [#217](https://github.com/nims-mdpf/rdetoolkit/issues/217)（SmartTable/Invoice 検証の安定化）

#### ハイライト
- SmartTable/Invoice の検証フローを安定化

#### 追加機能 / 改善
- バリデーションと初期化フローを整理し、不要なフィールド混入と例外の出力形式を改善。

#### 不具合修正
- SmartTableInvoice の検証で発生し得た例外伝播と型注釈の不整合を解消。

#### 移行ガイド / 互換性
- 互換性を損なう変更はありません。

#### 既知の問題
- 現時点で報告されている既知の問題はありません。

---

## v1.3.3 (2025-07-29)

!!! info "参照資料"
    - `local/develop/Release_v133.md`
    - 主なIssue: [#201](https://github.com/nims-mdpf/rdetoolkit/issues/201)

#### ハイライト
- `ValidationError` 構築不備を修正し、Invoice パイプラインを安定化
- コピー再構造化向け `sampleWhenRestructured` スキーマパターンを追加

#### 追加機能 / 改善
- スキーマに `sampleWhenRestructured` を追加し、再構造化ワークフローで `sampleId` のみが必須となるシナリオを正式サポート。
- すべてのサンプル検証パターンに包括的なテストを追加し、後方互換性を担保。

#### 不具合修正
- `_validate_required_fields_only` に起因する `ValidationError.__new__()` 例外を `SchemaValidationError` へ置き換えて解消。
- `InvoiceSchemaJson` と `Properties` 生成時にオプションフィールドを明示し、mypy 型チェックエラーを修正。

#### 移行ガイド / 互換性
- 追加の設定変更は不要。既存の `invoice.json` も後方互換性が保たれる。

#### 既知の問題
- 現時点で報告されている既知の問題はありません。

---

## v1.3.2 (2025-07-22)

!!! info "参照資料"
    - `local/develop/PR_v132.md`（相当）
    - 主なIssue: [#193](https://github.com/nims-mdpf/rdetoolkit/issues/193)

#### ハイライト
- SmartTableInvoice の必須項目検証を強化

#### 追加機能 / 改善
- `invoice.json` 検証で必須項目のみを許容する仕組みを導入し、不要なフィールド混入を防止。
- 早期終了（EarlyExit）時にもバリデーションが確実に実行されるよう統合。

#### 不具合修正
- 検証過程での例外伝播と型注釈の不具合を整理し、安定性を向上。

#### 移行ガイド / 互換性
- 後方互換。`invoice.json` に不要フィールドを付与している場合は除去を推奨。

#### 既知の問題
- 現時点で報告されている既知の問題はありません。

---

## v1.3.1 (2025-07-14)

!!! info "参照資料"
    - `local/develop/Release_v131.md`
    - 主なIssues: [#144](https://github.com/nims-mdpf/rdetoolkit/issues/144), [#161](https://github.com/nims-mdpf/rdetoolkit/issues/161), [#163](https://github.com/nims-mdpf/rdetoolkit/issues/163), [#168](https://github.com/nims-mdpf/rdetoolkit/issues/168), [#169](https://github.com/nims-mdpf/rdetoolkit/issues/169), [#173](https://github.com/nims-mdpf/rdetoolkit/issues/173), [#174](https://github.com/nims-mdpf/rdetoolkit/issues/174), [#177](https://github.com/nims-mdpf/rdetoolkit/issues/177), [#185](https://github.com/nims-mdpf/rdetoolkit/issues/185)

#### ハイライト
- Excel インボイス空シート生成の不具合を修正
- `extended_mode` の厳密バリデーションを導入

#### 追加機能 / 改善
- `invoice_schema.py` に `serialization_alias` を追加し、`invoice.schema.json` の `$schema` / `$id` を正しく出力。
- `models/config.py` の `extended_mode` で許可値を限定し、検証を強化。
- `save_raw` / `save_nonshared_raw` の挙動を再設計し、テストを拡充。
- SmartTable モードに `save_table_file` オプションと `SkipRemainingProcessorsError` を追加し、処理制御を柔軟化。
- `models/rde2types.py` の型注釈を拡張し、DataFrame 警告を抑制。
- Rust 側の文字列整形・`build.rs`・CI ワークフローを整理し、品質と速度を向上。

#### 不具合修正
- Raw ディレクトリ存在チェックを追加し、コピー時の例外を防止。
- Excel テンプレート生成で `generalTerm` / `specificTerm` シート欠落を修正し、変数名の誤りを解消。
- `FixedHeaders` クラスで `orient` を明示し、将来の警告を抑制。

#### 移行ガイド / 互換性
- `extended_mode` に非許可値が設定されている場合はエラーとなるため、設定ファイルの見直しが必要。
- SmartTable モードで `save_table_file` のデフォルト挙動が変わる可能性があるため、必要に応じて設定を追加。
- `tqdm` 依存を削除したため、外部スクリプトで利用している場合は対応を検討。

#### 既知の問題
- 現時点で報告されている既知の問題はありません。

---

## v1.2.0 (2025-04-14)

!!! info "参照資料"
    - `local/develop/PR_v120.md`
    - 主なIssue: [#157](https://github.com/nims-mdpf/rdetoolkit/issues/157)

#### ハイライト
- MinIO ストレージ対応
- 成果物アーカイブ生成とレポート生成ワークフローを追加

#### 追加機能 / 改善
- `MinIOStorage` クラスを実装し、オブジェクトストレージ連携を公式サポート。
- 成果物の圧縮（ZIP / tar.gz）およびレポート生成コマンドを追加。
- オブジェクトストレージ利用手順やレポート API を含むドキュメントを拡充。

#### 不具合修正
- 依存パッケージの更新と CI 設定の近代化を実施。

#### 移行ガイド / 互換性
- 後方互換。MinIO を利用する場合はオプション依存をインストールすること。

#### 既知の問題
- 現時点で報告されている既知の問題はありません。
