# Windows packaging

Windows release-only files live in this directory. Generated applications,
archives, manifests, and audit reports remain under the ignored `dist/`
directory.

## Baseline layout

```text
dist/MangaCrisp/
  MangaCrisp.exe
  _internal/
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
uv run python scripts/build_windows_app.py
uv run python scripts/audit_windows_distribution.py
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
The baseline intentionally omits Real-CUGAN because the Microsoft runtime
redistribution route is still under review. Validate the pinned official engine
locally with:

```powershell
uv run python scripts/fetch_realcugan_windows.py
```

That command writes `redistribution_approved=false` into development provenance;
the normal build does not copy the engine into `dist/`, and the audit cannot
mark it release-ready without an explicit approved record.

The `--development-baseline` ZIP is clearly named and must not be published as
a release.
