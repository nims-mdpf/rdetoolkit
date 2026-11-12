# Runner

Runner は、RDE の構造化処理に必要な手続きをすべて引き受ける実行枠です。設定の読み込み、
モードの判定、送り状とスキーマの検証、データタイルごとのディレクトリ作成、成果物の検証、
`job.failed` と RunReport の出力は Runner が行います。ユーザーのフローは、この手続きの
1 ステップとしてデータタイルごとに呼ばれる関数にすぎません。

## ライフサイクル

| 段階 | 内容 |
|------|------|
| 1. 設定の読み込み | `rdeconfig.yaml` などを探索し、`RdeConfig` を確定します |
| 2. モードの判定 | invoice / ExcelInvoice / SmartTable / MultiDataTile / RDEFormat を決めます |
| 3. 事前検証 | 送り状・`invoice.schema.json`・`metadata-def.json` を検証します |
| 4. データタイルの反復 | タイルごとにディレクトリを作り、予約型を注入してフローを呼びます |
| 5. 事後検証 | 生成された成果物の整合を確認します |
| 6. 終了処理 | RunReport・イベントログを書き、失敗時は `job.failed` を書きます |

`rdetoolkit run --flow ... --validate-only` は 1〜3 だけを実行し、フローは呼びません。

## 実行の入口

| 入口 | 受け取るもの | 戻り値 / 結果 |
|------|-------------|---------------|
| `workflows.run(flow=...)` | フロー関数、または `ProcessingTemplate` のサブクラス | `RunReport` |
| `rdetoolkit run --flow pkg.mod:attr` | 同上(文字列で指定) | RunReport の JSON と終了コード |
| `workflows.run(custom_dataset_function=...)` | v1 のコールバック関数 | v1 と同じ JSON 文字列 |
| `rdetoolkit run module::attr` | v1 のコールバック関数 | v1 と同じ |

どの入口も同じ Runner で実行されます。`flow` と `custom_dataset_function` を同時に
渡すと実行前に `RdeConfigError` になります(CLI では `TARGET` と `--flow` のどちらか一方を
指定しないと終了コード 3)。

## 設定の探索

`config` を渡さない場合、Runner は次の順に設定ファイルを探します。

1. プロジェクト直下の `rdeconfig.yaml`
2. プロジェクト直下の `pyproject.toml`(`[tool.rdetoolkit]`)
3. data ルートの `tasksupport/rdeconfig.yaml`・`tasksupport/rdeconfig.yml`・`tasksupport/pyproject.toml`(v1 形式として解釈)

`workflows.run(flow=..., config=...)` には `RdeConfig` か辞書を渡せます。辞書は探索した設定の
上に再帰的に上書きされ、`RdeConfig` は設定全体として扱われます。探索結果を確認してから
実行したい場合は `rdetoolkit.runner.load_run_config()` を使います。v2 の設定は未知のキーを
受け付けないため、キーの打ち間違いは読み込みの時点で `E1002` になります。

## モードとデータタイル

| モード | 反復の単位 | タイル数 |
|--------|-----------|----------|
| invoice | 1 回の登録 | 1 |
| ExcelInvoice | Excel 送り状の各行 | 行数 |
| MultiDataTile | `inputdata/` の各ファイル | ファイル数 |
| SmartTable | テーブルの各行 | 行数 |
| RDEFormat | 既存の RDE 形式データ | 1 |

モードは「SmartTable のファイル > ExcelInvoice のファイル > 設定値」の順で決まります。
設定の `system.extended_mode` とファイルの検出結果が食い違った場合は、警告
`W1001 ModeOverriddenByFileDetection` が RunReport と標準エラー出力に出ます。

フローは反復を意識する必要はありません。タイル番号などが必要な場合は、`IterationInfo` 型の
引数を宣言すると注入されます([フロー](flow.md#reserved-types-and-dependency-injection))。

## 失敗の扱いと終了コード

`execution.on_iteration_error` で、あるタイルが失敗したときの振る舞いを選べます。

| 値 | 振る舞い | 既定になる入口 |
|----|---------|---------------|
| `continue` | 残りのタイルを続けて処理する | flow の入口 |
| `fail_fast` | 最初の失敗で止める | v1 のコールバック入口 |

run 全体の状態と CLI の終了コードは次のとおりです。

| 状態 | 意味 | 終了コード | `job.failed` |
|------|------|-----------|--------------|
| `success` | すべてのタイルが成功 | 0 | 書かない |
| `partial` | 一部のタイルが失敗(`continue` のときのみ) | 2 | 書かない |
| `failed` | run が失敗 | 1 | 書く |
| (引数の誤り) | CLI の使い方の誤り、フローを解決できない | 3 | — |

タイルが失敗すると、失敗したタイル数が標準エラー出力に出ます(例: `1 iteration(s) failed`)。
どのタイルが失敗したかは RunReport の `iterations[*].status` で確認できます。

<!-- test: runner-error-policy -->
```python
from rdetoolkit import flow, node, workflows
from rdetoolkit.types import InputPaths


@node(id="docs.runner.check")
def check(paths: InputPaths) -> None:
    if any(path.name == "bad.txt" for path in paths.rawfiles):
        raise ValueError("bad input")


@flow(id="docs.runner.per_file")
def per_file(paths: InputPaths) -> None:
    check(paths)


mode = {"system": {"extended_mode": "MultiDataTile"}}
report = workflows.run(flow=per_file, config=mode)
assert (report.status, report.exit_code) == ("partial", 2)
assert [tile["status"] for tile in report.iterations] == ["failed", "completed"]

report = workflows.run(flow=per_file, config={**mode, "execution": {"on_iteration_error": "fail_fast"}})
assert (report.status, report.exit_code) == ("failed", 1)
assert report.error["code"] == 3001
```

この例は `inputdata/` に `bad.txt` と `good.txt` を置いた `rdetoolkit init` のプロジェクトで
実行します。MultiDataTile モードではファイル名の順にタイルが作られます。

## `job.failed`

run が `failed` で終わると、Runner は v1 と同じ形式で `data/job.failed` を書きます。

<!-- illustration: runner-job-failed -->
```text
ErrorCode=3001
ErrorMessage=Node execution failed for call docs.runner.check#1: bad input Remediation: ...
```

- rdetoolkit が検出したエラーは[エラーカタログ](../rdetoolkit/error_catalog.md)のコードを使います
  (1xxx 設定、2xxx 登録・宣言、3xxx 実行時、4xxx 検証、5xxx 内部エラー)。カタログのすべての
  エラーは対処法(`remediation`)を持ち、メッセージに含まれます。
- ユーザーコードが送出した v1 の `StructuredError(emsg, ecode)` は、そのコードとメッセージが
  そのまま `job.failed` に書かれます。

## RunReport と実行記録

Runner は run ごとに `data/logs/` へ次のファイルを書きます。

| ファイル | 内容 |
|----------|------|
| `run_report_<run_id>.json` | RunReport(状態、モード、設定のダイジェスト、タイルごとの呼び出し記録、警告、エラー) |
| `events_<run_id>.jsonl` | `run.started` / `iteration.completed` / `node.failed` などのイベント |
| `iterations/iteration_<n>.json` | タイルごとの結果 |

<!-- illustration: runner-report -->
```json
{
  "schema_version": "2",
  "run_id": "550956f7318c414eb15a5f9175309f22",
  "status": "success",
  "flow_id": "quickstart.pipeline",
  "mode": "invoice",
  "config_digest": "sha256:...",
  "iterations": [
    {
      "index": 0,
      "status": "completed",
      "node_calls": [
        {"call_id": "quickstart.normalize#2", "node_id": "quickstart.normalize", "seq": 2, "status": "completed", "duration_ms": 1.45}
      ],
      "error": null
    }
  ],
  "warnings": [],
  "error": null
}
```

RunReport は `rdetoolkit report show`(要約)、`rdetoolkit graph`(Call Sequence)、
`rdetoolkit repro export`(RunReport・入力・設定のアーカイブ)で利用できます。
v1 の戻り値と同じ JSON が必要な場合は `report.to_legacy_statuses()` を使います。

## Runner が提供しないもの

rdetoolkit v2 は RDE 構造化処理のためのバッチハーネスであり、汎用のワークフローエンジンでは
ありません。スケジューリング、ノードの並列実行、途中からの再開、結果のキャッシュは提供しません。
処理をやり直したいときは run を再実行してください。

## 関連ページ

- [フロー](flow.md) — Runner が呼び出す関数と依存性注入
- [CLI リファレンス](../reference/cli.md) — `run` / `report` / `graph` / `repro`
- [ADR-023](../adr/0023-single-runner-contract-compat.md) — v1 互換と単一 Runner
