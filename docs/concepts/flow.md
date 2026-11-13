# フロー

フローは、Runner がデータタイルごとに 1 回呼び出す関数です。flow デコレータを付けた関数は
**普通の Python 関数としてそのまま実行**されます。事前にグラフを組み立てる段階はなく、
`if` 文・`for` 文・デフォルト引数・リテラル・f-string はすべて Python の意味どおりに動きます
([ADR-020](../adr/0020-eager-execution.md))。

## flow デコレータの役割

1. **登録** — フローレジストリに登録します(`rdetoolkit flows list` で一覧できます)。
2. **直接呼び出し** — `pipeline(paths, out)` のような呼び出しは通常の関数呼び出しです。
   引数は Python の規則どおりに束縛されます。
3. **Runner との接続** — Runner から呼ばれるときだけ、引数の型注釈を見て実行時の値を
   注入します(後述の依存性注入)。

flow から別の flow を呼ぶのも、ただの関数呼び出しです。内側の flow で呼ばれたノードは、
内側の flow を `parent_flow` として同じ実行記録に残ります。

| 引数 | 既定値 | 意味 |
|------|--------|------|
| `id` | `"モジュール名.関数名"` | フロー ID。RunReport の `flow_id` になります |
| `error_code` | なし | 本体の例外を `job.failed` に書くエラーコードに変換します |
| `error_message` | なし | 同じくメッセージ。`{error}` / `{error_type}` を埋め込めます |

`error_code` / `error_message` は v1 の `catch_exception_with_message` に相当する機能です。
v1 からの書き換え方は [v1 から v2 への移行](../migration_v1_to_v2.md) を参照してください。

## 予約型と依存性注入 { #reserved-types-and-dependency-injection }

Runner がフローに渡せる値は、次の 5 つの**予約型**だけです。

| 推奨引数名 | 型(`rdetoolkit.types`) | 内容 |
|-----------|-------------------------|------|
| `paths` | `InputPaths` | 現在のデータタイルの入力パス(`inputdata`、`rawfiles` など) |
| `out` | `OutputContext` | 成果物ディレクトリ(`struct`、`meta`、`main_image` など) |
| `config` | `RdeConfig` | 実行時の設定 |
| `invoice` | `InvoiceData` | パース済みの送り状 |
| `iteration` | `IterationInfo` | データタイルの番号(`index`)、総数(`total`)、モード(`mode`) |

注入はフローの境界で 1 回だけ、次の順に決まります。

1. 引数の型注釈が予約型のいずれか → その値を注入します。**引数名は自由**です。
2. デフォルト値がある → 注入せず、Python のデフォルト値を使います。
3. どちらでもない → `E2003 UnresolvableFlowParam` で run を始める前に失敗します。

同じ予約型を複数の引数に注釈すると `E2006 DuplicateReservedTypeAnnotation` になります。
ノードの中では注入は行われないため、ノードが出力先などを使う場合はフローから引数で渡します。

<!-- test: flow-injection -->
```python
from rdetoolkit import flow
from rdetoolkit.testing import run_flow
from rdetoolkit.types import InputPaths, IterationInfo, RdeConfig

seen = {}


@flow(id="docs.concepts.injection")
def inspect_tile(files: InputPaths, cfg: RdeConfig, tile: IterationInfo, threshold: float = 0.5) -> None:
    seen["inputs"] = [path.name for path in files.rawfiles]
    seen["policy"] = cfg.execution.on_iteration_error
    seen["tile"] = (tile.index, tile.total, tile.mode)
    seen["threshold"] = threshold


fixture_dir = workdir / "injection"
fixture_dir.mkdir()
(fixture_dir / "sample.txt").write_text("sample", encoding="utf-8")
report = run_flow(inspect_tile, fixture_dir)
assert report.status == "success"
assert seen == {"inputs": ["sample.txt"], "policy": "continue", "tile": (0, 1, "invoice"), "threshold": 0.5}
```

注入できない引数は、フローを呼ぶ前に設定エラーとして報告されます。

<!-- test: flow-unresolvable -->
```python
from rdetoolkit import flow
from rdetoolkit.testing import run_flow
from rdetoolkit.types import InputPaths


@flow(id="docs.concepts.unresolvable")
def needs_threshold(paths: InputPaths, threshold) -> None:
    raise AssertionError("never called")


fixture_dir = workdir / "unresolvable"
fixture_dir.mkdir()
(fixture_dir / "sample.txt").write_text("sample", encoding="utf-8")
report = run_flow(needs_threshold, fixture_dir)
assert report.status == "failed"
assert report.error["code"] == 2003
```

## フローを直接呼び出してテストする

フローは普通の関数なので、`rdetoolkit.testing` のビルダーで予約型の値を作れば
Runner を使わずに呼び出せます。

<!-- test: flow-direct -->
```python
import pandas as pd

from rdetoolkit import flow
from rdetoolkit.nodes import save_csv
from rdetoolkit.testing import make_input_paths, make_output_context
from rdetoolkit.types import InputPaths, OutputContext


@flow(id="docs.concepts.direct")
def write_table(paths: InputPaths, out: OutputContext) -> None:
    rows = [{"name": path.name, "size": path.stat().st_size} for path in paths.rawfiles]
    save_csv(pd.DataFrame(rows), out, "files.csv")


paths = make_input_paths(workdir / "direct", files=["a.txt"])
out = make_output_context(workdir / "direct-out")
write_table(paths, out)
assert (out.struct / "files.csv").read_text(encoding="utf-8").splitlines() == ["name,size", "a.txt,0"]
```

テストの書き方の詳細は [テストガイド](../guides/testing.md) を参照してください。

## ProcessingTemplate — 骨格と穴(slot)

同じ種類の計測データを扱う処理では、処理の骨格を共通化したくなります。
`ProcessingTemplate` は「配線済みのフロー」と「利用者が埋める穴(slot)」を宣言する仕組みで、
テンプレートの作者が骨格を、利用者が slot だけを書きます。テンプレートは
フローの糖衣であり、実行・記録・テストの仕組みは通常のフローと同じです。

<!-- test: flow-template -->
```python
from typing import final

from rdetoolkit.templates import ProcessingTemplate, slot
from rdetoolkit.testing import run_flow
from rdetoolkit.types import InputPaths


class CountingTemplate(ProcessingTemplate):
    """Skeleton owned by the template author."""

    @slot
    def count(self, paths: InputPaths) -> int: ...

    @final
    def __flow__(self, paths: InputPaths) -> None:
        total = self.count(paths)
        assert total >= 0


class TextFileCount(CountingTemplate):
    """What a template user writes: only the slot."""

    def count(self, paths: InputPaths) -> int:
        return len(list(paths.inputdata.glob("*.txt")))


fixture_dir = workdir / "template"
fixture_dir.mkdir()
(fixture_dir / "sample.txt").write_text("sample", encoding="utf-8")
assert run_flow(TextFileCount, fixture_dir).status == "success"
```

テンプレートの誤用は、実行時ではなくクラス定義(import)の時点で検出されます。

| コード | 名前 | 原因 |
|--------|------|------|
| E2101 | TemplateSlotMissing | 必須 slot が実装されていない |
| E2102 | TemplateSlotSignatureMismatch | slot の引数名・型注釈が宣言と一致しない |
| E2103 | TemplateFinalOverride | 骨格(`__flow__`)を上書きした |
| E2104 | TemplateDeepInheritance | 利用者クラスをさらに継承した(継承は 1 段まで) |
| E2105 | TemplateCtorNotDefault | 引数なしで構築できない(パラメータは `config.custom` で受け取ります) |

slot 間で値を受け渡すときは、骨格が戻り値を明示的に次の slot に渡します。`self` に状態を
持たせると `nodes lint` が `W1101 TemplateSelfStateUsage` として指摘します。
slot は事実上ただのメソッドなので、`TextFileCount().count(paths)` のように直接テストできます。

登録されたテンプレートは CLI で探し、雛形を生成できます。

<!-- illustration: flow-template-cli -->
```bash
$ python -m rdetoolkit templates list
$ python -m rdetoolkit templates describe <テンプレート名>
$ python -m rdetoolkit init --processing-template <テンプレート名> --module <提供モジュール>
$ python -m rdetoolkit run --flow modules.processing:MyProcessing
```

雛形生成の流れは [v2 チュートリアル](../tutorial_v2.md) のレベル 1 で実際に試せます。

## 関連ページ

- [ノード](node.md) — フローから呼び出す記録付きの関数
- [Runner](runner.md) — フローを呼び出す実行枠
