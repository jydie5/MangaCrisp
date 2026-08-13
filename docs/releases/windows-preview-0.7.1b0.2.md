# MangaCrisp Windows Development Preview 0.7.1b0.2

This refresh fixes the first Windows capture human-check blocker found in
0.7.1b0.1. The previous default undo shortcut, `Alt+Z`, is commonly owned by
overlay software and failed with Windows error 1409 on the validation PC.

## Change

- The default Windows shortcuts are now `Control+Alt+C` for capture and
  `Control+Alt+Z` for undo.
- `Alt+C` / `Alt+Z` remains an optional preset for systems where it is available.
- `Control+Return` / `Control+Delete` remains the third preset.
- Capture behavior, page numbering, PNG output, and CBZ/ZIP packaging are unchanged.

## 日本語

0.7.1b0.1のWindows実機ヒューマンチェックで、既定の取消キー`Alt+Z`が
オーバーレイソフトに登録済みのため、Windowsエラー1409で撮影を開始できないことを
確認しました。

- Windowsの既定を、撮影`Control+Alt+C`／取消`Control+Alt+Z`へ変更しました。
- `Alt+C`／`Alt+Z`は利用可能なPC向けの代替プリセットとして残します。
- `Control+Return`／`Control+Delete`も引き続き選択できます。
- 撮影、連番、PNG、CBZ／ZIPの処理内容は変更していません。
