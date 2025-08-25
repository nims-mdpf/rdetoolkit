# Contributing to RDEToolKit

## ドキュメントのコントリビュート

RDEToolKitのモジュールドキュメントは、ユーザーがRDE構造化処理を正しく実行するために必要なリソースになります。利用者の皆様からのドキュメント改善にご協力ください。
必ずしも、RDEToolKitへの深い理解がある必要はありません。ドキュメントの内容が不足している、理解しにくいという箇所は、積極的にIssueでの報告をお待ちしています。

具体的な手順については、次のセクションから説明いたします。

### RDEToolKitのドキュメント

rdetoolkitのドキュメントは、本リポジトリの`docs`フォルダに格納しています。ドキュメントは、[MkDocs](https://www.mkdocs.org/)を使用してドキュメントを構築しています。すべてのコードが適切に文書化されていることを確認してください。以下は、適切にフォーマットされた docstring を使用して文書化する必要があります。

- モジュール
- クラス定義
- 関数の定義
- モジュールレベルの変数

### 注意事項

ドキュメント更新に関して知っておくべき重要事項について:

- rdetoolkitのドキュメントは、コード自体のdocstringと、その他のドキュメントの2つに大別されます。
- docstringは、各種モジュールの利用法が記載され、GitLab CI/CDで、自動ビルドされドキュメントが更新されます。
- docstringは、[PEP 257](https://peps.python.org/pep-0257/)ガイドラインに従ってフォーマットされた[Google Styleのdocstring](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)を使用します。 (その他の例については、「[Google スタイルの Python ドキュメント文字列の例](https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html)」を参照してください。)
  - Google Styleの docstring と pydocstyle lint の間で競合する場合は、pydocstyle lint のヒントに従ってください。

### ドキュメントの改善点をリクエストする

以下のURLより、RDEToolKitのリポジトリにアクセスし、issueを発行してください。
この時、ラベルは`Type:documentation`というラベルを付与してください。

> [RDEToolKit - github.com](https://github.com/nims-mdpf/rdetoolkit/issues)

### ローカル環境で変更する

変更方法は、ローカルリポジトリからブランチを変更して、変更をPushしてください。ブランチ名の先頭に`docs-***`という接頭辞をつけてください。

```shell
git checkout -b docs-***
# 実行例
git checkout -b docs-install-manual
```

ドキュメントを変更し、リモートリポジトリにPushします。

```shell
git add <変更したドキュメント>
git commit -m "コミットメッセージ"
git push origin <対象のブランチ名>
```

### ドキュメントをWeb上で確認する

ドキュメントをWebで確認する場合、以下の手順でドキュメントサーバーを起動して確認してください。

#### ryeをインストールしている場合

```shell
rye sync
mkdocs serve
```

#### ryeをインストールしていない場合

```shell
pip install -r requirements.lock
mkdocs serve
```

### ドキュメントをmainブランチにマージする

ドキュメントを追加しプルリクエストを作成します。管理者が確認し、問題がなければマージします。
