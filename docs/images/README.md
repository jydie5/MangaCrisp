# UI screenshots

The English images in this directory and Japanese images in `ja/` show
MangaCrisp's shared UI rendered on macOS. They are captured from actual Qt
widgets, with no artwork replacement or AI-generated UI.

| File (both languages) | View |
| --- | --- |
| `bookshelf.png` | Demo-only bookshelf, with a book selected |
| `reader.png` | Two-page reading and quality/layout settings |
| `reader-controls.png` | Center-click translucent controls and shortcut badges |
| `shortcut-help.png` | H/? help card (cropped to the card widget) |

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

The script creates a temporary library and settings store, imports only the
redistributable `demo/` ZIP files, then removes the temporary store when done.
It does not open the user's library. The bookshelf's location label identifies
the demo instead of exposing a temporary absolute path. No personal book
covers, titles, library database, or capture sessions are used.

## 日本語

実際のQtウィジェットをmacOS上で描画し、英語・日本語の本棚、読書設定、中央操作パネル、
H/?ヘルプを撮影しています。ヘルプ画像はカード部分のみを切り出しています。

素材はDavid Revoyの*Pepper&Carrot*（CC BY 4.0、エピソード1～3）です。
[出典・著作者表示](../../demo/ATTRIBUTION.md)を参照してください。
一時的なデモ専用本棚と設定を作成し、既存の個人ライブラリは開きません。
画像内の保存先はデモの説明へ置き換えています。
AI補正は撮影時には実行せず、画面デザインを再現可能な形で紹介しています。
