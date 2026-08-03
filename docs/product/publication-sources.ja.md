# PDF・Comic EPUB・OPDS 要件定義／設計

状態: 実装計画の設計基準
実装順: PDF → Comic EPUB → OPDS 1.2
対象: macOS・Windows共通機能

## 目的

MangaCrispを汎用文書ブラウザや電子書籍ストアにせず、正当に入手したDRMフリーの漫画を
より多く読めるようにします。形式を増やしても、次の製品価値を維持します。

- 最初の読めるページを早く表示する
- 右綴じ・左綴じと見開きを正しく扱う
- AI補正が使えない場合も原画で読める
- 全冊一括変換ではなく、現在位置周辺だけを補正する
- 取り込んだ本をオフラインで読める
- macOSとWindowsで同じ読書操作にする

実装順には次の理由があります。

1. PDFで一般的なスキャン文書を読めるようにする
2. Comic EPUBで出版社に依存しない固定レイアウト漫画を扱う
3. OPDSで既存の個人書庫とMangaCrispを接続する

## 対象外

初期実装では次を扱いません。

- Kindle、Kobo、Apple Books、AdobeなどのDRM解除・DRM付き書籍
- リフロー型EPUB、フォント変更、注釈、読み上げ、辞書
- Comic EPUB内のJavaScript実行や無制限な外部リソース取得
- MangaCrisp自身のOPDSサーバー化
- サーバー側AI補正
- OPDSの読書位置同期
- ダウンロード途中の遠隔書籍をストリーミングして読む機能

非対応のファイルは、ページ・文字・重ね合わせ・読書方向を欠落させたまま取り込まず、
理由を明示して停止します。

## 共通の出版物インターフェース

現在のビューアは `Sequence[Path]` を受け取ります。初期実装ではこれを維持し、
遅延生成できる出版物アダプターを追加します。

```text
PublicationProbe
  inspect(source) -> PublicationMetadata

PublicationPageSource (Sequence[Path])
  page_count
  page(index) -> ローカル画像Pathを遅延生成
  page_info(index) -> PageInfo
  close()
```

`PublicationPageSource`は要求されたページだけを画像化します。返されたPathは既存の
画像デコード、Real-CUGAN補正、原画比較、先読み、リボルビングキャッシュへ渡します。
形式固有処理を `viewer.py` に入れません。

必要な実装は次の4種類です。

- `FolderPageSource`
- `ArchivePageSource`
- `PdfPageSource`
- `FixedLayoutEpubPageSource`

本を開くファクトリーは拡張子だけでなく、検査した内容から実装を選択します。
既存の圧縮ファイルも同じ契約を経由させます。

```mermaid
flowchart LR
    A["ファイル・フォルダ・OPDS取得"] --> B["検査と安全確認"]
    B --> C["管理コピーとメタデータ"]
    C --> D["ページソース選択"]
    D --> E["遅延描画キャッシュ"]
    E --> F["既存ビューアと先読み"]
    F --> G["既存AI補正キャッシュ"]
```

### 共通メタデータ

```text
title
authors
series
volume
format
page_count
cover_page_index
reading_direction: rtl | ltr | unknown
layout: paginated | fixed | reflowable
content_fingerprint
capabilities
warnings
```

埋め込みメタデータが有効ならファイル名より優先し、ない場合は従来通りファイル名から
推定します。

### ページ情報

```text
intrinsic_width
intrinsic_height
spread_position: left | right | center | unspecified
source_kind: raster | vector | mixed
enhancement_recommendation: automatic | original_preferred
```

見開き位置が指定されていない場合は現在の「表紙を単ページ」規則を使います。
EPUB内に明示された見開き位置がある場合はそちらを優先します。

## 保存先とキャッシュ

永続保存と、削除可能なキャッシュを分離します。

```text
MangaCrisp Library/
  <管理対象の本>/
    original/
      <元のPDF、EPUB、圧縮ファイル>
    pages/
      <従来通り全展開する圧縮ファイルのページだけ>
    cover.*

MangaCrispキャッシュ/
  rendered/
    <内容指紋>/<レンダラー版>/<描画条件>/<ページ>.png
  upscale/
    <既存の補正キー>/<ページ>.png
```

要件:

- PDF/EPUB取り込み時は元ファイルを管理フォルダへコピーして表紙を作るが、全ページを
  画像化しない
- ユーザーが選択した元ファイルは削除しない
- ページ画像は一時ファイルへ書き、検証後にアトミックに置き換える
- キャッシュキーに内容指紋、レンダラー版、色モード、描画サイズ、ページ番号を含める
- 元ファイルが変更された場合は古い描画・補正キャッシュを再利用しない
- 本棚から削除すると管理コピーと対象キャッシュを消すが、元ファイルは残す
- 描画済みページのディスクキャッシュは全体LRU方式で初期上限2 GiBとする
- AI補正キャッシュは現在位置周辺だけを保持する既存方式を維持する

## ローカル取り込みと本棚UI

- PDF/EPUBを既存の複数ファイル選択とD&D対象へ追加する
- 確認画面は形式ごとの実動作を表示し、圧縮形式は「展開」、PDF/EPUBは
  「管理領域へコピーして索引作成」と説明する
- 混在バッチでは動作別件数を表示し、1件失敗しても他の有効な本を継続する
- 初期実装の取り込みは逐次処理とし、ディスク、CPU、表紙描画を同時に飽和させない
- PDF/EPUBはメタデータ・表紙処理後すぐ本棚へ表示し、全ページ描画やAI補正を待たない
- カードへ小さなPDF・EPUB・ネットワーク取得ラベルを表示してよいが、タイトルや巻数を
  隠さない
- ダブルクリック、「読む」、次巻移動、削除、しおり、読書位置を圧縮形式と共通にする
- 管理コピーが消失している場合はパスと本棚から除去する選択肢を表示し、確認なしに
  遠隔URLから再取得しない

## フェーズ1: PDF

### 対応範囲

- ローカルの `.pdf`
- 暗号化されていないPDF
- ラスター、ベクター、混在ページ
- 途中でページサイズが変わるPDF
- 利用可能な場合は埋め込みタイトル、著者、ページラベル、目次

パスワード付きPDFは破損ファイルと区別して表示します。将来パスワード入力を追加する
場合も、初期段階はセッション内だけに保持し、SQLiteや平文設定へ保存しません。

### 描画方式

第一候補を `pypdfium2` とします。ヘッドレス・クロスプラットフォーム・オンデマンド
描画に向き、PDFiumは制約の少ないライセンスです。ただし採用前に次の技術検証を
行います。

- arm64 macOSとx64 Windowsへの同梱
- RGB・グレースケールの色保持
- ワーカースレッドからの描画
- 破損・パスワード付きPDFのエラー判定
- 配布サイズと第三者ライセンス表記
- 出力寸法の再現性

代替候補は既存PySide6の `QPdfDocument` です。ただしQtオブジェクトのスレッド所有を
確認できない状態でバックグラウンド処理へ混在させません。

最初に現在の見開きだけを描画し、その後は既存先読みスケジューラへ渡します。
全PDFを固定高DPIで変換せず、画面サイズとAI倍率から必要描画サイズを決めます。

### AI補正

- PDF描画結果も既存のカラー保持補正へ渡す
- 十分大きいページは既存の高さ閾値で補正を省略する
- ベクター・混在ページは自動モードでは原画優先とし、綺麗な文字を劣化させない
- スキャンPDFはユーザーが補正プリセットを明示選択できる
- 原画比較は左右ページが揃った状態で同時に切り替える

### PDF受入条件

- 300ページのPDFを全ページ描画せず本棚登録できる
- 登録後に表紙が見える
- 1ページ目と保存済み位置のどちらから開いても、補正を待たず原画が読める
- 縦横混在ページの比率が崩れない
- カラーページがカラーのまま表示される
- 破損、暗号化、0ページを区別して説明できる
- 前後移動で描画・補正キャッシュを再利用する
- 本棚から削除してもユーザーの元PDFが残る

## フェーズ2: Comic EPUB

### 初期対応プロファイル

DRMフリーのEPUB 2/3のうち、視覚ページ列へ欠落なく変換できる固定レイアウトを
対象とします。

- package metadataがfixed/pre-paginatedを指定している、または
- 全spine項目が直接画像、SVGページ、あるいはスクリプト・外部リソース不要の
  全面ローカル画像1枚を持つXHTML
- spine順をページ順として使う
- `page-progression-direction` を右綴じ・左綴じへ反映する
- `page-spread-left/right` と同等のrendition属性を見開き位置へ反映する
- cover metadataから本棚表紙を作る

`META-INF/container.xml`、OPF manifest、metadata、spineを名前空間対応XMLで解析します。
ZIP内ファイル名のソートをページ順に使いません。

### 初期非対応

- リフロー型テキストEPUB
- DRM付きEPUB
- スクリプト・インタラクティブコンテンツ
- 外部フォント・CSS・画像・音声・動画が必須のページ
- XHTML/CSSを完全描画しないと欠落する複雑な組版
- Media Overlayと読み上げ

有効だが非対応のEPUBには「テキストまたはインタラクティブ型のため未対応」と表示し、
「破損」とは表示しません。

### セキュリティ

EPUBを信頼できないZIPとして扱います。

- 絶対パス、親ディレクトリ遡り、ドライブ名、NUL、不正な正規化パスを拒否
- XML外部エンティティとネットワーク解決を無効化
- メンバー数、単体展開サイズ、合計展開サイズ、圧縮率に上限を設定
- JavaScriptを実行しない
- 描画時に外部リソースを取得しない
- 可能な範囲で宣言MIME型と実ファイルシグネチャを照合する

### Comic EPUB受入条件

- RTL/LTRサンプルが正しい方向で開く
- 表紙単ページと明示見開き位置が正しい
- 画像1枚XHTML、直接画像spine、対応SVGを表示できる
- 色と透過を保持する
- ZIP内ファイル名が乱れていてもOPF spine順で表示する
- リフロー、スクリプト、外部参照、DRM、破損、zip bombを別々の理由で拒否する
- 現在位置と先読み対象だけを画像化する

## フェーズ3: OPDS 1.2

### ユーザー体験

本棚に「ネットワーク書庫」を追加します。

1. 書庫名とOPDS URLを登録
2. 接続と認証を確認
3. Navigation Feed、ページ分割されたAcquisition Feed、提供される場合は検索を閲覧
4. 表紙、タイトル、著者、形式、ダウンロード状態を表示
5. 「ダウンロードして本棚へ追加」で一時領域へ取得し、検証後に既存取り込みへ渡す
6. 取り込み後はオフラインで読む

初期版はダウンロード優先とし、遠隔ページを読書中に直接ストリーミングしません。
ネットワーク待ちを読書ループから排除し、AI補正、削除、キャッシュをローカル本と
共通化するためです。

### 相互運用対象

OPDS 1.2を先に実装し、次の現行版で検証します。

- Komga
- Kavita
- Calibre Content Server

必要機能:

- Atom Navigation/Acquisition Feed
- 相対URL解決
- `next`、`previous`、`start`、`search`、`self`、acquisition relation
- CBZ、CBR、PDF、EPUB
- cover/thumbnail relation
- HTTP Basic/Digest認証
- リダイレクト、タイムアウト、キャンセル、UIからの再試行
- Unicodeタイトル、著者、URL

OPDS 2.0とKomga/Kavita独自APIは後続です。OPDS 1.2だけでは一般的な読書位置同期を
保証できないため、初期版で同期をうたいません。

### 認証・通信セキュリティ

- 秘密でない書庫設定をSQLiteへ保存
- パスワード等はレビュー済み資格情報アダプターを介しmacOS Keychain／Windows
  Credential Managerへ保存
- URL、ログ、DB、エラー報告へ認証情報を含めない
- 有効なHTTPS証明書を標準とする
- 平文HTTPは主にLAN用途として、書庫ごとの明示警告後のみ許可
- 別originへのリダイレクト時にAuthorizationを転送しない
- 接続、応答、全体ダウンロードにタイムアウトを設定
- Feedサイズ、XML深さ、ダウンロードサイズ、リダイレクト回数を制限
- XML外部エンティティを無効化
- 一時領域へ取得し、Content-Typeとシグネチャを検証して管理領域へ移動
- キャンセル時は不完全ファイルを削除

### OPDSデータモデル

`books.source_uri`へ情報を詰め込まず、DB migrationで追加します。

```text
catalogs
  id
  name
  base_url
  auth_kind
  credential_key
  allow_insecure_http
  created_at
  updated_at

remote_publications
  catalog_id
  remote_id
  title
  authors_json
  cover_url
  acquisition_url
  media_type
  remote_updated_at
  local_book_id
  PRIMARY KEY (catalog_id, remote_id)
```

`credential_key`はKeychain検索用の不透明なキーであり、秘密そのものではありません。
ダウンロード後の読書位置・しおりは通常の `books` 行に紐付けます。書庫設定を削除しても
ダウンロード済みの本は削除しません。

### OPDS受入条件

- Komga、Kavita、Calibreを登録・閲覧できる
- Basic/Digest認証情報がログやDBへ露出しない
- ページ送りと検索で本棚UIが固まらない
- 待機、取得中、検証中、登録済み、失敗、キャンセルを表示できる
- 同じ書籍の再取得は既存ローカル本へ解決する
- ネット切断中もダウンロード済みの本を開ける
- 証明書不正、危険なリダイレクト、巨大Feed、不正XML、非対応形式、中断を区別する
- 書庫設定削除とダウンロード済み本の削除を別操作にする

## 性能目標

| 操作 | 目標 |
|---|---:|
| 一般的PDF/EPUBのメタデータ検査 | 1秒以内 |
| 取り込み後の表紙表示 | 検査完了後2秒以内 |
| キャッシュ済み見開きを開く | 100ms以内 |
| 未キャッシュPDF/EPUB原画見開き | 基準M4 Proで500ms以内 |
| ページ入力への反応 | 原画フォールバック込み50ms以内 |
| OPDS Feed操作 | UIスレッドを停止させない |
| ダウンロードキャンセル | 250ms以内に表示反映 |

300ページ以上、可能なら生成・スパースデータによる2 GiB、前後連打、10分連続読書で
メモリとディスクが無制限に増えないことを確認します。

## 実装順

### 共通基盤

1. 共通メタデータと遅延ページソースを追加
2. フォルダ・既存圧縮形式を見た目を変えずアダプター化
3. 遅延生成、終了処理、キャッシュ識別、見開き情報の共通テストを追加

### PDF

1. レンダラー・ライセンス・配布同梱の技術検証
2. PDF検査、管理取り込み、表紙、遅延描画
3. 補正推奨とキャッシュ無効化を統合
4. macOS/Windows配布物と実機で検証

### Comic EPUB

1. 安全なEPUB container/OPF parser
2. 対応固定レイアウトと診断
3. 悪意ある入力・非対応入力のfixture追加
4. RTL/LTR見開きとカラー補正を検証

### OPDS

1. 書庫DBと資格情報アダプター
2. ローカル固定サーバーによるprotocol/parserテスト
3. 非同期閲覧・検索・ダウンロードUI
4. ダウンロードを既存出版物取り込みへ接続
5. Komga、Kavita、Calibre互換試験

各フェーズは個別の `core/` PR群とし、共通実装をmainへ入れた後で各OSの配布変更を
行います。

### GitHub Issue分割案

1. 出版物メタデータ、対応可否エラー、遅延ページソースAPI
2. フォルダ・圧縮形式を共通ページソースへ移行
3. クロスプラットフォームPDFレンダラーの技術検証と選定
4. PDF検査、管理取り込み、表紙、遅延描画
5. PDF描画と表示・AI補正キャッシュ方針の統合
6. 安全なEPUB container/OPF解析と固定レイアウト判定
7. Comic EPUB遅延ページ生成と見開きメタデータ
8. OPDS書庫・遠隔書籍DB migrationと資格情報保存
9. mock serverテスト付きOPDS 1.2 client
10. ネットワーク書庫の閲覧、検索、取得、キャンセルUI
11. Komga、Kavita、Calibre相互運用試験
12. macOS/Windowsの依存関係監査と配布物更新

## テスト素材

- 生成物、パブリックドメイン、明示的に再配布可能な素材だけをコミット
- 小さなPDF/EPUB fixtureは決定的に生成し、生成方法を記録
- 破損、暗号化、巨大ヘッダー、path traversalは可能な限りテスト内生成
- CIではローカルmock OPDS serverを使用
- 個人書庫URL、認証情報、著作物をリポジトリとログへ含めない

## 決定事項

- PDFは取り込み時に全変換せず、遅延描画する
- Comic EPUBは欠落なく扱える固定レイアウト範囲を意味し、全EPUB対応とはしない
- OPDSは書庫・ダウンロード元であり、MangaCrispはローカル優先を維持する
- OPDS本も既存の本棚、ページ、AI補正、読書位置を利用する
- 大規模なviewer API変更の前に、遅延 `Sequence[Path]` で既存動作を保護する

## 参照仕様

- Qt PDF for Python: https://doc.qt.io/qtforpython-6/PySide6/QtPdf/
- pypdfium2: https://pypdfium2.readthedocs.io/
- EPUB 3.3: https://www.w3.org/TR/epub-33/
- OPDS 1.2: https://specs.opds.io/opds-1.2.html
