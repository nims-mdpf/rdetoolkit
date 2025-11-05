## 1. Project Overview

RDEToolKit is a fundamental Python package for creating workflows of RDE-structured programs. See [0-cite-0](#0-cite-0).

## 2. Development Environment Setup

This project uses `rye` as the package and environment manager. See [0-cite-1](#0-cite-1).

After installing `rye`, set up your local dev environment with `rye sync`. For code quality, we also use `pre-commit`. See [0-cite-2](#0-cite-2).

**Quick start**

```bash
cd <local rdetoolkit repo>
uv sync
source .venv/bin/activate
pre-commit install
```

## 3. Code Formatting & Linters

We use `Ruff` and `mypy` to maintain code quality. Ruff replaces isort/black/flake8 and, together with strict typing enforced by mypy, improves readability and maintainability. See [0-cite-3](#0-cite-3).

## 4. Documentation Guidelines

Docstrings **must** follow **Google Style**. See [0-cite-4](#0-cite-4).

## 5. Branch Strategy

When adding features or fixes, create a branch from `develop/v<x.y.z>` and append an arbitrary suffix to describe the change. See [0-cite-5](#0-cite-5).

We also standardize branch prefixes (e.g., `feature/`, `bugfix/`, `docs/`, `test/`, etc.). See [0-cite-6](#0-cite-6).

**Example**

```bash
git checkout -b develop/v<x.y.z>/<short-descriptor> origin/develop/v<x.y.z>
```

## 6. Testing

### 6.1 Environment

* **Language/Tools:** Python, `pytest`
* **Runner:** `tox` (primary entrypoint) — see [0-cite-7](#0-cite-7)

### 6.2 Mandatory Requirements (Read First)

1. **Present test-design tables *before* writing tests**

   * Provide **Equivalence Partitioning** and **Boundary Value** tables for each public API (function/class/method).
2. **Implement tests based on those tables**

   * Each row in the table(s) must map to at least one test case.
3. **Balance success/failure**

   * Include **at least as many failing (negative) cases as passing (positive) cases**.
4. **Required test viewpoints**

   * Normal (happy path)
   * Abnormal/error paths
   * Boundary values
   * Invalid types/formats
   * External dependency failures (e.g., I/O, network, DB)
   * Exception verification (type and message)
5. **Scenario comments**

   * Use **Given/When/Then** style comments in each test.
6. **Execution commands & coverage collection**

   * Provide concrete commands in the repo for both **per-env** and **tox** runs (see below).
7. **Coverage target**

   * **Branch coverage 100%** (aim for full decision/branch coverage across modules under test).

### 6.3 Templates You Must Include in PRs

**(A) Equivalence Partitioning Table (Template)**

| API           | Input/State Partition    | Rationale      | Expected Outcome       | Test ID     |
| ------------- | ------------------------ | -------------- | ---------------------- | ----------- |
| `module.func` | e.g., valid range (1–10) | valid domain   | returns computed value | `TC-EP-001` |
|               | e.g., below min (≤0)     | invalid domain | raises `ValueError`    | `TC-EP-002` |
|               | e.g., non-int type       | invalid type   | raises `TypeError`     | `TC-EP-003` |

**(B) Boundary Value Table (Template)**

| API           | Boundary                | Rationale      | Expected Outcome | Test ID     |
| ------------- | ----------------------- | -------------- | ---------------- | ----------- |
| `module.func` | `min-1`, `min`, `min+1` | lower boundary | …                | `TC-BV-00x` |
|               | `max-1`, `max`, `max+1` | upper boundary | …                | `TC-BV-00x` |

> Place these tables at the top of the test module or in a colocated `README` within the test directory. Each row should be traceable to a concrete test via `Test ID`.

**(C) pytest Structure & Style**

* File layout: `tests/<package>/test_<unit>.py`
* One assertion per behavior; multiple assertions allowed if they validate a single coherent behavior.
* **Given/When/Then comments** in each test:

  ```python
  def test_func_min_boundary():
      # Given: input at lower boundary
      x = 0
      # When: calling the target function
      # Then: it raises ValueError
      with pytest.raises(ValueError):
          module.func(x)
  ```

**(D) External Dependencies & Exceptions**

* Use fakes/mocks for external calls (filesystem, network, DB).
* Force dependency failures (timeouts, I/O errors) and verify:

  * The **exception type**
  * The **message** (or message pattern)
  * That **cleanup/rollback** occurs when applicable

**(E) Coverage & Commands**

* Recommended: `pytest-cov` with branch coverage.
* **Direct (active venv):**

  ```bash
  pytest -q \
    --maxfail=1 \
    --cov=rdetoolkit \
    --cov-branch \
    --cov-report=term-missing \
    --cov-report=html
  # HTML report at htmlcov/index.html
  ```
* **Via tox (preferred):**

  ```bash
  tox
  # Configure env in tox.ini, e.g.:
  # [testenv]
  # deps = pytest pytest-cov
  # commands = pytest -q --maxfail=1 --cov=rdetoolkit --cov-branch --cov-report=term-missing --cov-report=html
  ```
* **Fail CI if coverage < 100% (branch):** add a threshold, e.g. in `pyproject.toml` or `pytest.ini`:

  ```ini
  [tool.pytest.ini_options]
  addopts = --cov=rdetoolkit --cov-branch --cov-report=term-missing --cov-report=html --maxfail=1
  [tool.coverage.report]
  fail_under = 100
  ```

### 6.4 Minimum Content Checklist (PRs will be blocked if missing)

* [ ] EP table provided and linked to test IDs
* [ ] Boundary table provided and linked to test IDs
* [ ] Tests implement **all** rows from tables
* [ ] Failing cases ≥ Passing cases
* [ ] Given/When/Then comments present
* [ ] External failure scenarios covered (and asserted)
* [ ] Exceptions verified (type/message)
* [ ] Coverage reports generated; **branch coverage = 100%**

### 6.5 Authoring Workflow & Organization Rules

1. **Decide the test scope before coding.** Classify the target as either unit (pure logic, faked dependencies) or integration (real I/O). Keep integration suites under `tests/integration/**` and tag them with `@pytest.mark.integration`; default everything else to unit tests.
2. **Draft EP/BV tables per public API.** Place the tables at the module top (preferred) and assign stable `TC-` IDs. One row → at least one test; note related fixtures alongside the table if setup is non-trivial.
3. **Name tests after their Test ID.** Use `def test_<api>_<slug>__tc_ep_001():` pattern so traceability from the tables to the implementation stays obvious.
4. **Balance positive and negative cases.** Provide at least one failure scenario for every success, covering: invalid inputs, edge boundaries, external dependency failures (use monkeypatch/fakes), and exact exception type+message assertions.
5. **Structure each test consistently.** Follow Given/When/Then comments, prefer a single logical assertion per behavior, and isolate side effects in fixtures with cleanup (context managers or `yield` fixtures).
6. **Record execution commands.** Each new/updated test module must mention the precise `pytest` command (direct and `tox`) that was used to validate 100% branch coverage. Mirror any new requirements in `tox.ini`/`pyproject.toml` when needed.
7. **Review for gap analysis.** Before submitting, verify the checklist in §6.4, confirm coverage HTML reports are regenerated (`htmlcov/index.html`), and ensure integration tests are skipped by default in CI unless explicitly requested.

---

## Notes

When authoring AGENTS.md, keep these rules concise and explicit so AI assistants can operate effectively within this codebase. Document project-specific conventions, tools, and workflows so the assistant can generate code and changes that meet the project’s standards.

---

## Citations

### <a id="0-cite-0"></a>**File:** README.md (L12–14)

```markdown
RDEToolKit is a fundamental Python package for creating workflows of RDE-structured programs.
By utilizing various modules provided by RDEToolKit, you can easily build processes for registering research and experimental data into RDE.
Additionally, by combining RDEToolKit with Python modules used in your research or experiments, you can achieve a wide range of tasks, from data registration to processing and visualization.
```

### <a id="0-cite-1"></a>**File:** CONTRIBUTING.md (L21–23)

```markdown
### パッケージ管理ツールのインストール

rdetoolkitでは、`rye`を利用しています。ryeは、Flaskの作者が作成した、Pythonのパッケージ関係管理ツールです。内部実装はRustのため、非常に高速です。poetryを選択せずryeを採用した理由は、動作速度の観点と、`pyenv`を別途利用する必要があるためです。ryeは、`pyenv+poetry`のように、インタプリタの管理とパッケージの管理が統合されているため、メンテナンスの観点からもryeの方が優れているため、こちらを採用しています。
```

### <a id="0-cite-2"></a>**File:** CONTRIBUTING.md (L30–48)

````markdown
ryeをインストール後、以下の手順で開発環境をセットアップしてください。`rye sync`で仮想環境が作成され、必要なパッケージが仮想環境にインストールされます。

```shell
cd <rdetoolkitのローカルリポジトリ>
rye sync
````

仮想環境を起動します。

```shell
source .venv/bin/activate
```

また、RDEToolKitではコード品質の観点から、`pre-commit`を採用しています。pre-commitのセットアップを実行するため、以下の処理を実行してください。

```shell
pre-commit install
```

````

### <a id="0-cite-3"></a>**File:** CONTRIBUTING.md (L169–174)
```markdown
#### RDEToolKitでのフォーマッター・リンターについて

RDEToolKitでは、`Ruff`と`mypy`を使用してフォーマット、リンターを動作させてコード品質を一定に保つことを目標としています。`Ruff`は、isort, black, flake8の機能に変わるツールです。Rustで開発されているため、isort, black, flake8で動作させるより段違いに高速です。また、`mypy`は、静的型チェックツールです。RDEToolKitは型の詳細な定義を強制することで、コードの可読性と保守性の向上を目的としています。

> - Ruff: <https://docs.astral.sh/ruff/>
> - mypy: <https://mypy.readthedocs.io/en/stable/>
````

### <a id="0-cite-4"></a>**File:** CONTRIBUTING.md (L73–76)

```markdown
- rdetoolkitのドキュメントは、コード自体のdocstringと、その他のドキュメントの2つに大別されます。
- docstringは、各種モジュールの利用法が記載され、GitHub Actionsで、自動ビルドされドキュメントが更新されます。
- docstringは、**Google Style**で記述してください。
  - 参考: [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
```

### <a id="0-cite-5"></a>**File:** CONTRIBUTING.md (L133–139)

````markdown
新しい機能や修正を行う際は、新しいブランチを作成してください。

- ブランチ名の接頭辞は、`develop/v<x.y.z>`というブランチから、末尾に任意の文字列を追加して作成してください。

```shell
git checkout -b develop/v<x.y.z>/<任意の機能名など> origin/develop/v<x.y.z>
````

````

### <a id="0-cite-6"></a>**File:** CONTRIBUTING.md (L141–159)
```markdown
**接頭辞の例**

| **接頭辞**    | **意味**                                   | **例**                           |
| ------------- | ------------------------------------------ | -------------------------------- |
| `feature/`    | 新機能の開発                               | `feature/user-authentication`    |
| `bugfix/`     | バグ修正                                   | `bugfix/login-error`             |
| `fix/`        | バグ修正（`bugfix/`と同様）                | `fix/login-error`                |
| `hotfix/`     | 緊急の修正が必要な場合                     | `hotfix/critical-security-issue` |
| `release/`    | リリース準備やバージョン管理               | `release/v1.2.0`                 |
| `chore/`      | コードのリファクタリングやメンテナンス作業 | `chore/update-dependencies`      |
| `experiment/` | 試験的な機能やアイデアの検証               | `experiment/new-ui-concept`      |
| `docs/`       | ドキュメントの更新                         | `docs/update-readme`             |
| `test/`       | テスト関連の変更                           | `test/add-unit-tests`            |
| `refactor/`   | コードのリファクタリング                   | `refactor/cleanup-auth-module`   |
| `ci/`         | 継続的インテグレーション設定の変更         | `ci/update-github-actions`       |
| `style/`      | コードのスタイルやフォーマットの変更       | `style/format-codebase`          |
| `perf/`       | パフォーマンス改善                         | `perf/optimize-db-queries`       |
| `design/`     | デザイン関連の変更                         | `design/update-mockups`          |
| `security/`   | セキュリティ関連の修正や強化               | `security/enhance-encryption`    |
````

### <a id="0-cite-7"></a>**File:** CONTRIBUTING.md (L176–182)

````markdown
### テストの実行

変更を行った後は、テストを実行して正常に動作することを確認してください。

```shell
tox
````
