---
name: Custom Issue Reporting Template
about: A consistent template to document RDEToolKit issues with impact, evidence,
  proposed fixes, and test plans.
title: ''
labels: ''
assignees: sonoh5n

---

# Title (JP): <短く具体的に>
# Title (EN): <Concise English title>

- **観点 / Aspect**: <Architecture | Code Quality | Refactoring | Dependency | Documentation | Feature | Test>
- **重要度 / Priority**: High | Medium | Low
- **推奨リリース種別 / Recommended Release**: patch | minor | major (e.g., 1.5.x / 1.6.0)

## 問題 / Problem
<何が起きているか、どのように判明したか。スクリーンショットやログがあれば引用>

## 影響 / Impact
- <影響1>
- <影響2>

## 根拠 / Evidence
- <ログ/スタックトレース/計測結果/該当行>

## 対応案 / Proposed Fix
1) <短期策>  
2) <中期/恒久策>  
3) <オプションや後続検討事項>

## 作業項目 / Tasks
- [ ] 依存追加・設定変更
- [ ] 実装
- [ ] テスト追加・更新
- [ ] ドキュメント更新

## テスト / Tests
- コマンド: `pytest ...` / `tox ...`
- 観点: 正常系 / 異常系 / 境界値 / 外部依存エラー / 例外メッセージ

## 影響範囲 / Affected Files
- <path/to/file.py>
- <tests/...>
- <config/...>

## リスク・懸念 / Risks
- <互換性リスク、パフォーマンス、移行期間など>

## 備考 / Notes
- <参考リンク、関連Issue/PR、決定事項など>
