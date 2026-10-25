# Reading records: development handover

[日本語](#日本語)

This describes the next shared features after macOS beta 0.7.1b0.4 and Windows
preview 0.7.1b0.6. It does not change the published download or claim native
Windows/Linux acceptance. Build each platform's candidate on that platform.

## Reading status (F14)

- The bookshelf can filter All / Unread / Reading / Completed together with
  title search, sorting, and Recently read.
- Mark completed and Mark unread act on the visible selection only, including
  multiple books. A hidden selection is never changed by these actions.
- Completion is manual. Jumping to the final page does not mark a book read.
- Opening a completed book preserves completion, including during a reread.
- Mark unread resets the saved page to the beginning. Bookmarks, per-book
  display settings, and last-opened history remain. On reading again, the book
  becomes Reading. Mark completed preserves the saved position.
- The existing database schema already stores the three statuses. No schema
  migration or media/cache rewrite is needed.

## Reading-record backup (F15 first stage)

The first-stage export contains reading status, last-opened history,
position, per-book display settings, and bookmarks in a versioned JSON file.
It excludes media, managed copies, thumbnails, cache, source paths, and global
settings. Book titles and user-written bookmark text are included; this is a
personal backup, not an anonymized issue-report attachment.

Restore matches existing book IDs in the same bookshelf. It does not recreate
missing books, use title-only guesses, or reconnect moved sources. Current IDs
depend on the source location, so reimporting a book on another PC may produce
a different ID. Portable cross-PC matching requires a separate design.

Before applying, show how many books match, are missing or incompatible, and
how many bookmarks will be added. After explicit confirmation, restore the
saved position/status/settings for matching books. Preserve existing bookmarks
and add missing physical pages only. Repeated restore must not duplicate
bookmarks. The complete DB operation must roll back on failure. Global quality
preset definitions are not in this first format; missing named presets follow
the reader's existing fallback.

## Bookmark labels and notes (F05 follow-up)

Open Bookmarks with Shift+B, select a bookmark and choose Edit. A required label
and optional plain-text note can be saved without changing the bookmark ID,
physical page or creation time. Cancel/Escape makes no change. Invalid input or
storage failure keeps the editor open with the entered text. Even a bookmark
whose page is no longer available can be edited or removed.

Notes appear as a short preview in the list and in full in the editor/tooltip.
The label limit is 1,024 characters and the note limit is 4,096 characters.
Reading-record export includes them. Restore adds missing bookmark pages and
preserves labels/notes on existing pages; it does not undo later note edits.

## Native checklist

Use generated images or `demo/` only, in an isolated bookshelf.

1. Read two books, mark one complete, and combine the status filter with search
   and Recently read. Confirm the card and tooltip agree.
2. Select several books, hide one with a filter, then change the status. The
   hidden book must keep its state. Clear the filter to recover the selection.
3. Reopen a completed book, move backwards, and close it: it stays Completed.
   Mark it unread, reopen it: it starts at page one with its layout and
   bookmarks retained.
4. Export records, change the reading position, then cancel a restore: nothing
   changes. Confirm restore: the saved position and status return.
5. Restore twice: existing bookmarks and labels remain, with no duplicates.
6. Try an unrelated bookshelf or a malformed file: no books are created and no
   source or cache files are changed. Check the reported skipped/error counts.
7. Edit a bookmark label and multiline note, cancel once, then save. Reopen the
   list and confirm the edit. A deleted bookmark restored from a backup should
   recover its saved note; an existing bookmark should keep its current note.
8. Test at the minimum window size in English and Japanese; ensure the filter
   row and action buttons fit. Check keyboard focus and Escape/cancel.

## 日本語

これは公開済みMac b0.4 / Windows b0.6の次の共有機能の作業メモです。
配布物はまだ更新しません。Windows/Linuxの実機確認は各OS担当が行います。

読了は手動指定です。最終ページへ飛んだだけでは読了にせず、読み返しで読了が
消えないようにします。「未読に戻す」は位置だけ先頭へ戻し、しおり・本ごとの
表示設定・最終閲覧日時を残します。絞り込みで隠れた選択は一括変更の対象外です。

読書記録のJSONは同じ本棚の既存IDへ戻すための小容量バックアップです。
漫画本体・cache・保存先・全体設定を含めません。書名やしおりのメモは含むため、
そのまま公開用の診断情報として扱わないでください。別PCへの再取り込みや原本移動の
自動照合は対象外です。復元前に一致・対象なし・不一致・追加しおり件数を表示し、
確認後に保存済みの状態へ戻します。既存しおりのラベル・メモは残し、同じページを二重追加しません。

Shift+Bのしおり一覧からラベルとメモを編集できます。ID・ページ番号・作成日時は
維持し、キャンセル/Escでは変更しません。保存失敗時には入力を残します。
JSON復元は既存のメモ編集を巻き戻さず、消えたページのしおりだけを追加します。


## Synthetic scale check (2026-10-25)

One macOS arm64 run with Python 3.13.9 used a temporary SQLite database containing
10,000 generated books, 10,000 reading states and 10,000 bookmarks, without media.
Export was 0.177 s (8,110,920 bytes, 7.74 MiB), load/validation 0.200 s, initial
preview 0.083 s and restore 0.130 s. A second restore added zero bookmarks and
kept exactly 10,000 of each record type. The F14 bulk status update took 0.026 s.
Temporary data was removed. These are single-run measurements, not guarantees
for other machines or files with long notes. The input limit remains 16 MiB;
large payloads can briefly block the UI and worker/progress support is deferred.


## Current verification and review boundary

The integrated macOS source suite (Python 3.13.6, Qt offscreen) passed **410 tests,
8 skips and 12 subtests** after bookmark editing and selection retention were
added and the export suffix-overwrite fix was verified. The development PRs are stacked: reading status → record backup → reader
actions → bookmark editing. Review/merge in that order, retargeting each child to
main after its parent is integrated. Existing download links and release tags
are unchanged. Native CI evidence is recorded on the corresponding PR.

The older CI additions [#67](https://github.com/jydie5/MangaCrisp/pull/67) and
[#69](https://github.com/jydie5/MangaCrisp/pull/69) passed their earlier audit runs,
but their path filters omit many shared runtime files. Before a release, either
extend their triggers to shared runtime changes or dispatch the bundled macOS
and Linux clean-install audits on the exact release commit. Earlier green checks
must not be presented as validation of later reader changes. Signing/notarization,
Windows GPU variants and Linux desktop-session acceptance remain separate.


## macOS candidate and CI evidence (2026-10-25)

The four-feature runtime at `ecfeb6963f357e7dce5e7b451ea4cdf34ea14f31` passed
[macOS](https://github.com/jydie5/MangaCrisp/actions/runs/40163601224),
[Linux](https://github.com/jydie5/MangaCrisp/actions/runs/40163603007), and
[Windows](https://github.com/jydie5/MangaCrisp/actions/runs/40163604779) native CI.
The later `6f1e1aa` fix adds a confirmation when a filename without an extension
would resolve to an already existing backup after adding the JSON suffix.
Cancel is the default and leaves the prior bytes intact. Its full source suite
passed 410 tests; refreshed CI results are linked from PR #80. Do not treat the
earlier run URLs as validation of this later fix.

Native macOS automation on the isolated demo candidate verified launch, title
search, the Unread/All filter, opening a book, Shift+B, saving/reopening a label
and multiline plain-text note, Escape cancellation, return to the bookshelf and
Completed surviving a reread. A follow-up on `fe48735` also verified selecting
two demo books and marking them completed, the native JSON save/open dialogs,
restore preview, Escape cancellation, confirmed restore, and a repeated restore.
Read-only DB checks showed cancellation preserved the changed state; restore
returned one Unread, one Reading and one Completed book, with exactly one bookmark
after both restores. The cards visually matched those records. Popup menu contents
were not exposed reliably by native automation, but keyboard menu navigation
reached and verified each intended operation.

The normalized-filename overwrite prompt has automated cancellation/confirmation
coverage and English/Japanese visual checks. Its native platform-specific path
still needs human acceptance. Windows/Linux desktop input is also pending.

The local Mac test app uses a separate bundle identifier and demo-only TestData.
It is ad-hoc signed, not notarized, and has not been accepted by the user.
The accepted production app and published release assets are unchanged.

追加の書き出し確認も実機チェック対象です。拡張子なしの保存名にJSON拡張子を補い、
その保存先が既に存在する場合は、正しいファイル名を表示して確認します。
取消では既存バックアップを変更しません。現時点の次段階設計は
[欠損検出・再リンク／縦読み／キー設定](../product/reading-workflow-next-steps-2026-10-25.ja.md)
を参照してください。
