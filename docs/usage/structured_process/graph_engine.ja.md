# Graph Engine: GraphSpec・表の読み取り・描画エンジン

## 概要

`render_graph` は、`csv2graph` と `rdetoolkit plot` の土台になる、仕様(spec)を起点とした入口です。
*何を*描くかを `GraphSpec` で、*どこに*書き出すかを `OutputSpec` で指定すると、エンジンは `PlotPlan` を解決し、
すべての図を描画して、作成した成果物をすべて列挙した `GraphResult` を返します。
`csv2graph`、`plot_from_dataframe`、`rdetoolkit plot` は v1 のシグネチャのままです。[CSVをグラフ化する](csv2graph.ja.md) を参照してください。

エンジンには拡張点が 2 つあり、どちらも rdetoolkit を書き換えずに使えます。

- **表の読み取り**(`TableReader`): ファイルを表に変換します。
- **描画エンジン**(`GraphRenderer`): 計画済みの図をバイト列に変換します。

このページに出てくる名前はすべて `rdetoolkit.graph` からインポートできます。

## 1 回の呼び出しの流れ

1. **読み込み**: DataFrame(DataFrame のリスト、`TableData` も可)はそのまま使います。パスは表の読み取りで読み込みます(既定は `reader="auto"`、後述)。
2. **計画**: `build_plot_plan` が `GraphSpec` を表に照らして解決します(列、x と y の対応、ラベル、単位、図の構成、ファイル名)。
   不正な依頼は `PlotRequestError`(`ValueError` の一種。属性 `reason` で場合を判別できます)になります。
3. **成果物の計画**: 形式と図の種類ごとに描画エンジンを割り当て、任意依存の有無を確認し、出力先を検証し、ファイル名を確保します。
4. **描画・変換・書き込み**: 手順 3 が終わるまでファイルシステムには触れず、すべての図の描画が終わるまで何も書き込みません。

## GraphSpec と OutputSpec

| 項目 | 意味 |
|---|---|
| `GraphSpec.x`、`GraphSpec.series` | x 列と、y 列ごとの `SeriesSpec`(0 始まりの位置または列名)。`series` が空なら残りのすべての列を描きます。 |
| `GraphSpec.layout` | `"auto"`、`"overlay"`、`"individual"`、`"both"` |
| `GraphSpec.mark` | `"line"` または `"scatter"` |
| `GraphSpec.x_axis`、`GraphSpec.y_axis` | `AxisSpec`: `label`、`scale`(`"linear"` / `"log"`)、`limits`、`grid`、`invert`、`tick_format` |
| `GraphSpec.legend` | `LegendSpec`: 凡例の項目数の上限と配置方針 |
| `GraphSpec.unit_policy` | `"error"`(既定)、`"split"`、`"warn"`、`"allow"`。後述の「単位」を参照 |
| `GraphSpec.style` | `StyleSpec`: `figure_size` と Matplotlib の `rc_params`。その呼び出しの図にだけ適用されます |
| `OutputSpec.sink` | 成果物の出力先: `DirectorySink` または `OutputContextSink` |
| `OutputSpec.formats` | 例: `("png",)`、`("png", "svg")`、`("png", "html")` |
| `OutputSpec.base_name` | ファイル名の語幹(既定は `"plot"`) |
| `OutputSpec.on_existing` | `"overwrite"`(既定。成果物ごとに記録)または `"error"` |
| `OutputSpec.dpi` | ラスター画像の解像度(既定は 300) |

`AxisSpec.limits` は片側だけの指定を受け付けます。`(0, None)` は下限だけを固定します。
逆順の範囲は軸を反転します。有限でない値、等しい上下限、対数軸での `<= 0` の値は `PlotRequestError`(`reason="invalid_axis_limits"`)になります。

`output=` を省略すると、`render_graph` は何も書き込まず、呼び出し側が所有する図を `Artifact.figure` に入れて返します。

## 出力先

| 出力先 | 重ね描きの画像 | 個別グラフの画像 | HTML |
|---|---|---|---|
| `DirectorySink(output_dir, main_image_dir=None, html_dir=None)` | `main_image_dir`(未指定なら `output_dir`) | `output_dir` | `html_dir`(未指定なら `output_dir`) |
| `OutputContextSink(out)` | `main_image` | `other_image` | `struct` |

`OutputContextSink` はフローの `OutputContext` を通して書き込むため、グラフのファイルも他のノード出力と同じ所有の規則に従います。
出力先は名前と実際のパス(シンボリックリンクの先を含む)の両方で検査され、ディレクトリの外を指すものは `OutputPathError` になります。
`on_existing="error"` では、既存のファイルがあると描画の前に `ArtifactCollisionError` になります。

## 形式と描画エンジン

| 形式 | 重ね描き | 個別グラフ | 組み込みの描画エンジン |
|---|---|---|---|
| `png`、`svg`、`pdf` | 可 | 可 | Matplotlib |
| `html` | 可 | 不可 | Plotly(任意依存) |

それ以外の組み合わせは、何かを書き込む前に `UnsupportedFormatError` になります。
Plotly が入っていない環境での HTML は、やはり何かを書き込む前に `RendererUnavailableError`(`pip install "rdetoolkit[plotly]"` を案内する `ImportError`)になります。

## 表の読み取りと形式の自動判定

`reader="auto"`(`render_graph` の既定)では、次の順に読み取り方法を選びます。

1. ファイルの拡張子を名乗る読み取り(`TableReader.extensions`)。渡した `readers=` のレジストリ、組み込みの読み取り、インストール済みのエントリーポイントから探します。
   名乗るものが 2 つあれば推測せずに `AmbiguousFormatError` です。
2. それ以外は内容による判定(`detect_table_format`)。最大 64 KiB・50 行の標本を読み取り専用で調べ、組み込みの `standard`、`transpose`、`noheader`、`meta_block` から選び、文字コードと区切り文字も判定します。
   確信の持てる候補がなければ、`AmbiguousFormatError` が候補とその根拠、対処方法を示します。空のファイルは `InvalidCSVFormatError` です。

`reader="<id>"` で読み取り方法を明示でき、`reader=` には `TableReader` のインスタンスも渡せます。
判定結果は `GraphResult.detection`(`DetectionDecision`。`explain()` で読みやすい要約が得られます)として返ります。
コマンドラインでは `rdetoolkit plot data.csv --detect` が描画せずに同じ判定結果を表示し、`--csv-format auto` はその判定で描画します。
`csv2graph` と `rdetoolkit plot` の既定は従来どおり `standard` です。

### 読み取りをプラグインとして配布する

配布パッケージはエントリーポイントのグループ `rdetoolkit.graph.readers` で読み取りを公開できます。
エントリーポイント名が読み取りの ID で、対象は `TableReader` のインスタンスか、それを返す引数なしの呼び出し可能オブジェクトです。
読み取りのクラスもこの呼び出し可能オブジェクトに当たり、引数なしでインスタンス化されます。コンストラクタが失敗する場合や引数を必要とする場合は、エントリーポイント名を含む `ReaderPluginError` になります。
たとえば `pyproject.toml` の `[project.entry-points."rdetoolkit.graph.readers"]` に `"vendor.instrument" = "vendor_pkg.readers:READER"` と書きます。
エントリーポイントは読み取りを探すとき(`discover_readers()`)にだけ列挙され、インポート時には読み込まれません。
組み込みの読み取り、`"auto"`、他のエントリーポイントと ID が重なる場合は、どちらかを選ばずに `DuplicateReaderError` になります。
`readers=` で渡したレジストリが常に優先されます。

## 例: 独自の表の読み取り

次のスクリプトは架空の `.instrument` 形式の読み取りを定義し、`ReaderRegistry` に登録して、`render_graph` でファイルを描画します。
`reader="auto"` のもとでは、`.instrument` という拡張子を名乗るこの読み取りが選ばれます。

```python title="docs/usage/structured_process/graph_engine_samples/custom_reader.py"
--8<-- "docs/usage/structured_process/graph_engine_samples/custom_reader.py"
```

## 例: 独自の描画エンジン

次のスクリプトは、依存のない描画エンジン(図ごとに小さな SVG を書く)を定義し、`RendererRegistry` を通して差し込みます。
成果物は、その形式と図の種類を `RendererCapabilities` で宣言している最初の描画エンジンに渡されます。
登録済みのどの描画エンジンも宣言していない形式は `UnsupportedFormatError` になります。

```python title="docs/usage/structured_process/graph_engine_samples/custom_renderer.py"
--8<-- "docs/usage/structured_process/graph_engine_samples/custom_renderer.py"
```

どちらのスクリプトもテストで実行されるため、API と食い違うことはありません。

## 単位

単位は `voltage (V)` のような列名から読み取り、文字列として比較します。換算はしません(`mV` と `V` は別の単位で、単位のない列は互換とみなします)。

| `unit_policy` | 単位の混在する重ね描き |
|---|---|
| `"error"`(`render_graph` の既定) | 描画の前に `PlotRequestError`(`reason="unit_mismatch"`) |
| `"split"` | 単位ごとに 1 枚の重ね描き(語幹 `plot_v`、`plot_a` など) |
| `"warn"` | 1 枚の重ね描き。y 軸ラベルはすべての単位を並べたもの(`V (V) / I (A)`)で、`GraphUserWarning` を出します |
| `"allow"` | 1 枚の重ね描き。y 軸ラベルはすべての単位を並べたもので、警告は出しません |

`"split"`、`"warn"`、`"allow"` では、単位の不一致が計画とマニフェストに `unit_mismatch` の診断として記録されます。

`csv2graph`、`plot_from_dataframe`、`rdetoolkit plot` は従来どおり重ね描きを作り、警告を出して、y 軸ラベルにすべての単位を並べます。
2軸プロットには対応していません。代わりに `unit_policy="split"` または個別グラフを使ってください。

## ファイル名

個別グラフのファイル名は、最初の図を描く前に全系列分が確保されます。
大文字小文字・空白・Unicode 正規化の違いしかない 2 つの系列には、どちらにも系列 ID が付き(`plot_voltage_s000.png`、`plot_voltage_s001.png`)、`filename_collision` の診断が記録されます。
列名の `/`、`\`、`..` は `_` になります。1 回の実行の中で成果物が互いを上書きすることはありません。

## マニフェスト

`GraphResult.artifacts` は、書き込んだファイル(またはメモリ上の図)ごとの `Artifact` を計画の順に並べたものです。
図の ID、種類、役割、形式、描画エンジン、系列 ID、ラベル、パス、`replaced_existing` を持ちます。
`GraphResult.manifest()` と `manifest_json()` は同じ情報を、版付きで実行環境に依存しない文書として返します(ファイル名のみ、キーの順序は固定、判定結果は構造化したオブジェクト)。
エンジン自身はマニフェストを書き出しません。必要な場所に `manifest_json()` を書き出してください。
同じ依頼なら、出力先のディレクトリが違ってもマニフェストの内容は同じです。
