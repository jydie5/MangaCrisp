# Reader controls checkpoint

The correction/cache baseline is `1c1a8a6` (PR #53), merged into `main` as
`78c2cc6`. UI changes are isolated in PR #54 and preserve that baseline.

| Commit | UI checkpoint |
| --- | --- |
| `5320092` | Reader settings cards, shortcut buttons, and translucent center controls |
| `8fd3c81` | Remove the persistent bottom toolbar and refresh the bookshelf |
| `97dc06f` | Modernize H/? help; close by button, Escape, or backdrop click |
| `ed7fa11` | Portable font-metric layout regression tests |

After PR #54 is merged, start a new `core/` branch from the current `origin/main` to remove the UI changes while keeping the
correction fixes. Revert these commits in reverse order:

```bash
git revert ed7fa11 97dc06f 8fd3c81 5320092
uv run pytest -q
```

The sequence was verified against `ed7fa11`. Later handover edits cause
conflicts in this checkpoint document: retain its current content, stage it,
and run `git revert --continue` for each stopped revert. The correction/cache
implementation remains unchanged. Review conflicts against any later changes;
do not restore old shared files wholesale or reset `main`. Commit IDs are retained by merging the PR without
squashing. Reverting `97dc06f` restores the prior help dialog;
reverting `8fd3c81` also restores the old persistent toolbar, which is not the
current product preference.

These are source changes and do not delete library data. No separate source
or library backup copy is needed. Previous GitHub prerelease assets remain
available for an application rollback. See the
[platform handover](ux-maintenance-handover.md) for native verification before
publishing a rebuilt package.
