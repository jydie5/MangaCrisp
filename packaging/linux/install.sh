#!/bin/sh
# Install MangaCrisp for the current user.
#
# Copies this folder to ~/.local/opt/MangaCrisp, adds a launcher to the
# application menu, and links the command to ~/.local/bin/mangacrisp.
# The desktop entry is required for screen capture permissions on Wayland.
set -eu

APP_ID="com.jydie5.mangacrisp"
SOURCE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DATA_HOME=${XDG_DATA_HOME:-"$HOME/.local/share"}
INSTALL_DIR="$HOME/.local/opt/MangaCrisp"
BIN_DIR="$HOME/.local/bin"
APPLICATIONS_DIR="$DATA_HOME/applications"
ICONS_DIR="$DATA_HOME/icons/hicolor"

if [ ! -x "$SOURCE_DIR/MangaCrisp" ]; then
    echo "MangaCrisp executable was not found next to install.sh" >&2
    exit 1
fi

if [ "$SOURCE_DIR" != "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    mkdir -p "$(dirname "$INSTALL_DIR")"
    cp -a "$SOURCE_DIR" "$INSTALL_DIR"
fi

mkdir -p "$BIN_DIR" "$APPLICATIONS_DIR"
ln -sf "$INSTALL_DIR/MangaCrisp" "$BIN_DIR/mangacrisp"

for size in 256 512; do
    mkdir -p "$ICONS_DIR/${size}x${size}/apps"
    cp "$INSTALL_DIR/share/icons/${size}x${size}/$APP_ID.png" "$ICONS_DIR/${size}x${size}/apps/$APP_ID.png"
done

sed "s|@EXEC@|$INSTALL_DIR/MangaCrisp|" "$INSTALL_DIR/share/$APP_ID.desktop" > "$APPLICATIONS_DIR/$APP_ID.desktop"
chmod 644 "$APPLICATIONS_DIR/$APP_ID.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q "$APPLICATIONS_DIR" || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -t "$ICONS_DIR" || true
fi

echo "MangaCrisp was installed to $INSTALL_DIR"
echo "Open it from the application menu or run: mangacrisp"
