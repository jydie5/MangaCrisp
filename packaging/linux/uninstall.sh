#!/bin/sh
# Remove the per-user MangaCrisp installation created by install.sh.
# The library, settings, and caches are kept.
set -eu

APP_ID="com.jydie5.mangacrisp"
DATA_HOME=${XDG_DATA_HOME:-"$HOME/.local/share"}

rm -f "$DATA_HOME/applications/$APP_ID.desktop"
rm -f "$DATA_HOME/icons/hicolor/256x256/apps/$APP_ID.png"
rm -f "$DATA_HOME/icons/hicolor/512x512/apps/$APP_ID.png"
if [ "$(readlink "$HOME/.local/bin/mangacrisp" 2>/dev/null || true)" = "$HOME/.local/opt/MangaCrisp/MangaCrisp" ]; then
    rm -f "$HOME/.local/bin/mangacrisp"
fi
rm -rf "$HOME/.local/opt/MangaCrisp"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q "$DATA_HOME/applications" || true
fi

echo "MangaCrisp was removed. Your library and settings were kept."
