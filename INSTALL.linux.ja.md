# MangaCrisp Linux版

[English](INSTALL.linux.md) | [日本語](INSTALL.linux.ja.md)

## 対象

- Ubuntu 24.04 LTS 以降（x86_64）。GNOME の Wayland と X11 の両方に対応します。
- AI 高画質化には Vulkan 対応 GPU とドライバが必要です（Mesa の radv/anv、または NVIDIA ドライバ）。
  GPU がなくても原画で閲覧できます。

## 必要なパッケージ

```bash
sudo apt install libxcb-cursor0 libegl1 libgl1 libxkbcommon0 libfontconfig1 libdbus-1-3 libvulkan1 libgomp1 mesa-vulkan-drivers
```

NVIDIA ドライバを使っている場合、`mesa-vulkan-drivers` は不要です。
`vulkaninfo --summary`（`vulkan-tools` パッケージ）で GPU が表示されれば AI 補正を使えます。

## インストール

1. `MangaCrisp-<version>-linux-x86_64.tar.gz` をダウンロードし、添付の SHA-256 を確認します。
2. 展開して、インストールスクリプトを実行します。

```bash
tar xf MangaCrisp-*-linux-x86_64.tar.gz
MangaCrisp/install.sh
```

`~/.local/opt/MangaCrisp` にコピーされ、アプリ一覧に MangaCrisp が追加されます。
コマンドラインからは `mangacrisp` で起動できます（`~/.local/bin` が `PATH` に必要です）。
展開したフォルダの `MangaCrisp` を直接実行することもできますが、Wayland で画面キャプチャを
使うにはインストールが必要です（許可をアプリ単位で保存するため）。

削除するには `~/.local/opt/MangaCrisp/uninstall.sh` を実行します。ライブラリと設定は残ります。

## 保存先

| 用途 | 場所 |
|---|---|
| 設定・ライブラリ情報 | `$XDG_DATA_HOME/MangaCrisp`（既定は `~/.local/share/MangaCrisp`） |
| AI キャッシュ | `$XDG_CACHE_HOME/MangaCrisp`（既定は `~/.cache/MangaCrisp`） |
| 既定のライブラリ | `~/MangaCrisp Library` |

## 連番スクリーンキャプチャ

- **Wayland**: 初めて「撮影を開始」を押すと、デスクトップのスクリーンショット許可と、
  ショートカット登録（`Alt+C` / `Alt+U`）の確認ダイアログが出ます。どちらも許可してください。
  拒否した場合は、設定の「アプリ」で MangaCrisp の権限を変更できます。
- **X11**: 許可は不要です。他のアプリがキーを使っている場合は別のプリセットを選んでください。
- 撮影中、管理画面は最小化されて Dash / Alt+Tab に残ります。そこから戻って撮影停止や
  アーカイブ作成を行います。
- 権利を持つ画面、または保存を許可された画面だけに使ってください。

## ソースから起動

```bash
git clone https://github.com/jydie5/MangaCrisp.git
cd MangaCrisp
uv sync --extra dev
uv run pytest
uv run python scripts/fetch_realcugan_linux.py
uv run mangacrisp
```

リリース用のビルドは Ubuntu 24.04 上で行います。

```bash
uv sync --extra dev --extra app
uv run python scripts/build_linux_app.py
```
