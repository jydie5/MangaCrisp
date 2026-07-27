# MangaCrisp Windows版

[English](INSTALL.windows.md) | [日本語](INSTALL.windows.ja.md)

## 現在の状態

Windows 10/11 x64版は開発プレビューです。ソース版とPyInstaller
one-folderの基礎ビルドはWindowsで動作しますが、公開用ポータブル版はまだ完成していません。
baselineには固定ソースをZigでビルドしたReal-CUGANを同梱し、ソース、ツール、PE import、
モデル、ライセンス、ハッシュを監査します。現在のNVIDIA実機では、Microsoft VC/OpenMPや
MinGWのランタイムDLLを同梱せずに動作します。


AIエンジンがない場合も原画で閲覧できます。
RAR/CBRのフォールバック展開には、SHA-256を固定・検証した7-Zip 26.02 x64を使用し、
ライセンスと取得元情報もビルドへ同梱します。


## ソースから起動
Gitと[uv](https://docs.astral.sh/uv/)をインストールし、次を実行します。

```powershell
git clone https://github.com/jydie5/MangaCrisp.git
Set-Location MangaCrisp
git switch -c windows/bootstrap
uv sync --extra dev --extra app
uv run pytest
uv run mangacrisp
```

開発やスクリーンショットには、`demo/`内の再配布可能なアーカイブだけを使用してください。

## Windowsの保存先

- 設定とデータベース: `%APPDATA%\MangaCrisp`
- AI・表示キャッシュ: `%LOCALAPPDATA%\MangaCrisp`
- 管理用の展開済み漫画: 既定では`%USERPROFILE%\MangaCrisp Library`

本棚から削除すると、MangaCrispが管理するコピーと読書状態を削除します。
元のZIP、RAR、7zアーカイブは削除しません。

## one-folder基礎ビルド

```powershell
uv sync --extra dev --extra app
uv run python scripts/fetch_vulkan_sdk_windows.py --accept-licenses
uv run python scripts/build_realcugan_windows.py --clean
uv run python scripts/build_windows_app.py
uv run python scripts/audit_windows_distribution.py --require-engine
uv run python scripts/package_windows_portable.py --skip-build --development-baseline
```

アプリは`dist\MangaCrisp\MangaCrisp.exe`へ作成されます。
`MangaCrisp`フォルダ全体を同じ場所に置いてください。EXEだけをコピーしても動作しません。
baseline ZIPはローカル検証専用で、正式リリースとして公開しないでください。

## 開発プレビューの既知の制限

- 同梱エンジンはIntelおよびAMDのVulkan対応GPUで実機検証が必要です。
  補正を利用できない場合も原画で閲覧できます。
- 未署名で、インストーラー、ファイル関連付け、自動更新はありません。
- 公開前に、Python未導入のクリーンなWindowsアカウントで検証する必要があります。

開発ビルドをMangaCrispの正式リリースとして再配布しないでください。
