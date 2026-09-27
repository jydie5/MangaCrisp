# Linux dependency provenance

Third-party binaries used by Linux builds. Every entry is downloaded by a
`scripts/*_linux.py` script that pins the upstream URL and SHA-256.

## Real-CUGAN ncnn Vulkan

| Field | Value |
|---|---|
| Script | `scripts/fetch_realcugan_linux.py` |
| Upstream | https://github.com/nihui/realcugan-ncnn-vulkan (release `20220728`) |
| Archive | `realcugan-ncnn-vulkan-20220728-ubuntu.zip` |
| Archive SHA-256 | `d745174bd04c0232c89d935b74799311008fda06bea4195f61be5f0f3cc087cb` |
| Executable SHA-256 | `89cb341d9ffbdcdc7f63bdc75d9cb0bae82eabe6597054e2a812331b2831fcc2` |
| Architecture | x86_64, requires glibc 2.15 or newer |
| License | MIT (engine), MIT (Real-CUGAN models), BSD-3-Clause (ncnn), BSD-3-Clause (libwebp) |
| Modified | No |

The binary dynamically links only system libraries: `libvulkan.so.1`,
`libgomp.so.1`, `libstdc++.so.6`, `libgcc_s.so.1`, and glibc. None of them are
bundled. Users need `libvulkan1`, `libgomp1`, and a Vulkan driver
(`mesa-vulkan-drivers` or the NVIDIA driver).

Verified on Ubuntu 26.04 with an NVIDIA GeForce GTX 1060 6GB (2x upscale).

Usage for development (installs into the ignored `test/engines/` folder):

```bash
uv run python scripts/fetch_realcugan_linux.py
```

## 7-Zip

| Field | Value |
|---|---|
| Script | `scripts/fetch_7zip_linux.py` |
| Upstream | https://github.com/ip7z/7zip (release `26.02`) |
| Archive | `7z2602-linux-x64.tar.xz` |
| Archive SHA-256 | `41aaba7b1235304ab5aa0624530c67ae829496cd29e875925271efdccc28c03e` |
| `7zz` SHA-256 | `1676a968815b92e865bc0ffeecee3fa284ba4402bf23dc2bec2412c4b502e922` |
| License | GNU LGPL with the unRAR restriction and BSD-3-Clause parts (`License.txt`) |
| Modified | No |

Only the dynamically linked `7zz`, `License.txt`, and `readme.txt` are bundled.
`7zz` links only glibc, libstdc++, and libgcc_s.

## Qt license text

Linux PySide6 and shiboken6 wheels contain no license files. The build fetches
`LICENSES/LGPL-3.0-only.txt` from `qtproject/pyside-pyside-setup` tag `v6.11.1`
(SHA-256 `da7eabb7bafdf7d3ae5e9f223aa5bdc1eece45ac569dc21b3b037520b4464768`).
