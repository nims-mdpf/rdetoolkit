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

## pytest がない環境

`rdetoolkit.testing` を import しても pytest は import されず、`RdeTestRunner`
は通常のスクリプトでも使えます。pytest が必要なのは `rde_case(...)` だけで、
pytest がない場合は理由を示す `ImportError` を送出します。
