# 診断と従来トレースバックの互換性

v2 で失敗を調べるときは、コーディングエージェントを使うかどうかにかかわらず
`rdetoolkit report diagnose data/logs/run_report_<run_id>.json --json` から始めます。
推奨する診断の入口はこれ 1 つです。バージョン付きの出力は、失敗した iteration、
node と call の ID、カタログのコードと対処方法を示し、例外メッセージ、ソース行、
ローカル変数、環境変数の値、入力ファイルのパスは転載しません。形式と制限は
[診断コマンド](../diagnostics.ja.md) を参照してください。

RunReport 本体、イベント、コールログ、`report show`、stderr、`job.failed` は、
機密情報を含み得るローカル調査用の出力です。`report diagnose` の出力は新しいシリアライズの境界であり、
既存の互換出力を書き換えません。診断を LLM、テレメトリー、issue tracker に送る rdetoolkit のコマンドはありません。
外部共有前には利用者自身が内容を確認してください。

## 互換性の棚卸しと方針

次の v1 インターフェースは v2 でも維持します。公開シンボルの削除や名前空間の移動、
実行時の非推奨警告は追加しません。`<STACKTRACE>` をエージェント向けの主形式とする
推奨だけを廃止します。対処方法の定義元は引き続き単一の `ERROR_CATALOG` です。

| インターフェース・入口 | 方針 | 維持する動作 |
|---|---|---|
| `rdetoolkit.errors.handle_exception` | 維持・v1 互換として凍結 | `StructuredError` を返す。明示的な `Config.traceback`、環境設定、従来 Python 形式の順で選択 |
| `errors.handle_generic_error`、`handle_and_exit_on_structured_error`、`format_simplified_traceback` | 維持・v1 互換として凍結 | stderr、例外ラップ、終了動作を維持。生のメッセージ、パス、ソースを含み得る |
| `rdetoolkit.traceback.formatter.CompactTraceFormatter` と `errors.CompactTraceFormatter` プロキシ | 維持・v1 互換として凍結 | `<STACKTRACE>` の `CFG v=1`、`E`、任意の `T`、`F`、`RC` 行。v2 の対処カタログを重複実装しない |
| `rdetoolkit.traceback.masking.SecretsSanitizer` | 維持・v1 互換として凍結 | 変数名ベースのマスキング、追加パターン、値の表現・切り詰め |
| `rdetoolkit.models.config.TracebackSettings`、`Config.traceback` | 維持・v1 互換として凍結 | `compact`、`python`、`duplex` と従来のフィールド・既定値 |
| `config.get_traceback_settings_from_env`、`errors.get_traceback_settings_from_env` | 維持・v1 互換として凍結 | `TRACE_VERBOSE` / `TRACE_FORMAT` の既存制御 |
| `errors.pyi`、`traceback/{formatter,masking}.pyi`、`models/config.pyi`、`config/__init__.pyi` | 維持 | 既存のインポート名とシグネチャ |
| v1 コールバック `workflows.run(custom_dataset_function=...)` | 維持 | トレースバック設定と優先順位。新たな警告なし |
| v2 の主交換形式としての `<STACKTRACE>`、LLM / バグ報告の自動送信例 | 推奨を廃止 | `report diagnose --json` を使用し、意図的な外部共有前に確認 |
| 公開トレースバック API | 削除なし | 削除には別途互換性の判断と移行手順が必要 |

フォーマッタ、マスキング、設定のインポート先は既存モジュールのままです。
このトレースバックを出力するのは v1 コールバック入口(`workflows.run(custom_dataset_function=...)`)だけで、
v2 flow 入口は出力しません。プロジェクト直下の v2
`rdeconfig.yaml` は `traceback:` を拒否し、既存の v1 設定ファイルでは引き続き使えます。
[移行時の互換性表](../../migration_v1_to_v2.md) も参照してください。

## ローカル調査用の設定

コンパクト形式は既定で無効です。`TracebackSettings()` の既定値は
`enabled=False`、`format="duplex"`、`include_context=False`、
`include_locals=False`、`include_env=False`、ローカル変数の値ごとの
UTF-8 サイズ上限 `max_locals_size=512` バイトです。明示的な設定は環境変数より優先します。

| 制御 | 意味 |
|---|---|
| `TRACE_VERBOSE` 未設定・空文字 | 環境設定なし。従来トレースバックのフォールバックは残る |
| `TRACE_VERBOSE=off`、`false`、`disable`、`disabled`（大文字小文字不問） | コンパクト形式を無効化。Python トレースバックの停止・匿名化ではない |
| `TRACE_VERBOSE=context,locals,env` | それぞれソース、ローカル変数、実行環境情報を明示的に含める |
| `TRACE_FORMAT=compact`、`python`、`duplex` | 形式を選択。有効時の既定値は `duplex` |

`include_env` は Python と OS の情報を追加するもので、環境変数全体のダンプではありません。
ソースとローカル変数は別々の明示設定ですが、両方を無効にしても例外メッセージや
ファイル名の機密情報は除去されません。verbose 時の完全な Python トレースバックは
`__cause__`、`__context__`、`raise ... from None` による表示制御を維持します。
簡略化された呼び出し経路とコンパクト形式の `RC` は従来の要約であり、完全な原因解析ではありません。
`RC` はフレームのヒューリスティックと現在の例外文を使い、簡略化された呼び出し経路は
Python の完全表示で抑制された context のフレームも含み得ます。必要ならローカルで
Python の例外連鎖を確認してください。

## 情報開示の限界

`SecretsSanitizer` は値を表現する前に変数**名**を照合します。再帰的な匿名化ではなく、
一般的な名前の値にネストされた認証情報は残り得ます。例外メッセージ、ソース行、ファイル名、
任意の `repr` 出力はこのパターンで安全になりません。正規表現とサイズ制限は一部の露出を
減らす補助にすぎず、研究データ、認証情報、個人情報が除去された証明にはなりません。
従来の値ごとの上限は出力全体のサイズ上限でもありません。

詳細トレースバックと完全な再現 ZIP は、内容を意図的に確認するまでローカルに保管してください。
`report diagnose --json` を優先し、構造的なファイル情報が必要なら `repro export --manifest-only` を使います。
ダイジェストやサイズから既知ファイルを識別できる場合があるため、メタデータのみの ZIP も匿名とは
限らず、実行の再現にも使えません。どちらの ZIP も外部サービスへ自動添付しないでください。

## 関連ドキュメント

- [診断コマンド](../diagnostics.ja.md)
- [repro: 実行の書き出しと再実行](../cli.ja.md)
- [設定](../config/config.ja.md)
- [エラーハンドリング](errorhandling.ja.md)
