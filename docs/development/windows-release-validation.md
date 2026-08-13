# Windows release validation

This document defines how MangaCrisp records the external evidence required for
a Windows portable release. A local development baseline may be built without
all evidence. A clearly marked GitHub Development Preview may be published
while only Intel, AMD, and separate clean-account evidence remains. A stable
public release must pass every check against the exact bundled Real-CUGAN
executable.

## Release gates

The authoritative gate file is
`packaging/windows/release-validation.json`. It requires:

- NVIDIA Vulkan validation
- Intel Vulkan validation
- AMD Vulkan validation
- launch and packaged smoke validation from a separate Windows account without
  Python or uv installed

Every passed entry contains the Real-CUGAN SHA-256 and the SHA-256 of its source
JSON evidence. The distribution audit loads each evidence file, verifies its
hash, revalidates its contents, and confirms that all reports use the engine
bundled in `dist/MangaCrisp`. Clean-account evidence must also match the exact
`MangaCrisp.exe`; release packaging additionally requires the exact candidate
ZIP SHA-256.

Current status:

| Gate | Status |
|---|---|
| NVIDIA GeForce RTX 2070 SUPER | Passed |
| Intel Vulkan GPU | Pending |
| AMD Vulkan GPU | Pending |
| Separate clean Windows account | Pending |

Interactive checks on the development account passed application launch,
bookshelf import, reader rendering, and original/enhanced comparison on
2026-07-27. On 2026-08-03, the packaged 0.7.0b0 application also passed direct
color-PDF opening, lazy page navigation, and color-preserving original/enhanced
comparison with the bundled PDFium and Real-CUGAN engine. The distribution
audit reported `baseline_ready=true`, and the extracted ZIP passed the
sanitized-environment smoke test. These checks are useful product evidence but
do not replace the separate clean-account gate.

On 2026-08-13, the Windows 0.7.1b0 development build passed the full source
suite, Windows global-hotkey message delivery, fixed-region color capture,
numbered PNG-to-CBZ packaging, packaged Capture-controller launch, and packaged
Spread/Single Page switching with the redistributable Pepper&Carrot demo. Its
distribution audit reported `baseline_ready=true`, and the final local candidate
passed the sanitized-environment ZIP smoke test. These checks likewise do not
replace Intel, AMD, or separate clean-account evidence.

## Record a GPU report

Use the exact staged engine or the engine extracted from the candidate portable
ZIP. Do not rebuild it independently on the test machine unless the resulting
SHA-256 is identical.

Run the fixed redistributable demo:

```powershell
uv run python scripts/validate_realcugan_windows.py `
  --engine path\to\realcugan-ncnn-vulkan.exe `
  --gpu-label "GPU and machine label"
```

The script verifies the engine provenance and runtime mode, processes the first
page from the pinned Pepper&Carrot demo archive, checks the doubled output
dimensions, and writes `build/windows/realcugan-validation.json`. The report
does not contain user names or absolute local paths.

Record it under the matching vendor:

```powershell
uv run python scripts/record_windows_release_validation.py `
  --gpu-family intel `
  --report build\windows\realcugan-validation.json
```

Use `nvidia`, `intel`, or `amd`. Registration fails if the reported GPU vendor,
fixed recipe, demo hash, runtime dependency mode, provenance, output, or engine
SHA-256 is inconsistent.

## Record a clean-account report

Copy only these items to a separate Windows 10 or 11 account that has no Python
or uv installation:

- the candidate portable ZIP
- `scripts/validate_windows_clean_account.ps1`

First extract the ZIP normally, double-click `MangaCrisp.exe`, and confirm that
the bookshelf opens. Then run the standalone PowerShell validator:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\validate_windows_clean_account.ps1 `
  -Archive .\MangaCrisp-0.5.0b0-windows-x64-portable.zip `
  -Report .\clean-windows-account.json `
  -ConfirmSeparateAccount `
  -ConfirmInteractiveLaunch
```

The validator uses only Windows PowerShell facilities. It checks that Python
and uv are absent, extracts the candidate to a temporary directory, hashes the
archive, application, and engine, and runs the packaged smoke test with only
Windows system directories on `PATH`. It records no account name or local
absolute path.

Copy the resulting JSON back to the development checkout and record it:

```powershell
uv run python scripts/record_windows_release_validation.py `
  --clean-account `
  --report path\to\clean-windows-account.json
```

## Final audit

Run:

```powershell
uv run python scripts/audit_windows_distribution.py --require-engine
```

`baseline_ready=true` confirms that the local package itself passes. A public
Development Preview additionally requires the rebuilt engine to match the
committed NVIDIA evidence and permits only the three documented external
blockers. A stable release candidate requires `release_ready=true`. Never edit
a `passed` value by hand; record the source report so the audit can verify it.
