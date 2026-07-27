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

Status: technically validated, blocked from the public Windows release pending
redistribution review of the Microsoft runtime binary.

- Upstream: https://github.com/nihui/realcugan-ncnn-vulkan
- Release: 20220728
- Archive: `realcugan-ncnn-vulkan-20220728-windows.zip`
- Archive URL: https://github.com/nihui/realcugan-ncnn-vulkan/releases/download/20220728/realcugan-ncnn-vulkan-20220728-windows.zip
- Archive SHA-256: `c6e08d46c11704b1e3a1ada9ddd591cb5005f52f132136c8633ba25def400e01`
- Executable SHA-256: `af5a36b124c993c77d0e69e42f640cdc108060874ed060d34ceef66d52c77a9d`
- `vcomp140.dll` SHA-256: `54fe6b087528b33c2969143d811eb62f1bd49071d37de9db0745fc079764d698`
- Upstream project license: MIT

The official archive includes the executable, models, project license, and
`vcomp140.dll`. A one-page run using the repository''s freely redistributable
demo completed successfully on an NVIDIA GeForce RTX 2070 SUPER in about 4.2
seconds.

Microsoft documents Visual C++ runtime redistribution as subject to Visual
Studio license eligibility and recommends the supported Visual C++
Redistributable. The upstream MIT license does not itself establish permission
to redistribute Microsoft''s `vcomp140.dll`. Therefore MangaCrisp must not
bundle or publish this Windows engine archive until one of these routes is
documented:

1. Confirm that the release publisher has the required Microsoft redistribution
   rights and reproduce the required notices.
2. Require/install the official Microsoft Visual C++ Redistributable and omit
   `vcomp140.dll` from MangaCrisp.
3. Produce and audit a compliant engine build whose runtime dependencies have a
   documented redistribution path.

The distribution audit intentionally keeps `release_ready=false` while the
Windows Real-CUGAN engine is absent.
