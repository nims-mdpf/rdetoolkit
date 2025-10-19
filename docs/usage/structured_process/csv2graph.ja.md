# csv2graph ユーザーマニュアル

## 概要

`csv2graph`は、CSVファイルやPandas DataFrameから静的なグラフ画像（PNG）やインタラクティブなHTMLグラフ（Plotly）を自動生成するPythonモジュールです。バッテリーサイクルデータ、X線回折（XRD）、X線光電子分光（XPS）などの実験データの可視化に対応しています。

## 主な機能

- **多様なCSVフォーマット対応**: 標準CSV、転置CSV、ヘッダー無しCSVに対応
- **柔軟なプロットモード**: 統合プロット（overlay）と個別プロット（individual）
- **Direction機能**: Charge/Discharge/Restなどの状態変化を色分けして可視化
- **表示制御**: グリッド表示、軸反転、軸範囲指定、ログスケール
- **ヘッダ名の自動humanize**: snake_caseのヘッダを自動的にTitle Caseに変換
- **凡例制御**: 凡例項目数制限、凡例位置指定、追加情報表示
- **出力形式**: PNG画像（デフォルト）、インタラクティブHTML（オプション）

## CSVフォーマット対応

### standard（標準CSV）

ヘッダー行を持つ標準的なCSV形式です。デフォルトで使用されます。

```csv
X,Y1,Y2
1,10,20
2,15,25
3,20,30
```

### transpose（転置CSV）

行指向のCSVデータを転置して読み込みます。

```csv
X,1,2,3
Y1,10,15,20
Y2,20,25,30
```

### noheader（ヘッダー無しCSV）

ヘッダー行が無いCSVファイルです。列は自動的に`Column_0`, `Column_1`のように命名されます。

```csv
1,10,20
2,15,25
3,20,30
```

## プロットモード

### overlay（統合プロット）

すべての系列を1つのグラフに重ね合わせて表示します。デフォルトモードです。

- **代表画像**: 全系列を統合した画像を生成
- **個別画像**: 各系列の個別画像も生成（`no_individual=False`の場合）

### individual（個別プロット）

各系列を個別のグラフとして生成します。統合プロットはスキップされます。

## Direction機能

Direction機能を使用すると、Charge/Discharge/Restなどの状態変化を異なる色で可視化できます。

### Direction列の指定

```python
csv2graph(
    "battery_data.csv",
    direction_cols="direction",  # direction列を指定
)
```

### Directionフィルタリング

特定のdirection値のみを表示できます。

```python
csv2graph(
    "battery_data.csv",
    direction_cols="direction",
    direction_filter=["Charge", "Discharge"],  # ChargeとDischargeのみ表示
)
```

### Direction色のカスタマイズ

各direction値に対して色を指定できます。

```python
csv2graph(
    "battery_data.csv",
    direction_cols="direction",
    direction_colors={
        "Charge": "#FF6B6B",
        "Discharge": "#4ECDC4",
        "Rest": "#95E1D3",
    }
)
```

## 表示制御オプション

### グリッド表示

```python
csv2graph("data.csv", grid=True)
```

### 軸反転

X軸やY軸を反転できます。XPSスペクトルなどで有用です。

```python
csv2graph(
    "xps_data.csv",
    invert_x=True,  # X軸を反転
    invert_y=False,
)
```

### 軸範囲指定

表示する軸の範囲を指定できます。

```python
csv2graph(
    "data.csv",
    xlim=(0, 100),    # X軸範囲: 0-100
    ylim=(0, 50),     # Y軸範囲: 0-50
)
```

### ログスケール

X軸やY軸をログスケールで表示できます。

```python
csv2graph(
    "data.csv",
    logx=False,  # X軸: リニアスケール
    logy=True,   # Y軸: ログスケール
)
```

## ヘッダ名の自動変換

CSVヘッダがsnake_case形式の場合、軸ラベルや凡例では自動的にTitle Caseに変換されます。

| 元のヘッダ | 変換後 |
|----------|--------|
| `battery_voltage` | `Battery Voltage` |
| `current_density` | `Current Density` |
| `cycle_number` | `Cycle Number` |
| `discharge_capacity` | `Discharge Capacity` |

単位表記も保持されます：
- `battery_voltage (V)` → `Battery Voltage (V)`

## 列指定

### X列とY列の指定

列は整数インデックス、列名、またはそれらのリストで指定できます。

```python
# インデックスで指定
csv2graph("data.csv", x_col=0, y_cols=[1, 2, 3])

# 列名で指定
csv2graph("data.csv", x_col="time", y_cols=["voltage", "current"])

# 混在も可能
csv2graph("data.csv", x_col=0, y_cols=["voltage", 2])
```

### デフォルト動作

- `x_col=None`: 最初の列がX軸に使用されます
- `y_cols=None`: X列以外のすべての列がY軸に使用されます

## 出力制御

### 出力ディレクトリ

```python
csv2graph(
    "data.csv",
    output_dir="plots",           # 基本出力ディレクトリ
    main_image_dir="main_plots",  # 統合プロット用ディレクトリ
)
```

- `output_dir`: 個別プロットとHTML出力の保存先
- `main_image_dir`: 統合プロット（PNG）の保存先（指定時のみ）

### 個別プロットのスキップ

統合プロットのみを生成したい場合：

```python
csv2graph("data.csv", no_individual=True)
```

### HTML出力

インタラクティブなPlotlyグラフを生成します。

```python
csv2graph("data.csv", html=True)
```

**注意**: Plotlyライブラリのインストールが必要です。

### 凡例制御

```python
csv2graph(
    "data.csv",
    legend_loc="upper right",     # 凡例位置
    legend_info="Cell: 18650\n25C",  # 追加情報
    max_legend_items=10,           # 最大項目数
)
```

凡例項目数が`max_legend_items`を超えると、凡例は自動的に非表示になります。

## Python実行例

### 基本的なCSV変換

```python
from rdetoolkit.graph.api import csv2graph

# 最もシンプルな使用方法
csv2graph("data.csv")

# 出力先を指定
csv2graph(
    "experiment.csv",
    output_dir="plots",
    logy=True,
    title="Experiment Summary",
)
```

### 列選択と個別プロット生成

```python
from rdetoolkit.graph.api import csv2graph

# 統合プロットと個別プロットの両方を生成
csv2graph(
    "measurements.csv",
    output_dir="overlay_and_series",
    mode="overlay",
    x_col="time_s",
    y_cols=["voltage_v", "current_ma"],
    legend_loc="upper right",
    max_legend_items=5,
)

# 個別プロットのみを生成
csv2graph(
    "multi_sensor.csv",
    output_dir="per_series",
    mode="individual",
    x_col=0,
    y_cols=[1, 2, 3, 4],
    grid=True,
)
```

### Direction機能の使用

```python
from rdetoolkit.graph.api import csv2graph

# バッテリーサイクルデータの可視化
csv2graph(
    "battery_cycles.csv",
    output_dir="battery",
    direction_cols="direction",
    direction_filter=["Charge", "Discharge"],
    direction_colors={
        "Charge": "#FF6B6B",
        "Discharge": "#4ECDC4",
    },
    legend_info="Cell: 18650\n25C",
    html=True,
)
```

### 転置CSVの処理

```python
from rdetoolkit.graph.api import csv2graph

# 転置形式のCSVを処理
csv2graph(
    "transposed_data.csv",
    csv_format="transpose",
    output_dir="plots",
    mode="overlay",
)

# ヘッダー無しCSVを処理
csv2graph(
    "no_header_data.csv",
    csv_format="noheader",
    output_dir="plots",
)
```

### 出力ディレクトリの制御

```python
from rdetoolkit.graph.api import csv2graph

# 統合プロットと個別プロットを別ディレクトリに保存
csv2graph(
    "series.csv",
    output_dir="other_images",      # 個別プロット用
    main_image_dir="main_image",    # 統合プロット用
    html=True,
    grid=True,
)
```

### DataFrameからのプロット

```python
import pandas as pd
from rdetoolkit.graph.api import plot_from_dataframe

# DataFrameを読み込み
frame = pd.read_csv("processed.csv")
frame["normalized"] = frame["value"] / frame["value"].max()

# Figureオブジェクトを取得
artifacts = plot_from_dataframe(
    df=frame,
    output_dir="analysis",
    name="processed",
    title="Processed Output",
    x_col="time",
    y_cols=["value", "normalized"],
    return_fig=True,
)

# カスタム保存処理
for artifact in artifacts:
    artifact.figure.savefig(f"custom_{artifact.filename}", dpi=300)
```

### XPSスペクトルの可視化

```python
from rdetoolkit.graph.api import csv2graph

# X軸反転でXPSスペクトルを表示
csv2graph(
    "xps_spectrum.csv",
    output_dir="xps_plots",
    invert_x=True,
    xlim=(1200, 0),
    x_label="Binding Energy (eV)",
    y_label="Intensity (a.u.)",
    grid=True,
)
```

### 凡例項目数の制限

```python
from rdetoolkit.graph.api import csv2graph

# 多数の系列を持つデータで凡例を制限
csv2graph(
    "multi_series_data.csv",
    output_dir="plots",
    max_legend_items=10,  # 10項目を超えたら凡例を非表示
    title="Multi-Series Analysis",
)
```

## CLI実行例

### 基本的な使用方法

```bash
# 最もシンプルな実行
python -m rdetoolkit.graph.api.csv2graph data.csv

# 出力先を指定
python -m rdetoolkit.graph.api.csv2graph experiment.csv --output_dir plots --logy --title "Experiment Summary"
```

### 列選択と個別プロット

```bash
# 統合プロットと個別プロットの両方を生成
python -m rdetoolkit.graph.api.csv2graph measurements.csv \
    --output_dir overlay_and_series \
    --mode overlay \
    --x_col time_s \
    --y_cols voltage_v current_ma \
    --legend_loc "upper right" \
    --max_legend_items 5

# 個別プロットのみを生成
python -m rdetoolkit.graph.api.csv2graph multi_sensor.csv \
    --output_dir per_series \
    --mode individual \
    --x_col 0 \
    --y_cols 1 2 3 4 \
    --grid
```

### Direction機能の使用

```bash
# バッテリーサイクルデータの可視化
python -m rdetoolkit.graph.api.csv2graph battery_cycles.csv \
    --output_dir battery \
    --direction_cols direction \
    --direction_filter Charge Discharge \
    --legend_info "Cell: 18650\n25C" \
    --html

# Direction色のカスタマイズ（Pythonスクリプトでのみサポート）
```

### 転置CSVの処理

```bash
# 転置形式のCSVを処理
python -m rdetoolkit.graph.api.csv2graph transposed_data.csv \
    --csv_format transpose \
    --output_dir plots \
    --mode overlay

# ヘッダー無しCSVを処理
python -m rdetoolkit.graph.api.csv2graph no_header_data.csv \
    --csv_format noheader \
    --output_dir plots
```

### 出力ディレクトリの制御

```bash
# 統合プロットと個別プロットを別ディレクトリに保存
python -m rdetoolkit.graph.api.csv2graph series.csv \
    --output_dir other_images \
    --main_image_dir main_image \
    --html \
    --grid
```

### XPSスペクトルの可視化

```bash
# X軸反転でXPSスペクトルを表示
python -m rdetoolkit.graph.api.csv2graph xps_spectrum.csv \
    --output_dir xps_plots \
    --invert_x \
    --xlim 1200 0 \
    --grid
```

### 表示制御オプション

```bash
# ログスケールとグリッド表示
python -m rdetoolkit.graph.api.csv2graph data.csv \
    --output_dir plots \
    --logy \
    --grid

# 軸範囲指定
python -m rdetoolkit.graph.api.csv2graph data.csv \
    --output_dir plots \
    --xlim 0 100 \
    --ylim 0 50

# 軸反転
python -m rdetoolkit.graph.api.csv2graph data.csv \
    --output_dir plots \
    --invert_x \
    --invert_y
```

### 凡例制御

```bash
# 凡例項目数を制限
python -m rdetoolkit.graph.api.csv2graph multi_series_data.csv \
    --output_dir plots \
    --max_legend_items 10 \
    --legend_loc "upper right"

# 個別プロットをスキップ
python -m rdetoolkit.graph.api.csv2graph data.csv \
    --output_dir plots \
    --no_individual
```

## 出力仕様

### ファイル命名規則

#### overlay モード

- **統合プロット**: `{title}.png` または `{name}.png`
- **個別プロット**: `{title}_{series}.png` または `{name}_{series}.png`
- **HTML出力**: `{title}.html` または `{name}.html`（`html=True`の場合）

#### individual モード

- **個別プロット**: `{title}_{series}.png` または `{name}_{series}.png`

### ディレクトリ構造

```
output_dir/
├── plot.png              # 統合プロット（overlayモード）
├── plot_series1.png      # 個別プロット
├── plot_series2.png      # 個別プロット
└── plot.html             # HTML出力（html=Trueの場合）

main_image_dir/           # main_image_dir指定時のみ
└── plot.png              # 統合プロット（PNG）
```

### 出力形式

- **PNG画像**: Matplotlib によるベクター品質の静的画像
- **HTML**: Plotly によるインタラクティブグラフ（要Plotlyインストール）

### セキュリティ

- パストラバーサル攻撃を防止する検証機能を内蔵
- ファイル名は自動的にサニタイズされます
- ディレクトリは必要に応じて自動作成されます

## エラーハンドリング

### よくあるエラー

- **`ColumnNotFoundError`**: 指定された列が存在しない
- **`ValueError`**: X列とY列の設定が不整合
- **`ImportError`**: `html=True`だがPlotlyがインストールされていない
- **`PlotConfigError`**: dual_axisモードが使用されている（現在無効化）

### 推奨事項

- 出力ディレクトリが存在するか、作成可能であることを確認してください
- HTML出力を使用する場合は、Plotlyをインストールしてください（`pip install plotly`）
