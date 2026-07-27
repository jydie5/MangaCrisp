# Windows packaging

Windows release-only files live in this directory. Generated applications,
archives, manifests, and audit reports remain under the ignored `dist/`
directory.

## Baseline layout

```text
dist/MangaCrisp/
  MangaCrisp.exe
  _internal/
    engines/realcugan-ncnn-vulkan/
      realcugan-ncnn-vulkan.exe
      models-*/
      licenses/
      realcugan-provenance.json
  licenses/
  tools/7zip/
    7z.exe + 7z.dll
  INSTALL.windows.md
  INSTALL.windows.ja.md
  LICENSE
  THIRD_PARTY_NOTICES.md
```

Build and audit on Windows x64:

```powershell
uv sync --extra dev --extra app
uv run python scripts/fetch_vulkan_sdk_windows.py --accept-licenses
uv run python scripts/build_realcugan_windows.py --clean
uv run python scripts/build_windows_app.py
uv run python scripts/audit_windows_distribution.py --require-engine
uv run python scripts/package_windows_portable.py --skip-build --development-baseline
uv run python scripts/test_windows_portable_sanitized_environment.py
```

The sanitized-environment check extracts the ZIP to a new temporary directory,
removes Python, uv, and virtual-environment paths, and runs the packaged smoke
test with only Windows system directories on `PATH`. It does not replace the
final test on a separate clean Windows account.

The build script downloads the pinned official 7-Zip 26.02 x64 assets, verifies
their SHA-256 values, and bundles the license and provenance. The distribution
audit rejects missing or modified binaries and checks reported RAR/RAR5 support.

The Real-CUGAN build verifies the pinned source and submodule commits, Zig
toolchain, Vulkan SDK, official model archive, PE imports, model hashes, and
licenses. It disables OpenMP and produces an executable that does not require or
bundle Microsoft VC/OpenMP or MinGW runtime DLLs. The Vulkan SDK is build-time
only. Validate that staged engine locally with:

```powershell
uv run python scripts/validate_realcugan_windows.py --gpu-label "machine label"
```

The validation script processes one freely redistributable demo page and writes
a path-sanitized JSON report under ignored `build/windows/`. Collect reports on
Intel and AMD machines before release; the NVIDIA report already passes. Each
report must be registered rather than copied into the gate file by hand:

```powershell
uv run python scripts/record_windows_release_validation.py `
  --gpu-family intel `
  --report build\windows\realcugan-validation.json
```

Registration verifies the GPU vendor, fixed demo and recipe, output,
provenance, runtime mode, evidence hash, and engine SHA-256. All passed reports
must match the executable bundled in the candidate distribution.

A separate clean Windows account must also pass the standalone PowerShell
validator. The complete GPU and clean-account procedure is documented in
`docs/development/windows-release-validation.md`.

The distribution audit can mark this implementation baseline ready while
keeping `release_ready=false` until all external evidence passes. Therefore the
`--development-baseline` ZIP is clearly named and remains local-only.

## Public Development Preview

The GitHub Actions workflow `.github/workflows/windows-preview.yml` rebuilds the
engine and application from `main`, runs all tests and audits, and creates a
separately named preview:

```powershell
uv run python scripts/package_windows_portable.py `
  --skip-build `
  --development-preview
```

Preview packaging succeeds only when the distribution baseline passes and the
remaining blockers are Intel GPU, AMD GPU, and separate clean-account
validation. In particular, the rebuilt engine must match the committed NVIDIA
evidence SHA-256. A manual workflow dispatch can publish the verified ZIP,
checksum, audit, and manifest as a GitHub prerelease.
