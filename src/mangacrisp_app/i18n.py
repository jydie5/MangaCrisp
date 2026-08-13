from __future__ import annotations

import json
import locale
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from mangacrisp_app.branding import APP_SUPPORT_DIR

DEFAULT_SETTINGS_PATH = APP_SUPPORT_DIR / "settings.json"
VALID_LANGUAGE_PREFERENCES = {"auto", "en", "ja"}

_active_language = "en"


ENGLISH_TRANSLATIONS = {
    "未読": "Unread",
    "読書中": "Reading",
    "完了": "Completed",
    "未解析": "Not scanned",
    "{count}ページ": "{count} pages",
    "保存先: {path}    使用量: {size}": "Library: {path}    Storage: {size}",
    "ファイル/フォルダをドロップ: 本棚へ登録": "Drop files/folders: add to bookshelf",
    "ダブルクリック: 読む": "Double-click: read",
    "読む: 選択中の本を開く": "Read: open the selected book",
    "Delete: 選択中の本を本棚から削除。元ZIP/RARは残す": "Delete: remove the selected book; keep the source archive",
    "本棚から削除: 確認後、MangaCrisp管理フォルダを削除。元ZIP/RARは残す": "Remove: delete MangaCrisp's managed copy after confirmation; keep the source archive",
    "保存先を開く: ファイル管理画面でMangaCrisp Libraryを表示": "Open Library: reveal the managed library in the file manager",
    "?: このヘルプを表示": "?: show this help",
    "H / ?: このヘルプを表示": "H / ?: show this help",
    "画面左右クリック: 次へ/前へ（読書方向に連動）": "Click screen edges: next/previous (follows reading direction)",
    "Shift+画面左右クリック: 1ページ進む/戻す": "Shift+click screen edges: move forward/back one page",
    "画面中央クリック: ページ情報を表示/非表示": "Click screen center: show/hide reading info",
    "右クリック: 前へ": "Right-click: previous",
    "左側クリック/← 次 / 右側クリック/→ 前 / 中央クリック 情報 / V 表示切替 / O 原画比較 / P 設定 / H ヘルプ": "Left click/Left: next / Right click/Right: previous / Center click: info / V: layout / O: compare / P: settings / H: help",
    "右側クリック/→ 次 / 左側クリック/← 前 / 中央クリック 情報 / V 表示切替 / O 原画比較 / P 設定 / H ヘルプ": "Right click/Right: next / Left click/Left: previous / Center click: info / V: layout / O: compare / P: settings / H: help",
    "ショートカットを表示": "Show keyboard shortcuts",
    "その他の操作": "More actions",
    "診断情報をコピー": "Copy Diagnostics",
    "診断情報をクリップボードへコピーしました。": "Diagnostics copied to the clipboard.",
    "キャッシュを削除": "Clear Cache",
    "PDF描画とAI補正のキャッシュを削除しますか？": "Clear the PDF render and AI enhancement caches?",
    "本棚、元ファイル、読書位置、しおりは削除しません。": "Bookshelf items, source files, reading positions, and bookmarks will be kept.",
    "キャッシュを削除しました。": "Cache cleared.",
    "プロジェクト情報": "Project links",
    "ソースコード・不具合報告": "Source code and issue tracker",
    "開発を支援（任意）": "Support development (optional)",
    "ローカルの画像フォルダ、単画像、zip/cbz/rar/cbr/7z/cb7 を本棚へ登録します。": "Add image folders, individual images, ZIP/CBZ, RAR/CBR, and 7z/CB7 archives.",
    "ローカルのPDF、画像フォルダ、単画像、zip/cbz/rar/cbr/7z/cb7 を本棚へ登録します。": "Add local PDFs, image folders, individual images, ZIP/CBZ, RAR/CBR, and 7z/CB7 archives.",
    "言語": "Language",
    "システム設定": "System",
    "英語": "English",
    "日本語": "Japanese",
    "ファイルを追加": "Add Files",
    "画面を連番キャプチャ": "Screen Capture",
    "固定範囲をPNGで連番保存し、CBZまたはZIPにまとめます。": "Save a fixed screen region as numbered PNG files, then create a CBZ or ZIP.",
    "MangaCrisp 連番キャプチャ": "MangaCrisp Screen Capture",
    "連番スクリーンキャプチャ": "Sequential Screen Capture",
    "権利を持つ画面を手動で1枚ずつPNG保存し、CBZまたはZIPにまとめます。": "Manually save screens you have the right to capture as PNG files, then create a CBZ or ZIP.",
    "新しいキャプチャ": "New Capture",
    "セッション名": "Session Name",
    "保存先": "Destination",
    "選択...": "Choose...",
    "再開...": "Resume...",
    "保存済みの未完了キャプチャセッションを開きます。": "Open a saved unfinished capture session.",
    "未完了セッションを選択": "Choose an Unfinished Session",
    "現在のセッションを閉じてから再開してください。": "Close the current session before resuming another one.",
    "セッションを再開できません: {error}": "Could not resume the capture session: {error}",
    "セッションを再開しました: {count}枚": "Resumed session: {count} pages",
    "ディスプレイ": "Display",
    "画面収録権限": "Screen Recording Access",
    "画面収録設定を開く": "Open Screen Recording Settings",
    "許可済み（撮影できます）": "Allowed (ready to capture)",
    "要設定（初回のみ許可が必要です）": "Setup required (first use only)",
    "この環境では利用できません": "Unavailable in this environment",
    "MangaCrispを有効にした後、アプリを完全に終了して再起動してください。": "After enabling MangaCrisp, quit the app completely and open it again.",
    "画面収録設定を開けません: {error}": "Could not open Screen Recording settings: {error}",
    "画面収録の許可が必要です。": "Screen Recording access is required.",
    "システム設定でMangaCrispを有効にし、アプリを完全に終了して再起動してください。": "Enable MangaCrisp in System Settings, then quit the app completely and open it again.",
    "未選択": "Not selected",
    "範囲を選択": "Select Region",
    "画面全体": "Full Display",
    "撮影範囲": "Capture Region",
    "撮影ショートカット": "Capture Shortcuts",
    "撮影通知": "Capture Feedback",
    "アプリアイコンを動かして保存枚数を表示する": "Animate the app icon and show the saved page count",
    "対象アプリを前面のまま、アプリアイコンの動きと数字で保存成功を知らせます。": "Confirms a successful save with app-icon animation and a page count without bringing MangaCrisp to the front.",
    "保存成功時にシャッター音を鳴らす": "Play a shutter sound after a successful save",
    "対象アプリを前面のまま、PNG保存の成功を音で知らせます。": "Confirms a successful PNG save without bringing MangaCrisp to the front.",
    "撮影ごとにPNGへ即時保存します。完了時にページ順とCBZ/ZIPを確定します。": "Each capture is saved to PNG immediately. Completion finalizes page order and the CBZ/ZIP.",
    "撮影を開始": "Start Capture",
    "撮影を停止": "Stop Capture",
    "今すぐ1枚撮影": "Capture One Now",
    "直前取消": "Undo Last",
    "範囲を選択して撮影を開始してください。": "Select a region, then start capture.",
    "選択ページを撮り直す": "Retake Selected",
    "右へ90度回転": "Rotate Right 90°",
    "選択ページを削除": "Delete Selected Page",
    "完了後に本棚へ追加（表紙を作成）": "Add to Bookshelf when complete (create cover)",
    "撮影を完了": "Finish Capture",
    "完了済み": "Completed",
    "このセッションは完了済みです。": "This capture session is already complete.",
    "キャプチャ保存先を選択": "Choose Capture Destination",
    "ディスプレイが見つかりません。": "No display was found.",
    "ドラッグして撮影範囲を選択 / Escでキャンセル": "Drag to select a capture region / Esc to cancel",
    "{width} × {height} px / 位置 {x}, {y}": "{width} × {height} px / position {x}, {y}",
    "撮影範囲を設定しました。": "Capture region selected.",
    "先に撮影範囲を選択してください。": "Select a capture region first.",
    "利用できるグローバルショートカットがありません。": "No global shortcuts are available.",
    "画面収録を許可してください。システム設定 > プライバシーとセキュリティ > 画面収録でMangaCrispを有効にし、アプリを再起動してください。": "Allow Screen Recording in System Settings > Privacy & Security > Screen Recording, enable MangaCrisp, then restart the app.",
    "セッションを作成できません: {error}": "Could not create the capture session: {error}",
    "ショートカットを登録できません: {error}": "Could not register the shortcuts: {error}",
    "待機中: {capture} で撮影 / {undo} で直前取消。MangaCrispを開くと管理画面に戻れます。": "Ready: {capture} captures / {undo} undoes the last page. Open MangaCrisp to return to the controller.",
    "撮影を停止しました。保存済みページは維持されています。": "Capture stopped. Saved pages have been kept.",
    "保存中... 待ち {count}枚": "Saving... {count} queued",
    "保存待ちが3枚です。完了後にもう一度撮影してください。": "Three images are already queued. Capture again after saving completes.",
    "撮影できません: {error}": "Could not capture the screen: {error}",
    "画面収録権限が無効になったため撮影を停止しました。": "Capture stopped because Screen Recording permission is no longer available.",
    "空き容量が少ないため撮影を停止しました。保存先を変更してください。": "Capture stopped because disk space is low. Choose another destination.",
    "PNGを保存できません: {error}": "Could not save the PNG: {error}",
    "{number}枚目を保存しました。警告: {warnings}": "Saved page {number}. Warning: {warnings}",
    "{number}枚目を保存しました。": "Saved page {number}.",
    "保存 {number}枚": "Saved {number}",
    "取り消せるページはありません。": "There is no page to undo.",
    "保存完了後に直前取消を実行してください。": "Wait for saving to finish before undoing.",
    "{number}枚目を取り消しました。次の撮影で同じ番号を使います。": "Undid page {number}. The next capture will reuse that number.",
    "取消 {number}枚目": "Undid {number}",
    "撮り直すページを選択してください。": "Select a page to retake.",
    "次の1回で{number}枚目を置き換えます。": "The next capture will replace page {number}.",
    "回転するページを選択してください。": "Select a page to rotate.",
    "{number}枚目を右へ90度回転しました。": "Rotated page {number} right by 90°.",
    "回転できません: {error}": "Could not rotate the page: {error}",
    "削除するページを選択してください。": "Select a page to delete.",
    "ページを削除": "Delete Page",
    "{number}枚目をセッションから削除しますか？": "Delete page {number} from this session?",
    "ページを削除しました。": "Deleted the page.",
    "要確認": "Check",
    "ページ順を変更しました。": "Page order changed.",
    "ページ順を変更できません: {error}": "Could not change page order: {error}",
    "完了するページがありません。": "There are no pages to complete.",
    "PNG保存が完了してから作成してください。": "Wait for PNG saving to finish before packaging.",
    "ページ順を確定し、CBZ/ZIPを作成中...": "Finalizing page order and creating the CBZ/ZIP...",
    "残りのPNG保存を待って、CBZ/ZIPを作成中...": "Waiting for pending PNG saves, then creating the CBZ/ZIP...",
    "撮影を完了できません: {error}": "Could not finish the capture: {error}",
    "完成しました: {path}": "Completed: {path}",
    "完成して本棚への登録を開始しました: {path}": "Completed and started adding to the bookshelf: {path}",
    "連番キャプチャ": "Screen Capture",
    "保存完了後に閉じます...": "Closing after pending images are saved...",
    "この環境では連番キャプチャを開始できません: {error}": "Screen Capture cannot start in this environment: {error}",
    "撮影画像が極端に小さいため確認してください。": "The captured image is unusually small.",
    "撮影画像が完全に透明です。": "The captured image is fully transparent.",
    "撮影画像が黒一色に見えます。": "The captured image appears to be black.",
    "以前のページと完全に同じ画像です。": "This image is an exact duplicate of an earlier page.",
    "以前のページと似た画像です。": "This image looks similar to an earlier page.",
    "フォルダを追加": "Add Folder",
    "読む": "Read",
    "本棚から削除": "Remove",
    "保存先を開く": "Open Library",
    "{count}冊 / タイトル昇順": "{count} books / title order",
    "本棚保存先": "Bookshelf Location",
    "MangaCrispの本棚保存先を確認してください。": "Confirm the location of your MangaCrisp library.",
    "展開済み漫画は容量が大きくなるため、ファイル管理画面で見つけやすい場所に保存します。\n\n現在の保存先:\n{path}": "Extracted books can use substantial storage. Choose a location that is easy to find in the file manager.\n\nCurrent location:\n{path}",
    "この場所を使う": "Use This Location",
    "変更...": "Change...",
    "後で": "Later",
    "ショートカット": "Keyboard Shortcuts",
    "ドロップしたファイル/フォルダ": "Dropped files/folders",
    "\n- ほか {count} 件": "\n- {count} more",
    "{source}を本棚へ登録します。\n\n対象: {total}件（圧縮ファイル {archives}件 / フォルダ {folders}件 / ファイル {files}件）\n\n{examples}\n\n圧縮ファイルは本棚保存先へ展開し、表紙サムネイルを作成します。\n元のZIP/RAR/7zファイルは削除しません。": "Add {source} to the bookshelf.\n\nItems: {total} (archives: {archives} / folders: {folders} / files: {files})\n\n{examples}\n\nArchives are extracted into the managed library and a cover thumbnail is created.\nThe source ZIP/RAR/7z files are not deleted.",
    "{source}を本棚へ登録します。\n\n対象: {total}件（圧縮ファイル {archives}件 / PDF {pdfs}件 / フォルダ {folders}件 / ファイル {files}件）\n\n{examples}\n\n圧縮ファイルは展開し、PDFは原本をコピーして表紙だけを生成します。\n元のファイルは削除しません。": "Add {source} to the bookshelf.\n\nItems: {total} (archives: {archives} / PDFs: {pdfs} / folders: {folders} / files: {files})\n\n{examples}\n\nArchives are extracted. PDFs are copied and only their covers are generated during import.\nSource files are not deleted.",
    "本棚へ登録": "Add to Bookshelf",
    "展開して本棚へ登録しますか？": "Extract and add these items to the bookshelf?",
    "登録をキャンセルしました。": "Import canceled.",
    "本棚保存先を選択": "Choose Bookshelf Location",
    "保存先を変更できません: {error}": "Could not change the library location: {error}",
    "保存先を変更しました: {path}": "Library location changed: {path}",
    "本棚に追加": "Add to Bookshelf",
    "画像フォルダを本棚に追加": "Add Image Folder to Bookshelf",
    "取り込み待ち {count}件": "{count} items waiting to import",
    "取り込み中 {position}/{total}: {name}": "Importing {position}/{total}: {name}",
    "本棚に追加しました。展開中: {name}": "Added to the bookshelf. Extracting: {name}",
    "内容を確認しました。取り込み中: {name}": "Contents checked. Importing: {name}",
    "展開中 {position}/{total}: {title}": "Extracting {position}/{total}: {title}",
    "登録失敗: {error}": "Import failed: {error}",
    " ほか{count}冊": " and {count} more",
    "登録しました: {label}": "Imported: {label}",
    "保存先を開けません: {error}": "Could not open the library location: {error}",
    "削除する本を選んでください。": "Select a book to remove.",
    "この本を本棚から削除しますか？": "Remove this book from the bookshelf?",
    "MangaCrispが作成した展開済みフォルダ、読書位置、しおりを削除します。\n元のZIP/RAR/7zファイルは削除しません。": "MangaCrisp will delete its extracted copy, reading position, and bookmarks.\nThe source ZIP/RAR/7z file will not be deleted.",
    "削除をキャンセルしました。": "Removal canceled.",
    "本棚から削除しました: {title}": "Removed from bookshelf: {title}",
    "削除できませんでした: {title}": "Could not remove: {title}",
    "読む本を選んでください。": "Select a book to read.",
    "本が見つかりません。": "Book not found.",
    "読み込み失敗: {error}": "Could not open the book: {error}",
    "画像が見つかりません: {source}": "No images found: {source}",
    "次の巻はありません。": "There is no next volume.",
    "言語設定を保存しました。MangaCrispを再起動すると反映されます。": "Language preference saved. Restart MangaCrisp to apply it.",
    "言語設定": "Language",
    "原画": "Original",
    "自然": "Natural",
    "クリーニング": "Cleaning",
    "高画質": "High Quality",
    "カスタム補正": "Custom",
    "補正せず最速で表示します。画質比較の基準です。": "Show the source image without enhancement. Use this as the comparison baseline.",
    "se/noise 0。線とトーンを自然に整えます。": "se/noise 0. Naturally balances lines and screentones.",
    "se/noise 3。古いスキャンの荒れを強く抑えます。": "se/noise 3. Strongly reduces artifacts in older scans.",
    "pro/noise 3。処理時間より線と質感の仕上がりを優先します。": "pro/noise 3. Prioritizes line and texture quality over processing time.",
    "弱め": "Light",
    "標準": "Standard",
    "やや強め": "Moderately strong",
    "強め": "Strong",
    "{keys}: 次へ": "{keys}: next",
    "{keys}: 前へ": "{keys}: previous",
    "{keys}: 1ページ進める": "{keys}: shift one page forward",
    "{keys}: 1ページ戻す": "{keys}: shift one page backward",
    "F: 全画面表示/解除": "F: toggle full screen",
    "P: 右設定パネル表示/非表示": "P: show/hide Reading Settings",
    "V: 見開き/単ページを切り替え": "V: toggle Spread/Single Page",
    "O: 原画/補正版を切り替え": "O: toggle Original/Enhanced",
    "B: しおり追加": "B: add bookmark",
    "画像クリック: ページ情報を表示/非表示": "Click page: show/hide reading information",
    "Esc: 全画面解除 / 本棚へ戻る": "Esc: leave full screen / return to bookshelf",
    "← 次 / → 前 / Shift+← 1p進む / Shift+→ 1p戻す / O 原画比較 / P 設定 / H ヘルプ": "← Next / → Previous / Shift+← +1 page / Shift+→ -1 page / O Compare / P Settings / H Help",
    "→ 次 / ← 前 / Shift+→ 1p進む / Shift+← 1p戻す / O 原画比較 / P 設定 / H ヘルプ": "→ Next / ← Previous / Shift+→ +1 page / Shift+← -1 page / O Compare / P Settings / H Help",
    "次の巻へ": "Next Volume",
    "読了後に本棚順の次の巻を開きます": "Open the next volume in bookshelf order after finishing this book",
    "読書設定": "Reading Settings",
    "設定モード": "Settings Mode",
    "かんたん": "Simple",
    "マニュアル": "Manual",
    "画質: {mode}": "Quality: {mode}",
    "エンジン: Real-CUGAN / {model}": "Engine: Real-CUGAN / {model}",
    "状態: {state}": "Status: {state}",
    "先読み: {state} / 縦{threshold}px以上は原画": "Prefetch: {state} / original at {threshold}px height or above",
    "本棚へ戻る": "Back to Bookshelf",
    "読書画面を閉じて本棚に戻ります。": "Close the reader and return to the bookshelf.",
    "画質モード": "Quality Mode",
    "選択中: {name}": "Selected: {name}",
    "見開き": "Spread",
    "表示レイアウト": "Page Layout",
    "見開き（2画像）": "Spread (2 images)",
    "単ページ（1画像）": "Single Page (1 image)",
    "見開きを含む1枚の画像は、単ページで中央に大きく表示します。": "Use Single Page to center and enlarge an image that already contains a full spread.",
    "見開き調整": "Spread Alignment",
    "左右入替": "Swap Sides",
    "標準見開きに戻す": "Reset Spread Alignment",
    "カスタム設定": "Custom Presets",
    "保存済みの画質設定を選びます": "Choose a saved quality preset",
    "読込": "Load",
    "保存": "Save",
    "削除": "Delete",
    "倍率": "Scale",
    "拡大倍率。漫画確認はまず2倍が扱いやすいです。": "Upscale factor. 2x is a practical starting point for comics.",
    "ノイズ除去": "Noise Reduction",
    "0:自然 / 1:標準 / 3:強め。強いほど線が変わりやすいです。": "0: natural / 1: standard / 3: strong. Higher values can alter linework.",
    "タイル": "Tile Size",
    "処理タイルサイズ。0は自動、重い時だけ調整します。": "Processing tile size. Keep 0 for automatic unless processing is unstable.",
    "補正スキップ縦px": "Skip at Height",
    "この縦px以上は補正せず原画表示。今のMacは2234候補です。": "Pages at or above this height use the original. 2234 is tuned for the target Mac.",
    "モデル": "Model",
    "seは自然な補正向け。proは処理時間より仕上がりを優先します。": "se favors natural correction; pro favors finish quality over speed.",
    "反転推論で精度を上げます。かなり遅くなります。": "Test-time augmentation can improve detail but is much slower.",
    "現在の見開きを補正": "Enhance Current Spread",
    "現在表示中の見開きだけ処理して表示を差し替えます。": "Process only the visible spread and replace it when ready.",
    "原画を表示（OFFで補正版）": "Show Original (OFF = Enhanced)",
    "チェックで原画、解除で補正版へ即時に切り替えて見比べます。": "Enable for the source image; disable for the enhanced image.",
    "待機中": "Idle",
    "原画表示に切り替えました。補正処理は行いません。": "Switched to Original. Enhancement is disabled.",
    "{name}に変更しました。補正はバックグラウンドで行います。": "Switched to {name}. Enhancement will run in the background.",
    "保存済み設定を選択": "Choose a saved preset",
    "読み込むカスタム設定を選んでください。": "Choose a custom preset to load.",
    "カスタム設定を保存": "Save Custom Preset",
    "設定名": "Preset name",
    "保存できません": "Cannot Save",
    "原画・自然・クリーニング・高画質とは別の名前を付けてください。": "Choose a name other than Original, Natural, Cleaning, or High Quality.",
    "現在のモデルとパラメータの組み合わせは保存できません。": "The current model and parameter combination cannot be saved.",
    "設定を上書き": "Overwrite Preset",
    "「{name}」を現在の値で上書きしますか？": "Overwrite “{name}” with the current values?",
    "カスタム設定「{name}」を保存しました。": "Saved custom preset “{name}”.",
    "削除するカスタム設定を選んでください。": "Choose a custom preset to delete.",
    "カスタム設定を削除": "Delete Custom Preset",
    "「{name}」を削除しますか？": "Delete “{name}”?",
    "カスタム設定「{name}」を削除しました。": "Deleted custom preset “{name}”.",
    "この見開きは高解像度のため補正対象外です。原画と補正版は同じ表示です。": "This spread is above the resolution threshold. Original and Enhanced are identical.",
    "原画を表示中です。補正版がまだないページは、チェック解除後に生成します。": "Showing Original. Missing enhanced pages will be generated after you turn this off.",
    "原画を表示中です。チェックを外すと補正版に戻ります。": "Showing Original. Turn this off to return to Enhanced.",
    "この見開きは高解像度のため補正対象外です。原画を表示します。": "This spread is above the resolution threshold and uses the original.",
    "この見開きはまだ補正待ちです。現在ページを優先して生成します。": "This spread is waiting for enhancement. Visible pages are now prioritized.",
    "補正版を表示中です。チェックすると原画へ切り替わります。": "Showing Enhanced. Enable the checkbox to view Original.",
    "{model} では noise {noise} は使えません。{selected} に変更しました。": "noise {noise} is not available for {model}. Changed to {selected}.",
    "設定を変更しました。古い先読み結果は使いません。": "Settings changed. Previous prefetch results will not be reused.",
    "調整": "Adjusted",
    "原画表示中": "Showing Original",
    "ページなし": "No page",
    "片側が高解像度のため見開き原画": "Original spread because one page exceeds the threshold",
    "高解像度のため補正スキップ": "Enhancement skipped above the resolution threshold",
    "補正済み": "Enhanced",
    "原画表示中・補正準備中": "Showing Original / preparing enhancement",
    "現在の見開きを補正中": "Enhancing current spread",
    "先読み補正中 / 未処理 p.{page}": "Prefetching / pending p.{page}",
    "原画表示中・補正待ち p.{page}": "Showing Original / pending p.{page}",
    "オフ / 0ページ": "Off / 0 pages",
    "停止中 / 原画表示継続": "Stopped / continuing with originals",
    "生成中 / 自動{count}ページ先": "Processing / auto {count} pages ahead",
    "自動 / {count}ページ先": "Auto / {count} pages ahead",
    "右綴じ": "Right-bound",
    "左綴じ": "Left-bound",
    "左→右": "Left → Right",
    "右→左": "Right → Left",
    "表紙単独": "Single Cover",
    "通常": "Standard",
    "{direction} / 表示順 {order} / {phase}": "{direction} / display order {order} / {phase}",
    "単ページ / 1画像ずつ / 中央表示": "Single Page / one image / centered",
    "次の巻": "next volume",
    "次の巻へ: {label}": "Next Volume: {label}",
    "最後まで読んだので、続きの巻を開けます。": "You reached the end. Continue with the next volume.",
    "{model} では noise {noise} は使えません。": "noise {noise} is not available for {model}.",
    "models-pro は scale 3 / noise 3 の実験用に制限しています。": "models-pro is currently limited to experimental scale 3 / noise 3.",
    "現在見開きは閾値以上のため原画表示です。": "The current spread exceeds the threshold and uses the original.",
    "現在の見開きを補正中...": "Enhancing the current spread...",
    "先読みページ数が0のため、先読み補正は実行しません。": "Prefetch is disabled because its page count is zero.",
    "AI先読み補正を停止しました。Real-CUGANエンジンが見つかりません。": "AI prefetch stopped because the Real-CUGAN engine was not found.",
    " / {count}ページはスキップ": " / skipped {count} pages",
    "先読み補正中: {count}ページ{suffix}": "Prefetching {count} pages{suffix}",
    "古い先読み結果を破棄しました。": "Discarded stale prefetch results.",
    "AI先読み補正を停止しました。原画表示は継続します。": "AI prefetch stopped. Reading continues with original pages.",
    "補正エラーあり: {seconds:.1f}秒\n{errors}": "Enhancement error after {seconds:.1f}s\n{errors}",
    "先読み補正完了": "Prefetch complete",
    "補正完了": "Enhancement complete",
    "{prefix}: {seconds:.1f}秒": "{prefix}: {seconds:.1f}s",
}


def detect_system_language() -> str:
    override = os.environ.get("MANGACRISP_LANGUAGE", "").strip().lower()
    if override in {"en", "ja"}:
        return override
    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleLanguages"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            lines = [line.strip(' ",').lower() for line in result.stdout.splitlines()]
            first_language = next((line for line in lines if line and line not in {"(", ")"}), "")
            if first_language.startswith("ja"):
                return "ja"
            if first_language:
                return "en"
        except (OSError, subprocess.SubprocessError):
            pass
    language = locale.getlocale()[0] or os.environ.get("LANG", "")
    normalized = str(language).lower().replace("-", "_")
    return "ja" if normalized.startswith(("ja", "japanese")) else "en"


def load_language_preference(settings_path: Path | None = None) -> str:
    path = (settings_path or DEFAULT_SETTINGS_PATH).expanduser()
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return "auto"
    preference = str(settings.get("language", "auto")).lower()
    return preference if preference in VALID_LANGUAGE_PREFERENCES else "auto"


def resolve_language(settings_path: Path | None = None) -> str:
    override = os.environ.get("MANGACRISP_LANGUAGE", "").strip().lower()
    if override in {"en", "ja"}:
        return override
    preference = load_language_preference(settings_path)
    return detect_system_language() if preference == "auto" else preference


def initialize_language(settings_path: Path | None = None) -> str:
    language = resolve_language(settings_path)
    set_language(language)
    return language


def set_language(language: str) -> None:
    global _active_language
    _active_language = "ja" if language == "ja" else "en"


def current_language() -> str:
    return _active_language


def tr(japanese: str, **values: Any) -> str:
    template = japanese if _active_language == "ja" else ENGLISH_TRANSLATIONS.get(japanese, japanese)
    return template.format(**values) if values else template


def save_language_preference(preference: str, settings_path: Path | None = None) -> None:
    normalized = preference if preference in VALID_LANGUAGE_PREFERENCES else "auto"
    path = (settings_path or DEFAULT_SETTINGS_PATH).expanduser()
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        settings = {}
    if not isinstance(settings, dict):
        settings = {}
    settings["language"] = normalized
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)
