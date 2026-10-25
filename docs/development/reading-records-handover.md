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
7. Test at the minimum window size in English and Japanese; ensure the filter
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
確認後に保存済みの状態へ戻します。既存しおりは残し、同じページを二重追加しません。


## Synthetic scale check (2026-10-25)

One macOS arm64 run with Python 3.13.9 used a temporary SQLite database containing
10,000 generated books, 10,000 reading states and 10,000 bookmarks, without media.
Export was 0.177 s (8,110,920 bytes, 7.74 MiB), load/validation 0.200 s, initial
preview 0.083 s and restore 0.130 s. A second restore added zero bookmarks and
kept exactly 10,000 of each record type. The F14 bulk status update took 0.026 s.
Temporary data was removed. These are single-run measurements, not guarantees
for other machines or files with long notes. The input limit remains 16 MiB;
large payloads can briefly block the UI and worker/progress support is deferred.
