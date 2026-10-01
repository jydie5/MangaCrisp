# MangaCrisp for macOS — Beta 0.7.1b0.2

This update brings the macOS build up to the same shared source as
[MangaCrisp for Linux — Preview 0.7.1b0.2](https://github.com/jydie5/MangaCrisp/releases/tag/linux-preview-0.7.1b0.2).
It replaces `v0.7.1-beta` as the current macOS download. The product version
remains `0.7.1b0`; no reader features were added or removed.

## Changes since v0.7.1-beta

- **Bounded caches.** The PDF render cache and the AI enhancement cache are each
  limited to 2 GiB. Entries unused for more than 30 days are removed when the
  reader opens, and pages you are currently reading are protected.
- **Interrupted imports recover.** An import that was interrupted is cleaned up
  or restored at the next launch. Your books and capture sessions are not
  treated as caches.
- **RAR and CBR import falls back to an external extractor.** When the RAR
  reader can list an archive but cannot decompress it, MangaCrisp now retries
  with an external tool: the `bsdtar` included in macOS, or 7-Zip or `unar` if
  installed. Some RAR variants may still be unsupported.
- **Multi-volume archives split correctly.** An archive that contains several
  volumes in separate folders now becomes one book per volume with only that
  volume's pages when an external extractor is used.

Sequential capture is unchanged: `Option+C` captures and `Option+Z` undoes.

## Validation

- 131 automated tests passed and 8 platform-dependent tests were skipped on an
  Apple Silicon Mac.
- The ZIP was extracted to a temporary directory and passed the packaged-app
  startup check and a two-page color PDF open check.
- The standalone distribution audit verifies the bundled Real-CUGAN executable
  against its pinned checksum, the model set, dependency license notices, the
  app identifier, and the ad-hoc signature.
- The interactive capture acceptance check from `v0.7.1-beta` was not repeated
  for this build. The macOS capture adapter is unchanged since that release;
  the shared capture window changed only in wording.

## Update

Download `MangaCrisp-v0.7.1b0.2-macos-apple-silicon-standalone.zip`, replace
`MangaCrisp.app` in Applications, then Control-click it and choose **Open** on
first launch. Your library and settings are kept. Verify the download with the
attached `.sha256` file. Python, uv, and Terminal are not required.

macOS may ask again for **Screen & System Audio Recording** access before the
first capture with the new copy. Allow it, quit MangaCrisp completely, and
reopen the same installed copy.

This beta is ad-hoc signed but does not have an Apple Developer ID signature or
Apple notarization. It supports Apple Silicon only.

## Support MangaCrisp

MangaCrisp is free, MIT-licensed, and made by one independent developer. If it
makes your reading better, **[please support it on Buy Me a Coffee](https://buymeacoffee.com/jydie5)**.
Support helps pay for code signing, GPU validation hardware, build services,
and development time. Stars, shares, and bug reports help too.

---

## 日本語

macOS版を、[Linux版 Preview 0.7.1b0.2](https://github.com/jydie5/MangaCrisp/releases/tag/linux-preview-0.7.1b0.2)
と同じ共通ソースへそろえた更新です。`v0.7.1-beta`に代わる現在のmacOS配布版です。
製品バージョンは`0.7.1b0`のままで、読書機能の追加・削除はありません。

- **キャッシュに上限を設けました。** PDF描画キャッシュとAI補正キャッシュはそれぞれ
  最大2 GiBです。30日以上使っていない項目は読書画面を開いた時に整理し、表示中の
  ページは保護します。
- **中断した取り込みを復旧します。** 取り込みが途中で止まった場合、次回起動時に
  片付けるか元へ戻します。本やキャプチャセッションはキャッシュとして扱いません。
- **RAR／CBRの取り込みで外部ツールへ切り替えます。** 一覧は読めても展開できない
  RARは、macOS付属の`bsdtar`、または導入済みの7-Zip／`unar`で再試行します。
  一部のRAR形式は引き続き読めない場合があります。
- **複数巻をまとめたアーカイブを正しく分割します。** 巻ごとのフォルダを含む
  アーカイブが、外部ツールで展開した場合も、巻ごとに1冊ずつその巻のページだけで
  取り込まれます。

連番キャプチャは変更ありません。`Option+C`で撮影、`Option+Z`で直前取消です。

### 検証

- Apple Silicon Macで自動テスト131件が通過し、OS依存の8件はスキップされました。
- ZIPを一時フォルダへ展開し、配布アプリの起動確認と2ページのカラーPDFを開く確認に
  合格しました。
- 配布監査で、同梱Real-CUGANの固定チェックサム、モデル一式、依存ライセンス、
  アプリ識別子、ad-hoc署名を検証しています。
- `v0.7.1-beta`で行った実機キャプチャのヒューマンチェックは、この版では
  繰り返していません。macOSのキャプチャ処理はそのリリースから変更しておらず、
  共通のキャプチャ画面は文言だけが変わっています。

### 更新方法

`MangaCrisp-v0.7.1b0.2-macos-apple-silicon-standalone.zip`をダウンロードし、
`アプリケーション`の`MangaCrisp.app`を置き換えます。初回だけControlキーを押しながら
クリックして`開く`を選びます。ライブラリと設定はそのまま残ります。

新しいアプリで最初に撮影する前に、macOSが`画面とシステムオーディオ録音`の許可を
もう一度求める場合があります。許可したあとMangaCrispを完全終了し、同じアプリを
開き直してください。

本ベータはad-hoc署名済みですが、Apple Developer ID署名とApple notarizationは
未実施です。Apple Silicon専用です。

MangaCrisp は個人開発の無料・MIT ライセンスのソフトウェアです。役に立ったら
**[Buy Me a Coffee で支援していただけるとうれしいです](https://buymeacoffee.com/jydie5)**。
