# Linux packaging

Linux release-only files live in this directory. Generated applications and
archives remain under the ignored `dist/` directory.

## Layout

```text
dist/MangaCrisp/
  MangaCrisp                 # PyInstaller one-folder executable
  _internal/
    engines/realcugan-ncnn-vulkan/
  tools/7zip/7zz
  share/
    com.jydie5.mangacrisp.desktop   # template, @EXEC@ is filled by install.sh
    icons/{256x256,512x512}/com.jydie5.mangacrisp.png
  licenses/
  install.sh / uninstall.sh
  INSTALL.linux.md / INSTALL.linux.ja.md
  LICENSE, THIRD_PARTY_NOTICES.md
dist/MangaCrisp-<version>-linux-x86_64.tar.gz
```

## Build

Build on Ubuntu 24.04 x86_64 so that the bundled Python and Qt work on every
supported Ubuntu release. The Linux CI workflow builds the same archive.

```bash
uv sync --extra dev --extra app
uv run python scripts/build_linux_app.py
```

## Why tar.gz and not AppImage

The AppImage type 2 runtime statically links libfuse (LGPL-2.1), which would
add a relinking obligation for a binary we do not build. The one-folder archive
needs no extra runtime, and `install.sh` provides the desktop entry that the
XDG portals need to store screen capture permissions for MangaCrisp.
