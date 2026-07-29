# Mouse-first reading navigation

## Goal

Readers must be able to move through a manga or comic with only a mouse while
keeping the image area free of permanent controls. The behavior must remain
predictable for both right-bound manga and left-bound comics.

The design takes inspiration from MangaMeeya's mouse-first operation and
configurable navigation, while retaining MangaCrisp's reading-direction model
and center information overlay:

- [MangaMeeya basic operation](https://w.atwiki.jp/mangameeya/pages/20.html)
- [MangaMeeya operation settings](https://w.atwiki.jp/mangameeya/pages/54.html)

## Interaction model

The image area is divided using the full reader width:

| Zone | Width | Right-bound | Left-bound |
|---|---:|---|---|
| Left edge | 40% | Next spread | Previous spread |
| Center | 20% | Toggle reading information | Toggle reading information |
| Right edge | 40% | Previous spread | Next spread |

Additional input:

- `Shift` + edge click moves one page in the selected direction.
- Right-click moves to the previous spread from any image zone.
- A pointer movement greater than 12 pixels is treated as a drag and does not
  turn a page.
- A double-click produces at most one page-turn action.

## Scope and precedence

- Mouse navigation is active on the two page panes in both windowed and
  full-screen reading.
- Controls, dialogs, the reading-information overlay, and the next-volume
  action retain their own click behavior.
- Existing keyboard navigation remains unchanged.
- Reaching the first or last page uses the existing bounded navigation and
  next-volume behavior.
- Page changes continue to use the existing display cache, correction cache,
  prefetch scheduler, and debounced reading-position save.

## Implementation design

`reader_click_action` is the platform-independent zone mapper. `SpreadWindow`
maps a completed click from screen coordinates to the full image host and then
passes the resulting action to `handle_reader_click`.

Navigation is triggered on mouse release. Press and release positions are
compared to reject drags. The second release in a double-click sequence is
suppressed, preventing accidental two-spread jumps.

## Acceptance tests

- Right-bound and left-bound edge mappings are opposite and correct.
- Center clicks only toggle reading information.
- `Shift` changes a spread move from two pages to one page.
- Right-click always moves backward.
- Rapid forward/back clicks keep using the existing non-blocking page-turn
  path.
- Full-screen operation matches windowed operation.
- Clicking reader controls never turns a page.
