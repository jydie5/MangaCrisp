# Per-book reading state

The shared reader restores a book's page, Spread/Single Page layout, reading
direction, single-cover choice, and named quality preset before the first render
or correction request. A stored preset takes precedence over the global quality
default. Missing or deleted preset names fall back to that default, then Natural.
Opening a book does not rewrite the global quality preferences.

The **Original quality card** is a persistent choice. **O / Compare original** is
a temporary comparison and does not replace the saved quality choice, even if
the reader closes while comparing. Explicit quality selections still update the
global default as before; reopening another book restores that book's own choice.

Manual engine parameters must be saved as a named custom preset to restore them.
The current database stores a preset name, not an arbitrary parameter payload.
Unsaved manual settings therefore fall back on reopening. Swapped spread order
is also transient: reopening derives visual order from the saved reading direction.
No database migration is required.

Native verification should include two books with different layout and quality
choices, a named custom preset, an Original card choice, temporary O comparison,
an out-of-range saved page, and a deleted custom preset. Confirm that opening a
book leaves the settings file unchanged and that its first cache/correction lookup
uses the restored page and quality. Use only generated or licensed demo pages.

## 日本語

ページ、見開き／単ページ、読書方向、表紙単独、名前付き画質プリセットを、
最初の描画・補正要求より前に復元します。本ごとの画質を全体の既定値より優先し、
削除済み等で解決できない場合は全体の既定値、次に「自然」へ戻します。
本を開くだけでは全体の画質設定を書き換えません。

「原画」カードは保存する画質設定です。Oキーの原画比較は一時状態で、比較中に
閉じても保存する画質を変えません。画質を明示的に選んだ時の全体既定値の更新は
従来どおりで、別の本を開き直すとその本の設定を復元します。

手動パラメータは名前付きカスタム設定として保存してください。現在のDBは名前を
保存するため、未保存の手動設定一式は復元できません。左右入替も一時状態で、
開き直す時は保存した読書方向から表示順を決めます。DB移行はありません。
