# Windows UX candidate — 0.7.1b0+win.ux.20261015.2

**Local candidate, not a published release. General human acceptance received
on 2026-10-15.** Individual checklist sign-offs were not reported.
Built on Windows from main at PR #48 (`b892536`) with the local shared
`core/managed-removal-errors` fix (PR #49). The shared product version is `0.7.1b0`.
The shared fix is published separately before the Windows acceptance documents;
a later downloadable preview must be built and verified from merged main.

## Features

- Hide the fullscreen image-area cursor after two idle seconds and restore it on input.
- Return to the bookshelf through the reading-information overlay button.
- Select multiple books, open their right-click menu, and remove them with one confirmation.
- Correct the visible spread before forward lookahead; retain six pages behind.
- Reduce forward prefetch while reading slowly and increase it when reading faster.

## Fixes

- Keep the corrected spread visible instead of flashing to the original when prefetch finishes (PR #47).
- Report managed-copy deletion failures before removing the book's database entry; keep successful deletions of other books (PR #49).

The source archives are preserved. Failed recursive deletion is not atomic and
can leave a partly removed managed copy; retry after releasing file locks or
re-import from the source archive. Capture shortcuts remain Alt+C / Alt+U.

Windows checks: 186 tests passed, 9 skipped, 5 subtests passed. Distribution
audit and extracted-ZIP startup without development tools passed. Detailed
GUI coverage, user acceptance and detailed checks are in the
[Windows validation record](../testing/windows-ux-pr47-validation.ja.md).
The application is unsigned; Intel/AMD GPU and separate clean-account evidence
remain pending. No stable-release readiness is claimed.

## 日本語

**未公開のローカル確認用ビルドです。2026-10-15にヒューマンチェックの全体合格を受領しました。**
細目ごとの実施報告はありません。PR #48までのmainと共通削除修正（PR #49）を
Windows上でビルドしています。製品バージョンは`0.7.1b0`のままです。
共通修正を先に反映し、Windowsの合格記録を後続文書PRで反映します。
新しい配布版はその後のmainからビルド・検証して公開する必要があります。

### 機能5点

- 全画面の画像領域で2秒静止するとカーソルを隠し、操作で表示を戻します。
- 読書情報オーバーレイのボタンから本棚へ戻れます。
- 本棚の複数選択、右クリックメニュー、1回の確認での一括削除に対応します。
- 表示中の見開きを先読みより優先して補正し、後方6ページを保持します。
- 読書が遅いと先読みを縮め、速くなると増やします。

### 修正2点

- 先読み完了時に補正版が一瞬原画へ戻るちらつきを抑えます（PR #47）。
- 管理コピーの削除に失敗した本は登録を残して失敗を通知し、他の本の削除成功は反映します（PR #49）。

元ZIPなどのソースは残します。失敗時は管理コピーが途中まで消えることがあるため、
ロック解除後の再試行や元ファイルからの再登録が必要な場合があります。
キャプチャは従来のAlt+C／Alt+Uのままです。

Windowsテスト186成功、9スキップ、5サブテスト成功。配布監査と開発環境を除いたZIP展開後の
起動確認に合格しました。候補版の全体合格とは別に、Intel/AMD、別のクリーンアカウントの
証跡は未完了です。未署名のDevelopment Previewとして扱い、正式版合格とは扱いません。
