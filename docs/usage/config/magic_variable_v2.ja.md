# v2 の補間仕様

このページでは、`run(flow=...)` に適用される補間仕様バージョン 1 を説明します。
従来の `run(custom_dataset_function=...)` エントリと公開 API
`invoicefile.apply_magic_variable` は、真偽値の扱い、空値の扱い、参照元の選択について
既存の挙動を維持します。

## ポリシーと移行

v2 では `system.magic_variable` を省略すると `auto` になります。対象フィールドの文字列に
`${...}` が含まれている場合だけ、厳密な構文解析と解決が行われます。`${...}` を含まない
文字列は変更されません。明示的に指定した真偽値はこれまでどおり優先されます。`true` は
`enabled`、`false` は `disabled` を選びます。`disabled` では不正な式も含めてリテラルの
まま残し、対象フィールドにプレースホルダが残っている場合は診断を出します。

明示的なオプションは `custom.interpolation` に書きます。

```yaml
custom:
  interpolation:
    policy: auto
    missing: error
```

`policy` は `auto`、`enabled`、`disabled` のいずれかです。`missing` は `error` または
`omit` です。未知のオプションや、真偽値フラグと policy の矛盾する組み合わせはエラーに
なります。`magic_variable: false` を含む設定を移行する場合は、そのフラグを削除して
`auto` を使うか、上記の名前空間による明示指定に置き換えてください。

設定のフィンガープリントは、マジック変数フラグの省略と明示的な `false` を区別します。
repro export は、明示的な無効化を YAML の往復でも保持します。このポリシー対応以前に
作成したフィンガープリントは、フラグを省略した設定では値が変わることがあります。
repro export の前に、GA 前に作成したレポートを再生成してください。

## 文法と参照スコープ

| 式 | 参照元 |
| --- | --- |
| `${filename}` | タイルに一意に対応する raw 入力のファイル名 |
| `${invoice:basic:field}` | 元の invoice の basic 直下のフィールド |
| `${invoice:custom:field}` | 元の invoice の custom 直下のフィールド |
| `${invoice:sample:names}` | 元の invoice の試料名(順序を保持) |
| `${invoice-original:basic:field}` | 元の invoice を明示するスコープ。custom と sample の形式も使えます |
| `${invoice-current:basic:field}` | 現在のタイルの invoice。custom と sample の形式も使えます |
| `${metadata:constant:key}` | 現在のタイルのメタデータ定数の `value` |

元の invoice は、タイルを構築する前に取得した不変の値です。現在の invoice とメタデータは、
flow の実行後、補間の直前に取得します。すべてのフィールドはこれらのスナップショットに
対して解決されます。先に行った置換や先のタイルの結果が、後の置換の入力になることは
ありません。解決後の文字列が再帰的に解析されることもありません。

invoice とメタデータの式は、raw 添付ファイルがなくても使えます。filename は、適用される
各モードで raw 入力がちょうど 1 つ必要です。raw 入力が 0 個または複数のとき、エラーに
なるのは filename を参照した場合だけです。入力をまとめて扱う場合は、一意の入力を選ぶか、
invoice やメタデータの識別子を明示的に使ってください。SmartTable の行 CSV は raw 添付
ファイルではないため、filename の参照元にはなりません。

式の外側の空白は無視されます。内側の空白、余分なセグメント、空のキー、入れ子の式、未知の
参照元は不正です。キーには Unicode の文字・数字、`_`、`-` を使えます。キーはマッピングの
直下のキーとして扱われます。ドット、スラッシュ、角括弧、属性参照、実行可能な式は
サポートしません。`$${filename}` はリテラルの `${filename}` になります。式の外にある
通常の波括弧はそのまま残ります。閉じていない開始記号はエラーです。エスケープした開始記号で
閉じ括弧がない場合もエラーになります。

テンプレートは、対象フィールドごとに 16,384 文字、式 128 個までです。展開後のフィールドは、
省略と区切り文字の正規化を行った後で 16,384 文字までです。途中の長さが上限を超えても、
最終的な値が有効であれば拒否されません。`basic.dataName` にはさらに 1〜4,096 文字の制限が
あり、制御文字は使えません。これらはバージョン管理されたライブラリの上限です。invoice
スキーマでより厳しい制約を課すことができます。

エラーカタログでは、4005 と 4006 を SmartTable のマッピングと入力計画に予約しています。
補間の構文・ポリシーのエラーは 4009、参照元が利用できない場合は 4010 です。これらは、
マージされなかった GA 前のドラフトで衝突していた番号を置き換えるものです。出力の検証は
引き続き 4007、ルールマッピングの検証は 4008 です。

## 対象フィールドと欠損値

出力対象は、値が文字列である `basic.dataName` と `basic.description` だけです。
それ以外のフィールド、オブジェクト、配列、識別子、文字列以外の値は変更されません。
これは明示的な許可リストであり、JSON 全体を再帰的に補間するものではありません。
後続の任意の特徴量記述ステージが description を追記することがあります。

参照元がない、キーがない、null、空文字列、空リストは、それぞれ別の診断理由になります。
既定ではいずれもエラーです。`missing: omit` を指定すると、これらの値を明示的に省略します。
省略に伴って連続したアンダースコアをまとめるのは、両隣がテンプレートのリテラルである
場合だけです。参照元の文字列は、先頭や末尾のアンダースコアも含めて常にそのまま保持します。
名前が空になった場合はエラーのままです。

0 と false はスカラー値として扱い、`0` と `False` に整形します。Unicode のコードポイントは
NFC や NFKC で書き換えずに保持します。試料名は順序を保持し、空でない文字列を `_` で
連結します。文字列以外の要素があるとエラーです。オブジェクトとリストはスカラーとして
置換できません。有限でない数値はエラーです。パスのように見える値もラベルとして扱い、
補間がファイルシステムのパスとして開くことはありません。

flow の補間が有効な場合、最初の invoice 検証では、対象となるテンプレートの出力先に限り、
文字列値への直接の制約(`pattern`、`enum`、`const`、`format`、`minLength`、`maxLength`)
の検査を後回しにします。必須フィールド、型、その他の出力先は flow の前に検査します。
集約的な制約や祖先の制約は、この段階でも厳密に検査します。補間が無効な場合、RDEFormat、
`Runner.pre_validate()` を直接呼び出した場合は、値の検証をすべて行います。行単位のモードと
従来のコールバックは、既存の検証タイミングを維持します。

変更された invoice は、アトミックに置き換える前に、標準の invoice 契約と
`invoice.schema.json` に対して検証されます。式、スキーマ、書き込みのいずれかが失敗した
場合、invoice は変更されません。エラーの対処方法は、自動生成される
[エラーカタログ](../../rdetoolkit/error_catalog.md) を参照してください。書き込み失敗後の
後片付けも失敗した場合は、元の秘匿化済みエラーが保持されます。後片付けはベストエフォート
のため、一時ファイルが残ることがあります。

## 登録モード

| モード | 補間ステージ |
| --- | --- |
| Invoice | サムネイルと構造化出力の後、特徴量記述の前 |
| ExcelInvoice | サムネイル、構造化出力、特徴量記述の前 |
| MultiDataTile | サムネイル、構造化出力、特徴量記述の前 |
| SmartTable | 登録行ごとに Invoice と同じ順序。添付ファイルのない行も含みます |
| RDEFormat | 対象外。整形済みの登録成果物では補間を行いません |

元のテーブルを含む SmartTable の任意のタイルは、完了済みとして扱われ、flow と補間
ステージを行いません。従来の成果物の順序は維持されます。

## 純粋なプレビュー

`rdetoolkit.domain.magic` は `ResolutionContext`、`MagicOptions`、`resolve_invoice`、
`preview_invoice` を提供します。コンテキストは不変の JSON スナップショットを保持します。
プレビューは、ファイルを書き込まず、置換後の値も返さずに、バージョン付きの決定的な診断を
返します。診断には、出力先、式のオフセット、参照スコープとパス、タイル番号、状態、
対処方法が含まれます。値は秘匿化されます。

```pycon
>>> from rdetoolkit.domain.magic import ResolutionContext, preview_invoice, resolve_invoice
>>> context = ResolutionContext.from_sources(
...     original_invoice={"custom": {"batch": "B-1"}},
...     current_invoice={"basic": {"dataName": "${invoice:custom:batch}"}},
... )
>>> resolve_invoice(context)["basic"]["dataName"]
'B-1'
>>> preview_invoice(context).diagnostics[0].status
'resolved'

```

Runner の `--validate-only` は、元の invoice にあるテンプレートの構文を検査し、タイルごとの
参照元の解決は後回しになることを報告します。メタデータを作るために flow を実行することは
ありません。Runner の検証自体は通常のログやレポートを書き込みます。ファイルシステムを
変更しないことが必要な場合は、純粋なプレビュー API を使ってください。

### 後回しにする参照元

`preview_invoice` は `deferred_scopes` を受け取ります。これは、まだ参照元が利用できない
式のスコープ(`invoice`、`invoice-original`、`invoice-current`、`metadata`、`filename`)
の集合です。後回しにしたスコープの式は `deferred` の診断(理由 `deferred_source`、
エラーコードなし)になり、参照元は読み込まれません。後回しの式を含むフィールドは、
最終的な値がわからないため出力の検査を行いません。また、後回しの診断が 1 つでもある間は
スキーマ検証も行いません。未知のスコープ名を渡すと `ValueError` になります。
`resolve_invoice` が後回しにすることはありません。

```pycon
>>> from rdetoolkit.domain.magic import ResolutionContext, preview_invoice
>>> context = ResolutionContext.from_sources(
...     original_invoice={},
...     current_invoice={"basic": {"dataName": "${metadata:constant:thickness}"}},
... )
>>> preview_invoice(context, deferred_scopes=frozenset({"metadata"})).diagnostics[0].status
'deferred'

```

### `rdetoolkit run --explain`

explain 出力の `magic_preview` は、計画されたすべてのタイルに同じプレビューを適用します。
使うのは flow 実行前のスナップショット、つまり `invoice/invoice.json` とタイルの入力
ファイル名で、メタデータは使いません。ファイルの書き込み、ユーザーコードの読み込み、
参照元の値の出力は行いません。

検査するのは、テンプレートの構文、参照元の解決(`filename` の一意性を含む)、値の正規化、
出力の上限(`dataName` の妥当性と長さ)です。全体の状態は `previewed`、`disabled`
(ポリシーで無効)、`no_templates`、`not_applicable`(RDEFormat には補間ステージがない)の
いずれかです。各タイルは `previewed`、`skipped`(完了済み、またはモードにより省略)、
`deferred`(invoice が実行時にテーブルの行から作られる)のいずれかです。メタデータは flow が
`metadata.json` を作るため、メタデータの式は常に `deferred` になります。

invoice スキーマ、`InvoiceValidator` の標準検査とアプリケーション固有の検査、flow や
準備ステップによる変更は検査**しません**。これらは出力の `not_checked` に列挙されます。
そのため、プレビューですべて解決できても、登録が成功するとは限りません。`preview_invoice`
に `schema=` を渡すと、純粋なスキーマ検査が追加されるだけです。最終的な検証は引き続き
`InvoiceValidator` が行います。

`RuleBasedReplacer` は、ドット区切りの代入のための別の互換 API です。`{}` を含め、
`mapping_rules` を明示的に渡すと、保存済みのルールを置き換えます。呼び出しが成功した場合は、
文書化されている参照元の変更がそのまま行われます。置換値がない場合は空文字列になります。
不正な祖先パスや、親子で重なる代入は、何も変更する前にエラーになります。この API は
引き続き公開されており、インポートできます。
