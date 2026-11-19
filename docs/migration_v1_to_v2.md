# v1 から v2 への移行

v2 の正準入口は eager に実行される flow デコレータ付き関数と ProcessingTemplate です。
実行結果は `RunReport` で受け取り、`status`、タイルごとの結果、警告、エラーを
同じスキーマから確認します。このガイドでは既存のハンドラークラスを一度に
捨てず、機械変換と小さな手作業を組み合わせて移行します。

## 1. 既存コードを検査する

例として、次の v1 形式のファイルを `legacy.py` とします。

<!-- test: legacy-source -->
```python
import rdetoolkit.workflows as legacy_workflows


class TextHandler:
    def process(self, srcpaths, resource_paths):
        source = next(srcpaths.inputdata.glob("*.txt"))
        destination = resource_paths.struct / "structured.txt"
        destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def custom_dataset_function(srcpaths, resource_paths):
    TextHandler().process(srcpaths, resource_paths)


if __name__ == "__main__":
    legacy_workflows.run(custom_dataset_function=custom_dataset_function)
```

`migrate check` は移行点を報告する読み取り専用コマンドです。`migrate apply` は
既定で dry-run になり、変換後の flow 関数を表示します。内容を確認した後だけ
`--no-dry-run -o <別ディレクトリ>` を指定してください。入力ファイルを
直接書き換えることはありません。

<!-- test: migration-commands -->
```bash
$ python -m rdetoolkit migrate check legacy.py
$ python -m rdetoolkit migrate apply legacy.py
```

変換不能な動的ディスパッチなどは `TODO(rdetoolkit-migrate)` として残ります。
TODO がない場合でも、生成物のテストと出力ディレクトリを確認してから採用します。

## 2. ハンドラーを `as_node` でつなぐ中間形

付録 M の Protocol に適合する既存ハンドラーは、移行期間中だけ `as_node` で
メソッドを通常の node にできます。Protocol はこの移行判断の補助であり、DI や
新規設計の入口ではありません。

<!-- test: as-node-bridge -->
```python
from rdetoolkit import as_node


class LegacyReader:
    def read(self, name: str) -> str:
        return name.upper()


read_legacy = as_node(LegacyReader(), method="read", id="docs.migration.legacy_reader")
result = read_legacy("sample.txt")
assert result == "SAMPLE.TXT"
```

この段階ではクラスを残せますが、node 間の値は明示引数で渡し、`self.df` のような
隠れ状態を増やさないでください。

## 3. 最終形を選ぶ

対応するドメインテンプレートがある場合は、`skeletons show <name>` で slot を
確認し、`new processing <name>` が生成したクラスの TODO slot だけを
実装します。骨格、保存順序、出力規約はテンプレートが所有します。

テンプレートがない非定型処理では flow デコレータ付きの関数を 1 つ書きます。`if`、ループ、
f-string、リテラル引数、デフォルト引数は通常の Python と同じです。処理を再利用
したくなった時点でだけ node デコレータ付きの関数に分割します。保存処理には `rdetoolkit.nodes` の
組込ノードを使います。

測定メタデータには公開ノード `build_meta(values, metadef_path)` を使い、
`save_meta(metadata, out)` で保存します。metadata-def に従ってキーを絞り、
型変換、キー順、単位（`$Key` 参照を含む）、variable 行を揃えます。
繰り返し値は `repeated={key: values}` で渡せます。variable 定義に対するスカラー値は
1 行にまとめます。`Metadata.units` は constant の単位、`Metadata.variable` は
value/unit セルの行を保持します。`parse_invoice_meta` も invoice の `custom` に
同じ規則を適用します。flow で `rde2util.Meta` や v1 オブジェクトの変換層を使う必要はありません。

v1 の `rde2util.get_default_values` で読んでいた `tasksupport/default_value.csv`
（`key,value` の 2 列）は `read_key_values(path)` で読みます(#629)。既定では v1 と
同じく chardet で文字コードを判定し、値はすべて文字列のまま返すため、結果は
`get_default_values` と一致します。測定値と合わせて `build_meta` に渡します。

<!-- test: read-key-values -->
```python
from rdetoolkit.nodes import build_meta, read_key_values

defaults = read_key_values(paths.tasksupport / "default_value.csv", missing_ok=True)
metadata = build_meta({**defaults, **measured}, paths.tasksupport / "metadata-def.json")
```

列名は `key=` / `value=`、文字コードは `encoding=` で指定できます。ほとんどが ASCII の
短い Shift-JIS ファイルは v1 と同じく chardet が別の文字コードと誤判定することがあるため、
`encoding="cp932"` を指定してください。ファイルが無い場合は `FileNotFoundError` に
なり、`missing_ok=True` では空の dict を返します。

値のキーには定義キーと `originalName` のどちらも使えます。v1 の `Meta.assign_vals` と
同じく、両方がある場合は定義キーを優先し、`originalName` は定義キーが無いときだけ
参照します（定義キーが `None` で存在する場合は `originalName` を参照せず除外します）。
`match="original_name"` は宣言された別名だけを使い、`originalName` が未指定または
`null` の定義は定義キーを使います。明示的な空文字の別名は入力キーとして維持します。
`match="key"` は別名の照合を無効にします。既定の `match="both"` は上記の優先規則を保ちます。
`save_meta` は v1 の `Meta.writefile` と同じ 4 スペースのインデントで書き出し、
`indent=` で変更できます。

第2引数には定義の Mapping も渡せます。共有定義をメモリ上で絞り込んで直接渡せるため、
一時 JSON ファイルは不要です。文字列は空かどうかを判定する前に前後の空白を除去します。
`build_meta` は `""` と空白だけの文字列に、次の同じ規則を適用します。

| スキーマ型 | 既定 | `keep_empty_strings=True` |
|---|---|---|
| `string` | 値を除外 | format が許す場合に `""` を保持 |
| `number`、`integer`、`boolean` | 型変換の前に除外 | `StructuredError`（`ecode=1`） |

繰り返しセルにも同じ規則を適用し、行位置は維持します。空でない不正な値は、
どちらの設定でも型変換エラーになります。この正規化は `build_meta` に適用します。
v1 の `Meta.assign_vals` と `parse_invoice_meta` の既存規則は維持し、空白だけの
数値・整数・真偽値は従来どおり型変換エラーになります。

v1 の `castval` / `_assign_invoice_val` のように `invoice.custom` を更新するには
`set_custom_fields(invoice, updates, schema=...)` を使います(#603)。新しい
`InvoiceData` を返し、各値を `invoice.schema.json` の `type` と `format` で変換します。

| スキーマ | 受け付ける値 | 格納される値 |
|---|---|---|
| `integer` | 数字(単位付き `"12 mm"` も可)、整数値の float(`3.0`) | `int` |
| `number` | 数値の文字列(単位付きも可) | 整数なら `int`、それ以外は `float` |
| `boolean` | `"true"` / `"false"`(大文字小文字を区別しない)、それ以外は真偽値として評価 | `bool` |
| `string` + `date` / `date-time` / `time` | dateutil で解釈できる文字列、`date` / `datetime` オブジェクト | `2023-07-19` / ISO 8601 / `13:04:05` |
| `string`(他の format、または format なし) | 任意 | そのまま |
| すべての型 | `None`、NaN、`NaT`、`pd.NA`(NumPy の NaN / NaT も含む) | `None` |
| すべての型 | `""` または空白だけの文字列 | 適用しない: キーは元の値のまま(#619) |

`dtype_backend="numpy_nullable"` で読んだ空セル(`pd.NA`)も `None` になります。NumPy のスカラー
(`np.int64` など)は対応する Python の値として変換するので、そのまま `save_invoice` で保存できます。

空文字列や空白だけの文字列(`read_excel(..., dtype=str, keep_default_na=False)` で読んだ
空セルなど)は適用しません。キーは `custom` の現在の値のまま、または存在しないままで、
`build_meta` が空文字列を省略するのと同じ扱いです。`keep_empty_strings=True` を指定すると
他の値と同じく変換します。日付 format のない `string` 項目にはそのまま格納し、
`integer` / `number` / `boolean` と日付 format では型の不一致になります。

format のない `string` 項目は、文字列以外の値も v1 の `castval` と同じくそのまま保持します。
その値は処理後の invoice 検証で失敗する(`1.5 is not of type 'string'`、ErrorCode 4001)ので、
意図して変換してください。入力どおりの桁(`1.50`)を残すには、セルを文字列として読みます
(`read_excel(..., dtype=str)` / `read_csv(..., dtype=str)`)。`str(1.5)` は `1.5` になります。

スキーマにないキーはコード 4011(`InvoiceCustomKeyUndefined`)の `StructuredError`、
型に合わない値は v1 と同じメッセージの `StructuredError`(コード 1)になります。注入される invoice はすべてのモードで
`tasksupport/invoice.schema.json` を持つので、`schema=` は別のスキーマで変換するときだけ
指定します(#620)。結果は `save_invoice(invoice, out)` で保存します。表計算の列から値を
埋める場合は、`resolve_custom_key(schema, label)` が `label.ja` または `label.en` が
一致するキーを返します(`lang="ja"` / `"en"` で言語を限定できます)。該当しないラベルや
2 つの項目に共通するラベルは、それぞれコード 4012(`InvoiceCustomLabelUnknown`)と
4013(`InvoiceCustomLabelAmbiguous`)の `StructuredError` になります。この 3 つのコードは
メッセージに対処方法を含み、flow が `error_code=` を宣言していてもコードが置き換わりません(#621)。

<!-- test: ga603-custom-fields -->
```python
from rdetoolkit.nodes import resolve_custom_key, set_custom_fields
from rdetoolkit.types import InvoiceData

schema = {"properties": {"custom": {"properties": {
    "measured_date": {"type": "string", "format": "date", "label": {"ja": "測定日", "en": "Measured date"}},
    "cycles": {"type": "integer", "label": {"ja": "サイクル数", "en": "Cycles"}},
}}}}
invoice = InvoiceData(raw={"custom": {"measured_date": None, "cycles": None}}, schema=schema)
row = {"測定日": "2023/07/19", "Cycles": "12"}
updates = {resolve_custom_key(schema, label): value for label, value in row.items()}
invoice = set_custom_fields(invoice, updates)
assert invoice.raw["custom"] == {"measured_date": "2023-07-19", "cycles": 12}
```

ファイル・画像の保存では、`read_excel` にシート・ヘッダー・行・列の選択を、
`save_csv` に数値書式・ヘッダー・index の指定を渡せます。`save_csv` の `preamble=` には
表の前に書く `#title` / `#legend` などのヘッダー行(フィールド数は行ごとに異なってよく、
表と同じ CSV 形式で書かれます)か、そのまま書く文字列を渡せ、
`blank_line_after_preamble=True` でヘッダー行と表の間に空行を 1 行入れます。`save_json` と `save_text` は
出力先の `kind` を選べます。文字コードを検出する `read_json`、タイルの invoice を
所定の書式で保存する `save_invoice`、利用者が作った Figure を保存する `save_figure`
も利用できます。`plot_lines` は x/y 列または列ペア、ラベル・タイトル・軸スケール・
凡例・サイズ・DPI・出力先を指定できます。
列ペアは `(x, y, label)` でも指定でき、`labels=` で全系列の凡例名を指定することもできます。
`grid=True` でグリッドを描き、軸ラベルの文字サイズは `label_fontsize` を指定しない限り
matplotlib の rcParams に従います。
v1 の `csv2graph(..., xlim=..., ylim=...)` や `ax.set_xlim` / `ax.set_ylim` に当たる軸範囲は
`xlim` / `ylim` で、x 軸のスケールは `xscale` で指定します。片側を `None` にするとその側は
自動のままなので、`ylim=(0, None)` で軸を 0 から始められます。
複数領域の測定のように x 値や長さが異なる系列は、データフレームのリストで渡せます。
x/y 列または列ペアの指定は各データフレームに適用され、`labels=` はデータフレーム順の
全系列に名前を付けます（`pd.concat(axis=1)` で 1 つのデータフレームにまとめる必要はありません）。
2 つの描画ノードは既定で tight な bounding box で保存します。
v1 の `fig.savefig(path)` と同じ画像には `bbox_inches=None` を、
`savefig(path, bbox_inches="tight", pad_inches=0)` と同じ画像には `pad_inches=0` を指定してください。
インタラクティブなグラフは `save_html_figure(fig, out, "chart.html")` で、plotly の Figure を
`plotly.io.to_html` により既定で `structured/` に保存できます。plotly.js は既定で CDN から読み込みます
（`include_plotlyjs=`・`full_html=`・`kind=` で変更できます）。グラフの `<div>` の id は plotly の
ランダムな値ではなく、ファイル名の英数字部分とファイル名の短いハッシュから決まります
（`plotly-chart-3e67baf8`）。そのため毎回同じファイルになり、別ファイルの断片（`full_html=False`）を
1 ページに並べても id は重なりません。`div_id=` で指定することもできます。plotly はオプションの `rdetoolkit[plotly]` で導入し、
ノードの実行時にだけ import されます。
セルの塗りつぶし色で行を選ぶテンプレートでは、`read_excel` と同じシート・行指定で
`read_excel_fills(path, column="A", ...)` を呼ぶと、データフレームの各行に対応する
塗りつぶし色（ARGB 16 進文字列、`theme:<n>`、または `None`）を返します。
`OutputContext` には v1 の `resource_paths.temp` に当たる一時ディレクトリはありません。
作業用ファイルには `tempfile.TemporaryDirectory()` を使ってください（ブロック終了時に削除されます）。
v1 の simple-registration テンプレートのように、アップロードされた PDF や SVG から
代表画像を作る場合は `render_png(source_path, out, filename, *, kind="main_image", page=1, dpi=350)` を使います。
拡張子が `.pdf` ならそのページを `dpi` で描画し、`.svg` / `.svgz` なら SVG 自身のサイズで描画し、
それ以外は `to_png` と同じく Pillow で PNG に変換します。既定値(1 ページ目、350 dpi)は v1 テンプレートと同じです。
PDF と SVG には `pip install 'rdetoolkit[render]'` が必要で、SVG には Cairo のシステムライブラリも必要です。
未導入の場合は、必要な extra とライブラリ名を示す `ImportError` になります。
PDF の描画は v1 の pdf2image(poppler)ではなく pypdfium2 を使うため、画素単位では v1 と一致しないことがあります。

`to_png` / `to_jpeg` は `kind=` で出力先を選べます（既定は `other_image`）。TIF のアップロードを
代表画像の PNG にするには `to_png(path, out, "main.png", kind="main_image")` とします。
画像や添付ファイルを変換せずに登録するには `copy_file(src, out, filename, kind=...)` を使います。
`struct`・`other_image`・`thumbnail`・`attachment` など任意の出力先へバイト単位でそのまま複製します。
解析結果の重ね描きやマスクなど、NumPy 配列・Pillow 画像は `save_image(image, out, filename)` で保存します
（形式はファイル名の拡張子から決まり、既定の出力先は `other_image`）。OpenCV の配列は BGR 順なので、
`cv2.imwrite` と同じ画像にするには `channel_order="bgr"` を指定してください。
テキストを行単位で読むには `read_lines(path)` を使います（`read_text` と同じ文字コード判定で、
`f.read().splitlines()` と同じ行を返します。`keepends=True` で改行を残します）。
v1 の文字コード判定ヘルパーを直接呼んでいたコードは、builtin の読み込みノードと同じ規則の
`detect_encoding(path)` に置き換えられます。シート名の一覧は `list_excel_sheets(path)` で取得でき、
「名前に X を含むシート」を探して `read_excel(path, sheet_name=...)` に渡せます。
`unzip_inputs` は ZIP に加えて tar（`.tar`、`.tar.gz`、`.tar.bz2`、`.tar.xz`）も展開します。
UTF-8 フラグのない ZIP のメンバー名は CP932 として復元されるため、`ZipFile.extractall` で
cp437 のまま展開していた v1 コードとはファイル名が異なる場合があります。
`_feature` 付きメタデータを送り状の説明文に書き込む処理を自分で行う場合は、
`describe_features(invoice, metadata, metadef_path)` が Runner の `feature_description` と同じ書式で
`basic.description` に追記した送り状を返します。その結果を `save_invoice` で保存するときは、
同じ行が二重に追記されないよう `rdeconfig.yaml` の `system.feature_description` を `false` にしてください。

v1 のテンプレートが `subprocess.run` で行っていた外部変換プログラムの実行には
`run_program(args, ...)` を使います（#630）。変換プログラムは、`out.struct` や `out.logs`
など引数で渡したディレクトリへ書き込みます。標準出力と標準エラーは取り込まれ、
`CompletedProgram`（`args`、`returncode`、`stdout`、`stderr`、秒単位の `duration`）で返ります。
0 以外の終了コード、起動できないプログラム、`timeout` の超過は、ErrorCode 3001 ではなく
`error_code`（既定 1）の `StructuredError` になります。既定のメッセージはコマンドライン・
終了コード・実行時間・標準エラーの末尾行を含み、`error_message` を指定するとそれに置き換わります。
コマンドラインと結果はログにも出力されます。`env` は引き継いだ環境変数に追加されます。
Windows 用の変換プログラムでは、`wine="auto"` を指定すると Windows 以外で `wine` を前置し、
`Path` の引数を Windows 形式に変換します（`/data/structured` は `Z:\data\structured`）。
オプション文字列に埋め込むパスは `to_wine_path` で変換してください。例:
`f"-OutputFolder:{to_wine_path(out.struct)}"`。文字列の引数はそのまま渡します。

<!-- test: ga630-run-program -->
```python
import sys
import tempfile
from pathlib import Path

from rdetoolkit.nodes import run_program

with tempfile.TemporaryDirectory() as struct:
    export = Path(struct) / "export.txt"
    code = "import sys; open(sys.argv[1], 'w', encoding='utf-8').write('exported')"
    result = run_program([sys.executable, "-c", code, export], error_code=51, error_message="Converter failed")
    assert result.returncode == 0
    assert export.read_text(encoding="utf-8") == "exported"
```

v1 の `rdelogger.get_logger(name, file_path=Path(resource_paths.struct, "structured_log.txt"))` のように
処理ログをタイルの成果物として書き出すには、`artifact_logger(out, filename, name=..., kind="struct")` を
`with` で使います(#631)。ブロックの間だけ `name` のロガーへファイルハンドラーを追加し、終了時に
例外の有無にかかわらず取り除きます。ブロック内で記録した行だけがファイルに入るため、
モジュールで共有するロガーでも次のタイルのファイルに行が重複しません。呼び出しはノード呼び出しとして
コールログと RunReport の `node_calls` に記録されます。

- 行の書式は v1 と同じ `%(asctime)s - [%(name)s](%(levelname)s) - %(message)s` で、`fmt=` で変更できます。
- 既存ファイルには追記します(`mode="a"`、v1 と同じ)。`mode="w"` は最初の行で切り詰めます。
- 1 行も記録しなければファイルは作られません(v1 と同じ)。
- `level=`(既定 `DEBUG`)より低い行は書きません。ロガー自身のレベルが高い場合はブロックの間だけ下げ、終了時に戻します。
- 失敗時の ERROR 行は、ブロック内で `logger.exception(...)` を記録してから再送出すると残ります。
- ブロックに入ったコンテキスト(タイルのコードと、そこから呼ぶノード)で記録した行は、そのブロックのファイルにだけ書き込まれます。同じロガーを使う Runner を同じプロセスで並行に実行しても、行は混ざりません。
- どのブロックにも入っていないコンテキストの行(ブロック内で起動したワーカースレッドなど)は、そのロガーで有効なすべてのブロックのファイルに書き込まれます。
- 別プロセスの行は書き込まれません。ブロック内で fork したワーカーがブロック後も動き続ける場合も同じです。
- ブロックが重なっても、ロガーのレベルは最後のブロックが終わった時点で最初のブロックの前の値に戻ります。
- `name` を省略するとファイル名から拡張子を除いた名前のロガーを使います。

<!-- test: ga631-artifact-logger -->
```python
import logging
import tempfile
from pathlib import Path

from rdetoolkit import flow
from rdetoolkit.nodes import artifact_logger
from rdetoolkit.testing import make_output_context
from rdetoolkit.types import OutputContext

logger = logging.getLogger("eis")


def fit() -> None:
    logger.info("fitting started")
    logger.warning("baseline drift")


@flow
def pipeline(out: OutputContext) -> None:
    with artifact_logger(out, "structured_log.txt", name="eis"):
        try:
            fit()
        except Exception:
            logger.exception("fitting failed")
            raise


with tempfile.TemporaryDirectory() as tmp:
    out = make_output_context(Path(tmp))
    pipeline(out)
    lines = (out.struct / "structured_log.txt").read_text(encoding="utf-8").splitlines()
    assert [line.split(" - ", 1)[1] for line in lines] == ["[eis](INFO) - fitting started", "[eis](WARNING) - baseline drift"]
```

`unzip_inputs` は展開したファイルの絶対パスをアーカイブ順で返します。
ディレクトリエントリーと危険な展開先は含めず、重複メンバーは重複したパスを返します。
外向きシンボリックリンクを含む展開先の境界チェックは維持します。
戻り値を使用していなかった呼び出し方も継続できます。
アーカイブ構造を列挙する場合は `include_dirs=True` で空ディレクトリを含むディレクトリエントリーも返します。

Runner は flow の実行前に、タイルの入力ファイルを `system.save_raw` が有効なら `raw/` に、
`system.save_nonshared_raw` が有効なら `nonshared_raw/` にコピーします(v1 がデータセット関数の前に
コピーしていたのと同じです)。v1 のテンプレートがこのコピーを削除・置換していた処理には、
`remove_raw_copy(out, config, filename)` と `replace_raw_copy(out, config, filename, members)` を使います(#623)。
アップロードされた `*_meta.json` を `meta/` に保存して raw データとしては残さない場合は `remove_raw_copy`、
ZIP の代わりに展開したファイルを raw データとして保存する場合は
`replace_raw_copy(out, config, archive.name, unzip_inputs(archive, tmp))` とします。
どちらも有効な種類だけを操作し(無効な種類には触れません)、呼び出しはコールログに記録されます。
`replace_raw_copy` はメンバーをファイル名で(アーカイブ内のサブディレクトリは保持せず)コピーしてから
元のコピーを削除します。コピーがない、同名のメンバーが 2 つある、別の入力のコピーを上書きする、
置き換える対象のコピー自体またはその中のファイルをメンバーに渡す、
といった場合は何も変更せずに例外になります。
`out.path_for("nonshared_raw", name).unlink()` のように直接削除するコードは、これらに置き換えてください。

<!-- test: ga623-raw-copy -->
```python
import tempfile
import zipfile
from pathlib import Path

from rdetoolkit.nodes import remove_raw_copy, replace_raw_copy, unzip_inputs
from rdetoolkit.testing import make_output_context
from rdetoolkit.types import RdeConfig

config = RdeConfig.model_validate({"system": {"save_raw": True, "save_nonshared_raw": True}})
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    archive = root / "upload.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("image.tif", b"tif")
    out = make_output_context(root / "data")
    for directory in (out.raw, out.nonshared_raw):  # what the Runner copied before the flow
        (directory / "upload.zip").write_bytes(archive.read_bytes())
        (directory / "sample_meta.json").write_text("{}", encoding="utf-8")
    replace_raw_copy(out, config, "upload.zip", unzip_inputs(archive, root / "extracted"))
    remove_raw_copy(out, config, "sample_meta.json")
    stored = sorted(path.name for path in out.nonshared_raw.iterdir())
    assert stored == ["image.tif"]
```

### main.py で設定を読み込み、モードを上書きする

flow 入口の設定を事前に用意する場合は、`rdetoolkit.runner.load_run_config(root=None, *, overrides=None)`
を使います。`root` はプロジェクトルートまたは data ルートで、`Path` と文字列を受け付けます。
省略時はカレントディレクトリです。Runner と同じ data ルート解決・設定探索を使い、
プロジェクト直下の `rdeconfig.yaml`、`pyproject.toml`、解決した data ルートの
`tasksupport/{rdeconfig.yaml,rdeconfig.yml,pyproject.toml}` の順に探索します。
tasksupport の設定は v1 形式として解釈します（Design §6.3）。

`overrides` は発見した設定へ再帰的にマージします。戻り値の `RdeConfig` を
`run(flow=..., config=...)` に渡すと、そのオブジェクト全体を設定として使います。
マッピングを直接渡す場合も、発見した設定に対する上書きになります。
以下の例は tasksupport の他の値を保ったままモードを変更します。

<!-- test: load-run-config -->
```python
from rdetoolkit import flow, workflows
from rdetoolkit.runner import load_run_config
from rdetoolkit.types import RdeConfig


@flow
def pipeline(config: RdeConfig) -> None:
    print(config.system.extended_mode)


config = load_run_config(overrides={"system": {"extended_mode": "MultiDataTile"}})
report = workflows.run(flow=pipeline, config=config)
if report.status != "success":
    raise SystemExit(1)
```

`RdeConfig.model_validate({"system": {"extended_mode": None}})` も受理します。
YAML の `null` や上書きの `None` はモード未指定として正規化され、
値は既定の `"invoice"` になります。SmartTable / ExcelInvoice の検出で
W1001 は出ません。文字列で明示したモードと検出結果が競合する場合、
v2 flow はカタログ登録済みの設定エラーにします。検出結果による上書きと
W1001 を維持するのは v1 callback 経路だけです（Design §6.2）。

検証後の `config.system.extended_mode` は常に `str` です。未指定と、
文字列 `"invoice"` の明示指定は区別されたまま、モード解決・`config_digest`・
`repro` の export → import → run に引き継がれます。型付きの Python コードで
モードを未指定にするときは、`V2SystemSettings(extended_mode=None)` とせず
引数を省略してください。`None` を渡すのはマッピング（`load_run_config(overrides=...)`
や `RdeConfig.model_validate(...)`）と YAML の `null` だけです。型チェッカーは
`extended_mode=None` を `arg-type` エラーにします。

## 実行時の変更点

本番の `main.py` では、失敗・一部失敗をプロセスの終了コードへ反映する指定を追加してください。
RunReport、失敗時の `job.failed`、完了済み成果物を確定してから、失敗は1、一部失敗は2で終了します。
成功時は通常どおり戻ります。ライブラリからの既定の呼び出しは RunReport を返す契約を維持します。
公開の `report.exit_code` も CLI と同じ値を返すため、`SystemExit` に渡せます。
この値は派生プロパティであり、JSON のフィールドやスキーマバージョンは増やしません。

<!-- test: ga572-main -->
```python
from rdetoolkit import workflows
from processing import pipeline

workflows.run(flow=pipeline, exit_on_failure=True)
```

テンプレート探索では、`--module` を省略するとルートの Python モジュールと
`modules/` パッケージ内の骨格宣言を読み込みます。インストール済みプラグインも探索します。
別の場所の提供モジュールは `--module` で指定してください。
説明には slot のドキュメントとドメイン型を含め、標準ライブラリ型を除外します。
テンプレート用 init は `main.py`・実装・テスト雛形を生成し、3ファイルすべてを上書きから保護します。
slot の引数名と種類を含むシグネチャの一致、深さ2までの継承、flow 境界での DI は維持します。
公開済み骨格には任意 hook を追加して拡張し、必須 slot を追加する場合は具象実装も更新してください。

`migrate apply` は、未対応の別モジュール参照とヘルパーファイルを変更せず、
手動移行が必要なコールバックを報告します。そのコールバックと入口を一緒に移行してください。
変換可能なローカル関数ではコメントと文字列を保持し、旧入口を削除したことと
変換後の flow を CLI で実行する方法を明示します。

- `run()` を呼ぶ前に `data/inputdata/` を書き換える v1 の `main.py`（連結された
  装置ファイルの分割、SmartTable CSV と zip の生成など）は、その処理を
  flow デコレータの `prepare=prepare_inputs` オプションとして宣言します。シグネチャは
  `def prepare_inputs(inputdata: Path, config: RdeConfig) -> None` です。Runner は
  設定の読み込み後、モード判定の前に 1 回だけ呼ぶため、`workflows.run(flow=...)`
  と `rdetoolkit run <pkg.mod:flow>` のどちらでも準備後の入力でモードが決まります。宣言しない
  場合、`rdetoolkit run` は準備前のファイルでモードを判定します。`--validate-only` でも
  実行されるため、事前チェックは本番と同じモードで検証しますが、`inputdata/` を
  変更することがあります。再実行や `rdetoolkit repro` は準備済みの入力に対して再び呼ぶので、
  冪等にしてください。渡される設定は複製なので、変更しても実行には影響しません。
  実行は `prepare.started` / `prepare.completed` / `prepare.failed` イベントとして
  記録されます。flow の `error_code` / `error_message` は本体と同様に prepare の
  失敗にも適用され、指定がなければ通常の例外はタイル処理の前に 3001 で失敗します。
  `StructuredError` はそのコードとメッセージを保ちます。prepare が実行されるのは
  Runner が実行する flow だけで(入れ子の flow の `prepare` は実行されません)、
  flow を直接呼び出したときも実行されません。
- flow デコレータの `error_code=7, error_message="Cannot process input"` で、本体（と prepare）の例外を
  両 v2 入口から同じコード・メッセージにまとめられます。コードだけなら元の
  メッセージを保ち、メッセージだけならコードは 3001 です。メッセージには例外の文字列
  `{error}` と例外クラス名 `{error_type}` を埋め込めます（例:
  `error_message="Cannot read sample: {error}"`）。それ以外の波括弧はそのまま残ります。
  本体で送出した
  `StructuredError` は v1 の `catch_exception_with_message` と同じく、そのコードと
  メッセージを保ちます。直接の関数呼び出しでは
  元の例外がそのまま送出されます。Runner では元の例外をチェーンに残し、
  `KeyboardInterrupt`・`SystemExit` などのプロセス制御例外は変換しません。
- **v1 の `catch_exception_with_message` を flow に書き換えるときは `error_code=1` を明示してください。**
  v1 のデコレータは素の例外を `ecode=1`、メッセージ先頭に `Error: ` を付けた
  `StructuredError` に変換します。flow の `error_message` だけを移すとコードは 3001 になり、
  `job.failed` の `ErrorCode` が 1 から変わります。v1 と同じ結果にする対応は次のとおりです。

  | v1 の `catch_exception_with_message` の引数 | flow デコレータの引数 |
  |---|---|
  | `error_message="m"` | `error_code=1, error_message="Error: m"` |
  | なし | `error_code=1, error_message="Error: {error}"` |
  | `error_code=c, error_message="m"` | `error_code=c, error_message="Error: m"` |

  `Error: ` 接頭辞が不要なら `error_code=1, error_message="m"`、
  引数なしの場合は `error_code=1` だけで構いません(コードは同じで、メッセージは
  それぞれ `m`、例外の文字列になります)。
- **`catch_exception_with_message` は非推奨です。** デコレータを付けた時点で
  `DeprecationWarning` が出ます。動作は変わらず、v2 では削除しません。
  `job.failed` の `ErrorCode` を v1 と同じ値に保つ必要があるときは上の表で書き換えます。
  そうでなければ、利用者に伝えたい失敗を `ProcessingError` で送出し、
  デコレータを外してください。エラーコードは指定しません。Runner が 3007
  `ProcessingFailed` として `RunReport`・反復ログ・`job.failed` に書き込み、
  メッセージの後ろに `Remediation: <対処法>` を付けます。`remediation` を省略すると
  カタログの既定文になります。`raise ... from exc` で元の例外を残せます。
  `ValueError` などの通常の例外はこれまでどおり 3001 です。次の例は、ファイルが
  見つからないときの `FileNotFoundError` を `ProcessingError` に置き換えます。

<!-- test: processing-error -->
```python
from pathlib import Path

from rdetoolkit.exceptions import ProcessingError


def read_sample(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ProcessingError(
            "Input file was not found.",
            remediation="Check that the file is in inputdata.",
        ) from exc


try:
    read_sample(Path("missing.csv"))
except ProcessingError as error:
    caught = error

assert caught.code == 3007
assert isinstance(caught.__cause__, FileNotFoundError)
```

  `ProcessingError` は flow の `error_code` / `error_message` でも
  `catch_exception_with_message` でも変換されず、3007 と対処法を保ちます。
- flow に注入される `InputPaths` は v1 と同じく作業ディレクトリからの相対パスです。
  入力パスを含むユーザーのエラーメッセージも v1 と同じ表記になります。
  Runner 内部では、開始時に一度確定した data root を引き続き使います。
- v2 の正準戻り値は `RunReport` です。`report.status` と
  `report.iterations` を起点に結果を処理してください。
- **flow 入口では `on_iteration_error` の既定値が `continue` です。** v1 の
  即時停止(fail-fast)が必要なら設定で `fail_fast` を明示してください。
  `run(custom_dataset_function=...)` の v1 入口は v1 の反復規則を保ちます
  (後述の「意図的な差分」を参照)。
- グラフは実行前 DAG ではなく、実行後の call sequence です。通常の Python
  制御構文をそのまま使えます。
- MultiDataTile のタイル(`data/`、`divided/0001`、…)は、v1 の MultiDataTile と
  同じくファイル名順に割り当てられます。v1 の構造化処理が
  `for f in inputdata.glob("*")` のように自前で `inputdata` を列挙してタイルを
  作っていた場合は、ディレクトリの列挙順になっていました。同じ順序が必要なら
  `multidata_tile.order: filesystem` を設定してください(既定は `name`)。
  列挙順はファイルシステムに依存します(#597)。

## CLI コマンド名の変更 { #cli-command-renames }

v2.0 で CLI は `rdetoolkit <名詞> <動詞>` 形式に再編されました。v1 のコマンドは
v2.0.x では警告を表示する非推奨の別名として動作し、v2.1 で削除されます。v2 の
リリース候補版にだけ存在した名前は別名なしで削除されました。スクリプト、CI 定義、
Dockerfile を新しい名前に更新してください。

| 旧 | 新 | 由来 |
|---|---|---|
| `gen-config [OUTPUT_DIR] [--template X] [--overwrite]` | `new config [-o DIR] [--preset X] [--force]` | v1 — v2.0.x では非推奨の別名として残り、警告を表示、v2.1 で削除 |
| `gen-invoice` | `new invoice` | v1 — 非推奨の別名 |
| `make-excelinvoice` | `new excelinvoice` | v1 — 非推奨の別名 |
| `csv2graph` | `plot` | v1 — 非推奨の別名 |
| `artifact --output-archive` | `package -o/--output` | v1 — 非推奨の別名 |
| `run TARGET` (`module::attr`) | `run --legacy TARGET` | v1 — `--legacy` なしの `::` 形式も実行される(出力互換のため警告なし)。v2.1 で `--legacy` が必須 |
| `init --processing-template X` | `new processing X` | v2 rc のみ — 別名なしで削除 |
| `run --flow X` | `run X` | v2 rc のみ — 削除 |
| `graph REPORT` | `report trace REPORT` | v2 rc のみ — 削除 |
| `templates list/describe` | `skeletons list/show` | v2 rc のみ — 削除 |
| `nodes describe`, `flows describe` | `nodes show`, `flows show` | v2 rc のみ — 削除 |
| `migrate apply --out DIR` | `migrate apply -o/--output DIR` | v2 rc のみ — 削除 |

`rdetoolkit migrate check` は、Python の文字列リテラルと `*.sh`、`*.yml`、`*.yaml`、
`*.toml`、`*.cfg`、`Makefile`、`Dockerfile` に残っている旧コマンド名を報告します。
各コマンドの詳細は[コマンドライン機能](usage/cli.md)を参照してください。

## v1 ユーザー向け互換範囲とスケジュール

この節は 2.0.0rc1 時点の確定内容です。v1 の実行経路(反復ループとモード別処理)は
削除され、すべての入口が単一の Runner を通ります。v1 の**契約**(入口・成果物・
終了の仕方)は、v1.7.1 の契約を取り込んだ v1 実行経路から凍結した契約スナップショットとの比較テストで守られて
います。

### 維持されるもの

- **入口**: `rdetoolkit.workflows.run(custom_dataset_function=...)` のシグネチャ。
  コールバックは従来どおり `(srcpaths, resource_paths)` を受け取ります。
- **v1 契約**: 戻り値の JSON(各タイルの status 一覧)、失敗時の
  `SystemExit(1)`、既定の fail-fast、`data/job.failed` の書式、出力
  ディレクトリ構成(`raw/`、`structured/`、`divided/NNNN/` など)、
  `data/logs/rdesys_<タイムスタンプ>.log`。
- **Tier 1 API**: `rdetoolkit.models.rde2types`、`rdetoolkit.rde2util`、
  `rdetoolkit.invoicefile`、`rdetoolkit.errors`、`rdetoolkit.exceptions`、
  `workflows.check_files` / `check_files_result`、
  `workflows.generate_folder_paths_iterator`。
- v1 の CLI コマンド。`rdetoolkit init` と `rdetoolkit validate` は名前もそのままで、
  名前が変わった v1 コマンドも v2.0.x では非推奨の別名として動作します
  ([CLI コマンド名の変更](#cli-command-renames)を参照)。

### 削除されたもの(2.0.0rc1)

- `rdetoolkit.modeproc` モジュール。
- `rdetoolkit.processing` パッケージ(`Pipeline`、`ProcessingContext`、
  `Processor` とその派生クラス一式)。
- `rdetoolkit.workflows` のモード別関数 `invoice_mode_process`、
  `excel_invoice_mode_process`、`multifile_mode_process`、
  `rdeformat_mode_process`、`smarttable_invoice_mode_process`。
- `rdetoolkit` パッケージからの `impl` と `interfaces` の公開 export。両モジュールは
  Runner の内部実装として残りますが、公開 API ではありません。

これらを直接 import しているコードは、`run(custom_dataset_function=...)` 経由の
呼び出しに戻すか、flow 関数へ移行してください。

**非推奨(呼び出し元なし、互換のためだけに残存)**:
`rdetoolkit.errors.handle_and_exit_on_structured_error` と
`rdetoolkit.models.result.WorkflowResultManager`。新しいコードでは使わないで
ください。`RdeOutputResourcePath` の `smarttable_rowfile=` 引数も、v1.7 と同じく
`smarttable_rawfile` への非推奨エイリアスです。

### 削除されたもの(2.0.0rc1 以降、GA 前)

- v1.6.0 で追加されたパッケージ同梱の AI エージェントガイド:
  `rdetoolkit.get_agent_guide()`、CLI の `agent-guide` コマンド、
  内部モジュール `rdetoolkit._agent` と同梱 Markdown、およびパッケージ内の
  `.agents/` ガイド。インストールされたパッケージにはエージェント向け文書を
  同梱しません。代替 API はありません。呼び出しているコードやスクリプトからは
  削除してください(#644)。v2 向けのエージェント用ガイダンスは、別配布の
  バージョン一致 [Agent Skills pack](usage/agent_skills.ja.md) として提供します。
- v2 プレリリースの草案エラー体系: 文字列の `rdetoolkit.errors.ErrorCode` 列挙
  (`E001`〜`E025`)、`RdeGraphError`、`RdeCompileError`、`RdeIOError`、
  `UnconnectedInputError`、および定数 `E_CYCLE` / `E_UNCONNECTED_INPUT` /
  `E_DUPLICATE_ID` / `E_AMBIGUOUS_DEPENDENCY`。いずれも 2.0.0a1 / 2.0.0rc1 の
  プレリリースにのみ存在し、v1 には含まれていません。`ERROR_CATALOG` の int
  コードを持つ `RdeError` の派生クラス(`RdeConfigError`、`RdeRegistryError`、
  `RdeExecutionError`、`RdeValidationError`、`RdeInternalError`)を使ってください
  (#646)。

### 挙動の変更

**v1.7 系で入った変更(v2 でもそのまま)**

- SmartTable モードの行 CSV(`fsmarttable_*.csv`)は `rawfiles` に含まれません
  (#503)。行 CSV が必要な場合は `smarttable_rawfile` を使います
  (旧名 `smarttable_rowfile` は誤記の改名)。
- `smarttable.save_table_file: true` のとき、元の SmartTable ファイルは
  `divided/0001` として先頭に登録され、データ行は `divided/0002` 以降に
  ずれます(#503)。
- SmartTable の `meta/<key>` 列を使うには `tasksupport/metadata-def.json` が
  必須です。ない場合は無視されず `StructuredError` で失敗します(#496)。

**2.0.0rc1 で入った変更**

- 実行ごとのイベントログ `data/logs/events_<run_id>.jsonl` が既定で出力されます。
  ファイルは 1 実行あたり 64 MiB が上限で、超えた時点で警告 **W1002**
  (`EventsLogTruncated`)を 1 回記録し、以降のノード単位イベントだけを
  省きます(実行・タイル単位のイベントと警告は残ります)。
  `data/logs/**` は v1 の成果物契約の対象外です。
- `data/logs/iterations/` はタイル反復の開始時に空にされます。
  `job.failed`、`run_report_*`、`events_*` は従来どおり実行をまたいで残ります。

**2.0.1 で入った変更: `templates/` を `template/` に改名**

- `rdetoolkit init` は `templates/tasksupport/` ではなく `template/tasksupport/`
  を生成します。生成されるディレクトリ(`container/`、`input/`、`template/`)は
  すべて単数形になります。
- v1 で作成したプロジェクトには `templates/tasksupport/` が残っています。
  プロジェクトのルートに対して `rdetoolkit migrate apply <project>` を実行します。
  dry-run では Python の変換結果と並べて `templates/` → `template/` の移動を表示します。
  `--no-dry-run` を付けると、出力先(`--out`、省略時は `<name>_migrated`)に
  `template/` が作られます。入力ディレクトリは変更しません。
  `migrate check <project>` は `templates/` を検出結果として報告します。
- `templates/` と `template/` の両方がある場合、`migrate apply` は終了コード 3 で
  停止し、両者をマージしません。残したいファイルを `template/` へ移し、
  `templates/` を削除してから再実行してください。
- 移行するまでの間、`validate all` は `template/tasksupport/` がなければ
  `templates/tasksupport/` を読み、`deprecated_layout` 警告を出します。
  この警告は終了コードを変えませんが、`--strict` では失敗になります。
- `templates/tasksupport/` があるディレクトリで `init` を実行すると、
  `template/` は作られず、`migrate apply` を案内する警告が表示されます。
- `migrate apply` が改名するのはディレクトリだけです。`pyproject.toml` の
  `[tool.rdetoolkit.init]` や、スキーマを `templates/tasksupport/` へコピーする
  CI スクリプトなど、ご自身で書いたパスは書き換えてください。

### 意図的な差分(v1 と結果が異なるケース)

ヘッダーだけでデータ行がない Excel invoice はタイル実行前に検出します。
互換コールバック入口では v1 の汎用エラー（999）を保ち、flow 入口では
入力検証エラー `EmptyExcelInvoice`（4004）とデータ行を追加する案内を返します。
invoice シート自体がないブックについては既存のエラー契約を維持します。

| ケース | v1 | v2 |
|---|---|---|
| コールバックが `StructuredError(msg, ecode)` を送出 | `job.failed` に `ecode` と `msg` | 同じ |
| コールバックが素の例外を送出 | `ErrorCode=999`、`Unexpected error in <mode> mode: ...` | `ErrorCode=3001`。メッセージはエラーカタログ E3001 の文で、ユーザーの例外メッセージを含みます |
| コールバック失敗時の stderr トレースバック(`traceback:` 設定 / `TRACE_*`) | `errors.handle_exception` が `Config.traceback`、なければ `TRACE_*`、なければ python 形式で `compact` / `python` / `duplex` を出力 | v1 コールバック入口では同じフォーマッタ・同じ設定・同じ優先順で出力し、設定は警告を出しません。素の例外では、最外の例外が `StructuredError: Unexpected error in <mode> mode: ...` ではなく E3001 メッセージの `TileExecutionError`(ユーザーの例外から連鎖)になります。`run()` 自体を `except` ブロックの中から呼んだ場合も、例外の連鎖は Python が記録したとおりに表示します(1.7.1 はこの場合にコールバック自身の暗黙の連鎖を失っていました)。コールバック外の失敗(設定、invoice 検証、出力の検証など)でも、`job.failed` が報告するエラーのトレースバックを同じ形式で出力します。flow 入口(`run(flow=...)`、`rdetoolkit run <module>:<flow>`)はこのトレースバックを出さず、プロジェクト直下の v2 形式 `rdeconfig.yaml` では `traceback:` はエラー(E1002)です |
| `invoice.schema.json` 自体が不正で、コールバックも失敗 | コールバック側のエラーコード(検証はコールバックの後) | `ErrorCode=4001`(スキーマ検証の理由付き)。コールバックは呼ばれません |
| invoice の必須項目を行やコールバックで補完 | 行の反映・コールバックの後に検証 | ExcelInvoice / SmartTable は両入口とも元の invoice の内容検証を省略し、行反映後のタイルを検証します。v1 コールバック入口では全モードで内容検証を遅らせるため、コールバックで必須項目を補完できます。ファイルの存在確認(4003)とスキーマ自体の検証(4001)は事前に行います |
| 最終 invoice がスキーマに違反 | モードごとに異なるコード、一部モードではコールバック実行済み・出力も生成済み | 最終成果物の検証で `ErrorCode=4001`。作成済みの成果物は残ります。この検証は最後のタイルの後に行うため、複数タイルの run ではすべてのコールバックが実行済みです(1.7.1 は invoice が不正な最初のタイルで停止)。invoice / MultiDataTile / RDEformat の flow 入口は元の invoice も事前検証するため、flow で必須項目の欠落を補完できません。この早期検証で失敗した場合、flow は呼ばれずタイルの成果物も作られません(`job.failed`・ログ・run report は残ります) |
| 設定ファイルの探索(`config=None`) | `data/tasksupport` から読み込み | 同じ。不正な設定ファイルは v1 と同じく `ErrorCode=999` |
| `rdesys_<タイムスタンプ>.log` の場所 | `data/logs` | 標準構成では同じ |
| 実行中の SIGTERM | プロセスが終了するだけで `job.failed` も記録も残らない | `job.failed` に `ErrorCode=3004`(`RunInterrupted`)、`RunReport` も書き出し、完了済みタイルの成果物は残ります。公開入口の終了コードは 1 |
| 同じデータルートで 2 つの実行が同時に動く(スレッドまたはプロセス)(#737) | 両方の実行が同じタイルファイルに書き込み、片方が書き換え中の送り状を読んで失敗する(例: `ErrorCode=4010`、`4003`、`1`)か、公開される送り状に両方の実行が混ざることがありました | 先に始まった実行がレポートを書き終えるまでデータルートを占有します。2 つ目の実行は直ちに `ErrorCode=3008`(`RunRootBusy`)で拒否され、そのルートには何も書きません。`job.failed`、実行レポート、イベントログは作られません(v1 入口が自分で作る `rdesys_<timestamp>.log` は除く)。v1 コールバック入口と `rdetoolkit run` の終了コードは 1、`Runner.run` は失敗の `RunReport` を返します。別のデータルートでの実行には影響しません。プロセス間のロックはシステムの一時ディレクトリにあるファイルで、占有したプロセスが終了すると OS が解放します。一時ディレクトリが異なるプロセス同士は排他されません | 同時に実行する場合は実行ごとに別のデータルートを使うか、前の実行が終わってから次を始めてください |
| `rdetoolkit run` CLI の終了コード | v1 に `run` コマンドはなし | `0` 成功 / `1` 失敗 / `2` 一部失敗 / `3` 使い方の誤り。Python の v1 コールバック入口は失敗で `SystemExit(1)` を維持。flow 入口は `exit_on_failure=True` で失敗1・一部失敗2を反映し、同じ値を `RunReport.exit_code` でも公開 |
| `multidata_tile.ignore_errors: true` で全タイルが失敗 | MultiDataTile のみ全件 `failed` の JSON を返し終了コード 0。他モードではフラグは無視され最初の失敗で停止 | v1 コールバック入口は全モードで v1 と同じ。flow 入口では全タイル失敗は `failed` となり `job.failed` を書きます |
| `rde2util.Meta.assign_vals` が値 `None` を受け取る(#570) | `None` を文字列 `"None"` として変換します。`number` / `integer` / `boolean` の項目は `StructuredError`(`ERROR: failed to cast metaDef value` など)。コールバックが捕捉しなければ `job.failed` に `ErrorCode=1` となり、`metadata.json` など以降の出力は作られません。`string` の項目は値 `"None"`、`$` 参照の単位は `"unit": "None"` として書き出されます | そのキーは代入されず、`metadata.json` はそのキー(参照単位なら `unit`)を含めずに書き出されます。コールバックの他の出力もそのまま作られます。`None` 以外の変換できない値は従来どおり `ErrorCode=1` |
| `invoice.custom` の値の変換: v1 の `castval` / `_assign_invoice_val` と v2 の `set_custom_fields`(#603) | v1.7.1 までは、format が `uri` / `uuid` / `markdown` の `string` 項目も日付として解釈しようとして失敗します(v1.7.2 と v2 で #622 により修正)。解釈できない日付や日付 format への文字列以外の値は dateutil の `ValueError` / `TypeError` になります。`boolean` 項目の `None` は `False`、`integer` / `number` 項目の `None` は失敗します。スキーマにないキーは `KeyError`。`3.0` のような整数値の float は `integer` で失敗します | `date` / `date-time` / `time` 以外の format は値をそのまま保持します。不一致はすべて v1 と同じメッセージの `StructuredError`(コード 1)で、原因の例外を連鎖します。`None`・NaN・`NaT`・`pd.NA`(NumPy の NaN / NaT を含む)はすべての型で `None` として格納し、NumPy のスカラーは Python の値として変換します。空文字列や空白だけの文字列は適用しません(v1 は `string` 項目に `""` を格納し、他の型では失敗しました。`keep_empty_strings=True` でその動作になります、#619)。スキーマにないキーはコード 4011 `InvoiceCustomKeyUndefined` の `StructuredError`(#621)。`3.0` は `3` になり、`date` / `datetime` オブジェクトも受け付けます。#622 の修正で `castval` も `set_custom_fields` と同じ扱いになった点を除き、v1 の関数自体は変更していません |
| コールバックや flow が処理中に run 単位の invoice(`paths.invoice_org`。MultiDataTile / ExcelInvoice / RDEformat では `temp/invoice_org.json`)へ書き込む(#603) | 後続タイルは書き換え後のファイルから作られるため、前のタイルが書いた値がタイル順に依存して後続へ引き継がれました | サポートしません。`paths.invoice_org` は読み取り専用の入力です。Runner は各タイルの invoice を登録時の invoice から作り(ExcelInvoice と SmartTable はその行を上書き)、タイル固有の値は flow が `save_invoice` で上書きします。各タイルは登録時の状態から始まります。`invoice_org` への書き込みが後続タイルに届くかどうかは v2 では定めていません |

`Meta.assign_vals` の行は Tier 1 API の不具合修正です。そのため v1 コールバック入口にも
適用されます。この不具合は 1.7 系にもありますが、修正を含む 1.7.x はまだリリース
されていません。表の v1 列は最新の v1 リリース 1.7.1 の挙動で、1.7.1 に
ロールバックすると旧挙動に戻ります。今後 1.7.x に同じ修正が入った場合は、その版との
比較ではこの行の差分はなくなります。

run 単位の invoice の行について: 登録時の値は各タイルに用意された invoice を使い、
タイル固有の値はそのタイルの flow の中で求めて `save_invoice` で書き出してください。

### csv2graph / Graph Engine

グラフの入口で意図して変えた振る舞いには、IC-1 から IC-16 までの固定の ID が付いています。
以下の表は話題ごとにまとめ、各表の行は ID の順に並べています。
仕様起点の API(`render_graph`、`GraphSpec`、独自の表の読み取りと描画エンジン)は [Graph Engine](usage/structured_process/graph_engine.ja.md) を参照してください。

`csv2graph`、`plot_from_dataframe`、`rdetoolkit plot` は、図を描画する前に依頼内容を検証します。
次の依頼は `PlotRequestError` になります。これは `PlotConfigError` であり、同時に `ValueError` でもあるため、
`ValueError` を捕捉する既存のコードはそのまま動きます。理由は属性 `reason` で判別できます。
エラーはファイルやディレクトリを作る前に発生します。CLI は同じ条件を終了コード 2 の使い方の誤りとして扱います。

| ID | 変更 | v1 | v2 | 対処 |
|---|---|---|---|---|
| IC-1 | `mode` に `"overlay"` / `"individual"` 以外の値を渡す(大文字小文字の違いや `"dual_axis"` を含む) | 個別グラフとして描画 | `PlotRequestError`(`reason="invalid_mode"`) | 正しい `mode` を渡す |
| IC-2 | `mode="individual"` と `no_individual=True`(CLI では `--mode individual --no-individual`)を同時に指定 | 何も出力せずに終了 | `PlotRequestError`(`reason="contradictory_switches"`)。CLI は終了コード 2 | どちらか一方を外す |

列が 1 つもない表は従来どおり `ColumnNotFoundError`、y 系列がない表は従来どおり `ValueError` です。

個別グラフのファイル名は、最初の図を描く前に全系列分が確保されるため、1 回の実行の中で成果物が互いを上書きすることはありません。

| ID | 変更 | v1 | v2 | 対処 |
|---|---|---|---|---|
| IC-3 | 個別グラフのファイル名が大文字小文字・空白・Unicode 正規化の違いしかない 2 系列(例: `Voltage` と `voltage`、`A B` と `A_B`)、または `/`・`\`・`..` を含むヘッダー | 後の図が先の図を上書き。危険なヘッダーは重ね描き画像を書いた後にエラー | 衝突した系列すべてに系列 ID を付加(`plot_voltage_s000.png`、`plot_voltage_s001.png`)し、`GraphUserWarning` を出す。危険な文字は `_` に置換。衝突しない名前は従来どおり | 特定のファイル名が必要なら列名を変える |

軸範囲は `csv2graph`、`plot_from_dataframe`、`rdetoolkit plot`、`GraphSpec`(`AxisSpec.limits`)で共通の規則により検証されます。
`None` の側は自動範囲のままなので、`xlim=(0, None)` は下限だけを固定します。逆順の範囲(`min > max`)は従来どおり受け付け、軸を反転します。
CLI では `--xmin`、`--xmax`、`--ymin`、`--ymax` でそれぞれ片側だけを指定できます。同じ軸で `--xlim`/`--ylim` と併用すると使用法エラー(終了コード 2)です。
同じ表には、Matplotlib のスタイルと図の所有(IC-5)、単位の混在する重ね描き(IC-6)、2 軸プロット(IC-7)、図の大きさとスタイルの設定(IC-10)の変更も含めています。

| ID | 変更 | v1 | v2 | 対処 |
|---|---|---|---|---|
| IC-4 | `(0, None)` や `(None, 10)` のような片側だけの `xlim`/`ylim`。有限でない値、上下限が等しい範囲、対数軸(`logx`/`logy`)での `0` 以下の値 | 片側だけの指定は無視(両側とも自動)。不正な範囲は Matplotlib に渡され、警告とともに無視 | 指定した側だけを適用し、もう片側は自動のまま。不正な範囲は何も書き出す前に `PlotRequestError`(`reason="invalid_axis_limits"`)となり、軸と値をメッセージで示す。CLI は終了コード 2 | 従来の完全自動にしたい場合は範囲を省略する。対数軸では正の値を渡す |
| IC-5 | `csv2graph`・`plot_from_dataframe`・`rdetoolkit plot` 実行後の Matplotlib のスタイルと図 | グラフ用のスタイル(`font.size` 20、内向きの目盛りなど)がプロセス全体の `rcParams` に残り、後の描画にも影響した。保存に失敗した場合も含め、図はすべて開いたまま残った | スタイルは図の描画と保存の間だけ適用され、呼び出し後の `rcParams` は変わらない。保存した図は書き込みに失敗した場合も閉じる。`return_fig=True` で返す図は開いたまま呼び出し側の所有となり(`plt.close` で閉じる)、レイアウトが固定されるため 300 dpi で保存すると従来と同じ画像になる。バックエンドは切り替えない | 後の描画が従来のグローバルなスタイルに依存していた場合は、描画の前に `apply_matplotlib_config()` を呼ぶ |
| IC-6 | `csv2graph`・`plot_from_dataframe`・`rdetoolkit plot` の重ね描きに単位の異なる系列(例: `voltage (V)` と `current (A)`)があり、`y_label` を指定しない | y 軸のラベルは最初の列だけから作られ(`Voltage (V)`)、重ね描きにもすべての個別グラフにも使われた | 重ね描きは従来どおり描画するが、`GraphUserWarning` を出し、y 軸のラベルにすべての単位を並べる(`Voltage (V) / Current (A)`)。個別グラフはそれぞれの列から作ったラベルになる(`Current (A)`)。単位は文字列として比較し、換算はしない(`mV` と `V` は別の単位)。単位のない列は互換とみなし、換算しない。`render_graph` は同じ重ね描きを既定で `PlotRequestError`(`reason="unit_mismatch"`)とし、`GraphSpec(unit_policy="split")`(単位ごとに重ね描き)、`"warn"`、`"allow"` を選べる | すべての図で同じラベルにしたい場合は `y_label=` を渡す。単位ごとに分けて描画してもよい |
| IC-7 | `PlotMode.DUAL_AXIS` または `y2_axis` を含む従来の `PlotConfig` を描画する(例: `collect_render_results(df, config, PlotMode.DUAL_AXIS)`、`MatplotlibRenderer.render_overlay`、`PlotlyRenderer.render_html`、描画ストラテジー) | `collect_render_results` に `PlotMode.DUAL_AXIS` を渡すと、代わりに個別グラフを黙って描画した。`y2_axis` は無視された。`DualAxisStrategy` は `PlotConfigError` | 2軸プロットは非対応。図やファイルを作る前に `PlotRequestError`(`reason="dual_axis_unsupported"`、従来どおり `PlotConfigError` でもある)となり、別の図への代替描画はしない。メッセージに代替手段を示す。`PlotMode.DUAL_AXIS`・`set_y2_axis`・`y2_axis`・`DualAxisStrategy`・`DualAxisError` は引き続きインポートできるが、`DualAxisStrategy` は `rdetoolkit.graph.strategies.__all__` から外した。`csv2graph`・`plot_from_dataframe`・`rdetoolkit plot` の `mode="dual_axis"` は従来どおり不正なモード(IC-1) | 単位ごとに分けて描画する: `render_graph` に `GraphSpec(unit_policy="split")`、`mode="individual"`、または `Axes.twinx()` で作った Matplotlib の図を `save_figure` ノードで保存 |
| IC-10 | `build()` の前に `PlotConfigBuilder.set_figure_size(...)` または `set_matplotlib_params(...)` を呼び、その設定を `MatplotlibRenderer` や描画ストラテジーで描画する。`render_graph` に `GraphSpec.style` を渡す | どちらの設定も無視され、図は常に 8.85 x 8 インチ・グラフ用の既定スタイルだった | 生成された `PlotConfig.style`(`StyleSpec`)が図のサイズを決め、rcParams を既定スタイルの上に、その呼び出しの図にだけ適用する。HTML はサイズを明示した場合だけそのサイズになる。不正なサイズや rcParam は図を作る前に `PlotRequestError`(`reason="invalid_figure_size"` または `"invalid_rc_param"`)となる。設定メソッド自体は従来どおりどの値も受け付ける | 従来の図のままにしたい場合は設定メソッドを呼ばない |

Matplotlib(PNG/SVG/PDF)と Plotly(HTML)の図は、1 つに解決された系列の計画から描画されます。
列の位置、x と y の対応、方向による分割と絞り込み、凡例の項目、系列の色は描画の前に一度だけ決まるため、
不正な列の指定は図を作る前にエラーになります。凡例のラベルは各バックエンドで v1 の形を保ちます
(画像では整形済み、HTML では列名どおり)。

| ID | 変更 | v1 | v2 | 対処 |
|---|---|---|---|---|
| IC-11 | 同じ見出しを持つ 2 つの y 列を位置または既定の選択で指定する。`direction_cols` が `y_cols` より少ない状態で `PlotlyRenderer.render_html` を直接呼ぶ。凡例ラベルが等しい系列 | 同じ見出しは `ValueError`("resolved to a slice")。Plotly は短い方向列リストで `ValueError`。HTML はラベルの等しい系列をすべて凡例に並べ、同じ色にした | 両方の列をそれぞれのデータで描画する。短い方向列リストは画像と同様に補完する(足りない系列は方向列なし)。等しいラベルは凡例に 1 回だけ載り、色は画像でも HTML でも系列の位置で決まる。共有された見出しを名前で指定すると `PlotRequestError`(`reason="ambiguous_column"`) | 対処は不要。凡例で区別したい場合は列名またはラベルを変える |

描画エンジンは差し替えられます。`render_graph` の `renderers` に `RendererRegistry` を渡すと、成果物ごとに、その形式と図の種類を `RendererCapabilities` で宣言している最初の描画エンジンが使われます。`GraphRenderer` プロトコル(`capabilities`、`render`、`export`、`close`)を満たす任意のオブジェクトを登録でき、rdetoolkit の内部を書き換える必要はありません。省略時は呼び出しごとに新しい `builtin_renderers()`(画像は Matplotlib、重ね描きの HTML は Plotly)を使います。対応しない形式、個別グラフの HTML、Plotly が入っていない環境での HTML は、ファイルやディレクトリを作る前に `UnsupportedFormatError` または `RendererUnavailableError`(`ImportError` の一種で、`pip install "rdetoolkit[plotly]"` を案内する)になります。`csv2graph` と `plot_from_dataframe` の `html=True` も、描画を始める前に Plotly の有無を確認します。従来も Plotly がなければファイルを書き出す前に `ImportError` で失敗していたため、`ImportError` を捕捉するコードはそのまま動きます。

表形式の自動判定(`csv_format="auto"`、`--csv-format auto`、`render_graph` の既定 `reader="auto"`)は、ファイル先頭の限られた範囲(最大 64 KiB・50 行)だけを読み取り専用で調べ、判断の根拠を `DetectionDecision` として返します。確信が持てないファイルは推測せずにエラーにします。`csv2graph` と `rdetoolkit plot` の既定は従来どおり `standard` です。`rdetoolkit plot --detect` で、描画せずに判定結果(選ばれる読み取り方法、根拠、列名、行数)を確認できます。

| ID | 変更 | v1 | v2 | 対処 |
|---|---|---|---|---|
| IC-8 | `ParserFactory.auto_detect` に、1 行目がすべて数値のファイル、1 行目に文字と数値が混在するファイルなど形式を決めきれないファイルを渡す | ヘッダーなしの形式(`NoHeaderParser`)と推測。ヘッダー付きで最初のデータ行が数値のファイルも、ヘッダーをデータとして読んでいた | `AmbiguousFormatError` を出し、候補・根拠・対処(`--csv-format`)をメッセージに示す。ヘッダー付きのファイルはヘッダーとして読み、転置・タブ区切り・Shift-JIS・メタデータブロックのファイルにはそれに合う parser を返す。空のファイルは `InvalidCSVFormatError` | 形式を明示する(`ParserFactory.create(...)`、`csv_format=...`、`--csv-format ...`) |

成果物の出力先は `render_graph` の `OutputSpec(sink=...)` で指定します。`DirectorySink` は通常のディレクトリへ、`OutputContextSink` は RDE の `OutputContext` のディレクトリへ書き込みます。
振り分けは従来の csv2graph と同じで、重ね描きの画像は `main_image`、個別グラフの画像は個別グラフ用のディレクトリ(`OutputContextSink` では `other_image`)、HTML は HTML 用のディレクトリ(`OutputContextSink` では `struct`)です。
画像は PNG・SVG・PDF を重ね描きと個別グラフに、HTML は重ね描きにだけ出力できます。それ以外の組み合わせは何かを書き込む前に `UnsupportedFormatError` に、Plotly がない場合の HTML は `RendererUnavailableError`(インストール方法を示す `ImportError`)になります。
出力先は名前と実際のパス(シンボリックリンクの先を含む)の両方で検査され、ディレクトリの外を指すものは `OutputPathError`(`ValueError`)です。既存のファイルは既定で上書きし、`Artifact.replaced_existing` に記録します。`OutputSpec(on_existing="error")` では描画の前に `ArtifactCollisionError` になります。
`GraphResult.manifest_json()` はすべての成果物を計画の順に、ファイル名だけで列挙します(表形式の判定結果も構造化して含みます)。同じ依頼なら出力先のディレクトリが違っても同じ内容になり、HTML のバイト列も同じです。

| ID | 変更 | v1 | v2 | 対処 |
|---|---|---|---|---|
| IC-9 | 出力先のファイルがシンボリックリンクで、出力ディレクトリと文字列の先頭が同じ別のディレクトリ(例: `out` に対する `out2`)を指す。`csv2graph`・`plot_from_dataframe`・`rdetoolkit plot`・`FileWriter` が使う `PathValidator` | 文字列の前方一致で判定していたため、ディレクトリの内側として書き込んだ | パスの構成要素で判定し、`ValueError`("Security violation")とする。従来の保存処理は、最初のファイルを書く前にすべての出力先を検査する | なし(セキュリティ修正) |
| IC-13 | `OutputConfig.formats` に PNG 以外の画像形式(例: `["png", "svg"]`)を指定して `IndividualStrategy` で描画する | 個別グラフは常に PNG だけ | 系列ごとに、HTML 以外の各形式で 1 ファイルずつ(同じファイル名で拡張子だけが異なる)出力する。画像形式が 1 つもなければ従来どおり PNG。`csv2graph` と `plot_from_dataframe` の出力は変わらない | PNG だけにしたい場合は `formats=["png"]` を指定する |
| IC-14 | `xlim`/`ylim`(または `AxisSpec.limits`)を指定して HTML を出力する(`html=True`、`PlotlyRenderer`、`render_graph`) | HTML では軸範囲を無視し、常に自動範囲 | 画像と同じ範囲を HTML の軸にも適用する。対数軸は 10 を底とする対数で指定し、`None` の側は自動のまま | 自動範囲にしたい場合は範囲を指定しない |
| IC-15 | `MatplotlibRenderer.render_individual(df, config, y_col_index)` に、フレームの列数を超える `y_col_index` を渡す | 描画中に pandas の `IndexError` | 図を作る前に `PlotRequestError`(`reason="unknown_column"`、`ValueError` であり `IndexError` ではない)。フレームにあるが `config.y_cols` に含まれない列は、v1 と同じく描画する | `IndexError` ではなく `ValueError` か `PlotRequestError` を捕捉する |
| IC-16 | `invert_x`/`invert_y`(または `AxisSpec.invert`)を指定して HTML を出力する(`html=True`、`PlotlyRenderer`、`render_graph`) | 画像では軸が反転するのに、HTML では反転を無視して通常の向きのまま | 画像と同じく HTML の軸も反転する。自動範囲の軸はそのまま反転し、範囲を指定した場合は反転した範囲になる(対数軸は 10 を底とする対数)。`None` の側は自動のまま | 通常の向きにしたい場合は `invert_x`/`invert_y` を指定しない |

組み込みノード `plot_lines` と `plot_scatter` は、列・ペア・複数フレーム・系列ラベルの解決と軸範囲の検証に、`render_graph` と同じ計画処理と検証を使います。同じ依頼は両方の API で同じ系列・ラベル・データになります。ノード ID、引数、呼び出し記録、出力先、画像は変わらず、csv2graph 用のスタイルも適用しません。`save_figure` は従来どおり呼び出し側の図を閉じずに保存します。

| ID | 変更 | v2 プレリリース | v2 | 対処 |
|---|---|---|---|---|
| IC-12 | `plot_lines`・`plot_scatter` に存在しない列名、または複数の列が持つ列名を渡す。`plot_lines` に不正な `xlim`/`ylim`(有限でない値、上下限が等しい範囲、`"log"` 軸での `0` 以下の値)を渡す | 存在しない列は `KeyError`。重複した列名は、`plot_lines` では該当する列すべてを 1 つのラベルで描画し、`plot_scatter` では Matplotlib の `ValueError`。不正な範囲は Matplotlib に渡され、警告とともに無視または自動で拡張 | 図を作る前に `PlotRequestError`(`ValueError` の一種)。`reason` は `"unknown_column"`、`"ambiguous_column"`、`"invalid_axis_limits"` | `KeyError` を捕捉していた場合は `ValueError` または `PlotRequestError` を捕捉する。列名を一意にし、対数軸では正の値を渡す |

### 診断と従来のトレースバック

v2 で失敗を調べるときは、コーディングエージェントを使うかどうかにかかわらず
`rdetoolkit report diagnose <run_report.json> --json` を使います。バージョン付きの出力は、
例外メッセージ、ローカル変数、環境変数の値、入力ファイルのパスを含みません
([診断コマンド](usage/diagnostics.ja.md)を参照)。従来のトレースバック API
(`handle_exception`、`CompactTraceFormatter`、`SecretsSanitizer`、`Config.traceback`、
`TRACE_VERBOSE` / `TRACE_FORMAT`)は変更せず、新しい非推奨警告も出しません。
`<STACKTRACE>` 形式は v1 コールバック入口でのローカル利用のために残しますが、
エージェントに渡す形式としては推奨しません。変数名によるマスキングは匿名化ではありません。
[互換性表](usage/structured_process/traceback.ja.md)を参照してください。

`repro export` のアーカイブは 2 種類になりました。生の入力を含み、手元から出す前に確認が必要な
完全なアーカイブと、ダイジェストと診断だけを含み再実行には使えない `--manifest-only` です。
`repro export` は既存の `-o` のファイルを置き換えなくなり、`repro import` は安全でないアーカイブや
整合しないアーカイブを拒否します([repro](usage/cli.ja.md)を参照)。自動アップロードは行いません。

### ロールバック

v2 で問題が出た場合は、v1 系の最新版 `1.7.1` を固定してください(例:
`requirements.txt` に `rdetoolkit==1.7.1`)。旧経路を含む開発版は PyPI にはなく、
git タグ `v2.0.0a1` からのソースインストールのみ可能です(切り分け用途。この
タグの `__version__` は `2.0.0` と表示されます)。

### スケジュール

`2.0.0rc1` → GA `2.0.1` の順に公開します。版番号 `2.0.0` は欠番で、
正式版としては公開しません。

## 登録モード選択とreproの変更

v2 flowでは`system.extended_mode`を登録単位の明示指定として扱います。
canonical名は`invoice`、`multidatatile`、`smarttable`、`excelinvoice`、
`rdeformat`です。従来の`Invoice`、`MultiDataTile`、`SmartTableInvoice`、
`ExcelInvoice`、`RDEFormat`も完全一致のaliasとして使用できます。
その他の綴りや大小文字は、有効な名前を示す設定エラーになります。

設定の省略とnullは自動選択です。明示的な`invoice`はInvoiceモードの要求なので、
SmartTableやExcelInvoice入力との競合を拒否します。競合ファイルを取り除くか、
その形式を明示指定してください。複数の特殊形式やworkbook、曖昧な特殊archiveも
登録前に拒否します。通常ファイルが複数あってもInvoiceでは1タイルです。
1ファイルずつ登録する場合は`multidatatile`を指定してください。

v1 callback経路は従来のファイル検出優先順位とW1001を維持します。
同じ競合入力でもv2 flowではカタログ登録済み設定エラーになります。
設定ファイルがv1形式でも、flowの選択契約はv2です。

`RDEFormat`という綴りは、設定読込とreproでそのまま保持します。
互換callbackでは`RDEFormat`はInvoice、`rdeformat`はRDEFormatとして扱われるため、
両者のconfig digestは異なります。v2 flowでは実行境界で`RDEFormat`を
`rdeformat`に正規化します。repro後も同じ入口で再実行すれば、モードとタイル数を維持します。

設定正規化と新しいrepro archiveは、invoiceが明示指定されたかどうかを保持します。
config digestも自動選択と明示invoiceを区別します。以前のexportが既に省略した
明示性は復元できません。モードが省略されていた、または既定値で保存されていた
過去archiveや、`RDEFormat`と`rdeformat`を同一digestにしていた版のarchiveは、
現行版のimportでconfig digestが一致せず、終了コード3になる場合も
あります。そのarchiveを作成したRDEToolKitのバージョンでimportしてください。
復元した`rdeconfig.yaml`を確認して意図したモードを設定し、現行版で再実行して
新しいレポートとarchiveをexportします。archive内の設定だけを書き換えても、
manifestとレポートのdigestは修復されません。

`rdetoolkit run pkg.mod:pipeline --validate-only --explain --format json`は現在の入力を読み取り専用で
説明します。ユーザーのprepareやflowを実行せず、成果物やレポートを出力しません。
タイルのグループ・順序・出力先・モード別stageを確認できます。
既存の`--validate-only`単独はprepareとレポート出力を維持します。
prepareが入力を変更する場合、後の実行ではその変更後のsnapshotが対象になります。

system fileを除外した後、各モードは次の登録グループを作ります。
タイル0は解決済みdata root直下、タイル1以降は`divided/0001/`、
`divided/0002/`のように出力します。この番号は出力タイルのindexであり、
RDEFormat archive内のディレクトリ番号とは異なる場合があります。

| モード | グループと順序 | タイル数 |
| --- | --- | --- |
| `invoice` | 通常ファイルとZIPをすべて1グループにする。ZIPは展開せず生入力として扱う。通常ファイル、ZIPの順で、それぞれの内部はfilesystem順。 | 空入力を含めて1 |
| `multidatatile` | 1入力ファイルを1グループにする。既定の`name`はファイル名順、`filesystem`はディレクトリの列挙順。 | ファイル数。空入力は1空タイル |
| `smarttable` | 各データ行が参照するファイルをグループにする。最終行がタイル0、先行する行は表の順。`save_table_file=true`なら元の表がタイル1、先行する行はタイル2から。 | データ行数。元の表を保存する場合はさらに1 |
| `excelinvoice` | workbookのデータ行ごとに1グループを作り、workbook順に並べる。ZIPがなければ生ファイルは空。フォルダグループが1つなら全行で共有できる。ファイル指定はarchive内で一意なファイル名が必要。 | データ行数。データ行がないworkbookは拒否 |
| `rdeformat` | ZIPのパスで最初に現れる4桁の数値ディレクトリごとにグループ化し、該当しないmemberはグループ0に入れる。グループは数値順、内部はarchive内の順序。 | グループ数。空ZIPは1空タイル |

ExcelInvoiceで親フォルダと子フォルダの両方にファイルがある場合は、従来どおり
親を先にグループ化してからworkbook順を適用します。各ファイルと対応行のinvoiceを維持します。

ヘッダーだけのSmartTableは0タイルですが、`save_table_file=true`なら元の表だけを
タイル0にします。元の表のタイルではflowを呼びません。このSmartTableのindexは、
rootタイルを最後に登録するRDEの慣例を維持しています。

v2 RDEFormatは数値ディレクトリでグループを並べ、各グループ内はarchive内の順序を
previewと実行で共有します。v1 callback内のfilesystem順序は維持します。
MultiDataTileの`filesystem`指定は順序の非決定性を説明出力に示します。

RDEFormatのレポート`datatile_id`と`target`は従来どおり最初の入力から決まります。
v2はarchive順の先頭を使うため、callbackのfilesystem順の先頭とは値が異なる場合が
あります。タイルindexと成果物の出力先は既存契約を維持します。
v2の特殊入力の不正レイアウトは、展開やinvoice不足の検証より先に計画エラーになる
場合があります。callbackは従来のエラー優先順位と部分成果物を維持します。
