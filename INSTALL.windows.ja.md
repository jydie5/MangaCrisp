# MangaCrisp Windows版

[English](INSTALL.windows.md) | [日本語](INSTALL.windows.ja.md)

## 現在の状態

Windows 10/11 x64版は公開Development Previewとして利用できます。
Intel／AMD／別Windowsアカウントの証跡が未完了のため、正式Windows版ではありません。
previewには固定ソースをZigでビルドしたReal-CUGANを同梱し、ソース、ツール、PE import、
モデル、ライセンス、ハッシュを監査します。現在のNVIDIA実機では、Microsoft VC/OpenMPや
MinGWのランタイムDLLを同梱せずに動作します。


AIエンジンがない場合も原画で閲覧できます。
RAR/CBRのフォールバック展開には、SHA-256を固定・検証した7-Zip 26.02 x64を使用し、
ライセンスと取得元情報もビルドへ同梱します。

## Development Previewをダウンロード

[MangaCrisp 0.6.0b0 Windows x64ポータブルpreview](https://github.com/jydie5/MangaCrisp/releases/download/windows-preview-0.6.0b0.1/MangaCrisp-0.6.0b0-windows-x64-portable-preview.zip)

1. ZIPをダウンロードします。
2. `MangaCrisp`フォルダ全体を展開します。
3. `MangaCrisp.exe`をダブルクリックします。
4. 未署名previewに対するWindowsの警告が表示された場合は、ダウンロードURL
   または添付SHA-256を確認します。公式`jydie5/MangaCrisp` Releaseから
   取得したZIPだけで「詳細情報」から「実行」を選びます。

ReleaseにはSHA-256チェックサム、配布監査、ポータブルmanifestも添付します。

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

メンテナーは、別名の公開previewを次のコマンドで作成できます。

```powershell
uv run python scripts/package_windows_portable.py --skip-build --development-preview
```

preview作成は、Intel、AMD、別アカウント以外のリリース阻害要因がある場合に
失敗します。NVIDIA証跡と一致しないエンジンも公開できません。

## 開発プレビューの既知の制限

- 同梱エンジンはIntelおよびAMDのVulkan対応GPUで実機検証が必要です。
  補正を利用できない場合も原画で閲覧できます。
- 未署名で、インストーラー、ファイル関連付け、自動更新はありません。
- 正式Windows版の公開前に、Python未導入のクリーンなWindowsアカウントで
  検証する必要があります。

Development Previewを正式Windows版として再配布しないでください。
