# MangaCrisp for macOS — Beta 0.7.1b0.3

**UI/UX improvements and minor bug fixes.** This Apple Silicon beta updates the
bookshelf, reading settings, and shortcut help, and makes AI correction more
reliable when moving forward and backward. The product version remains `0.7.1b0`.

## Features

- A navy-and-teal bookshelf with clearer cover selection and Read, Import,
  Capture, and Remove buttons.
- Reading settings with quality cards, layout buttons, and a visible
  original/enhanced comparison control.
- Click the page center, including in fullscreen, to open translucent controls
  for navigation, one-page movement, settings, comparison, fullscreen, and
  returning to the bookshelf. Shortcut badges show `P`, `O`, `F`, `V`, and
  `Shift` + arrow keys. Controls appear on demand; there is no permanent bottom bar.
- `H` / `?` opens redesigned shortcut help from both the bookshelf and reader.
  Close it with the Close button, `Esc`, or a click outside the card. Dismissing
  help does not turn a page or exit fullscreen.
- This package also includes the previous shared UX improvements: fullscreen
  cursor auto-hide, multi-select and batch removal, and visible-page-first
  correction with adaptive prefetch.

## Fixes

- High-quality correction uses accurate tile synchronization to prevent false
  colors. Old pro-model cache entries are regenerated automatically; the first
  correction can take longer.
- Correction scheduling, disk cache reuse, and display-cache ownership were
  refactored to handle rapid forward/back movement and resizing. Late results
  cannot replace the current spread; both corrected pages appear together.
- Cache cleanup protects active processing and completed output is published
  atomically. Navigation can retry a failed correction.
- Arrow keys in settings inputs and Space on buttons stay with those controls.
- Includes the earlier fixes for corrected-display flashing and managed-copy
  removal errors.

## UI gallery

![Clean demo bookshelf](../images/bookshelf.png)

![Center-click reading controls](../images/reader-controls.png)

Screenshots show the shared UI on macOS with only David Revoy's *Pepper&Carrot*
under CC BY 4.0. See [attribution](../../demo/ATTRIBUTION.md),
[Japanese screenshots](../../README.ja.md), and the
[reproducible capture procedure](../images/README.md).

## Validation and platform handover

- Apple Silicon source suite: **274 passed, 8 skipped, 12 subtests passed**.
- Native macOS checks covered bookshelf selection, reading, center controls,
  original comparison, settings, fullscreen, shortcut help dismissal, and
  returning to the bookshelf. Cold/warm correction and forward/back navigation
  were checked during the correction work.
- Distribution checks cover the bundled engine and models, license notices,
  ad-hoc signature, packaged startup, and an extracted color-PDF smoke test.
- The capture acceptance test was not repeated for this release; capture
  platform adapters are unchanged by these UI/correction PRs.
- On 2026-10-20 the user reported successful native operation of the current
  UI on Windows and Linux. This is general UI acceptance; individual GPU,
  session, scaling, and checklist results were not supplied. See the
  [shared handover](../development/ux-maintenance-handover.md).

## Install or roll back

Download `MangaCrisp-v0.7.1b0.3-macos-apple-silicon-standalone.zip`, check its
attached SHA-256 file, and replace `MangaCrisp.app` in Applications. Your library
and reading settings are kept. Python and uv are not required.

This beta is **ad-hoc signed, without Apple Developer ID signing or notarization**,
and supports Apple Silicon only. Follow [the installation guide](../../INSTALL.md)
if macOS blocks first launch. Existing release assets remain available, including
[Beta 0.7.1b0.2](https://github.com/jydie5/MangaCrisp/releases/tag/macos-beta-0.7.1b0.2).
Source-level UI rollback is documented in the
[checkpoint](../development/reader-controls-checkpoint.md).

---

## 日本語

**UI/UX改善と軽微なバグ修正**のApple Silicon向けベータです。本棚、読書設定、
ショートカット一覧を刷新し、前後移動時のAI補正とキャッシュの動作を改善しました。
製品バージョンは`0.7.1b0`のままです。

### 機能

- 本棚を紺色と青緑のデザインに統一し、本の選択状態や「読む」「登録」「撮影」「削除」を明確にしました。
- 読書設定は画質カード、レイアウトボタン、原画比較ボタンで操作できます。
- 全画面でもページ中央をクリックすると半透明の操作パネルを開けます。ページ移動、
  1ページずらし、設定、原画比較、全画面、本棚への復帰をまとめ、`P`、`O`、`F`、`V`、
  `Shift`＋カーソルキーを表示します。下部の常時操作バーはありません。
- 本棚と読書画面の`H`／`?`一覧も同じデザインになりました。「閉じる」、`Esc`、
  パネル外クリックで閉じられます。閉じる際のページ移動や全画面解除は起きません。
- 先行した共通UX更新（全画面カーソル自動非表示、本棚の複数選択・一括削除、
  表示ページ優先の補正と可変先読み）も収録します。

### 修正

- 高画質補正で一部のページに偽色が出る問題を、タイル間の正確な同期で修正しました。
  旧proモデルのキャッシュは自動的に作り直すため、最初の補正には時間がかかる場合があります。
- 補正キュー、ディスクキャッシュ、表示キャッシュを整理し、連続した前後移動や
  リサイズに対応しました。古い処理結果が現在の見開きを上書きせず、左右の補正がそろって切り替わります。
- キャッシュ整理が処理中のファイルを保護し、完成した補正結果だけを保存します。
  処理失敗後もページ移動で再試行できます。
- 設定入力欄のカーソルキーや、フォーカス中のボタンのSpaceが読書操作へ流れる問題を修正しました。
- 先行した補正版のちらつき、管理コピー削除失敗の修正も含みます。

### 検証と引き継ぎ

Apple Siliconで自動テスト**274件通過、8件スキップ、12 subtests通過**。
実機で本棚、読書、中央パネル、原画比較、設定、全画面、ヘルプの各種閉じ方、本棚への復帰を確認しました。
補正修正時にはキャッシュのない状態／ある状態での補正と前後移動も確認しています。
配布物はエンジン・モデル・ライセンス・ad-hoc署名・起動・展開後のカラーPDF表示を検証します。
キャプチャの受入試験は今回繰り返していません。これらのPRはOS別キャプチャ処理を変更していません。

2026-10-20に、利用者から現行UIがWindows／Linuxの実機で動作したとの報告を受領しました。
全体的な操作確認として記録し、GPU・セッション・倍率・各項目の個別結果は未報告として区別しています。
詳細は[共通引き継ぎ](../development/ux-maintenance-handover.ja.md)、
[Windows](../development/windows-handover.md)、[Linux](../development/linux-handover.ja.md)を参照してください。

### 更新・戻し方

`MangaCrisp-v0.7.1b0.3-macos-apple-silicon-standalone.zip`とチェックサムを取得し、
アプリケーション内の`MangaCrisp.app`を置き換えます。本棚と設定は保持します。
Apple Silicon専用で、**ad-hoc署名済み、Apple Developer ID署名・notarization未実施**です。
初回起動については[導入案内](../../INSTALL.ja.md)を参照してください。
旧ベータの配布物は残し、ソースのUIだけを戻す方法も[チェックポイント](../development/reader-controls-checkpoint.md)に記録しています。
