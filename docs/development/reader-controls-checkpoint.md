# Reader controls checkpoint

The correction/cache baseline is `1c1a8a6` (PR #53), merged into `main` as
`78c2cc6`. UI changes are isolated in PR #54 and preserve that baseline.

| Commit | UI checkpoint |
| --- | --- |
| `5320092` | Reader settings cards, shortcut buttons, and translucent center controls |
| `8fd3c81` | Remove the persistent bottom toolbar and refresh the bookshelf |
| `97dc06f` | Modernize H/? help; close by button, Escape, or backdrop click |

To remove all three UI changes while keeping correction fixes, start a new
`core/` branch from the current `origin/main` and revert these commits in
reverse order:

```bash
git revert 97dc06f 8fd3c81 5320092
uv run pytest -q
```

Review conflicts against any later changes; do not restore old shared files
wholesale or reset `main`. Commit IDs are retained by merging the PR without
squashing. Reverting only the latest commit restores the prior help dialog;
reverting `8fd3c81` also restores the old persistent toolbar, which is not the
current product preference.

These are source changes and do not delete library data. No separate source
or library backup copy is needed. Previous GitHub prerelease assets remain
available for an application rollback. See the
[platform handover](ux-maintenance-handover.md) for native verification before
publishing a rebuilt package.
