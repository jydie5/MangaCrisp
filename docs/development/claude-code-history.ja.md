# Claude Code 会話履歴の要約（Linux 機）

Claude Code から Codex へ移行するときに、この Linux 機での過去の会話をまとめたものです（2026-10-23 作成）。
元の会話ログは `~/.claude/projects/-home-test-MangaCrisp/` にあります。
Linux 版の詳しい状況は [linux-handover.ja.md](linux-handover.ja.md) と [linux-port-plan.ja.md](linux-port-plan.ja.md) を見てください。

## Ubuntu への移植（2026-09-26〜27）

計画を [linux-port-plan.ja.md](linux-port-plan.ja.md) にまとめ、L0〜L5 の順に進めた。PR #29〜#37 は main にマージ済み。

| フェーズ | 内容 |
|---|---|
| L0 基盤 | `platform/linux.py`、Ubuntu の CI、AGENTS.md に `linux/<topic>` ブランチを追加 |
| L1 リーダー | Linux での閲覧（Ubuntu 26.04、125% スケーリングで問題なし） |
| L2 AI 補正 | 公式 Real-CUGAN の Ubuntu 版を SHA-256 で固定して取得。GTX 1060 の Vulkan で動作確認。Vulkan の有無を診断に表示（#37） |
| L3 キャプチャ | Wayland はスクリーンショットと GlobalShortcuts のポータル、X11 は XGetImage と XGrabKey。Wayland は実機で確認、X11 は Xvfb のみ |
| L4 パッケージ | tar.gz とユーザー単位の `install.sh`/`uninstall.sh`、7-Zip（7zz）同梱。Ubuntu 24.04 の CI でビルドし、クリーンな 24.04/26.04 コンテナで検証 |
| L5 公開 | README（英・日）に Linux を追加し、プレビュー版を GitHub で公開 |

## 公開したリリース

- `linux-preview-0.7.1b0.1`（2026-09-27）
- `linux-preview-0.7.1b0.2`（2026-09-27）: RAR の修正（PR #40）を含む
- b0.4 は 2026-10-20 時点でユーザーが公開済み

## 直した不具合

- **RAR が本棚に入らない**: rarfile がページを取り出すときに `PATH` 上の unrar などを探し、同梱の 7zz を使っていなかった。
- **複数巻の RAR で、どの巻にも全巻のページが入る**: 全 OS 共通の不具合。PR #40 で共通コードを修正。
  Windows / macOS のリリースは各 OS で作り直す必要がある（2026-09-27 時点の注意）。

## この PC の状態

- リリース版をインストール済み: `~/.local/opt/MangaCrisp`、ランチャーは `~/.local/share/applications/`、コマンドは `~/.local/bin/mangacrisp`。
- 開発用にはソースから `uv run mangacrisp` でも起動できる。どちらも同じ本棚と設定を使う。
- GNOME の権限ストアに、テスト時の記録（`com.jydie5.mangacrisp` 許可、`com.anthropic.Claude` 拒否）が残っている。
- テスト撮影の画像が `~/Pictures/MangaCrisp Captures/` にある。
- この PC は NVIDIA GPU と Wayland のみ。AMD/Intel GPU と実機の X11 は未検証。

## 2026-10-19〜20: 新しい UI/UX の Linux 実機確認

- mac 側で作った新しい UI 候補（main `d7bbf50`）を Linux で確認した。全テスト 274 成功、ビルドとコンテナ検証も成功。
- ユーザーの実機確認は「確認おわり」の一言で、項目ごとの報告ではなかった。
- 引き継ぎ用の PR #58 は、b0.4 が既に公開済みだったため閉じた。
- 未対応: 公開中の b0.4 を Ubuntu 26.04 で起動すると、同梱の GLib が古いため gvfs モジュールの警告が出る（閲覧・取り込み・キャプチャには影響なし）。

## 既知の課題

- 日本語環境ではキャプチャの保存先が `~/ピクチャ` ではなく `~/Pictures` になる（`capture_window.py` で `Pictures` 固定）。
  `QStandardPaths.PicturesLocation` を使えば直る。ユーザーは「このままでわかる」として修正を見送った。
- Wayland のキャプチャは1枚あたり約1秒かかる。

## ユーザーの好み

- 返事は日本語で、報告は短く。
- PR のレビューはユーザーが行わない。CI が通ればそのまま進めてよい、と言われている（2026-09-26）。
- 公開リリースなど外部に出る操作は、了承を得てから行う。
- この PC での git のコミットは、作者を `jydie5 <jydie5@yahoo.co.jp>` にしていた（グローバル設定はしていない）。
