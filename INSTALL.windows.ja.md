# MangaCrisp Windows版

[English](INSTALL.windows.md) | [日本語](INSTALL.windows.ja.md)

## 現在の状態

Windows 10/11 x64版は開発プレビューです。ソース版とPyInstaller
one-folderの基礎ビルドはWindowsで動作しますが、公開用ポータブル版はまだ完成していません。
特に、Windows版Real-CUGANの固定パッケージ、チェックサム、完全なライセンス一式の
リリース検証が残っています。

AIエンジンがない場合も原画で閲覧できます。

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
uv run python scripts/build_windows_app.py
uv run python scripts/audit_windows_distribution.py
uv run python scripts/package_windows_portable.py --skip-build --development-baseline
```

アプリは`dist\MangaCrisp\MangaCrisp.exe`へ作成されます。
`MangaCrisp`フォルダ全体を同じ場所に置いてください。EXEだけをコピーしても動作しません。
baseline ZIPはローカル検証専用で、正式リリースとして公開しないでください。

## 開発プレビューの既知の制限

- 公式Windowsアーカイブと全ライセンスを固定・検証するまでReal-CUGANは同梱しません。
- RAR/CBRは、再配布可能な展開バックエンドの選定とライセンス監査が残っています。
- 未署名で、インストーラー、ファイル関連付け、自動更新はありません。
- 公開前に、Python未導入のクリーンなWindowsアカウントで検証する必要があります。

開発ビルドをMangaCrispの正式リリースとして再配布しないでください。
