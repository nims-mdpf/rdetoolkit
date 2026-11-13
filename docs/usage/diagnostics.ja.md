# 診断コマンド (JSON)

次の 3 つのコマンドは、同じ形式のバージョン付き JSON を出力します。スクリプトやコーディングエージェントは、人間向けの文章を解析しなくても、プロジェクトの状態や失敗した実行の内容を確認できます。JSON オプションを付けない場合は、従来どおりテキストを出力します。

| コマンド | 確認する内容 | 終了コード |
| -------- | ------------ | ---------- |
| `rdetoolkit nodes lint --json` | 登録済みの node、flow、処理スケルトン | `0` 問題なし。`3` 何らかの指摘あり(警告を含む)、またはモジュールの import に失敗。`2` コマンドラインの誤り |
| `rdetoolkit doctor --format json` | 入力ファイル、設定、モード、invoice とメタデータの定義。`--ref` を付けると flow も確認 | `0` 合格(警告は可)。`1` 失敗したチェックあり。`3` `PROJECT_DIR` がディレクトリでない、または `--format` が不明。`2` コマンドラインの誤り |
| `rdetoolkit report diagnose <run_report.json> --json` | 実行レポートに記録された失敗 | `0` 診断できた(実行自体が失敗していても 0)。`1` `--fail-on-error` 指定時に失敗の記録あり。`3` レポートがない、または対応していない形式。`2` コマンドラインの誤り |

## 共通の形式

[JSON Schema](diagnostics.schema.json) で定義しています。どの出力にも次のキーがあります。

- `schema_version`: `"1"`。読み取る側はこの値を確認してください。対応しているバージョンの中で知らないキーが増えていても無視してかまいません。
- `command`: `"nodes lint"`、`"doctor"`、`"report diagnose"` のいずれか。
- `status`: エラーの指摘が 1 件でもあれば `"failed"`、警告があれば `"warning"`、それ以外は `"passed"`。これは診断結果です。終了コードは上の表のとおりコマンドごとに決まります。
- `diagnostics`: 指摘の配列。`subject`、`name` の順に並びます。各要素には `code`(エラー/警告カタログの整数、または `null`)、`severity`(`error`、`warning`、`info`)、`name`、`message`、`remediation`、`subject` があり、必要に応じて `location` が付きます。

`code` が `null` の指摘には、文書化された `name`(例: `ModuleImportFailed`)が付きます。これらのチェックのために新しいエラーコードは割り当てていません。

標準出力には UTF-8 の JSON が 1 つだけ出力されます。import したプロジェクトのモジュールが出力した文字列は標準エラー出力に回します。

## 出力しない情報

メッセージは固定文かカタログのテンプレートです。例外のメッセージ、トレースバック、引数のプレビュー(`repr`)、invoice や入力ファイルの値、設定値は、研究データや認証情報を含むおそれがあるため、どのフィールドにもコピーしません。カタログのテンプレートにある `{reason}` や `{node_id}` などのプレースホルダーは、実行時の値で埋めずにそのまま出力します。

node・flow・call の ID、モジュール名、run ID、プロジェクトまたはレポートからの相対パスは出力します。これらからプロジェクトの内容が推測できる場合もあるため、組織の外へ共有する前に内容を確認してください。どのコマンドもネットワークには何も送信しません。

## nodes lint

```shell
python3 -m rdetoolkit nodes lint --module modules.processing --json
```

node ID の重複(E2001)、不安定な node ID(E2005)、flow の予約型アノテーションの重複(E2006)、スケルトンの宣言エラー(E2101〜E2105)、インスタンスの状態を読むスケルトンのスロット(W1101、`severity` は `warning`)を報告します。型アノテーションのない引数は `MissingTypeAnnotation`、import できなかった `--module` は `ModuleImportFailed` で、どちらも `code` は `null` です。`location.source` は関数の `module:qualname` です。

lint は指定されたモジュールを import するため、モジュールのトップレベルのコードが実行されます。サンドボックスでも静的解析でもありません。node や flow の本体は呼び出しません。

テキスト出力と終了コードは変わりません。テキストモードで import に失敗した場合は、これまでどおりエラーを標準エラー出力に表示し、終了コード 3 で終わります。

## doctor

```shell
python3 -m rdetoolkit doctor --format json
python3 -m rdetoolkit doctor container --format json --ref modules.processing:pipeline
```

`PROJECT_DIR`(省略時はカレントディレクトリ)は `rdetoolkit run` と同じ規則で解決します。`data/` を含むプロジェクトルート、`data/` ディレクトリそのもの、`data/` を省いたフラットな配置のいずれにも対応します。doctor は次の順に確認します。

1. `data/inputdata/`、`data/invoice/invoice.json`、`data/tasksupport/invoice.schema.json` があること。ない場合は Runner と同じ E4003 を報告します。`tasksupport/metadata-def.json` がない場合は警告 `MetadataDefinitionMissing` です。実行自体はこのファイルがなくても成功します。
2. 有効な設定を読み込めること(`load_run_config`。失敗時は E1002)。
3. JSON ファイルを解析でき、`metadata-def.json` と `invoice.schema.json` が定義として正しいこと(E4002 / E4001)。外部の `$ref` を含むスキーマは `ExternalSchemaReference` として報告します。doctor がスキーマをダウンロードすることはありません。
4. 設定ファイルと `inputdata/`、`invoice/`、`tasksupport/` を一時ディレクトリにコピーし、代わりの flow を使って `Runner.run(validate_only=True)` を実行します。実際の実行と同じ方法でモードを決定し、invoice を検証します。設定したモードが入力ファイルの検出結果で上書きされる場合は W1001 を報告します(終了コードは 0)。コピーは最後に削除します。
5. `--ref pkg.mod:callable` を指定した場合は、モジュールを import できること(`FlowImportFailed`)と、Runner がすべての引数を注入できること(E2003、E2006、`FlowSignatureInvalid`)を確認します。flow に `prepare=` がある場合は警告 `FlowPreparationSkipped` を出します。doctor が確認したのは現在あるファイルであり、`prepare=` の実行後はモードが変わる場合があります。

doctor は flow も `prepare=` フックも呼び出さず、プロジェクトには何も書き込みません。`temp/`、ログ、実行レポート、`job.failed` は作られず、invoice も書き換えられません。`--ref` を指定すると flow のモジュールを import するため、そのトップレベルのコードは実行されます(出力は破棄し、`__pycache__` は書き込みません)。入力のコピーには `inputdata/` の大きさに応じた時間とディスク容量がかかります。

共通の形式に加えて、`data_root`(`PROJECT_DIR` からの相対パス)、`mode`(事前検証を実行できなかった場合は `null`)、`config`(`digest`、`on_iteration_error`、`repr_head` のみ)、`checks`(合否にかかわらず各チェックの `check_id`、`status`、`path`)を出力します。指摘には `check_id` と、ファイルに関するものであれば `location.path` が付きます。

## report diagnose

```shell
python3 -m rdetoolkit report diagnose data/logs/run_report_<run_id>.json --json
```

失敗は実行レポートからだけ読み取ります。`failures` の各要素には `iteration_index`、`node_id`、`call_id`(記録がない場合はそれぞれ `null`。例: node が 1 つも実行される前の失敗)、`code`、`name`、`message`、`remediation`、`source: "report"` があります。v2 カタログのコードにはカタログの名前と対処方法が付きます。それ以外のコード(v1 の `StructuredError` のコードを含む)は、番号はそのままで名前を `ExecutionError` とします。ここに出るのは call log に記録された実際の呼び出しであり、推定した依存関係や原因の断定ではありません。

`evidence` はレポートの隣にあるファイルの状態を示すだけで、失敗を追加することはありません。

- `evidence.iterations[].iteration_detail`: `path`(`iterations/iteration_<index>.json`)、`state`、`flags`。このファイルは実行のたびに同じ番号で上書きされるため、`schema_version` が `"1"` で、`run_id` と `iteration_index` がレポートと一致する場合だけ `verified` になります。それ以外の状態は `missing`、`corrupt`、`unverified`(バージョンが付く前に書かれたファイル)、`unsupported`、`mismatched`(別の実行のファイル)、`truncated` です。
- `evidence.events`: `path`(`events_<run_id>.jsonl`)、`flags`、`verified_records`。別の実行や別のイベントバージョンのレコードは数えません。`run.completed` のないログは `incomplete`、W1002 のレコードがあれば `truncated` です。

どのフラグも `SupportingEvidence<Flag>`(例: `SupportingEvidenceMismatched`)という名前の警告としても出力します。レポートを移動するときは、`iterations/` ディレクトリとイベントログも一緒に移動してください。出力全体の形式は[診断結果のスキーマ](diagnostics-report.schema.json)を参照してください。

このリリースから、`iterations/iteration_<index>.json` には既存のフィールドに加えて `schema_version: "1"` と `run_id` が入ります。実行レポート(`schema_version: "2"`)、イベント、call record の形式は変わりません。

## 関連項目

- [コマンドライン操作](cli.ja.md)
- [エラーカタログ](../rdetoolkit/error_catalog.md)
