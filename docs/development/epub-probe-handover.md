# EPUB Stage A probe handover（PR #72 ready・native CI中）

状態: PR #72でStage Aのメタデータ検査を検証中。EPUBを読書できる機能や配布版の対応表ではない。
この文書はmain統合済みの対応宣言ではなく、PRのsource・target tests・native CI境界を記録する。

## Stage Aで確定したAPI

[`epub_probe.py`](https://github.com/jydie5/MangaCrisp/blob/02c37d7/src/mangacrisp_app/epub_probe.py)の
`inspect_epub(path) -> EpubMetadata`は、EPUBを展開・抽出・描画せずに検査する。
返却値は`dataclass(frozen=True)`の不変値で、次の情報を含む。

- title、creators、language、EPUB version、OPF package path
- `manifest`: id、EPUB内の正規化済みresource path、MIME type、properties
- `spine`: OPF順のidref、EPUB内の正規化済みresource path、MIME type、`linear`、spread位置、effective layout
- `page_spine`: `linear=yes`の読書候補、`auxiliary_spine`: `linear=no`の補助項目
- package単位の`global_layout`と、spine上書きを反映した`effective_layout`
- `direction`（`rtl` / `ltr` / `unknown`）とcover path
- warningsと、構造上の`content_profile`

`content_profile`の`direct-image-candidate`は、linear spineが直接画像の候補に見えるという
構造上のヒントであり、実際に読書できることや、色・透明度を完全に保持できることを保証しない。
画像以外を含む場合は`unverified`となる。Stage Aではこの値をimportやviewerの選択に使わない。

## 読み取るレイアウトと順序

- package metadataの`rendition:layout=pre-paginated`をglobal fixedとして扱い、既定はreflowable。
- spine itemの`rendition:layout-pre-paginated` / `rendition:layout-reflowable`を個別上書きとして記録する。
- 混在時は`effective_layout=mixed`とwarningを返す。mixedを固定レイアウトとして読ませない。
- `page-progression-direction`は`rtl`または`ltr`だけを採用し、それ以外はunknownにする。
- `page-spread-left/right/center`と`rendition:page-spread-*`の両方を同じaliasとして扱う。
- 複数のspread指定が衝突した項目は`unspecified`とwarningにする。
- `cover-image` propertyを優先し、EPUB 2の`meta name=cover`も読み取る。競合はwarningにする。
- `linear=no`の項目はmetadataとして保持するが、page spineには含めない。
- ZIP内のファイル名順ではなく、常にOPF spine順を保持する。

## 安全検査とエラー契約

EPUBは信頼できないZIPとして扱う。メンバー数、単体・合計展開量、圧縮率、XMLサイズに
bounded checkを適用し、重複名、unsafe path、symlink、暗号化ZIP、未対応圧縮方式を区別する。
XMLはExpatでDOCTYPE、内部/外部entity、外部参照を拒否してからElementTreeへ渡す。

URIは外部scheme/netlocを取得せず、percent decode後にNFCへ正規化する。絶対パス、drive prefix、
NUL、制御文字、親ディレクトリ逸脱、package外resourceを拒否する。raw URIのquery/fragment（`?`または`#`）
は拒否するが、ファイル名の`%23`はdecode後のEPUB内pathとして許可する。NFDのmanifest hrefは
安全なNFC pathへ揃えるが、これはファイルを取り込む処理ではない。

`EpubProbeError.reason`は公開上この4分類だけを使う。

| reason | 意味 |
| --- | --- |
| `corrupt` | ZIP/EPUB構造、mimetype、XML、manifest/spine、URIが壊れている |
| `protected` | ZIP暗号化または`META-INF/encryption.xml`を検出した |
| `archive-abuse` | 展開量、圧縮率、重複名、symlink、path traversal等が制限を超えた |
| `unsupported` | 未対応圧縮方式や外部URIなど、構造は読めるが対象外 |

`rights.xml`があるだけではDRMと断定しない。Stage Aのprotected判定は上記の暗号化状態に
限る。DRM対応を追加する場合は、別の要件・ライセンス・受入判断を先に置く。

## 現在できないこと

`inspect_epub`はUI、importer、book factory、cover生成、managed copy、page sourceへ未接続である。
`.epub`を本棚へ登録する導線も、EPUBページをviewerへ渡す導線もまだない。
したがって、このStage Aを根拠に「MangaCrispでEPUBが読める」と案内してはいけない。
`content_profile`も対応形式の宣言ではない。

出版物全体の契約、キャッシュ、保存、削除、固定レイアウト要件は
[日本語のpublication sources](../product/publication-sources.ja.md)と
[English publication sources](../product/publication-sources.md)を正本とする。

## Stage B以降の段階導入

1. **direct-image lazy source**: probeのlinear spineを基に、要求ページだけを既存の
   `Sequence[Path]`契約へmaterializeする。全ページ展開、viewer内のEPUB分岐、外部取得はしない。
2. **cover/importer/factory**: 安全検査とmetadata後にcoverを作り、元EPUBを管理コピーへ保存する。
   `.epub`のpicker、D&D、削除、読書位置、しおりを既存形式と同じ契約へ接続する。
3. **XHTML/SVG**: direct imageの受入後に、script・remote resource不要の画像一枚XHTML、
   透過を含む安全なSVGを個別fixtureで追加する。複雑なCSS、reflow、media overlayは後段で判定する。

各段階で、spine順、RTL/LTR、cover単独、明示spread、linear auxiliary、warningと4分類errorを
壊さない。page sourceはlazyでclose可能にし、既存のdecode・補正・先読み・表示cacheへ渡す。

## 検証記録と参考仕様

Stage Aのtarget testsはEPUB probe 21ケースを通過し、対象ファイルは
[`test_epub_probe.py`](https://github.com/jydie5/MangaCrisp/blob/02c37d7/test/test_epub_probe.py)と
[`test_epub_probe_adversarial.py`](https://github.com/jydie5/MangaCrisp/blob/02c37d7/test/test_epub_probe_adversarial.py)である。
対象Ruffもpass。PR #72の記録では共有suiteが329 passed / 9 skipped / 12 subtests、
EPUB probeが21 passed。native CIは提出済みで検証中であり、UI/importer、配布EPUB smokeはStage Aに含まれない。

規格の根拠は[W3C EPUB 3.3](https://www.w3.org/TR/epub-33/)と
[W3C EPUB Reading Systems 3.3](https://www.w3.org/TR/epub-rs-33/)を参照する。
元の調査spikeや一時ファイルは再現補助であり、正本はprobe、target tests、publication sources、
およびPRの検証記録とする。個人ライブラリ、個人パス、認証情報、権利不明の作品は記録しない。
