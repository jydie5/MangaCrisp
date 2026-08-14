# MangaCrisp Windows Development Preview 0.7.1b0.3

This refresh fixes the second Windows capture human-check blocker found in
0.7.1b0.2. Starting capture previously hid both MangaCrisp windows. Unlike the
macOS Dock, the Windows taskbar then had no app window to restore.

## Change

- Starting capture hides the bookshelf but minimizes the capture controller.
- The controller remains available from the Windows taskbar while staying out
  of the selected capture region.
- Restoring the controller allows capture to be stopped, reviewed, or completed.
- The macOS hidden-window and Dock restore behavior is unchanged.
- Capture shortcuts, page numbering, PNG output, and CBZ/ZIP packaging are unchanged.

## 日本語

0.7.1b0.2のWindows実機確認で、撮影開始後に本棚とキャプチャ画面の両方が非表示になり、
タスクバーから管理画面へ戻れない問題を確認しました。

- 撮影開始時は本棚だけを隠し、キャプチャ画面をWindowsのタスクバーへ最小化します。
- タスクバーのMangaCrispアイコンから管理画面へ戻り、撮影停止、確認、完成を行えます。
- macOSの非表示とDockからの復帰動作は変更していません。
- ショートカット、連番、PNG、CBZ／ZIPの処理内容は変更していません。
