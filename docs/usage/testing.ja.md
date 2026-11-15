# 構造化処理のテスト

rdetoolkit は pytest プラグインを同梱しています（`pytest11` エントリポイントで
登録されるため、rdetoolkit と pytest をインストールすれば自動で読み込まれます）。
テストは 3 段階あり、確認したい範囲を満たす最小の段階を選びます。

| 段階 | 道具 | Runner を実行するか | 主な用途 |
|------|------|---------------------|----------|
| 単体 | `@node` / `@flow` 関数を直接呼ぶ、`rde_paths`・`rde_out`・`rde_config`・`rde_invoice` fixture | しない | 1 つのノードのロジック |
| 結合 | `rde_runner` fixture → `RdeTestResult` | する（複製上で） | invoice や tasksupport を含む実プロジェクト |
| 宣言的 | `rde_case` マーカー + `rde_run` fixture | する（複製上で） | 装置やデータ形状ごとのシナリオ |

`rdetoolkit.testing.run_flow` はこれまでどおり利用できます。

## `rde_runner` による隔離実行

```python
from pathlib import Path

from modules.processing import main  # 対象の flow

PROJECT = Path(__file__).parent / "cases" / "sample"


def test_process(rde_runner):
    run = rde_runner.run(flow=main, project=PROJECT)
    run.assert_success()
    assert (run.data_root / "structured" / "result.csv").exists()
```

`rde_runner.run(flow=..., project=..., config=None)` は次のように動作します。

- `project` をテストの `tmp_path` 配下の新しいディレクトリ
  （`<tmp_path>/rde_runner/run-NNN/<プロジェクト名>`）に複製します。元の
  fixture には一切書き込まず、呼び出しごとに別の複製を作るため、テスト同士や
  実行順序に依存しません。シンボリックリンクは内容としてコピーします。
- 2 つのレイアウトに対応します。`data/`（`data/inputdata`・`data/invoice`・
  `data/tasksupport`）を持つプロジェクトディレクトリと、`inputdata/`・
  `invoice/`・`tasksupport/` を直下に持つ alias-flat なデータルートです。
  データルートは本番と同じ規則で決まります。
- 複製したプロジェクトを作業ディレクトリにして、`workflows.run(flow=...,
  config=...)` と同じく実際の Runner で flow を実行します。呼び出し元の
  作業ディレクトリは実行後に元へ戻ります。
- `config` には `RdeConfig` または上書き用マッピング
  （例: `{"system": {"extended_mode": "MultiDataTile"}}`）を渡せるので、
  すべてのモードをテストできます。
- `flow` は flow 関数または具象 `ProcessingTemplate` サブクラスです。
- 相対パスの `project` は現在の作業ディレクトリを基準に解決します。

失敗した実行は例外にならず、**結果として返ります**。Runner 自体から送出される
例外（`KeyboardInterrupt` や、呼び出し可能でない flow に対する `TypeError` など）
はそのまま伝播し、複製は調査用に残ります。

### `RdeTestResult`

| 属性 | 意味 |
|------|------|
| `report` | `RunReport` |
| `status` | `"success"`・`"partial"`・`"failed"` |
| `project_root` | 複製したプロジェクト |
| `data_root` | 複製側のデータルート |
| `iterations` | タイルごとの `RdeIterationSummary`（`index`・`datatile_id`・`status`・`error_code`・`error_name`・`error_message`） |
| `report_path` | `logs/run_report_<run_id>.json`、なければ `None` |
| `events_path` | `logs/events_<run_id>.jsonl`、なければ `None` |
| `diagnostics_path` | `logs/diagnostics_<run_id>.json`、診断サイドカーが書かれていなければ `None` |
| `job_failed_path` | `job.failed`、なければ `None` |
| `artifact_path(name)` | `data_root / name`。絶対パスや `..` を含む名前は `ValueError` |
| `assert_success()` | 成功以外なら `AssertionError` |
| `assert_*`・`read_*`・`iter_csv` | 成果物のアサーションと上限付きの読み込み（下記「成果物のアサーション」） |
| `assert_checks(*checks)` | 再利用可能なチェックを明示的に実行（下記「再利用可能なチェック」） |

`assert_success()` のメッセージには、ステータス、実行全体のエラー、失敗した
各タイル（カタログコード・名前・メッセージ・記録されたスタックトレース）と、
データルート・`job.failed`・実行レポート・診断サイドカーの場所が含まれます。

`RdeTestRunner(base_dir)` は pytest を使わない同じランナーです。fixture は
`RdeTestRunner(tmp_path / "rde_runner")` を返します。

## `rde_case` による宣言的なケース

```python
from rdetoolkit.testing import rde_case

from modules.processing import main


@rde_case(
    flow=main,
    project="tests/cases/valid_measurement",
    expect_status="success",
    expect_files=("structured/result.csv",),
)
def test_valid_measurement(rde_run):
    assert "time" in rde_run.artifact_path("structured/result.csv").read_text(encoding="utf-8")
```

`rde_case(...)` は通常の pytest マーク（`pytest.mark.rde_case`）を返します。
テストモジュールの import 時や収集時には何も実行しません。`pytest --collect-only`
やエディタのテスト探索で flow が実行されたり、データが複製・変更されたりする
ことはありません。

`rde_run` fixture は fixture のセットアップ時に最も近い `rde_case` マーカーを
読み、`rde_runner` でケースを実行して `RdeTestResult` を返します。テスト本体の
実行前に宣言した期待値を検査し、満たさない場合はテストが説明付きで **失敗**
します。

| パラメータ | 意味 |
|------------|------|
| `flow` | flow 関数または具象 `ProcessingTemplate` サブクラス（必須） |
| `project` | プロジェクトディレクトリまたは alias-flat なデータルート（必須）。相対パスは pytest の rootdir を基準に解決 |
| `expect_status` | `"success"`（既定）・`"partial"`・`"failed"` |
| `expect_files` | 存在すべき成果物。隔離されたデータルートからの相対パス |
| `expect_error_code` | 実行全体またはいずれかのタイルが記録すべきカタログコード（成功以外のケースのみ） |
| `expect_phase` | 診断サイドカーが記録すべきフェーズ（成功以外のケースのみ） |
| `config` | `RdeConfig` または上書き用マッピング |
| `checks` | 実行後に走らせる再利用可能な出力チェック（下記「再利用可能なチェック」） |

設定の誤りは、データを複製する前に fixture セットアップ時のテストエラーとして、
該当パラメータを示すメッセージで報告されます。対象は、位置引数、未知の
パラメータ、存在しない・ディレクトリでないプロジェクト、未知のステータス、
文字列 1 つで渡した `expect_files`、絶対パスや `..` を含む期待パス、成功ケースに
指定したエラーコードやフェーズです。`rde_case` を付けたのに `rde_run` を要求しない
テストもエラーになります。そのままではケースが一度も実行されないためです。

### 複数のデータケース

`pytest.param(..., marks=...)` でパラメータごとにケースを持たせます。`id` が
読みやすいテスト ID になります。

```python
import pytest


@pytest.mark.parametrize(
    "label",
    [
        pytest.param("valid", marks=rde_case(flow=main, project="tests/cases/valid"), id="valid-measurement"),
        pytest.param(
            "broken",
            marks=rde_case(flow=main, project="tests/cases/broken", expect_status="failed", expect_error_code=3001),
            id="broken-reader",
        ),
    ],
)
def test_measurements(rde_run, label):
    ...
```

通常の `pytest.mark.parametrize` の引数もデコレータ付きのケースと組み合わせられ、
各項目がそれぞれの複製でケースを実行します。

## 成果物のアサーション

`RdeTestResult` には、隔離実行の成果物を確かめる小さく組み合わせやすい
アサーションがあります。名前はすべてデータルートからの相対パスで（絶対パスや
`..` は `ValueError`）、失敗メッセージは成果物、差分の内容、保持された実行の
場所（データルートと実行レポート）を示します。

```python
def test_process(rde_runner):
    run = rde_runner.run(flow=main, project=PROJECT)
    run.assert_status("success")
    run.assert_artifact("structured/result.csv")
    run.assert_artifact("job.failed", exists=False)
    run.assert_csv_columns("structured/result.csv", {"time", "value"})
    run.assert_json_subset("invoice/invoice.json", {"custom": {"temperature": 300}})
    run.assert_metadata_valid()
```

| メソッド | 確認内容 | 失敗時の表示 |
|----------|----------|--------------|
| `assert_status(status)` | 実行ステータス | ステータス、実行とタイルのエラー、成果物の場所 |
| `assert_error_code(code)` | 実行またはタイルのカタログコード | 記録されたコード |
| `assert_artifact(name, exists=True)` | 存在・非存在 | パスと同じ場所にあるファイル |
| `assert_tree(files, root=None, ignore=())` | データルート（または `root`）以下のファイル集合が完全一致 | 不足・余分なファイル |
| `assert_json_subset(name, expected)` | JSON が `expected` を含む | JSON ポインタごとの差分 |
| `assert_json_equal(name, expected)` | JSON の完全一致 | 不足・変更・余分なポインタ |
| `assert_csv_columns(name, columns, exact=False)` | CSV ヘッダ | 不足列（`exact` なら余分な列も） |
| `assert_csv_rows(name, rows)` | すべてのデータ行をセル単位で（セルは文字列） | 行数、変更のある行番号と列 |
| `assert_metadata_valid(name="meta/metadata.json", definition="tasksupport/metadata-def.json")` | メタデータの構造と、全キーが定義に含まれること（`definition=None` でキー確認を省略） | 検証エラーまたは未定義キー |
| `assert_invoice_valid(name="invoice/invoice.json", schema="tasksupport/invoice.schema.json")` | invoice がスキーマに適合 | 検証エラー |
| `assert_snapshot(artifact, golden, ...)` | 承認済みゴールデンとの一致 | 下記「ゴールデンスナップショット」 |

JSON の値は厳密に比較します。`1`・`1.0`・`true` は別の値で、`null` とキーが
ないことも区別します。`assert_tree` の `ignore=` は `"logs/*"` のような
`fnmatch` パターンで、列挙したもの以外は無視しません。

読み込み用の `read_bytes`・`read_text`・`read_json`・`read_csv`（行は
`{列: セル}`、セルは文字列）は既定で 16 MiB を超えるファイルを拒否します
（`max_bytes=None` で上限なし）。大きな CSV は `iter_csv` で逐次読み込めます。
同じ関数は `rdetoolkit.testing.assertions.<name>(run, ...)` としても使えます。

## ゴールデンスナップショット

`assert_snapshot` は、成果物のファイルまたはディレクトリを、レビューして
コミットしたゴールデンファイルと比較します。期待値をテスト実行時に本番コード
から導出することはありません。

```python
GOLDEN = Path(__file__).parent / "golden"


def test_structured_output(rde_runner):
    run = rde_runner.run(flow=main, project=PROJECT)
    run.assert_snapshot(
        "structured",
        GOLDEN / "structured",
        ignore_fields=("/run_id",),     # JSON ポインタ。'*' は任意のキー・添字
        ignore_columns=("timestamp",),  # CSV の列
        ignore_files=("*.log",),        # ディレクトリ比較から外すファイル
    )
```

- `.json` は JSON ポインタ単位、`.csv` はセル単位、その他のテキスト
  （`.txt`・`.md`・`.yaml` など）は行差分、それ以外（画像やバイナリ形式）は
  サイズと sha256 で比較します。バイナリを文字列に変換することはありません。
- 正規化するのは列挙したものだけです。無視したフィールドや列もキー・ヘッダは
  残り（削除されれば差分になります）、値だけが両側で
  `<rde-snapshot:ignored>` に置き換わります。
- 不足・余分なファイル、セルや値の変更、`null` とキーの不在、`1` と `1.0`、
  改行コードの変化はすべて報告されます。相対パスの `golden` はカレント
  ディレクトリ基準で解決されるため、`Path(__file__).parent / ...` を推奨します。

**変更の承認。** 一致しない（またはまだ存在しない）スナップショットは失敗し、
変更されるファイルを正確に列挙します。承認するには変更をレビューしたうえで
ローカルで実行します。

```bash
pytest --rde-update-snapshots
```

ゴールデンファイルが書き換えられ（生成されなくなったファイルは削除）、
ターミナルのサマリ `rdetoolkit: snapshot updates` に全ファイルが表示されます。
環境変数 `CI` が真の値のときこのオプションは **拒否** され、`update=True` も
拒否されるため、CI が変更を承認することはありません。

**プライバシー。** ゴールデンファイルは通常リポジトリと一緒にコミット・公開
されます。`inputdata/`・`raw/`・`nonshared_raw/` のスナップショットは
`allow_raw=True` を渡さない限り拒否します。無視したフィールドはプレース
ホルダとして書かれるため、run ID やタイムスタンプはゴールデンに残りません。
シンボリックリンクの成果物と、`max_bytes`（既定 16 MiB）を超えるファイルも
拒否します。共有してよいものだけをスナップショットしてください。

## 再利用可能なチェック

チェックは `RdeTestResult` を受け取り、例外（通常は `assert`）で失敗を示す
関数です。`rde_check(id=...)` は失敗メッセージ用の安定したルール ID を付ける
だけで、同じ関数を返します。通常の関数や lambda もそのまま使えます。

```python
from rdetoolkit.testing import rde_case, rde_check


@rde_check(id="xrd.positive-intensity")
def positive_intensity(run):
    rows = run.read_csv("structured/peaks.csv")
    assert all(float(row["intensity"]) >= 0 for row in rows)


@rde_check(id="invoice.temperature")
def physical_temperature(run):
    assert run.read_json("invoice/invoice.json")["custom"]["temperature"] >= 0


@rde_case(flow=main, project="tests/cases/xrd", checks=(positive_intensity, physical_temperature))
def test_xrd(rde_run):
    pass


def test_xrd_without_the_decorator(rde_runner):
    run = rde_runner.run(flow=main, project=PROJECT)
    positive_intensity(run)  # 通常の呼び出し
    run.assert_checks(positive_intensity, physical_temperature)
```

- チェックは実際の Runner の実行後、テストが列挙した場所でだけ実行されます。
  どこにも登録されず、本番の実行から呼ばれることはありません。
- `rde_case` では `expect_status` が満たされたときにチェックを実行し、失敗した
  チェックをすべて報告します。処理結果が期待と異なる場合はそれを報告し、
  チェックを実行しなかったことを示します。
- 失敗は `output contract failed: rde_check '<id>'` で始まり、データセット、
  結果のヘルパーで読んだ全成果物とそのタイル（`divided/0001/...` はタイル 1）
  とデータタイル、アサーションとその行を示します。
- 失敗したチェックは pytest のテストを失敗させるだけで、実行の
  `RunReport.status` や `job.failed` は変わりません。
- 値を返すチェック（例: `return all(...)`）は失敗扱いです。チェックは例外で
  失敗を示す必要があり、`assert` の書き忘れが黙って通ることはありません。

ネガティブケースは、既知の不正データとチェックを組み合わせ、失敗を明示的に
期待します。

```python
def test_negative_intensity_is_caught(rde_runner):
    run = rde_runner.run(flow=main, project="tests/cases/xrd_negative")
    with pytest.raises(AssertionError, match="xrd.positive-intensity"):
        run.assert_checks(positive_intensity)
```

## `rdetoolkit test`

`rdetoolkit test [PATH] [PYTEST_ARGS]...` は、同じインタプリタ・カレント
ディレクトリで `python -m pytest` を実行し、引数をすべてそのまま渡して、
pytest の終了コードで終了します。最初の一歩のための便利コマンドで、`pytest`
そのものと完全に等価です。プラグインやオプションを直接管理する CI では
`pytest` の直接実行を推奨します。

```bash
pip install "rdetoolkit[testing]"   # rdetoolkit だけでは pytest は入りません
rdetoolkit test
rdetoolkit test tests/ -k xrd -x
rdetoolkit test -- --help           # '--' 以降は必ず pytest に渡ります
```

pytest がない場合はインストール方法を表示して終了コード 2 で終了します。
どちらのコマンドでも、`rde_runner` または `rde_run` を使って失敗したテストには
pytest 自身の失敗出力のあとに `rdetoolkit: retained runs` セクションが表示され、各実行の
データルート・実行レポート・診断サイドカー・`job.failed` の場所を示します。

## pytest がない環境

`rdetoolkit.testing` を import しても pytest は import されず、`RdeTestRunner`
は通常のスクリプトでも使えます。pytest が必要なのは `rde_case(...)` だけで、
pytest がない場合は理由を示す `ImportError` を送出します。
