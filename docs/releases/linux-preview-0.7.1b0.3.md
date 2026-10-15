# MangaCrisp for Linux — Preview 0.7.1b0.3

This preview brings the shared reader and bookshelf UX improvements to Linux.
It includes the corrected-display flash fix and managed-copy removal error fix.
The application version remains `0.7.1b0`; the new preview tag identifies this build.

## Features

- Hide the fullscreen image-area cursor after two idle seconds and restore it on input.
- Return to the bookshelf from the reading-information overlay.
- Select multiple books with Ctrl / Shift, use their right-click menu, and remove them with one confirmation.
- Correct the visible spread first and retain six pages behind it.
- Reduce forward prefetch while reading slowly and increase it when reading faster.

## Fixes

- Keep the corrected spread visible when prefetch finishes, avoiding a corrected → original → corrected flash (PR #47).
- Report managed-copy removal errors and keep the failed book registered; successful removal of other books remains effective (PR #49).

Source archives remain untouched. Recursive removal is not atomic: a failed
managed copy may be partly deleted. Retry after resolving the error, or re-import
from the source archive. Disposable-cache cleanup remains best-effort.
The RAR/CBR fixes from preview b0.2 are included.

## Install or update

Ubuntu 24.04 or newer, x86_64. Check `SHA256SUMS.txt`, extract the archive,
and run `MangaCrisp/install.sh`. Updating keeps your library and settings.
See [the Linux installation guide](../../INSTALL.linux.md) for system dependencies
and Wayland capture permissions. Python, uv and CUDA are not required.

## Validation and limitations

Built on Ubuntu 24.04 from main commit `6d9600f8a1a5e320f1fdcfd227b3e95fa04147fb`
by [Linux CI run 38709826090](https://github.com/jydie5/MangaCrisp/actions/runs/38709826090).
The local Linux source suite passed 187 tests, with 8 skips and 5 subtests passed.
The fixed Real-CUGAN engine passed a 2× enhancement check on an NVIDIA GTX 1060 6GB.
Clean Ubuntu 24.04 and 26.04 containers passed installation, packaged startup,
demo reading, bundled RAR support, CPU Vulkan enhancement, and uninstallation.
The user accepted the candidate on Ubuntu 26.04.1 / GNOME 50.1 / Wayland on
2026-10-15. This is general desktop acceptance, not individual checklist sign-offs.
Package and desktop validation results are recorded in the
[Linux validation record](../testing/linux-ux-20261015-validation.ja.md).

AMD / Intel GPU validation and a physical X11 desktop session remain pending.
Xvfb capture/shortcut tests cover the X11 implementation, but do not establish
physical-desktop acceptance. Other distributions, aarch64 and other Wayland
compositors are not validated. This is an unsigned preview, not a stable release.

## Support MangaCrisp

MangaCrisp is free, MIT-licensed software made by an independent developer.
If it helps your reading, **[support continued development on Buy Me a Coffee](https://buymeacoffee.com/jydie5)**.
Support helps fund AMD / Intel test hardware, builds, and development.
Stars, shares, reproducible bug reports and GPU/distribution reports also help.

---

## 日本語

Linuxに共通の読書・本棚UX改善を反映しました。補正版のちらつきと管理コピー削除失敗も
修正しています。製品バージョンは`0.7.1b0`のまま、新しいpreviewタグで区別します。

### 機能5点

- 全画面の画像領域で2秒静止するとカーソルを隠し、操作で戻します。
- 読書情報オーバーレイから本棚へ戻れます。
- 本棚のCtrl / Shift複数選択、右クリックメニュー、1回の確認でのまとめて削除。
- 表示中の見開きを優先する補正と、後方6ページの保持。
- じっくり読む時は前方先読みを減らし、速く送ると増やします。

### 修正2点

- 先読み完了時に「補正版→原画→補正版」とちらつく問題を修正しました（PR #47）。
- 管理コピーの削除失敗を通知し、失敗した本の登録を保持します。他の本の削除成功は反映します（PR #49）。

元アーカイブは削除しません。再帰削除は原子的ではなく、失敗時に管理コピーが途中まで
消える場合があります。原因を解消して再試行するか、元アーカイブから再登録してください。
使い捨てキャッシュの整理はbest-effortです。b0.2のRAR / CBR修正も含みます。

### 導入と検証範囲

Ubuntu 24.04以降のx86_64向けです。`SHA256SUMS.txt`を照合して展開し、
`MangaCrisp/install.sh`を実行します。更新時も本棚と設定は保持します。
依存パッケージとWaylandの権限は[Linux導入手順](../../INSTALL.linux.ja.md)を参照してください。
Python、uv、CUDAは不要です。

Ubuntu 24.04のCIでmain `6d9600f`からビルド。Linuxの共通テストは187成功、8スキップ、
5サブテスト成功です。NVIDIA GTX 1060 6GBで固定エンジンの2倍補正も確認しました。
クリーンなUbuntu 24.04 / 26.04でインストール、配布版起動、デモ表示、同梱RAR対応、
CPU Vulkan補正、アンインストールをすべて確認しました。
Ubuntu 26.04.1 / GNOME 50.1 / Waylandの候補版について、2026-10-15に利用者の全体合格を受領しました。
細目それぞれの個別合格を意味するものではありません。
配布物と実機確認の結果は[検証記録](../testing/linux-ux-20261015-validation.ja.md)に記録しています。
AMD / Intel実GPU、実デスクトップのX11、他ディストリビューション、aarch64、
他のWaylandコンポジタは未確認です。Xvfbでのキャプチャ・キー入力テストは実機合格の代用にはしません。
未署名のpreviewとして扱い、正式版の合格とはしません。

MangaCrispは個人開発の無料・MITライセンスのソフトウェアです。役に立ったら
**[Buy Me a Coffeeで継続開発を支援していただけるとうれしいです](https://buymeacoffee.com/jydie5)**。
支援はAMD / Intel検証機材、ビルド、開発に使います。スター、共有、不具合やGPU動作報告も助かります。
