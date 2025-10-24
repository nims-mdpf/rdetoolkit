# gen-config コマンド

## 目的

このモジュールは `gen-config` CLI コマンドの実装を提供します。定義済みテンプレートまたは対話形式の質問に基づき、検証済みの `rdeconfig.yaml` を生成し、プロジェクト開始時点から設定の整合性を保ちます。

## 主な機能

### テンプレート生成
- Minimal / Full / MultiDataTile / RDEFormat / SmartTable のプリセットを提供
- `--overwrite` 指定時は直ちに上書きし、未指定なら確認プロンプトを表示
- `rdetoolkit` の設定モデルに準拠した YAML を出力

### 対話モード
- 各設定項目を順に質問して入力を補助
- `--lang` オプションで英語・日本語のプロンプトを切り替え
- ブール値や extended_mode の選択を自動的に YAML に反映

---

::: src.rdetoolkit.cmd.gen_config.GenerateConfigCommand

---

## 実用例

### 最小構成テンプレートの生成

```python title="generate_minimal_config.py"
from pathlib import Path
from rdetoolkit.cmd.gen_config import GenerateConfigCommand

command = GenerateConfigCommand(
    output_dir=Path("./project"),
    template="minimal",
    overwrite=False,
    lang="en",
)

command.invoke()
print("./project/rdeconfig.yaml に最小構成の設定ファイルを生成しました")
```

### 日本語プロンプトによる対話生成と上書き

```python title="interactive_config_generation.py"
from pathlib import Path
from rdetoolkit.cmd.gen_config import GenerateConfigCommand

command = GenerateConfigCommand(
    output_dir=Path("./project"),
    template="interactive",
    overwrite=True,
    lang="ja",
)

# コマンドは click により CLI 上で質問を行います。invoke() は CLI 上で実行してください。
command.invoke()
```
