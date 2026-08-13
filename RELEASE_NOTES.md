# MangaCrisp v0.7.1-beta

This macOS beta adds manual sequential screen capture and a Single Page reader
layout for captured images that already contain a complete spread.

## Changes

- Capture a fixed screen region to numbered, color-preserving PNG files with `Option+C`.
- Undo the last capture with `Option+Z` and reuse its page number.
- Keep MangaCrisp hidden while capturing and restore the controller from the Dock.
- Finish capture after pending saves complete, producing one CBZ/ZIP with optional bookshelf import.
- Prevent repeated completion from creating duplicate archives or bookshelf entries.
- Keep source PNG files after packaging.
- Toggle **Spread (2 images)** and **Single Page (1 image)** with `V`.
- Apply original/enhanced comparison and AI enhancement in Single Page layout.

## 日本語

- `Option+C`で固定範囲をカラー連番PNGへ保存するmacOSキャプチャを追加しました。
- `Option+Z`で直前取消を行い、同じページ番号で撮り直せます。
- 撮影中はMangaCrispを隠し、DockからCapture画面だけを復帰できます。
- 保存待ちを確定してからCBZ／ZIPを1個作り、本棚へ登録できます。
- 完成ボタン連打による重複アーカイブと重複本棚登録を防止しました。
- 完成後も元の連番PNGを保持します。
- `V`キーで見開き表示と単ページ表示を切り替えられます。
- 単ページ表示でも原画比較とAI補正を利用できます。

権利または許諾を持つ画面だけにキャプチャを使用してください。初回はmacOSの
画面収録許可とアプリ再起動が必要です。Apple Silicon Macで86枚の連続撮影を含む
実機確認を完了しています。

詳細は[リリース文書](docs/releases/v0.7.1-beta.md)を参照してください。

# MangaCrisp v0.7.0-beta

This macOS beta adds local PDF reading, safer archive imports, bounded PDF
render caching, and privacy-safe diagnostics.

## Changes

- Add PDF files through drag and drop or the file picker.
- Copy the source PDF into the managed library and generate only its cover at import time.
- Render PDF pages on demand in color, then reuse them through a bounded disk cache.
- Keep the existing spread, fullscreen, mouse, resume, and Real-CUGAN comparison behavior for PDF books.
- Reject unsafe archive paths, excessive member counts, oversized entries, and extreme compression ratios.
- Stage archive imports so a failed extraction does not replace a working managed copy.
- Back up an existing library database before applying a schema migration.
- Add **Copy Diagnostics** and **Clear Cache** to the bookshelf menu.
- Add Apple Silicon CI coverage for source tests, standalone packaging, and packaged PDF startup.

## 日本語

- PDFをドラッグ＆ドロップまたはファイル選択から本棚へ登録できます。
- 登録時はPDF原本を管理フォルダへコピーし、表紙だけを生成します。
- 本文は必要なページだけカラーのまま描画し、上限付きキャッシュで再利用します。
- PDFでも見開き、全画面、マウス操作、読書位置、原画／Real-CUGAN補正版の比較を利用できます。
- 危険なパス、過剰なファイル数、巨大ファイル、異常な圧縮率を持つ圧縮ファイルを拒否します。
- 展開失敗時に正常な管理コピーを置き換えない段階的取り込みへ変更しました。
- DB更新前のバックアップ、診断情報コピー、キャッシュ削除を追加しました。

Apple Silicon向けstandalone ZIPにはPython、Qt、PDFium、Real-CUGAN本体、
モデル、ライセンス文書を同梱します。利用者によるPythonやuvの導入は不要です。
このベータ版はad-hoc署名済みですが、Apple Developer ID署名と公証は未実施です。

# MangaCrisp v0.6.0-beta

This beta preserves color in AI-enhanced pages and adds mouse-first reading for
right-bound manga and left-bound comics.

## Changes

- Preserve RGB color channels when displaying Real-CUGAN output.
- Remove incompatible legacy grayscale display caches automatically.
- Click the forward or backward side of the reader to turn a spread.
- Use `Shift` with a side click to move one page.
- Click the center to show or hide reading progress and file information.
- Right-click to return to the previous spread.
- Ignore drags and suppress duplicate page turns from double-clicks.
- Keep mouse behavior consistent in windowed and full-screen reading.
- Update English and Japanese help and installation links.

## 日本語

- Real-CUGAN補正版のカラー原稿をRGBのまま表示します。
- 旧版が作成した互換性のないモノクロ表示キャッシュを自動削除します。
- 読書方向に連動した左右クリックで見開きを進む／戻る操作を追加しました。
- `Shift+クリック`で1ページ単位の調整ができます。
- 中央クリックで進行情報を表示／非表示にします。
- 右クリックで前の見開きへ戻ります。
- ドラッグとダブルクリックによる意図しない複数ページ送りを防止します。

# RAIV for mac v0.4.0-beta

RAIV for mac has moved from alpha to beta. The core bookshelf, archive import,
right-bound spread reader, Real-CUGAN enhancement, bounded prefetch cache, and
Python-free standalone distribution are now in place.

## Changes since v0.3.0-alpha

- New RAIV application icon, used by the app bundle and shown in the README
- `O` shortcut to toggle the visible spread between Original and Enhanced
- `H` shortcut for help without requiring Shift
- Clickable GitHub, issue-reporting, and optional support links in app help
- Direct standalone download links near the top of both READMEs
- A18 Pro MacBook Neo compatibility assessment and physical-test checklist

## β版への移行

本棚、圧縮ファイル登録、右綴じ見開き、Real-CUGAN補正、上限付き先読み
キャッシュ、Python不要のstandalone配布が一通り成立したため、β版へ移行します。

- RAIV専用アプリアイコンを追加
- `O`キーで表示中の見開きを原画／補正版へ即時切り替え
- Shift不要の`H`ヘルプキーを追加
- アプリ内ヘルプへGitHub、不具合報告、任意支援リンクを追加
- 英語／日本語README上部へstandalone版の直接ダウンロードリンクを追加
- A18 Pro搭載MacBook Neoの互換性調査と実機テスト項目を追加

このβ版はad-hoc署名済みですが、Apple Developer ID署名とnotarizationは未実施です。
正式版までに複数のApple Silicon実機で性能と起動手順を確認します。

# RAIV for mac v0.3.0-alpha

## Highlights

- English and Japanese interface with automatic macOS language detection
- Language selector in the bookshelf header
- English bookshelf, reader controls, dialogs, keyboard help, and processing status
- Faster back-and-forth page navigation with asynchronous display decoding
- Adaptive Real-CUGAN prefetch with bounded forward, backward, memory, and disk caches
- English-first public documentation and freely licensed demo books

The standalone ZIP includes RAIV.app and the pinned Real-CUGAN engine. End users
do not need Python, uv, or a separate AI engine installation.

## 主な変更

- macOSの優先言語に追従する英語／日本語UI
- 本棚右上に言語選択を追加
- 本棚、読書設定、確認画面、ヘルプ、補正状態を英語化
- 非同期画像デコードにより前後ページ移動を高速化
- 前後ページを過不足なく保持する適応型Real-CUGAN先読み
- 英語を基本とした公開ドキュメントと自由ライセンスのデモ本

## Features

- 縦方向に画像が最大化された見開きでも、左右ページを中央の綴じ目へ寄せて表示
- 全画面表示では下部ステータス行を隠し、画像に使える縦方向の表示領域を拡大
- 先読み範囲を前方12ページ・後方4ページへ再配分し、速いページ送りへの余裕を拡大
- 原画・自然・クリーニング・高画質の4種類に整理した「かんたん」画質モード
- モデルやnoiseなどを調整できる「マニュアル」画質モード
- 名前付きカスタム画質設定の保存・読込・上書き・削除
- 読書速度と実測補正時間に応じて前方12〜24ページへ伸縮する適応先読み
- かんたんモードでは先読みの詳細ログを隠し、読書を妨げないバックグラウンド処理へ変更

## Fixes

- 先読み中のページ移動で、見開きの片側だけ補正画像になる問題を修正
- 左右の補正がそろうまで見開き全体を原画で表示し、完成後に同時切り替え
- 古い先読み処理が完了してから現在位置へ追従する際の結果混入を防止
- 補正キャッシュと表示用キャッシュを現在位置周辺へ限定し、無制限なディスク増加を防止
- ウィンドウ終了時にタイマー、イベント監視、縮小画像キャッシュを解放
- 前後移動のたびに先読みを破棄していた処理を廃止し、補正済みページ間の往復を高速化
- 表示画像の予熱とキャッシュ整理を操作停止後へ移し、キー入力中の引っ掛かりを低減
- 補正済みディスクキャッシュを後方12ページまで保持し、短い読み返しでの再補正を防止
- PNG読込、グレースケール変換、高品質縮小を表示スレッドから分離
- 補正版が未予熱でも原画見開きを先に表示し、補正版が左右揃ってから同時に差し替え
- 15〜19MBの実画像でキー応答0.68ms、初回見開き表示15.57msを確認
- 読書位置のSQLite保存を350msデバウンスし、連続ページ送り中の同期書込みを廃止

## Next

今後の設計と実装順は[ROADMAP.md](ROADMAP.md)に記載します。

# RAIV for mac v0.2.0-alpha

一般ユーザーがPythonやターミナル操作なしで試せるstandalone版です。

## 主な変更

- 公式Real-CUGAN 20220728 macOS実行ファイルとモデルを同梱
- 公式ZIPと実行ファイルをSHA256で検証する再現可能なビルド
- Real-CUGAN、モデル、ncnn、libwebp、MoltenVK、LLVM OpenMPのライセンス全文をアプリへ収録
- 原画／補正版チェック切り替え時の表示キャッシュを破棄し、即時再描画
- 比較チェックの表示を`原画を表示（OFFで補正版）`へ明確化
- 一般ユーザー向け日本語READMEとインストールガイド

## ダウンロード

`RAIVformac-v0.2.0-alpha-macos-apple-silicon-standalone.zip`をダウンロードしてください。Python、uv、Real-CUGANの個別インストールは不要です。

## 初回起動

このα版は署名・Apple notarization未実施です。ZIPを展開して`RAIV.app`をアプリケーションへ移動し、初回だけControlキーを押しながらクリックして`開く`を選んでください。

## 対象環境

- Apple Silicon Mac
- macOS 13以降を推奨

## ライセンス

RAIV for mac本体はMIT Licenseです。同梱物の由来とライセンスは`THIRD_PARTY_NOTICES.md`およびアプリ内の`Contents/Resources/licenses/`を参照してください。
