# MangaCrisp Windows Development Preview 0.7.1b0.1

This unsigned Windows 10/11 x64 portable preview synchronizes the macOS 0.7.1
reader work and adds the Windows implementation of manual sequential screen
capture.

## Highlights

- Capture a user-selected fixed screen region as numbered, color-preserving PNG files.
- Use a Windows global shortcut (`Alt+C` by default) to capture without moving focus.
- Undo the latest capture with `Alt+Z` and reuse the same page number.
- Finish a session as one CBZ or ZIP while retaining the numbered PNG files.
- Switch the reader between **Spread (2 images)** and **Single Page (1 image)** with `V`.
- Apply original/enhanced comparison and AI enhancement to the visible single image.
- Keep page turning manual; MangaCrisp does not automate another application or
  bypass capture protection.

## Validation

- 93 automated tests passed; three platform/environment-dependent tests skipped.
- Windows native hotkey delivery was verified through the real message loop.
- Two fixed-region color captures were written as RGBA PNG and packaged in CBZ order.
- The portable app opened the capture controller and showed the Windows display and
  shortcut preset.
- The portable reader opened a redistributable demo and showed one centered image in
  Single Page mode.
- The distribution audit reached the Development Preview baseline and the extracted
  ZIP passed the sanitized-environment smoke test.

The external 10-page capture check remains the first public human-check point.
Intel/AMD Real-CUGAN evidence and a separate clean Windows account are still required
before a stable Windows release.

## 日本語

Windows 10/11 x64向け未署名ポータブルDevelopment Previewです。macOS 0.7.1の
単ページ表示を同期し、Windowsの手動連番スクリーンキャプチャを追加しました。

- 固定範囲をカラー連番PNGへ保存し、CBZ／ZIPとして完成できます。
- 既定では`Alt+C`で撮影、`Alt+Z`で直前の撮影を取り消します。
- ホットキーは対象アプリのフォーカスを移さず、ページ送りは利用者が手動で行います。
- `V`キーで見開き（2画像）と単ページ（1画像）を切り替えられます。
- 自動ページ送りやキャプチャ保護の回避は行いません。

公開previewを最初の10枚連続撮影ヒューマンチェック地点とします。正式Windows版には、
Intel／AMDのReal-CUGAN証跡とPython未導入の別Windowsアカウント検証が引き続き必要です。
