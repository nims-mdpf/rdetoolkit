# Changelog

## バージョン一覧

| バージョン | リリース日 | 主な変更点 | 詳細セクション |
| ---------- | ---------- | ---------- | -------------- |
| v1.4.2     | 2025-12-18 | Invoice overwrite検証 / Excelインボイス統合 / csv2graph単一系列自動判定 / MultiDataTile空入力実行 | [v1.4.2](#v142-2025-12-18) |
| v1.4.1     | 2025-11-05 | SmartTable行CSVアクセサ / 旧`rawfiles`フォールバック警告 | [v1.4.1](#v141-2025-11-05) |
| v1.4.0     | 2025-10-24 | SmartTableの`metadata.json`自動生成 / LLM向けスタックトレース / CSV可視化ユーティリティ / `gen-config` | [v1.4.0](#v140-2025-10-24) |
| v1.3.4     | 2025-08-21 | SmartTable検証の安定化 | [v1.3.4](#v134-2025-08-21) |
| v1.3.3     | 2025-07-29 | `ValidationError`修正 / 再構造化用`sampleWhenRestructured`追加 | [v1.3.3](#v133-2025-07-29) |
| v1.3.2     | 2025-07-22 | SmartTableの必須項目検証の強化 | [v1.3.2](#v132-2025-07-22) |
| v1.3.1     | 2025-07-14 | Excelインボイス空シート生成の修正 / `extended_mode`厳密化 | [v1.3.1](#v131-2025-07-14) |
| v1.2.0     | 2025-04-14 | MinIO対応 / アーカイブ生成 / レポート生成 | [v1.2.0](#v120-2025-04-14) |

# リリース詳細

## v1.4.2 (2025-12-18)

!!! info "参照資料"
    - 対応Issue: [#30](https://github.com/nims-mdpf/rdetoolkit/issues/30), [#36](https://github.com/nims-mdpf/rdetoolkit/issues/36), [#246](https://github.com/nims-mdpf/rdetoolkit/issues/246), [#293](https://github.com/nims-mdpf/rdetoolkit/issues/293)

#### ハイライト
- `InvoiceFile.overwrite()` が辞書入力を受け付け、`InvoiceValidator` での検証と `invoice_path` へのフォールバック保存に対応。
- Excel インボイスの読み込みを `ExcelInvoiceFile` に集約し、`read_excelinvoice()` は v1.5.0 で削除予定の警告付き互換ラッパーへ移行。
- csv2graph が単一系列を自動検出し、CLI フラグの明示がない限り個別プロット生成を抑止して CLI / API のデフォルト動作を統一。
- MultiDataTile パイプラインが Excel のみ / 空ディレクトリでも実行され、必ずデータセット検証が発火。

#### 追加機能 / 改善
- `InvoiceFile.overwrite()` のシグネチャをマッピング受け取りに拡張し、`InvoiceValidator` によるスキーマ検証とインスタンス `invoice_path` へのデフォルト書き込みを追加。docstring と `docs/rdetoolkit/invoicefile.md` も更新。
- `read_excelinvoice()` を警告付きラッパーとして `ExcelInvoiceFile.read()` に委譲し、`src/rdetoolkit/impl/input_controller.py` がクラス API を直接利用するよう変更。`df_general` / `df_specific` が `None` を取り得ることをドキュメントと型定義で明確化。
- `Csv2GraphCommand` の `no_individual` を `bool | None` 型に改め、CLI では `ctx.get_parameter_source()` を用いて明示指定を検出。`docs/rdetoolkit/csv2graph.md` に新しい自動判定の仕様を追記。
- `assert_optional_frame_equal` を追加し、csv2graph CLI/API・MultiFileChecker（Excelのみ/空/単体/複数ファイル）を網羅する新規テストで退行を防止。

#### 不具合修正
- 単一系列の自動検出により空の個別グラフ生成を回避し、CLI と Python API の出力整合性を確保。
- `_process_invoice_sheet()` / `_process_general_term_sheet()` / `_process_specific_term_sheet()` が一貫して `pd.DataFrame` を返すように修正し、フレーム操作の前提崩壊を防止。
- 入力ファイルが存在しない場合に `MultiFileChecker.parse()` が `[()]` を返すよう変更し、MultiDataTile でも空ディレクトリ時に検証が必ず実行されるよう統一。

#### 移行ガイド / 互換性
- `InvoiceFile.overwrite()` には辞書を直接渡せるようになった。出力先を省略した場合はインスタンスの `invoice_path` に書き込まれ、不正なスキーマは検証エラーとして通知される。
- `read_excelinvoice()` は非推奨となり v1.5.0 で削除予定のため、`ExcelInvoiceFile().read()` への移行を推奨。
- `csv2graph` は `--no-individual` を指定しない単一系列入力でオーバーレイのみを生成する。旧挙動を維持するには `--no-individual=false` を指定し、常に抑止したい場合は `--no-individual` を付与する。
- MultiDataTile では空ディレクトリでも処理と検証が走るため、これまで静かにスキップされていたケースでも不足ファイルのエラーが表に出る。

#### 既知の問題
- 現時点で報告されている既知の問題はありません。

---

## v1.4.1 (2025-11-05)

!!! info "参照資料"
    - 対応Issue: [#204](https://github.com/nims-mdpf/rdetoolkit/issues/204), [#272](https://github.com/nims-mdpf/rdetoolkit/issues/272), [#273](https://github.com/nims-mdpf/rdetoolkit/issues/273), [#278](https://github.com/nims-mdpf/rdetoolkit/issues/278)

#### ハイライト
- SmartTable 行CSVへの専用アクセサを追加し、`rawfiles[0]` 依存の既存コールバックとの互換性を維持。
- MultiDataTile ワークフローが必ずステータスを返し、失敗モード名付きで `StructuredError` を通知するよう改善。
- CSV パーサーがメタデータ行と空データに対応し、`ParserError` / `EmptyDataError` を防止。
- グラフ可視化ヘルパー（`csv2graph`, `plot_from_dataframe`）を `rdetoolkit.graph` 直下からインポート可能に。

#### 追加機能 / 改善
- `RdeOutputResourcePath` に `smarttable_rowfile` を追加し、`ProcessingContext.smarttable_rowfile` と `RdeDatasetPaths` から参照可能に。
- SmartTable 系処理で行CSVを自動設定し、フォールバックで `rawfiles[0]` を参照した場合は移行を促す `FutureWarning` を発行。
- SmartTable の開発者向けドキュメントを更新し、行CSVの取得方法を新アクセサ基準に整理。
- `rdetoolkit.graph` パッケージで `csv2graph` / `plot_from_dataframe` を再エクスポートし、ドキュメントとサンプルのインポート例を統一。

#### 不具合修正
- MultiDataTile モードが `WorkflowExecutionStatus` を必ず返し、応答がない場合は失敗したモード名付きで `StructuredError` を送出するよう修正。
- `CSVParser._parse_meta_block()` / `_parse_no_header()` で `#` 始まりのメタデータ行を無視し、データが空のときは空の `DataFrame` を返すことで `ParserError` / `EmptyDataError` を解消。

#### 移行ガイド / 互換性
- `resource_paths.rawfiles[0]` を利用するコードは動作を継続するが、`smarttable_rowfile` へ移行しないと警告が表示される。
- `rawfiles` タプル自体は引き続きユーザー投入ファイルの一覧として利用される。先頭要素が常に SmartTable 行CSVであるという前提のみ段階的に解消する方針。
- CSV 取り込み側での追加対応は不要。今回の改修は後方互換。
- 推奨インポートは `from rdetoolkit.graph import csv2graph, plot_from_dataframe`。従来の `rdetoolkit.graph.api` パスは当面利用可能。

#### 既知の問題
- 現時点で報告されている既知の問題はありません。

---

## v1.4.0 (2025-10-24)

!!! info "参照資料"
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
