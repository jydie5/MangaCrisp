#!/bin/sh
# Validate a Linux release archive in a clean Ubuntu container.
#
# Usage: packaging/linux/validate-clean-ubuntu.sh dist/MangaCrisp-<version>-linux-x86_64.tar.gz [ubuntu:24.04]
#
# Installs only the packages documented in INSTALL.linux.md, then checks the
# installer, the packaged smoke test, opening a demo book, the bundled 7-Zip,
# the bundled Real-CUGAN engine on Mesa's CPU Vulkan driver, and uninstall.
set -eu

ARCHIVE=$(realpath "$1")
IMAGE=${2:-ubuntu:24.04}
ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)

docker run --rm \
    -v "$ARCHIVE:/work/MangaCrisp.tar.gz:ro" \
    -v "$ROOT_DIR/demo:/demo:ro" \
    -v "$ROOT_DIR/assets/mangacrisp-app-icon.png:/work/in.png:ro" \
    "$IMAGE" sh -euc '
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq --no-install-recommends \
    libxcb-cursor0 libegl1 libgl1 libxkbcommon0 libfontconfig1 libdbus-1-3 \
    libvulkan1 libgomp1 mesa-vulkan-drivers >/dev/null
useradd -m tester
su tester -s /bin/sh -c "
set -eu
cd ~
tar xf /work/MangaCrisp.tar.gz
MangaCrisp/install.sh
export QT_QPA_PLATFORM=offscreen MANGACRISP_LANGUAGE=en
~/.local/bin/mangacrisp --smoke-test
echo PASS: smoke test
~/.local/bin/mangacrisp \"/demo/Pepper-and-Carrot v01 The-Potion-of-Flight.zip\" --no-auto-prefetch --smoke-close-ms 3000
echo PASS: reader
~/.local/opt/MangaCrisp/tools/7zip/7zz i | grep -q Rar5
echo PASS: 7-Zip RAR support
cd ~/.local/opt/MangaCrisp/_internal/engines/realcugan-ncnn-vulkan
./realcugan-ncnn-vulkan -i /work/in.png -o /tmp/out.png -s 2 >/tmp/engine.log 2>&1
test -s /tmp/out.png
echo PASS: Real-CUGAN on CPU Vulkan
~/.local/opt/MangaCrisp/uninstall.sh
test ! -e ~/.local/opt/MangaCrisp
echo PASS: uninstall
"
'
