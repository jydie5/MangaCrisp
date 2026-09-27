# MangaCrisp for Linux

[English](INSTALL.linux.md) | [日本語](INSTALL.linux.ja.md)

## Supported systems

- Ubuntu 24.04 LTS or newer (x86_64), on GNOME Wayland or X11.
- AI enhancement needs a Vulkan GPU and driver (Mesa radv/anv or the NVIDIA
  driver). Without one, pages are shown at their original quality.

## Required packages

```bash
sudo apt install libxcb-cursor0 libegl1 libgl1 libxkbcommon0 libfontconfig1 libdbus-1-3 libvulkan1 libgomp1 mesa-vulkan-drivers
```

Skip `mesa-vulkan-drivers` when using the NVIDIA driver. If
`vulkaninfo --summary` (from `vulkan-tools`) lists your GPU, AI enhancement is
available.

## Install

1. Download `MangaCrisp-<version>-linux-x86_64.tar.gz` and check the attached
   SHA-256.
2. Extract it and run the installer:

```bash
tar xf MangaCrisp-*-linux-x86_64.tar.gz
MangaCrisp/install.sh
```

MangaCrisp is copied to `~/.local/opt/MangaCrisp` and added to the application
menu. The `mangacrisp` command is linked into `~/.local/bin`. You can also run
`MangaCrisp` from the extracted folder, but screen capture on Wayland requires
the installed desktop entry because permissions are stored per application.

Run `~/.local/opt/MangaCrisp/uninstall.sh` to remove it. Your library and
settings are kept.

## Data locations

| Purpose | Location |
|---|---|
| Settings and library data | `$XDG_DATA_HOME/MangaCrisp` (default `~/.local/share/MangaCrisp`) |
| AI cache | `$XDG_CACHE_HOME/MangaCrisp` (default `~/.cache/MangaCrisp`) |
| Default library | `~/MangaCrisp Library` |

## Sequential screen capture

- **Wayland**: the first time you press Start capture, the desktop asks for
  screenshot permission and confirms the `Alt+C` / `Alt+U` shortcuts. Allow
  both. If you denied one, change it for MangaCrisp under Settings > Apps.
- **X11**: no permission is needed. Choose another preset if another app
  already uses the keys.
- While capturing, the controller is minimized and stays in the Dash and
  Alt+Tab. Return there to stop capturing and create the archive.
- Only capture screens you own or are allowed to save.

## Run from source

```bash
git clone https://github.com/jydie5/MangaCrisp.git
cd MangaCrisp
uv sync --extra dev
uv run pytest
uv run python scripts/fetch_realcugan_linux.py
uv run mangacrisp
```

Release builds run on Ubuntu 24.04:

```bash
uv sync --extra dev --extra app
uv run python scripts/build_linux_app.py
```
