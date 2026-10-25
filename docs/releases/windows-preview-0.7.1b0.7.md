# MangaCrisp for Windows — Development Preview 0.7.1b0.7

Reading status, reading-record backup, bookmark notes, and safer reimport for
Windows 10/11 x64. Product version remains `0.7.1b0`; the preview tag identifies
the package. PRs #77 → #78 → #79 → #80 → #81 were merged into main in that order.

## Changes

- Filter All / Unread / Reading / Completed alongside search and recent reading.
  Mark visible selected books completed or unread in bulk. Completion is manual
  and survives rereading. Mark unread resets the saved page, not bookmarks,
  per-book settings or last-opened history.
- Export and restore reading records from the bookshelf's **…** menu. Versioned
  JSON stores status, history, positions, per-book settings and bookmarks.
  Restore previews matching/missing/incompatible books, then restores matching
  state and adds missing bookmark pages without duplicating existing ones.
- In `Shift+B` Bookmarks, edit the label and multiline plain-text note without
  changing the bookmark's identity or page. Cancel/Escape makes no change.
- Centralize built-in reader actions, shortcut badges and help while preserving
  input focus, modal and popup guards. User-customizable key mapping is not added.
- Reimporting the same existing book ID preserves reading/completed status and
  last-opened history instead of replacing them with scanner defaults.

## Backup boundaries

This is **same-library record recovery, not cross-PC library migration**.
Restore matches existing book IDs plus format/page count; it does not recreate
missing books, reconnect moved files or guess matches by title. Media, source
paths, caches and global settings are excluded. Existing bookmark labels/notes
are preserved; only missing bookmarked pages are added. The JSON includes book
titles and personal notes: keep it private. Its size limit is 16 MiB, and large
valid backups may briefly block the UI. An extension-normalized filename that
would replace an existing export requires confirmation; cancellation preserves it.

## Build provenance and acceptance

The release reuses the **unchanged native Windows CI ZIP** from
[run 40167593501](https://github.com/jydie5/MangaCrisp/actions/runs/40167593501),
source `7605b641e6c6bffb672c06e5ae9787ab7aadd6b3`. CI passed source tests, engine
build/provenance, packaging, distribution audit and sanitized extracted startup.
The same integrated source passed
[macOS CI](https://github.com/jydie5/MangaCrisp/actions/runs/40167588467) and
[Linux CI](https://github.com/jydie5/MangaCrisp/actions/runs/40167591018).

After the ordered merges, main `143ad66` matched that candidate's application,
assets, dependencies and build scripts. Local Windows source tests recorded
**413 passed, 9 skipped, 12 subtests passed**. The exact downloaded ZIP passed
checksum/manifest verification and a repeated sanitized-environment startup.
On 2026-10-25 the user accepted the isolated demo candidate on Windows and
authorized merging and release. This is general user acceptance, not an agent
visual inspection, every checklist item's sign-off, or all-GPU certification.

ZIP: `MangaCrisp-0.7.1b0-windows-x64-portable-preview.zip`

SHA-256: `3ef9961d6844811b54b535adfacc8588f8d2598a70074d12733b5be15df7f4ec`

Extract the entire ZIP and launch `MangaCrisp.exe`. Python, uv, CUDA and an
installer are not required. The checksum, distribution audit and portable
manifest are attached. The package is unsigned; SmartScreen may warn.
Intel/AMD engine-matched evidence and a separate clean Windows account remain
stable-release gates. Original-image reading remains available without
enhancement. The old b0.6 assets are retained unchanged for rollback.

## 日本語

Windows向けに読了状態、読書記録バックアップ、しおりメモ、再登録時の履歴保護を追加しました。
PR #77→#78→#79→#80→#81を依存順にmainへマージしています。製品バージョンは`0.7.1b0`のままです。

- 未読／読書中／読了フィルターと、表示中の選択への一括変更。読了は手動指定で、読み返しても維持します。
  未読に戻すと保存ページだけ先頭へ戻り、しおり・本ごとの設定・最終閲覧履歴は残ります。
- 本棚の「…」から読書状態・履歴・位置・設定・しおりをJSONへ書き出し／復元。
  復元前に照合結果を表示し、既存しおりのメモは維持して未登録ページだけ追加します。
- `Shift+B`の一覧でしおりラベルと複数行メモを編集。キャンセルでは変更しません。
- キー処理・キー表示・ヘルプを共通定義へ整理。キー割当編集UIの追加ではありません。
- 同じIDの本を再登録しても、読了／読書中と最終閲覧日時を取り込み時の初期値で上書きしません。

バックアップは**同じ本棚の記録復旧用で、別PCへの本棚移行ではありません**。
移動・改名された原本の再リンクや、存在しない本の再作成は行いません。
漫画本体・cache・全体設定は含みませんが、書名と個人メモを含むため公開しないでください。
16 MiBの上限があり、大きな有効データでは短時間UIが待つ場合があります。
拡張子補完後に既存ファイルを置換する場合も確認し、取消では既存内容を保持します。

3OS CI成功済みの統合候補から、Windows CIのZIPを再コンパイルせず配布します。
mainへの統合後もコード一致を確認し、Windowsテスト413成功・9スキップ・12サブテスト成功。
2026-10-25に利用者がデモ専用候補の実機確認を行い、マージと公開を承認しました。
一般的な受入であり、エージェントによる画面検証、全項目・全GPUの個別合格を意味しません。

ZIP全体を展開して`MangaCrisp.exe`を起動します。Python、uv、CUDA、インストーラは不要です。
未署名のDevelopment Previewであり、Intel/AMDのエンジン一致証跡と別クリーンアカウントは
正式版までの残項目です。旧b0.6は上書きせず残しています。
