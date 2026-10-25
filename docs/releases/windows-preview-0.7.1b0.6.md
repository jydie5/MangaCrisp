# MangaCrisp for Windows — Development Preview 0.7.1b0.6

Reader navigation, lazy page overview, and archive-cache fixes for Windows
10/11 x64, matching the shared application code in macOS Beta 0.7.1b0.4.
Product version remains `0.7.1b0`; the new preview tag identifies this package.

## Changes

- Search the bookshelf, sort by title / last opened / added order, and use
  Recently read.
- Jump by physical page number without changing binding or spread rules.
- Press `B` to bookmark the current page; `Shift+B` opens that book's bookmarks.
- Restore layout, binding, cover and quality settings per book. Original-image
  comparison remains temporary; zoom and pan are not saved.
- Use `+` / `-`, `0` (fit), `W` (width), `1` (actual size), Ctrl+wheel, and
  drag-to-pan. The display-cache target is 192 MiB, not a process memory cap.
- Press `T` to open a lazy page overview and select a destination. It requests
  visible thumbnails rather than rendering every PDF page or extracting the
  whole archive; the thumbnail-image cache is 16 MiB.
- Keep processed-page lookup lazy and isolate ZIP extraction by physical page,
  preventing collisions between duplicate or sanitized member names.

Comic EPUB reading is not included. Capture adapters and shortcuts are unchanged.

## Package provenance and checks

This release reuses the **unchanged Windows-native CI artifact**, not a local
recompile, from [run 40057157576](https://github.com/jydie5/MangaCrisp/actions/runs/40057157576).
Its tested merge revision is `47f0c2c388de6c87e89fef76100c04f82838779d`.
Application sources, dependencies and Windows build/package scripts were
compared against `main` at `cdab340`; there are no runtime changes. Later
release/download documentation commits do not modify the application.

- CI passed source checks, the pinned engine build, portable packaging,
  distribution audit and extracted startup without development-tool paths.
- On 2026-10-25, the downloaded ZIP matched its checksum and manifest, and
  extracted startup with Python/uv/virtual-environment paths removed was
  repeated successfully on the Windows development PC.
- The user confirmed native startup, `T` overview selection/page navigation,
  `+` zoom and `0` fit, then approved publication. This is the user's manual
  check, not an automated visual inspection or every checklist item's sign-off.

ZIP: `MangaCrisp-0.7.1b0-windows-x64-portable-preview.zip`

SHA-256: `54596edeec782990b18fc95bdd0b0087145c0595afc9c1b38944f50a544a6187`

The checksum, distribution audit and portable manifest are attached to the
release. Extract the entire ZIP and launch `MangaCrisp.exe`; Python, uv, CUDA
and an installer are not required. Keep the bundled files together.

## Preview limitations

The package is unsigned and Windows SmartScreen may warn. Intel/AMD
engine-matched GPU evidence and a separate clean Windows account test remain
stable-release gates. High-DPI/multi-monitor behavior, Ctrl+wheel, drag-pan,
capture and long-duration reading were not individually reaccepted in this
manual check. Original-image reading remains available without enhancement.
The previous b0.5 release is retained unchanged for rollback. See
[installation](../../INSTALL.windows.md).

## 日本語

Windows 10/11 x64向けの読書操作・ページ一覧・アーカイブキャッシュ更新です。
macOS Beta 0.7.1b0.4と同じ共通アプリコードを含みます。
製品バージョンは`0.7.1b0`のままで、新しいpreviewタグで配布物を区別します。

- 本棚検索、タイトル／最終閲覧／追加順の並べ替え、「最近読んだ本」。
- 物理ページ番号ジャンプ、`B`のしおり追加、`Shift+B`の本ごとのしおり一覧。
- 本ごとのレイアウト・綴じ・表紙・画質設定の復元。原画比較は一時操作で、ズーム／パンは保存しません。
- `+`／`-`、`0`全体、`W`幅、`1`実寸、Ctrl＋ホイール、ドラッグパン。
  表示キャッシュ192 MiBはプロセス全体のメモリ上限ではありません。
- `T`の遅延ページ一覧と選択移動。表示範囲のサムネイルだけを要求し、PDF全ページ描画や
  ZIP全体展開を起こしません。サムネイル画像キャッシュは16 MiBです。
- 処理済みページ探索の遅延化とZIPの物理ページごとの展開先分離。

Comic EPUBの読書対応は含みません。キャプチャのOS別処理・キーは変更していません。

上記のWindows CI成果物を再コンパイルせず、そのまま配布します。現在のmainとの
アプリ・依存関係・Windowsビルド処理の一致を確認しています。2026-10-25にchecksum照合と、
開発ツールのパスを除いたZIP展開後起動を再確認しました。
利用者は実機で起動、`T`一覧からのページ移動、`+`拡大、`0`全体復帰を確認し、公開を承認しました。
これは利用者の目視確認であり、自動操作による画面検証や全チェック項目の個別合格ではありません。

ZIP全体を展開して`MangaCrisp.exe`を起動してください。Python、uv、CUDA、インストーラは不要です。
checksum・監査レポート・manifestを添付します。未署名のDevelopment Previewで、
SmartScreen警告が出る場合があります。Intel/AMDのエンジン一致GPU証跡、別クリーンアカウント、
今回個別に確認していない高DPI・複数画面・Ctrl＋ホイール・ドラッグパン・キャプチャ・長時間読書は
未完了の詳細確認として残します。旧b0.5の配布物は上書きせず保持します。
