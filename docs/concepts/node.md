# ノード

ノードは「呼び出しが記録される、ただの関数」です。node デコレータを付けた関数は
そのまま Python 関数として呼び出せ、pytest からも直接テストできます。

## node デコレータの役割

node デコレータが行うのは次の 3 つだけです。

1. **登録** — import 時にノードの静的メタデータ(NodeSpec)をノードレジストリに登録します。
   登録されたノードは `rdetoolkit nodes list` で一覧できます。
2. **記録** — Runner が実行中のときに限り、呼び出しごとに実行記録(コールログ)を残します。
   Runner の外で呼んだ場合は何も記録されず、普通の関数として動きます。
3. **実行時型チェック(任意)** — 設定で有効にした場合だけ、引数と戻り値を型注釈と照合します。

<!-- test: node-basic -->
```python
from rdetoolkit import node


@node(id="docs.concepts.scale", tags=["math"], version="1.0.0")
def scale(values: list[float], factor: float = 2.0) -> list[float]:
    """Multiply every value by a factor."""
    return [value * factor for value in values]


assert scale([1.0, 2.0]) == [2.0, 4.0]
assert scale([1.0], factor=3.0) == [3.0]
```

デコレータの引数はすべて省略でき、括弧なしでも付けられます。

| 引数 | 既定値 | 意味 |
|------|--------|------|
| `id` | `"モジュール名.関数名"` | ノード ID。レジストリと実行記録での名前 |
| `tags` | なし | `nodes list` などで使う分類用のタグ |
| `version` | `"0.0.0"` | ノード実装のバージョン(記録とドキュメント用) |
| `idempotent` | `False` | 同じ入力で同じ結果を返すことの宣言(記録用) |

## ノード ID

- `id` を指定した場合はその値、省略した場合は `"{モジュール名}.{関数の qualname}"` が ID になります。
- 同じ ID の二重登録は import 時に `E2001 DuplicateNodeId`(`RdeRegistryError`)になります。
- 関数内で定義したローカル関数は import のたびに ID が安定しないため、`nodes lint` が
  `E2005 UnstableNodeId` として報告します。ノードはモジュールのトップレベルで定義してください。

<!-- test: node-duplicate -->
```python
from rdetoolkit import node
from rdetoolkit.errors import RdeRegistryError


@node(id="docs.concepts.unique")
def first(value: int) -> int:
    return value


try:

    @node(id="docs.concepts.unique")
    def second(value: int) -> int:
        return value

except RdeRegistryError as error:
    code = error.code

assert code == 2001
```

## ノードを調べる

ノードを定義したモジュールを `--module` で読み込ませると、CLI から一覧・詳細・静的検査が
行えます(`concepts_nodes.py` は上の `scale` を定義したファイルです)。

<!-- test: node-inspect -->
```bash
$ python -m rdetoolkit nodes list --module concepts_nodes
$ python -m rdetoolkit nodes describe docs.concepts.scale --module concepts_nodes
$ python -m rdetoolkit nodes lint --module concepts_nodes
```

<!-- illustration: node-describe-output -->
```text
id: docs.concepts.scale
name: scale
input_schema: {'values': {'type_name': 'list[float]', 'has_default': False, 'default_repr': None}, 'factor': {'type_name': 'float', 'has_default': True, 'default_repr': '2.0'}}
output_schema: ('list[float]',)
tags: ('math',)
version: 1.0.0
idempotent: False
source_location: concepts_nodes:scale
```

`nodes lint` は型注釈のない引数や不安定な ID などを報告し、問題があれば終了コード 3 を返します。
CI に組み込むと、登録の誤りを実行前に検出できます。

## 実行記録(コールログ)

Runner の中でノードが呼ばれるたびに、次の情報が 1 件ずつ記録されます。

| 項目 | 内容 |
|------|------|
| `call_id` | `"{ノード ID}#{通番}"`。同じノードを何度呼んでも区別できます |
| `seq` | run 全体での呼び出し順(決定的) |
| `iteration_index` | 呼び出しが属するデータタイル |
| `parent_flow` | 呼び出し元の flow の ID |
| `status` / `duration_ms` / `error` | 成否・所要時間・失敗時のエラー |
| `inputs` / `outputs` | 引数と戻り値の**型の要約**(型名と `repr` の先頭) |

記録されるのは「いつ・何が・どの順で・何回・何ミリ秒かかり・どこで失敗したか」までです。
値の同一性は追跡しません。そのため `rdetoolkit graph` が描くのは呼び出しの順序(Call Sequence)
であり、データフローの図ではありません([ADR-022](../adr/0022-call-log-without-lineage.md))。

`repr` の先頭を記録したくない場合は、`rdeconfig.yaml` で無効にできます。

<!-- test: node-config -->
```yaml
provenance:
  repr_head: "off"      # "on" (default) | "off"
  repr_head_len: 80
execution:
  type_check: "warn"    # "off" (default) | "warn" | "strict"
```

!!! warning "`on` / `off` は引用符で囲む"
    YAML では引用符のない `on` / `off` が真偽値として読まれるため、設定の読み込みが
    `E1002 ConfigLoadFailed` で失敗します。`"on"` / `"off"` のように文字列として書いてください。

`type_check` を `warn` または `strict` にすると、ノードの呼び出し境界で引数・戻り値を
型注釈と照合し、不一致を `E3002 NodeTypeMismatch` として扱います。既定の `off` では
検査のコストはかかりません。

## flow とノードの境界

- ノードの中では依存性注入は行われません。ノードが出力先などを必要とする場合は、flow が
  引数として明示的に渡します。これにより、データの流れは常にコード上に見えます。
- ノードの中で発生した例外は `RdeExecutionError`(コード 3001)に包まれ、どの呼び出し
  (`call_id`)で失敗したかが RunReport と `job.failed` に残ります。元の例外は `__cause__`
  にそのまま保存されます。

## 組込ノード

rdetoolkit が提供する処理は、すべて組込ノード(`rdetoolkit.nodes`)として登録されています。
成果物の保存は組込ノードを使うのが正規の方法で、保存した事実が実行記録に残ります。

| 分類 | ノード |
|------|--------|
| 読み込み | `read_text`, `read_csv_with_header`, `read_excel`, `read_excel_fills`, `read_json`, `unzip_inputs` |
| 構造化データの保存 | `save_csv`, `save_json`, `save_text`, `save_invoice` |
| メタデータ | `parse_invoice_meta`, `build_meta`, `save_meta` |
| 画像 | `to_png`, `to_jpeg`, `make_thumbnail`, `save_main_image`, `copy_raw` |
| グラフ | `plot_lines`, `plot_scatter`, `save_figure` |

組込ノードはユーザーが書くノードと同じ仕組みで動き、特別な権限は持ちません。各ノードの
引数は [API リファレンス](../rdetoolkit/v2/nodes.md) を参照してください。

v1 のハンドラークラスを段階的に移行するための `as_node` もありますが、これは移行専用です。
使い方は [v1 から v2 への移行](../migration_v1_to_v2.md) を参照してください。

## 関連ページ

- [フロー](flow.md) — ノードを呼び出す側の関数と依存性注入
- [Runner](runner.md) — 実行記録を所有する実行枠
