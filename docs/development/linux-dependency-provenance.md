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
