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
```

The bootstrap build intentionally omits Real-CUGAN. Before it is bundled, pin
the official Windows release URL and SHA-256 values, document provenance and
all transitive licenses, and make the distribution audit require those files.
The `--development-baseline` ZIP is clearly named and must not be published as
a release.
