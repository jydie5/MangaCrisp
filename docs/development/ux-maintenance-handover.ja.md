# 読書・本棚UX引き継ぎ（macOS先行分）

[English](ux-maintenance-handover.md)

macOS側で共通の読書画面と本棚の挙動を先に進めました（PR #44、
`core/reader-bookshelf-ux`、2026-10-15にmainへ反映）。この文書は、Windows／Linux担当者が
共通コードの変更点、macOSでしか確認していない点、次のpreview build前に各OSで確認すべき点を
把握するためのものです。Windows／Linuxの作業は必ず最新の`origin/main`から始めてください。

## 共通コードの変更

変更はすべて`src/mangacrisp_app/`内でOS非依存です。`platform/`、`packaging/`、OS固有の
scriptは触っていません。

| 領域 | ファイル | 挙動 |
|---|---|---|
| 全画面のカーソル自動非表示 | `cursor_autohide.py`（新規）、`viewer.py` | 全画面中、画像領域で2秒操作がないとカーソルを隠す。マウス移動・クリック・ホイール・キーで表示してタイマー再開。読書情報オーバーレイ、次巻バナー、ドラッグ中、モーダル／ポップアップ表示中、ウインドウ非アクティブ、全画面解除、終了時は隠さない。 |
| オーバーレイの「本棚へ」ボタン | `viewer.py`、`i18n.py` | 中央クリックで出るオーバーレイに**本棚へ**ボタン。全画面を解除し、読書位置を保存して読書画面を閉じる。ページ送りとしては扱わない。設定パネルの「本棚へ戻る」と`Esc`は従来どおり。 |
| 本棚の複数選択と右クリック | `bookshelf.py`、`i18n.py` | `QListWidget.ExtendedSelection`（Windows／LinuxはCtrl／Shift、macOSはCommand／ShiftをQtが供給）。右クリックメニューは「読む」「本棚から削除」。未選択の本を右クリックするとその本だけ選択、選択内なら選択を維持。 |
| 共通の削除フロー | `bookshelf.py`、`viewer.py` | Delete／Backspace、下部ボタン、メニューはすべて`BookshelfWindow.delete_books()`を通る。確認は1回で冊数と先頭3件の書名を表示。本ごとに管理コピー、読書位置、しおり、PDF描画キャッシュ、ページ単位のAI補正キャッシュ（`remove_enhancement_cache_for_sources`）を削除。元アーカイブは残す。失敗はまとめて通知し、成功分は反映。 |
| 補正の優先度キュー | `viewer.py` | Real-CUGANワーカーは`correction_queue`から`correction_priority`順（表示中 → 前方 → 後方）に取り出す。ワーカー実行中のページ移動で`refresh_correction_queue()`が優先順を更新し、新しく表示されたページを追加。処理中のページ（`correction_in_flight`）は再登録しない。 |
| 先読み調整 | `viewer.py` | `DEFAULT_PREVIOUS_PREFETCH_COUNT` 4 → 6。前方は通常12〜24、ページ送り間隔の中央値が`SLOW_READER_INTERVAL_SECONDS`（8秒）以上なら`MIN_FORWARD_PREFETCH_COUNT`（6）まで減少。直近`CORRECTION_MISS_WINDOW`（10）回中`CORRECTION_MISS_THRESHOLD`（2）回以上表示ページが未補正だったら先行量を`CORRECTION_MISS_LEAD_FACTOR`（1.5）倍。 |

新規・変更テスト: `test/test_cursor_autohide.py`、`test/test_bookshelf_delete.py`、
`test/test_prefetch_policy.py`、`test/test_viewer_navigation.py`への追加。
共通suiteはmacOSで`180 passed, 8 skipped`です。

## macOSでのみ確認した項目

Apple Silicon Macで`scripts/build_macos_app.py --bundle-engine`により作った
`dist/MangaCrisp.app`と`demo/`のPepper&Carrot 3巻で目視確認しました。

- 全画面で2秒後にカーソルが消え、マウス・キー・オーバーレイ上・設定パネル上・ドラッグ・
  アプリ切替・全画面解除で戻ること
- ウインドウ表示と全画面の両方からオーバーレイの**本棚へ**で戻れること
- Command／Shiftの複数選択、選択済み／未選択の本の右クリック、Deleteキーとボタンの削除、
  確認1回、元ZIPが残ること
- ページ送り後、エンジン1回分程度で補正版が出ること（`O`を何度か押した後も同様）
- じっくり読む間に前方先読みが6まで下がり、速く送ると12以上に戻ること

## Windowsで確認すること

Windows上で`scripts/build_windows_app.py`と`scripts/package_windows_portable.py`で
作ったportable版を使います。クロスビルドはしません。

1. **カーソル自動非表示**: image hostに`Qt.BlankCursor`を設定しています。全画面（`F`）で
   消え、移動／キーで戻ること。読書情報オーバーレイ、次巻バナー、設定パネル上では消えないこと。
   `Alt+Tab`で離れて戻ったときに表示されること。
2. **選択修飾キー**: 本棚のCtrl+クリックとShift+クリック。ヘルプ文言は既に
   「Command/Ctrl」です。コード変更は不要なはずです。
3. **右クリックメニュー**: listの`customContextMenuRequested`。ポインタ位置に出ること、
   未選択の表紙を右クリックするとその表紙だけ選択されること。
4. **削除**: 2冊同時に削除し、ダイアログが1回であること、ライブラリ配下の管理フォルダが
   消えて元アーカイブが残ること。管理フォルダをExplorerで開いたまま削除した場合は
   その本だけ失敗として通知され、他は削除されること。
5. **補正キャッシュの削除**: 補正付きで読んだ本を削除後、`%LOCALAPPDATA%`／app-support配下の
   `upscale/interactive/<key>/`にその本のページフォルダが残っていないこと。
6. **先読み**: 本を開き約1秒間隔でページを送り、10秒止まってから再度送る。設定パネルの
   状態欄で先読み枚数が6へ下がり、再び増えること。
7. 共通suiteとWindows固有テストを実行: `uv run pytest -q`。

キャプチャ（`platform/capture_windows.py`）、`Alt+C`／`Alt+U`、タスクバーのcontroller挙動は
影響を受けません。

## Linuxで確認すること

Ubuntu 24.04以降で`scripts/build_linux_app.py`を使います。

1. **WaylandとX11でのカーソル自動非表示**: `Qt.BlankCursor`はcompositorが空カーソルを
   尊重する前提です。GNOME WaylandとX11を別々に確認してください。compositorがカーソルを
   描き続ける場合は`viewer.py`にOS分岐を足さず、この文書に記録してください。Linux限定の
   回避策は`platform/linux.py`に置きます。
2. **全画面解除でカーソルが戻ること**: `F`、`Esc`、オーバーレイの本棚へボタン、フォーカス喪失。
3. **選択修飾キー**: Ctrl+クリックとShift+クリック。
4. **右クリックメニューの位置**（Waylandのpopup配置はcompositor任せですが、ポインタ位置に
   出ること）。
5. **削除とキャッシュ整理**: Windowsと同様に`~/.local/share`／app-support配下の
   `upscale/interactive/<key>/`を確認。
6. **先読み**: Windowsと同様。
7. Linuxキャプチャテストを含めて`uv run pytest -q`。

キャプチャ（`platform/capture_linux.py`）とGNOME portalの流れは影響を受けません。

## 触った共通ファイルと競合回避

| ファイル | 変更 | 競合時の注意 |
|---|---|---|
| `src/mangacrisp_app/viewer.py` | カーソルタイマーとイベント追跡、オーバーレイボタン、`return_to_bookshelf`、補正キュー、先読み定数と判定関数、`remove_enhancement_cache_for_sources` | `eventFilter`、`toggle_fullscreen`、`closeEvent`、`request_prefetch`、`start_prefetch`、`_process_pages_worker`、`on_upscale_done`に触る前に`main`へrebaseしてください。ワーカーの引数は`(settings, generation, parameter_key, is_prefetch)`に変わりました。 |
| `src/mangacrisp_app/bookshelf.py` | 選択モード、コンテキストメニュー、`delete_books`、`selected_book_ids`、`remove_enhancement_cache`、クラス上部のヘルパー関数 | `delete_selected_book`は`delete_books`へ委譲します。新しい削除経路もここを通してください。 |
| `src/mangacrisp_app/i18n.py` | オーバーレイボタン、削除メッセージ、本棚ヘルプの英語文言 | 文言は末尾に追加し、辞書の並び替えはしないでください。 |
| `test/test_viewer_navigation.py` | `ViewerWindowTestCase`基底クラスとテストクラスに分割 | 読書画面のテストは`ViewerWindowTestCase`を継承してください。 |

## 次のpreviewのリリース文書

Windows／Linux previewを次に`main`から再ビルドしたら、リリース文書に日英で次を載せてください。

- 全画面のカーソル自動非表示
- 読書情報オーバーレイの本棚へボタン
- 本棚の複数選択、右クリックメニュー、まとめて削除
- 表示中見開きを優先する補正キューと後方6ページ
- じっくり読む時の先読み縮小

READMEでは共通機能として既に記載済みなので、各OSのダウンロード段落に
「PR #44以降の`main`からビルド」の一文を足すだけで済みます。

## 他OSへの確認事項

- 対応するLinux compositorすべてで`Qt.BlankCursor`が効くか。
- WindowsでUACやシステムダイアログがフォーカスを奪った際にカーソルを明示的に戻す必要が
  あるか（`WindowDeactivate`経路で足りるはず）。
- Intel／AMD GPUで`CORRECTION_MISS_LEAD_FACTOR`を変える必要があるか。定数は`viewer.py`にあり、
  `test/test_prefetch_policy.py`で固定しています。
