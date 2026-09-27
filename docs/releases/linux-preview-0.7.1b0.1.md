# MangaCrisp for Linux — Preview 0.7.1b0.1

**MangaCrisp now runs on Linux.** The free, open-source manga and comic viewer
with automatic Real-CUGAN AI upscaling is available for Ubuntu 24.04 and newer
(x86_64), with the same bookshelf, two-page reader, and sequential screen
capture as the macOS and Windows builds.

## Highlights

- **Crisp pages on any Vulkan GPU.** The official Real-CUGAN ncnn Vulkan engine
  is bundled and upscales pages in the background while you read. NVIDIA, AMD,
  and Intel GPUs use their normal Vulkan drivers; no CUDA or Python needed.
- **Reads what you already have.** PDF, CBZ, CBR, ZIP, RAR, 7z, CB7, image
  folders, and single images. RAR support comes from a bundled, pinned 7-Zip.
- **Sequential screen capture on Wayland and X11.** Select a region once, press
  `Alt+C` per page and `Alt+U` to undo, and finish as CBZ or ZIP. On GNOME
  Wayland, MangaCrisp uses the desktop's own screenshot and global-shortcut
  permissions.
- **Installs for one user, no root.** Extract, run `install.sh`, and MangaCrisp
  appears in the application menu. `uninstall.sh` removes the app and keeps
  your library.

## Install

```bash
sudo apt install libxcb-cursor0 libegl1 libgl1 libxkbcommon0 libfontconfig1 libdbus-1-3 libvulkan1 libgomp1 mesa-vulkan-drivers
tar xf MangaCrisp-0.7.1b0-linux-x86_64.tar.gz
MangaCrisp/install.sh
```

Check the download against `SHA256SUMS.txt`. Full instructions, data
locations, and capture permissions are in
[INSTALL.linux.md](https://github.com/jydie5/MangaCrisp/blob/main/INSTALL.linux.md).

## Tested

- Built on Ubuntu 24.04 in GitHub Actions from the tagged source.
- Clean Ubuntu 24.04 and 26.04 containers with only the documented packages:
  install, launch, opening a book, 7-Zip RAR support, Real-CUGAN on Mesa's CPU
  Vulkan driver, and uninstall.
- Ubuntu 26.04, GNOME 50 Wayland, 4K at 125%, NVIDIA GeForce GTX 1060:
  AI upscaling, capture permission, `Alt+C` / `Alt+U`, and returning to the
  controller from the Dash.
- X11 capture and shortcuts are tested automatically on Xvfb.

## Known limitations

- Preview quality: AMD and Intel GPUs and X11 on a physical desktop have not
  been validated by hand yet. Reports are very welcome.
- x86_64 only. Other distributions may work but are not tested.
- On Wayland, a capture takes about one second because it goes through the
  desktop's screenshot portal.
- The build is unsigned; verify the SHA-256 checksum.

## Support MangaCrisp

MangaCrisp is built by one independent developer and stays free and
MIT-licensed. Porting to Linux meant new capture code, new packaging, and
testing on real hardware. If MangaCrisp makes your books look better,
**[please support it on Buy Me a Coffee](https://buymeacoffee.com/jydie5)**.
Support pays for GPU test hardware (AMD and Intel for Linux next), build
services, and development time. It never unlocks features.

Free ways to help: star the repository, share this release with other Linux
readers, and report your GPU and distribution in an issue so the compatibility
list can grow.

---

## 日本語

**MangaCrisp が Linux で動くようになりました。** Real-CUGAN による AI 高画質化を
備えた無料・オープンソースのマンガ／コミックビューアを、Ubuntu 24.04 以降（x86_64）
で使えます。本棚、見開き表示、連番スクリーンキャプチャは macOS／Windows 版と同じです。

### 主な特長

- **Vulkan 対応 GPU で高画質化。** 公式の Real-CUGAN ncnn Vulkan エンジンを同梱し、
  読んでいる間にバックグラウンドで補正します。NVIDIA／AMD／Intel の通常の Vulkan
  ドライバで動き、CUDA や Python は不要です。
- **手持ちの本をそのまま。** PDF、CBZ、CBR、ZIP、RAR、7z、CB7、画像フォルダ、画像。
  RAR は固定・検証済みの 7-Zip を同梱して開きます。
- **Wayland と X11 で連番キャプチャ。** 範囲を一度選び、ページごとに `Alt+C`、
  取消は `Alt+U`。CBZ／ZIP にまとめられます。GNOME の Wayland ではデスクトップ標準の
  スクリーンショットとショートカットの許可を使います。
- **root 不要のユーザー単位インストール。** 展開して `install.sh` を実行するだけで
  アプリ一覧に追加されます。`uninstall.sh` はライブラリを残して削除します。

### インストール

上の英語版のコマンドを実行してください。詳細は
[INSTALL.linux.ja.md](https://github.com/jydie5/MangaCrisp/blob/main/INSTALL.linux.ja.md)
にあります。ダウンロード後は `SHA256SUMS.txt` で確認してください。

### 検証済みの内容

- タグのソースから GitHub Actions の Ubuntu 24.04 でビルド。
- 記載したパッケージだけを入れたクリーンな Ubuntu 24.04／26.04 のコンテナで、
  インストール、起動、本の表示、7-Zip の RAR 対応、CPU Vulkan での Real-CUGAN、
  アンインストールを確認。
- Ubuntu 26.04、GNOME 50 Wayland、4K 125%、GeForce GTX 1060 で、AI 補正、
  キャプチャの許可、`Alt+C`／`Alt+U`、Dash からの復帰を確認。
- X11 のキャプチャとショートカットは Xvfb 上で自動テスト。

### 制限事項

- プレビュー版です。AMD／Intel GPU と実機の X11 はまだ手動で検証していません。
  報告を歓迎します。
- x86_64 のみです。他のディストリビューションは未検証です。
- Wayland ではスクリーンショットポータルを経由するため、1 枚あたり約 1 秒かかります。
- 未署名です。SHA-256 を確認してください。

### MangaCrisp を支援する

MangaCrisp は個人の開発者が作っている、無料・MIT ライセンスのソフトウェアです。
Linux 版のために、キャプチャ処理とパッケージを新しく作り、実機で検証しました。
読書体験が良くなったと感じたら、
**[Buy Me a Coffee で支援していただけるとうれしいです](https://buymeacoffee.com/jydie5)**。
支援は GPU の検証機材（次は Linux 用の AMD／Intel）、ビルドサービス、開発時間に
使います。支援によって機能が制限・解放されることはありません。

お金をかけずに応援する方法もあります。リポジトリへのスター、Linux ユーザーへの
共有、使っている GPU とディストリビューションの報告（Issue）が大きな助けになります。
