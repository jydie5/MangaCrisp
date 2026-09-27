# Linux (Ubuntu) 移植計画

目標: macOS / Windows と同じ機能を Ubuntu で提供し、Linux 用のリリース成果物を
Linux 上でビルドできるようにする。

## 対象

| 項目 | 方針 |
|---|---|
| 一次対象 | Ubuntu 24.04 LTS / 26.04 LTS (x86_64) |
| 表示環境 | Wayland (GNOME 既定) と X11 の両方 |
| GPU | Vulkan 対応 GPU (Mesa の radv/anv、NVIDIA 独自ドライバ) |
| 二次対象 | 他の glibc ディストリ (AppImage で動けば可、公式検証は行わない) |
| 対象外 (初期) | aarch64、Flatpak/Snap の公式配布 |

## 現状調査 (2026-09-27、Linux 上で確認)

- 共通テスト: `uv run --extra dev pytest` → 95 passed, 7 skipped。
- GUI: `QT_QPA_PLATFORM=offscreen` で起動エラーなし。
- `platform/common.py` がフォールバックとして XDG ディレクトリ
  (`$XDG_DATA_HOME`, `$XDG_CACHE_HOME`) と `xdg-open` を実装済み。
- 言語検出は `locale` / `LANG` で動作する (`i18n.py`)。
- 画面キャプチャ: `create_screen_capture_backend()` が `RuntimeError`。
  本棚のキャプチャボタンは `bookshelf.py` で非表示。
- AI エンジン: `engine_utils.py` の探索名に Linux パッケージ名がなく、取得
  スクリプトも macOS / Windows 用のみ。
- アーカイブ: RAR は外部ツール (`7zz`/`7z`/`bsdtar`/`unrar`) 依存。
  Linux では同梱候補 (`bundled_archive_tool_candidates`) が空。
- パッケージング: `packaging/linux/` なし。README / INSTALL / `pyproject.toml`
  の説明文は macOS と Windows のみ。

## ブランチ方針

AGENTS.md に `linux/<topic>` を追加する (本計画の最初の `core/` PR で合意)。

- Linux 固有コード: `src/mangacrisp_app/platform/linux.py`,
  `platform/capture_linux*.py`, `packaging/linux/`, `scripts/*_linux.py`
- 共通 API の変更は必ず先に `core/` PR。
- macOS / Windows のファイルは変更しない。

## フェーズ

### L0: 基盤の合意 (`core/linux-platform`)

- [x] AGENTS.md と `cross-platform-workflow.md` に Linux スコープと
      `linux/` ブランチを追加。
- [x] `platform/__init__.py` に `sys.platform.startswith("linux")` 分岐を追加し、
      `platform/linux.py` を新設 (`common.py` は OS 不明時の最小実装として残す)。
- [x] `pyproject.toml` の description に Linux を追加。
- [x] CI: GitHub Actions の `ubuntu-latest` で ruff と pytest
      (`QT_QPA_PLATFORM=offscreen`) を実行。
- 完了条件: Linux で全テストが通り、CI が main で常に緑。

### L1: リーダー本体の動作 (`linux/reader`)

- [ ] ZIP/CBZ/7z/PDF/EPUB の開封、本棚、ビューア操作を Ubuntu で手動確認
      (`docs/testing/` に Linux 用チェックリストを追加)。
- [ ] RAR: システムの `7zz` (`7zip` パッケージ) / `unrar` / `bsdtar` を検出。
      同梱する場合は 7-Zip の Linux 版を provenance・checksum 付きで取得する
      `scripts/fetch_7zip_linux.py`。
- [ ] `open_directory`: `xdg-open` がない場合と、Flatpak ポータル環境の扱い。
- [ ] 高 DPI (Wayland fractional scaling) と全画面・カーソル自動非表示の確認。
- [ ] Wayland で `QT_QPA_PLATFORM` 未指定時に xcb へ落ちないことの確認
      (`qt6-wayland` 相当のプラグインが PySide6 wheel に含まれるか)。
- 完了条件: キャプチャと AI 補正を除く全機能が Ubuntu で動く。

### L2: AI 補正エンジン (`linux/realcugan`)

- [x] `scripts/fetch_realcugan_linux.py`: 公式
      `realcugan-ncnn-vulkan-20220728-ubuntu.zip` を固定 SHA-256 で取得し、
      ライセンス一式を配置。
- [x] `engine_utils.py` の探索名に `-ubuntu` パッケージを追加 (`core/` で)。
- [x] 取得バイナリの glibc / libvulkan 依存を確認 (glibc 2.15 以上。再ビルドは不要)。古い場合は
      `scripts/build_realcugan_linux.py` でソースから再ビルド
      (Windows の `build_realcugan_windows.py` と同じ方針)。
- [ ] `libvulkan1` と Mesa ドライバが必要なことを INSTALL に記載。Vulkan が
      使えない場合は診断画面にわかりやすいエラーを表示。
- [ ] `docs/hardware-compatibility.md` に AMD / Intel / NVIDIA の検証結果を追記。
- 完了条件: Ubuntu 実機 GPU で補正が動き、`diagnostics` にエンジン情報が出る。

### L3: 連番スクリーンキャプチャ (`linux/capture`)

最も難しいフェーズ。`ScreenCaptureBackend` プロトコルを満たす実装を 2 系統用意する。

| 機能 | X11 | Wayland |
|---|---|---|
| 画面取得 | XGetImage / XShm (`python-xlib` または Qt `QScreen.grabWindow`) | xdg-desktop-portal Screenshot / ScreenCast (D-Bus) |
| 権限 | 不要 | ポータルのダイアログで許可 (`request_permission` に対応) |
| グローバルホットキー | `XGrabKey` | xdg-desktop-portal GlobalShortcuts (GNOME 48+ / KDE)。未対応環境ではコントローラ上のボタン操作にフォールバック |
| 領域選択 | 既存 `region_selector.py` | 同左 (レイヤーシェルが使えないため、全画面の透明ウィンドウで代替) |

- [x] `platform/capture_linux.py` がセッション種別 (`XDG_SESSION_TYPE`) を見て
      X11 / Wayland の実装を選ぶ。
- [x] 連続キャプチャで毎回ダイアログが出ないようにする。Screenshot ポータルは
      初回に一度許可すれば、以降は非対話で撮影できる (GNOME 50 で 1 枚約 1.1 秒)。
      速度が問題になったら ScreenCast (PipeWire) を再利用する方式に切り替える。
- [x] Host アプリとして `org.freedesktop.host.portal.Registry` にアプリ ID
      `com.jydie5.mangacrisp` を登録し、権限をアプリ単位で保存する
      (`com.jydie5.mangacrisp.desktop` のインストールが必要。L4 で対応)。
- [x] GNOME はフォーカス中のアプリにしか許可ダイアログを出さないため、
      「撮影を開始」を押した時点で許可を求める。
- [ ] 必要なら `bookshelf.py` のボタン表示条件と `capture_window.py` の権限ボタン
      条件を、OS 名ではなくバックエンドの能力で判定するよう変更 (`core/` で)。
- [x] `test/test_capture_linux.py`: D-Bus と X をモックしたユニットテスト。
- [ ] `docs/testing/capture-human-check.linux.ja.md`。
- 完了条件: Ubuntu の GNOME (Wayland) と X11 セッションの両方で、
  capture-human-check の全項目が通る。

### L4: パッケージングと配布 (`linux/packaging`)

- [x] 一次配布は **tar.gz (PyInstaller onedir) + `install.sh`**。
      AppImage のランタイムは libfuse (LGPL-2.1) を静的リンクしているため見送った
      (`packaging/linux/README.md`)。`scripts/build_linux_app.py`、`packaging/linux/`。
- [x] `.desktop` ファイル (`com.jydie5.mangacrisp`)、アイコン (hicolor 256/512)、
      MIME 関連付け (CBZ/CBR/CB7/PDF)。`install.sh` / `uninstall.sh` はユーザー単位。
- [x] 同梱バイナリ (realcugan、7-Zip 26.02 `7zz`) の出所・checksum・ライセンスを
      `THIRD_PARTY_NOTICES.md` と `docs/development/linux-dependency-provenance.md` に記載。
- [x] Linux CI (ubuntu-24.04) でパッケージをビルドし、スモークテストして artifact に保存。
- [ ] まっさらな Ubuntu 24.04 (VM / コンテナ) での起動検証と記録。
- [ ] 検討 (後回し): `.deb`、Flatpak、AppImage。
- 完了条件: クリーンな Ubuntu 24.04 で tar.gz を展開して `install.sh` を実行するだけで、
  全機能が動く。

### L5: ドキュメントとリリース (`docs/linux-install` → リリース)

- [ ] `INSTALL.linux.md` / `INSTALL.linux.ja.md`
      (apt で入れる依存: `libvulkan1`, `mesa-vulkan-drivers`, `7zip`, `libfuse2t64`)。
- [ ] README (英・日) の対応 OS と画像、`docs/development/linux-handover.md`。
- [ ] `ROADMAP.md` に Linux の項目を追加。`check_release_ready.py` が Linux 成果物
      を扱えるようにする。
- [ ] 最初は `linux-preview-<version>` として公開し、その後正式リリースに含める。

## リスク

| リスク | 対策 |
|---|---|
| Wayland でグローバルホットキーが使えない環境がある | GlobalShortcuts ポータルが使えない場合はボタン操作にフォールバックし、ドキュメントに明記 |
| ポータルが毎回許可を求める | ScreenCast セッションの再利用と `restore_token` |
| realcugan 公式バイナリが古い glibc 前提 / 新しい Ubuntu で動かない | ソースからビルドするスクリプトを用意し、ハッシュを固定 |
| AppImage の FUSE 依存 (Ubuntu 24.04 は `libfuse2t64`) | INSTALL に記載し、`--appimage-extract-and-run` の手順も案内 |
| 3 OS 分の検証負荷 | Linux は CI で自動テスト、手動チェックはリリース前のみ |

## 作業順序と PR 単位

1. `core/linux-platform` (L0)
2. `linux/reader` (L1) と `linux/realcugan` (L2) は並行して進められる
3. `core/capture-capabilities` → `linux/capture` (L3)
4. `linux/packaging` (L4)
5. `docs/linux-install` (L5) → Linux プレビュー版のリリース
