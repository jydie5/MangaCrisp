# 次期機能引き継ぎ（macOS beta 0.7.1b0.4後）

この文書は、現在の `main` をWindows/Linux担当が検証・継続実装するための作業メモです。
配布済みのstableやpreviewの操作保証を更新する文書ではありません。各OSの配布物は対象OSで
ビルドし、再配布可能な合成データまたは `demo/` の素材だけで確認してください。

## 現在の反映状況

| 状態 | PR | 内容 |
| --- | --- | --- |
| main統合済み | #59 | Linux開発履歴のprivacy整理 |
| main統合済み | #60 | 計画と導入リンク |
| main統合済み | #61 | PDF cache rootの注入経路（F02） |
| main統合済み | #62 | 補正ライフサイクル回帰（F09） |
| main統合済み | #63 | 本棚検索・ソート・最近読んだ本（F03） |
| main統合済み | #64 | ページ番号ジャンプ（F04） |
| main統合済み・3OS native pass | #65 | 実装済みのしおり管理（F05） |
| main統合済み・3OS native pass | #66 | 本ごとの読書状態復元（F06） |
| main統合済み | #68 | ビューポート境界 |
| main統合済み | #70 | ズーム・パン・幅/全体合わせ・実寸（F07） |
| main統合済み | #74 | 処理済みページ探索の遅延化、ZIP物理ページごとの展開先分離 |
| main統合済み・3OS native pass | #71 | 可視ページ一覧・遅延サムネイル（F08） |
| 今回の配布対象外 | #72 | F13 Stage A EPUBメタデータprobe（読書接続なし） |
| 未統合のCI整備 | #67 | macOS同梱エンジン監査CI |
| 未統合のCI整備 | #69 | Linux clean install CI |

Windows/Linuxの既存ダウンロードはこのmacOS betaによって更新されません。各OSの更新を公開する場合は、
対象OSで新しい`main`からbuildし、ここに記した未確認事項を実機で記録してください。

## 利用者から見える現在の操作

### 本棚

- タイトル検索は日本語・英字の大小を区別せず、数字を含むタイトルは自然順で扱う。
- タイトル、最終閲覧、追加順を切り替えられる。「最近読んだ本」を選んだ場合は最終閲覧の
  降順になるため、表示名と並び順を別の意味にしない。
- 検索解除や並べ替え後も、表示中の項目に対応する選択と現在位置を復元する。
- 絞り込みで隠れた項目は削除対象へ持ち越さない。複数選択の削除は現在表示されている
  選択集合だけを対象にする。
- 再読み込み時に作ったスナップショットとアイコンキャッシュを表示更新へ再利用する。
  検索・並べ替えのたびに本一覧、reading state、directory size、表紙statを読み直さない。

### 読書画面

- F04のページ番号ジャンプは物理ページ番号を使い、右綴じ・左綴じ・見開き境界を含めて
  到着した位置を通常のページ移動と同じ補正経路へ渡す。
- F05のしおりは本ごとに一覧・移動・削除する。同じ本の同じページを二重登録せず、削除は
  現在の本に属するIDだけを対象にする。本や原本の削除にはつながらない。
- F06の読書状態は本ごとに保存・復元する。OS別に共有readerの意味を変えず、無効な状態は
  既定値へ戻る経路を確認する。
- 中央操作ペイン、キー表示、Esc、モーダル外クリックの既存UI契約を壊さない。下バーを
  常設の操作表へ戻さない。

## F07の実装仕様

#70と#68はmainへ統合済みです。macOS beta 0.7.1b0.4に含めます。

- `+` / `-`: 拡大・縮小
- Ctrl（Windows/Linux）またはMeta（macOS）+ホイール: 倍率変更
- `0`: 全体に合わせる
- `W`: 幅に合わせる
- `1`: 実寸
- ドラッグ: パン

表示デコードはDPRを考慮した約8.4MP（8×1024²画素）上限と192MiB LRUを実装する。ただし
元画像をQImageへ読み込む全体ピークはこの上限の対象外であり、制限済みとは報告しない。
ズームとパンはDBへ保存しない。補正キャッシュのキーやAI実行と、画面だけの表示変換を混ぜない。

## F08（#71、macOS beta 0.7.1b0.4の対象）

`T`でページoverviewを開き、
visible範囲だけを要求する。画面外のsource PNG生成、archive全体extract、AI補正を起こさず、
thumbnail LRUは16MiB、offscreen iconは解放する。ページ一覧を開いただけで大冊PDFを全ページ描画しない。
overview選択からの物理ページjump、キャンセル、close後のworker停止を対象OSで確認する。
最終統合候補のmacOS/Linux source・package、Windows portable build・配布監査・展開起動CIはすべて通過した。
CI記録: [macOS](https://github.com/jydie5/MangaCrisp/actions/runs/40057157561)、
[Windows](https://github.com/jydie5/MangaCrisp/actions/runs/40057157576)、
[Linux](https://github.com/jydie5/MangaCrisp/actions/runs/40057157588)。
これはWindows/Linuxの実GPU・デスクトップ操作の受入を代替しない。

## 検証手順

共有コードを変更したPRでは、対象テストと共有suiteを実行し、実際の結果をPRへ記録する。
本棚のF03を再測定する場合は、合成10,000冊・表紙なし・ファイルなしの一時ライブラリを
使い、個人ライブラリや個人パスをログへ出さない。既存の測定ではmacOS arm64、Python 3.13、
PySide6 6.11.1、Qt offscreenで、初回表示は1回測定して320ms、検索・解除・ソートは5回の条件で、
1件検索197ms（最大200ms）、
約8,000件検索296ms（最大301ms）、解除353ms（最大359ms）、最終閲覧順197ms（最大202ms）
だった。検索中の本一覧/reading state/directory size追加取得は各0回、アイコンキャッシュは
10,000件で固定だった。これは条件付きの判断材料であり、他OSや個人ライブラリの性能保証ではない。

F07の合成画像測定は、macOS 27.0.1 arm64、Python 3.13.6、Qt 6.11.1、offscreen、
3200×4800 RGB 4枚、`auto_prefetch=False`、0.25/1/2/4/8倍→W→actualと前後往復で行った。
8倍時は6件・191.92MiB（201,242,592 bytes）で、192MiB（201,326,592 bytes）のcache単体target内だった。
復帰時にcacheは増えず再利用した。DPR-aware表示上限は約8.4MP（8×1024²画素）。
別processの`resource.ru_maxrss`は745.6MiB、paint後754.5MiBだったが、元QImage全読込・同時decode・
表示cacheを含むprocess全体peakであり、source単体の値ではない。192MiBはcache単体の保護targetで、
一時超過を許容しprocess全体を制限しない。QImageReader target decode、worker同時数、長時間計測はF24へ残す。

## F13 Stage A（PR #72、今回の配布対象外）

PR #72のStage Aは純Pythonのmetadata/manifest/spine probeだけである。UI、importer、factory、cover、
page sourceは未接続で、EPUBを読める機能として案内しない。`content_profile`は構造上の候補ヒントであり、
対応形式の保証ではない。詳細なAPI、4分類error、URI/XML/ZIP境界、
Stage Bのdirect-image lazy source→cover/importer→XHTML/SVG段階は
[EPUB Stage A引き継ぎ](epub-probe-handover.md)を参照する。

## Windows担当

Windowsでは対象OS上で配布物を作り、クリーンな利用者環境で本棚検索、ページジャンプ、
しおり、読書状態復元、F08ページ一覧を順に確認する。F07を試す場合はDPI変更、見開き、右綴じ/左綴じ、
ドラッグ中の誤ページ送り、Ctrl+ホイールを確認し、Intel/AMD/NVIDIAの実GPU結果を混同しない。
開発ツールの有無、入力フォーカス、H/?ヘルプと中央ペインのキー表示も確認対象にする。
既存のWindows手順は [windows-handover.md](windows-handover.md) と
[cross-platform-workflow.md](cross-platform-workflow.md) に従う。

## Linux担当

Linuxでは新しいmainからpackageをbuildする場合、Ubuntu 24.04/26.04のclean install、tar展開、CPU/Vulkan/RARのsmoke、uninstallを
確認する。CIの成功だけでGLib/gvfs警告、Wayland/X11、portal、倍率、実GPUの受入を
宣言しない。これらは対象OSの実機でログを残して確認する。警告を環境変数で隠さず、再現時の
stdout/stderrと依存状態を証跡にする。既存のLinux移植方針と引き継ぎは
[linux-port-plan.ja.md](linux-port-plan.ja.md) と [linux-handover.md](linux-handover.md) を読む。

## 残課題と境界

- Windows/Linux実機でのoverview選択・キャンセル・可視範囲・倍率・入力操作の確認。
- #72のStage B設計。EPUBの読書接続は後続で、現時点のStage Aを読書対応と宣伝しない。
- #67/#69はCI整備として未統合。macOS CIは署名・公証を、Linux CIは実GPU・実デスクトップを保証しない。
- F12の署名・公証・各GPU/操作ゲート。
- F13 Comic EPUB、続いてF22 OPDS。EPUBのspine順、拒否条件、秘密や取得の境界を先に確定する。
- F14以降の読了フィルター、export/restore、メタデータ、再リンク、Webtoon、キー割当などは
  [開発レビューと次期計画](../product/development-plan-2026-10-23.ja.md) の順序を維持する。

個人ライブラリ、ローカルの絶対パス、認証情報、著作権に不確かな漫画を、ソース・テスト・CI・
公開ログへ含めない。OS固有の処理は既存のplatform境界へ置き、共有readerをOS別挙動へ分岐させない。
