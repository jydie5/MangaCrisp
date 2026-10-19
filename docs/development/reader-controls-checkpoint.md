# Reader controls checkpoint

- The correction baseline is `1c1a8a6` on `core/fix-enhancement-color`.
- Reader controls are isolated in the separate `core/reader-controls` change.
- To restore the correction baseline while removing the UI change, revert the
  reader-controls commit. This preserves the correction fixes and does not
  delete user data; it only changes source code and the reader UI.

- The first UI checkpoint is `5320092` (reader controls). The following revision
  removes the persistent toolbar and applies the same visual scheme to the
  bookshelf. Reverting that follow-up commit restores the first UI checkpoint.
