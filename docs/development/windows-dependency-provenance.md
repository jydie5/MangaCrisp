# Windows dependency provenance

This file records the externally sourced native binaries evaluated for the
Windows x64 port. Checksums are release gates, not substitutes for reviewing
the upstream licenses. This is a practical engineering record, not legal
advice.

## 7-Zip RAR/CBR backend

Status: approved for the Windows development baseline.

- Upstream: https://www.7-zip.org/
- Release: 26.02 x64
- Installer: `7z2602-x64.exe`
- Installer URL: https://github.com/ip7z/7zip/releases/download/26.02/7z2602-x64.exe
- Installer SHA-256: `6745fa76dc2ea031596d8678f6f6b99c3c1b435b4164a63485adbbc7b8d82ef0`
- Bootstrap extractor: `7zr.exe`
- Bootstrap URL: https://github.com/ip7z/7zip/releases/download/26.02/7zr.exe
- Bootstrap SHA-256: `56b8cc9f4971cef253644fafe54063ed7fdca551d4dee0f8c6baa81b855acd72`
- Bundled `7z.exe` SHA-256: `83967f1b02b43c4efeda302795722c809e0e81b8307de73558d10484d5676a7d`
- Bundled `7z.dll` SHA-256: `69fd4df057985c40e510e2fac182881c7f85e90aa13ec703f763a8fdb2ce61f8`
- License file SHA-256: `519ac0a4bded9c18ea02e0afb71f663d8c47373bd9facd3ac96a79f51d77765d`

The build downloads the two official release assets, verifies them before use,
extracts the installer with the pinned standalone extractor, and then verifies
the two bundled binaries again. The distribution contains the upstream
`License.txt`, `readme.txt`, and generated `7zip-provenance.json`.

The 7-Zip license is GNU LGPL 2.1 or later with BSD-licensed components and an
unRAR restriction. MangaCrisp uses the unRAR capability only to extract RAR/CBR
files, not to create a RAR-compatible archiver.

Validation on 2026-07-27:

- Official 7-Zip 26.02 x64 reports both RAR and RAR5 handlers.
- Extraction of the ISC-licensed `rarfile` project fixture
  `rar5-solid.rar` succeeded through the pinned `7z.exe` and `7z.dll`.
- The test fixture and vendor downloads remain ignored and are not committed.
- The packaged-app audit probes handler support and enforces all binary hashes.

## Real-CUGAN ncnn Vulkan

Status: approved for the Windows development baseline and portable packaging.
Public release still requires Intel, AMD, and separate clean-account evidence.

- Upstream: https://github.com/nihui/realcugan-ncnn-vulkan
- Selected source commit: `395302c5c70f1bff604c974e92e0a87e45c9f9ee`
- Source submodules are pinned in `scripts/build_realcugan_windows.py`.
- Compiler/toolchain: Zig 0.16.0 targeting `x86_64-windows-gnu`
- Zig archive URL: https://ziglang.org/download/0.16.0/zig-x86_64-windows-0.16.0.zip
- Zig archive SHA-256: `68659eb5f1e4eb1437a722f1dd889c5a322c9954607f5edcf337bc3684a75a7e`
- Build frontend: CMake 4.4.0 and Ninja 1.13.0
- Vulkan SDK: 1.4.350.0, used only at build time
- Vulkan SDK installer URL: https://sdk.lunarg.com/sdk/download/1.4.350.0/windows/vulkansdk-windows-X64-1.4.350.0.exe
- Vulkan SDK installer SHA-256: `855b27ba05d2d8119c5114c5d4ff870ca38f2c632b11e1bb9923b9b7e6ecfe7b`
- OpenMP: disabled
- ncnn CPU AVX kernels: disabled; the selected path is Vulkan GPU execution
- Upstream project license: MIT

The build verifies the source and every submodule commit, downloads and verifies
the Zig toolchain, uses the copy-only Vulkan SDK, and stages models from the
verified official 20220728 package. The staged provenance records every model,
license, executable, import, tool version, and source hash. Notices for
Real-CUGAN, ncnn, glslang, libwebp, Zig, MinGW-w64, libc++, libc++abi, and
libunwind are bundled.

The resulting executable imports only Windows system API/UCRT API-set DLLs and
the Vulkan loader supplied by the graphics driver. It does not import or bundle
`vcomp140.dll`, `vcruntime`, `msvcp`, `libgcc`, `libstdc++`, or
`libwinpthread` DLLs. The Vulkan SDK is not redistributed.

### Official package used as the model and behavioral reference

- Release: 20220728
- Archive: `realcugan-ncnn-vulkan-20220728-windows.zip`
- Archive URL: https://github.com/nihui/realcugan-ncnn-vulkan/releases/download/20220728/realcugan-ncnn-vulkan-20220728-windows.zip
- Archive SHA-256: `c6e08d46c11704b1e3a1ada9ddd591cb5005f52f132136c8633ba25def400e01`
- Upstream executable SHA-256: `af5a36b124c993c77d0e69e42f640cdc108060874ed060d34ceef66d52c77a9d`
- Upstream `vcomp140.dll` SHA-256: `54fe6b087528b33c2969143d811eb62f1bd49071d37de9db0745fc079764d698`

The official archive supplies the verified model files and a behavioral
reference. Its executable and `vcomp140.dll` are not copied into MangaCrisp.
The reproducible validation command for the selected Zig build is:

```powershell
uv run python scripts/validate_realcugan_windows.py --gpu-label "machine label"
```

On the current NVIDIA GeForce RTX 2070 SUPER, the pinned engine processed the
first 1200 x 1660 Pepper and Carrot demo page to 2400 x 3320 in 2.216 seconds.
The path-sanitized JSON evidence is committed under
`packaging/windows/validation/`. It records the actual execution GPU,
name/driver inventory, input and engine hashes, settings, dimensions, runtime,
output size, and stdout without personal paths. The release gate also pins the
evidence-file SHA-256. Intel, AMD, and separate clean-account reports are still
required.

### Historical runtime investigation

The official upstream executable was also tested after removing its local
`vcomp140.dll`; it ran through the supported system VC++ runtime. That route was
not selected because it would add an end-user runtime prerequisite and Microsoft
redistribution eligibility question. The selected Zig build instead removes
the VC/OpenMP dependency from the executable itself. This is the audited
compliant-build route identified by the investigation.

The distribution audit verifies the staged executable, imports, provenance,
models, notices, and absence of bundled DLLs. It can mark the packaged baseline
ready with Real-CUGAN present, while `release_ready` remains false until the
engine-matched Intel, AMD, NVIDIA, and separate clean-account evidence all pass.
