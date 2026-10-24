# MangaCrisp for macOS — Beta 0.7.1b0.4

**Reader navigation, page overview, and archive-cache fixes.** This Apple
Silicon beta adds zoom and pan controls, a lazy page overview, bookshelf
discovery tools, page-number jumps, bookmarks, and per-book reading settings.
It also fixes processed-page lookup so it remains lazy and ZIP pages with
ambiguous extracted names cannot share the wrong image. The product version
remains `0.7.1b0`.

The release tag `macos-beta-0.7.1b0.4` is the source reference for this
package. GitHub release metadata records the exact `main` commit selected when
the tag is created; this note intentionally does not substitute a pre-release
working-tree SHA.

## Features

- Search the bookshelf by title, sort by natural title / last opened / added
  order, and select **Recently read** for most-recent-first order.
- Enter a physical page number in the reader to jump to it without changing
  right-to-left, left-to-right, cover, or spread rules.
- Press `B` to bookmark the current page. `Shift+B` opens bookmarks for the
  current book, where a bookmark can be opened or removed.
- Restore each book's layout, binding direction, cover setting, and selected
  quality preset before its first reader paint. `O` remains a temporary
  original/enhanced comparison and is not saved as a book preference.
- Use `+` / `-`, `0` (fit), `W` (fit width), and `1` (actual size), or
  Command + mouse wheel, to choose a view. Drag a zoomed spread to pan it.
- Press `T` or use **Pages** in the center controls for a page overview. It
  requests thumbnails only around the visible range; opening it does not run
  AI correction, render every PDF page, or extract an entire archive.

## Fixes and operating limits

- A processed-page lookup no longer materializes every PDF or ZIP page. ZIP
  extraction paths are isolated by physical page index, so duplicate or
  sanitized member names cannot make a later page reuse another page's image.
- Zoom and pan are display-only and are not restored from the database. The
  display cache targets 192 MiB and the decode target is about 8.4 megapixels;
  neither is a whole-process memory cap. Large source images and concurrent
  decoding can use more memory.
- The overview has a 16 MiB thumbnail-image cache and one active thumbnail
  decode. Closing it waits for that worker to finish, so a close can be brief
  rather than instantaneous on a slow image.
- This release does **not** add Comic EPUB reading. EPUB metadata work remains
  outside this package; the reader, importer, and EPUB page source are not
  connected in this release.

## UI gallery

![Clean demo bookshelf](../images/bookshelf.png)

![Center-click reading controls](../images/reader-controls.png)

![Lazy page overview](../images/page-overview.png)

Screenshots use a clean demo-only bookshelf and David Revoy's *Pepper&Carrot*
under CC BY 4.0. See [attribution](../../demo/ATTRIBUTION.md) and the
[reproducible capture procedure](../images/README.md).

## Validation and platform handover

- The integrated shared suite recorded **367 passed, 8 skipped, and 12
  subtests passed** on macOS.
- The local Apple Silicon test package passed its distribution audit, startup
  smoke check, and interactive UI check. The user accepted the integrated
  candidate as generally satisfactory; this is not a replacement for separate
  Windows or Linux package checks.
- Windows and Linux downloads are unchanged for this release. Their maintainers
  must build on the target OS and verify scaling, Ctrl+wheel input, GPU behavior,
  and Wayland/X11 (Linux) before publishing a matching platform update.
- The macOS package is ad-hoc signed and is not Developer ID signed or
  notarized. It supports Apple Silicon only.

See the [next-features handover](../development/next-features-handover.md) for
the current cross-platform work and the [shared UX handover](../development/ux-maintenance-handover.md)
for target-OS validation instructions.

## Install or roll back

Download `MangaCrisp-v0.7.1b0.4-macos-apple-silicon-standalone.zip` and its
attached SHA-256 file, then replace `MangaCrisp.app` in Applications. The
library and reading settings are retained. Python and uv are not required.

Follow [the installation guide](../../INSTALL.md) if macOS blocks the first
launch. Older release assets remain available for rollback; do not overwrite
them.

---

## 日本語

**読書操作、ページ一覧、アーカイブキャッシュを改善したApple Silicon向けベータ**です。
ズーム／パン、必要な範囲だけ作るページ一覧、本棚検索、ページ番号ジャンプ、しおり、
本ごとの読書設定を追加しました。処理済みページの探索を遅延化し、ZIP内で展開名が
衝突した場合に別ページの画像を再利用する不具合も修正しています。製品バージョンは
`0.7.1b0`のままです。

release tag `macos-beta-0.7.1b0.4`をこの配布物のソース参照とします。tag作成時に選ぶ
正確な`main`のcommitはGitHub Releaseのメタデータへ記録し、ここへ作業中のSHAを記載しません。

### 機能

- 本棚でタイトル検索、自然順／最終閲覧／追加順の並べ替え、「最近読んだ本」の新しい順表示を使えます。
- 読書画面で物理ページ番号を入力して移動できます。右綴じ／左綴じ、表紙、見開きの規則は変わりません。
- `B`で現在ページをしおりへ追加し、`Shift+B`で現在の本のしおり一覧を開いて移動・削除できます。
- 本ごとのレイアウト、綴じ方向、表紙、画質presetを初回表示前に復元します。`O`の原画／補正版比較は一時操作で、
  本の設定として保存しません。
- `+`／`-`、`0`（全体）、`W`（幅）、`1`（実寸）、Command＋ホイールで表示を選び、拡大中は見開きをドラッグして移動できます。
- `T`または中央操作ペインの**ページ一覧**でサムネイル一覧を開けます。表示範囲の近くだけを要求し、
  一覧を開いただけでAI補正、PDF全ページ描画、アーカイブ全体展開は行いません。

### 修正と制限

- 処理済みページの探索がPDF／ZIPの全ページを先に展開しなくなりました。ZIP展開先は物理ページ番号ごとに分離し、
  同名または安全化後の名前が衝突しても別ページの画像を使いません。
- ズーム／パンは表示だけの操作で、DBへ保存しません。表示キャッシュは192 MiB、デコード対象は約8.4 MPを目安にしますが、
  プロセス全体のメモリ上限ではありません。大きな元画像や同時デコードにより、それ以上のメモリを使うことがあります。
- ページ一覧は16 MiBのサムネイル画像キャッシュと、1本のデコード処理を使います。閉じるときはその処理の終了を待つため、
  重い画像では短い待ちが発生することがあります。
- Comic EPUBの読書対応は収録しません。EPUBのmetadata検査は別作業であり、reader、importer、EPUB page sourceは
  この配布物へ接続していません。

### UIギャラリー

![デモ専用の本棚](../images/ja/bookshelf.png)

![中央クリックで開く読書操作](../images/ja/reader-controls.png)

![遅延生成するページ一覧](../images/ja/page-overview.png)

画像はデモ専用の本棚と、David Revoy氏の*Pepper&Carrot*（CC BY 4.0）で撮影しています。
[クレジット](../../demo/ATTRIBUTION.md)と[再現可能な撮影手順](../images/README.md)を参照してください。

### 検証と引き継ぎ

- macOS上の統合共有suiteは**367成功、8スキップ、12 subtests成功**でした。
- Apple Siliconのローカルテスト版で、配布監査、起動smoke、対話UI確認を通過しました。利用者は統合candidateを
  おおむね問題ないと確認しています。ただし、これはWindows／Linux個別の配布版確認の代わりにはなりません。
- Windows／Linuxのダウンロード配布物は今回更新していません。対応する更新を公開する前に、各OSでbuildし、倍率、
  Ctrl＋ホイール、GPU、LinuxのWayland／X11を確認してください。
- macOS版はApple Silicon専用で、ad-hoc署名済み、Developer ID署名・notarization未実施です。

クロスプラットフォームの継続作業は[次期機能引き継ぎ](../development/next-features-handover.md)、
対象OSの検証項目は[共通UX引き継ぎ](../development/ux-maintenance-handover.ja.md)を参照してください。

### 更新・戻し方

`MangaCrisp-v0.7.1b0.4-macos-apple-silicon-standalone.zip`と添付のSHA-256を取得し、
`アプリケーション`内の`MangaCrisp.app`を置き換えます。本棚と読書設定は保持されます。
Pythonとuvは不要です。初回起動をmacOSに止められた場合は[導入案内](../../INSTALL.ja.md)を参照してください。
以前のrelease assetは戻すために残し、上書きしません。
