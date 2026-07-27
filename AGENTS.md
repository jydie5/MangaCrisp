# MangaCrisp Development Rules

This repository is developed concurrently on macOS and Windows. Read this file
before changing code, packaging, documentation, or release assets.

## Required reading

- `docs/development/cross-platform-workflow.md`
- `docs/development/windows-handover.md` when working on Windows
- `README.md`, `ROADMAP.md`, and `THIRD_PARTY_NOTICES.md`

## Ownership boundaries

- Keep product behavior and reusable logic in `src/mangacrisp_app/`.
- Put operating-system integration behind a small platform-specific module.
- Put Windows-only build and release code under `packaging/windows/` or in a
  script whose name ends in `_windows.py`.
- Put macOS-only build and release code under `packaging/macos/` or in a script
  whose name ends in `_macos.py`.
- Do not make the shared reader behave differently on each OS unless a
  documented OS convention requires it.
- Do not edit the other platform's packaging files as part of an unrelated
  change.

## Concurrent work

- Never develop directly on `main`.
- Use `windows/<topic>` for Windows-only changes.
- Use `macos/<topic>` for macOS-only changes.
- Use `core/<topic>` for shared behavior.
- Keep each pull request limited to one of those scopes.
- Rebase or merge the latest `origin/main` before final verification.
- Never resolve a conflict by discarding the other platform's changes.
- If a shared file must change from both platforms, coordinate through a
  `core/<topic>` pull request first.

## Verification

- Run the shared test suite after changing `src/mangacrisp_app/`.
- Add platform-independent tests for shared behavior.
- Add platform-specific tests without requiring the other operating system.
- Build release artifacts on their target OS. Do not cross-build Windows
  releases on macOS or macOS releases on Windows.
- Generated files, local libraries, caches, signing credentials, and release
  artifacts must remain untracked.

## Public repository safety

- Do not commit copyrighted test manga, personal library data, local paths,
  credentials, signing profiles, API keys, or payment-account information.
- Demo material must have redistribution terms documented in `demo/`.
- New bundled binaries require provenance, a pinned checksum, and license
  notices before release.
