# macOS開発引き継ぎ

[English](macos-handover.md)

Windows側の作業がPR #27まで先行したあと、macOSでMangaCrisp開発を再開するための
引き継ぎです。Macでは必ず最新の`origin/main`から続けてください。古いMac側チェックアウトで
共有ファイルを上書きしてはいけません。

## 現在のチェックポイント（2026-08-15）

- 最低限必要な共通チェックポイントはcommit `9f463c0`（PR #27）です。この引き継ぎ自体が
  mainへ入るとさらに先のcommitになるため、固定commitへ戻らず最新のremote headを使います。
- macOS配布版はApple Silicon向け`v0.7.1-beta`です。
- Windows配布版はDevelopment Preview `windows-preview-0.7.1b0.4`です。
- PR #27は全ソーステスト（`99 passed, 3 skipped`）、macOS source/package CI、Windowsの
  portable build、配布監査、開発環境なしの展開スモークテストを通過しました。
- Windows b0.4のヒューマンチェックで2キー操作を確認済みです。Windowsは
  `Alt+C`／`Alt+U`、macOSは従来どおり`Option+C`／`Option+Z`です。

macOSのrelease assetはPR #27より前に作られていますが、ソースが分岐したわけではありません。
macOS作業前にmainをpullしてください。既存の`v0.7.1-beta` assetは置き換えず、新しいmacOS
配布物は別のversion/tagとリリース判断で公開します。

## Windows先行作業でmainへ入った内容

### Windows固有

- `src/mangacrisp_app/platform/capture_windows.py`に固定範囲キャプチャとWindows
  `RegisterHotKey`処理があります。
- 撮影中のWindows controllerはタスクバーへ最小化して残ります。macOSは従来の非表示と
  Dockからの復帰を維持します。
- Windowsの既定は`Alt+C`／`Alt+U`で、3キーの代替presetも残しています。
  macOSのshortcutは変更していません。
- Windows packaging、来歴、検証、preview公開はWindows専用ファイルにあります。
  MacからWindows配布物を再ビルド・公開しません。

### OS共通

- 連番キャプチャと単ページ表示は共通機能です。画面取得、global shortcut、window復帰だけを
  OS別にしています。
- `src/mangacrisp_app/cache_utils.py`に共通PNG cache整理処理を追加しました。
- PDF描画cacheとAI補正cacheはそれぞれ最大2 GiBです。30日以上未使用の項目を整理し、
  読書中のfileは保護します。
- cache再利用時に更新時刻を進め、最後に使った時期に基づいて整理します。
- 強制終了で残った管理本の`.import-*`／`.backup-*`を次回起動時に削除または復元します。
  利用者の本やcapture sessionをcache扱いしません。
- 連番キャプチャのsession folderとPNGは利用者の成果物なので自動削除しません。
- README上部に任意の開発支援を表示し、`.github/FUNDING.yml`からGitHubのSponsorボタンにも
  同じBuy Me a Coffeeを表示します。支援による機能解放はありません。

## Macでの安全な同期手順

最初にworktreeがcleanか確認します。未保存のMac作業を破棄するresetは使いません。

```bash
git status --short
git fetch origin
git switch main
git pull --ff-only origin main
uv sync --extra dev --extra app
uv run pytest -q
uv run python -m mangacrisp_app.main --smoke-test
git switch -c macos/<作業名>
```

未mergeのMac branchがある場合は`origin/main`をfetchし、差分を確認して意図的にrebaseまたは
mergeします。共有fileの競合では両OSの動作を残してください。古い`viewer.py`、
`bookshelf.py`、`library.py`、`page_provider.py`をfile単位で採用して解決してはいけません。

## 同期直後のmacOS確認

`demo/`の再配布可能素材と生成したcolor PDFだけを使います。

1. 本棚を起動し、既存library metadataを正常に開けることを確認します。
2. demo archiveとcolor PDFを開き、見開き／単ページ（`V`）、ページ送り、原画／補正版（`O`）で
   colorからモノクロへ変化しないことを確認します。
3. 画面収録権限を許可して連番キャプチャを開始し、`Option+C`撮影、`Option+Z`取消、Dockからの
   controller復帰、color PNGとCBZ／ZIPの正しい順序を確認します。
4. 補正しながら複数ページを開き、readerを再起動してcacheを再利用できることを確認します。
   新しい整理処理が読書中のpageを消してはいけません。
5. `キャッシュを削除`でPDF描画／AI補正cacheだけが消え、本棚の管理本が残ることを確認します。
6. Helpを開き、project linkと任意の支援linkが動くことを確認します。

ここまで通ればWindows作業をMacで再実装する必要はありません。macOSだけのregressionは
`macos/<作業名>`、共通修正は`core/<作業名>`で扱います。

## 競合に注意する共有file

| File | 現在の責務 |
|---|---|
| `src/mangacrisp_app/bookshelf.py` | 共通本棚とOS別capture window復帰 |
| `src/mangacrisp_app/viewer.py` | 共通reader、単ページ、補正schedule、AI cache整理 |
| `src/mangacrisp_app/library.py` | 管理取り込み、DB、削除、中断取り込み復旧 |
| `src/mangacrisp_app/page_provider.py` | color保持のlazy PDF描画と上限付きcache |
| `src/mangacrisp_app/cache_utils.py` | 使用中fileを保護するsize／age共通整理 |
| `src/mangacrisp_app/capture/` | 共通session、review、採番、packaging |
| `src/mangacrisp_app/platform/capture_macos.py` | macOS権限と画面取得 |
| `src/mangacrisp_app/platform/capture_windows.py` | Windows画面取得、global hotkey、preset |

既存のplatform境界がある処理を共有readerのOS分岐へ戻したり、Windows処理をmacOS adapterへ
移したりしません。

## 残るリリース境界

- macOS署名／notarizationはmacOS側のリリース作業です。
- Windows正式版にはIntel／AMD Vulkan証跡と別のclean Windows account確認が残っています。
  これはmacOSのsource開発を妨げません。
- 配布物は対象OSでbuild・検証します。
- tagとrelease assetはmainから作り、既存prerelease assetを新しいsourceのものとして
  上書きしません。
