# MangaCrisp for Linux — Preview 0.7.1b0.4

UI/UX features and minor bug fixes for Ubuntu 24.04+ x86_64. Product version
remains `0.7.1b0`; the preview tag identifies this new package.

## Changes

- Refreshed navy/teal bookshelf, clearer selection, and Read/Import/Remove actions.
- Quality cards and layout buttons in Reading Settings.
- Center-click translucent navigation and shortcut controls, including in
  fullscreen. The bottom controls bar is not permanently displayed.
- Redesigned H/? help closes by button, Escape, or an outside click without
  changing the page or leaving fullscreen.
- Accurate pro-model synchronization prevents false colors and regenerates old
  pro cache entries automatically.
- Correction and cache lifecycle fixes improve rapid forward/back movement and
  resizing, protect active processing, and reject stale results.
- Keyboard input remains with focused settings inputs and buttons.

![Demo bookshelf](../images/bookshelf.png)

![On-demand reading controls](../images/reader-controls.png)

Images show the shared UI on macOS with David Revoy's *Pepper&Carrot* under
CC BY 4.0. See [attribution](../../demo/ATTRIBUTION.md) and
[the clean capture procedure](../images/README.md).

## Package and verification

The native Ubuntu 24.04 package is from `main` at `d7bbf50`,
[Linux CI run 39335510308](https://github.com/jydie5/MangaCrisp/actions/runs/39335510308).
The source suite and packaged startup checks passed. The attached archive is
unchanged from that CI artifact; verify it with `SHA256SUMS.txt`.
On 2026-10-20 the user reported that the current UI worked on a real Linux
machine. This is general native acceptance. The current report does not identify
the compositor, GPU, driver, scaling, or individual capture/checklist results.
Historical b0.3 environment results remain recorded separately in the handover.

Extract and run `MangaCrisp/install.sh`, then launch MangaCrisp. Library and
settings are retained. See [Linux installation](../../INSTALL.linux.md) for
system dependencies and capture permissions. Python, uv, and CUDA are not required.

This is an unsigned preview. AMD/Intel GPU evidence, physical X11 and fractional
scaling coverage, other distributions/compositors, and aarch64 remain limited
or unverified. No broader hardware claim is inferred from the general report.
Old preview assets remain available for rollback.

## 日本語

Ubuntu 24.04以降のx86_64向けUI/UX改善と軽微なバグ修正です。本棚、画質カード、
レイアウト操作、中央クリックの半透明操作パネル、H/?ヘルプを刷新しました。
高画質補正の偽色、前後移動時の補正・キャッシュ、入力欄のキー操作を改善しています。

Ubuntu 24.04のネイティブCIでmain `d7bbf50`から作成し、自動テストと配布版起動確認に合格した
アーカイブをそのまま公開します。`SHA256SUMS.txt`を照合してください。
2026-10-20に利用者から現行UIのLinux実機動作確認を受領しました。今回の報告では
GPU・ドライバ・Wayland/X11・倍率・各チェック項目の個別結果は特定されていません。
b0.3時点の検証環境は過去の記録として区別します。

展開後に`MangaCrisp/install.sh`を実行します。本棚と設定は保持します。
未署名のpreviewで、AMD/Intel、実X11、小数倍率、他ディストリビューション、aarch64等の
確認範囲は引き続き限定的です。画像はmacOSで撮影した共通UIで、CC BY 4.0の作品のみです。
