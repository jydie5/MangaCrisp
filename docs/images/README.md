# UI screenshots

The English images in this directory and Japanese images in `ja/` show
MangaCrisp's shared UI rendered on macOS 27.0.1 (build 26A434), Apple Silicon,
with Python 3.13.6 and PySide6/Qt 6.11.1. The gallery was refreshed for
macOS Beta 0.7.1b0.5 on 2026-10-25. They are captured from actual Qt
widgets, with no artwork replacement or AI-generated UI.

| File (both languages) | View |
| --- | --- |
| `bookshelf.png` | Demo-only bookshelf with Unread / Reading / Completed states |
| `reader.png` | Two-page reading and quality/layout settings |
| `reader-controls.png` | Center-click translucent controls and shortcut badges |
| `shortcut-help.png` | H/? help card (cropped to the card widget) |
| `page-overview.png` | Lazy page overview with visible demo thumbnails |
| `bookmarks.png` | Bookmark list with a generated label and note |
| `bookmark-edit.png` | Plain-text bookmark label/note editor |

Artwork is *Pepper&Carrot*, episodes 1–3, by David Revoy under CC BY 4.0.
See [the complete attribution and source links](../../demo/ATTRIBUTION.md).
The English comic pages are used unchanged in both interface languages.
Images are displayed by the normal reader at window size. Enhancement is
disabled for this reproducible capture; this is a UI gallery, not an AI-quality
comparison. The source pages in `demo/` retain their original artwork.

## Reproduce

From the repository root, with the GUI dependencies installed:

```bash
uv run python scripts/capture_readme_screenshots.py --language en --output-dir docs/images
uv run python scripts/capture_readme_screenshots.py --language ja --output-dir docs/images/ja
```

The script creates temporary library, settings, correction-cache, and
display-cache locations, imports only the redistributable `demo/` ZIP files,
then removes the temporary store when done. Reading states and short sample
notes are generated in that store; no personal reading history or notes are used.
The overview capture opens the reader's `T` page overview and waits until the
visible demo thumbnails have loaded; it does not use a personal library or
private image file.
It does not open the user's library or reuse its correction/display cache. The
bookshelf's location label identifies the demo instead of exposing a temporary
absolute path. No personal book covers, titles, library database, cache data,
or capture sessions are used.

## 日本語

実際のQtウィジェットをmacOS上で描画し、英語・日本語の本棚、読書設定、中央操作パネル、
H/?ヘルプを撮影しています。ヘルプ画像はカード部分のみを切り出しています。
`page-overview.png`は`T`で開いたページ一覧で、表示中のデモ用サムネイルが読み込まれた後に撮影しています。

素材はDavid Revoyの*Pepper&Carrot*（CC BY 4.0、エピソード1～3）です。
[出典・著作者表示](../../demo/ATTRIBUTION.md)を参照してください。
一時的なデモ専用本棚と設定を作成し、既存の個人ライブラリは開きません。
補正・表示cacheも一時領域へ分離し、既存のcacheを再利用しません。
画像内の保存先はデモの説明へ置き換えています。
AI補正は撮影時には実行せず、画面デザインを再現可能な形で紹介しています。

今回のギャラリーには未読／読書中／読了の状態と、生成したサンプルラベル・メモを表示しています。
`bookmarks.png`と`bookmark-edit.png`も実際のしおり画面で、個人の記録は使用していません。
