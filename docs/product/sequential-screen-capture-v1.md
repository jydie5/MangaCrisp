# Sequential Screen Capture v1 Requirements and Design

Updated: 2026-08-13

Status: initial implementation and macOS human acceptance completed on
2026-08-13. Included as a macOS beta feature in v0.7.1-beta.

Related documents:

- [Initial discussion and legal/product boundaries](sequential-screen-capture.ja.md)
- [Cross-platform workflow](../development/cross-platform-workflow.md)
- [macOS human check](../testing/capture-human-check.md)

## v1 decisions

| Area | Decision |
|---|---|
| Product surface | A separate compact Capture controller launched from the MangaCrisp bookshelf |
| First platform | macOS on Apple Silicon; keep the core reusable on Windows |
| Required target | A fixed rectangle selected by the user |
| Optional target | Full display; defer window-specific capture |
| Page turning | Manual, in the target application |
| Trigger | One image per configurable global shortcut press |
| Image | Color-preserving PNG with no AI enhancement or color reduction |
| Package | CBZ by default, ZIP as an option |
| Feedback | Dock animation and a saved-page badge are primary; the shutter sound is supplemental |
| Completion | Finish is available during capture, stops capture, drains pending PNG saves, then creates one archive |
| Duplicate prevention | A completed page set cannot be packaged or imported again until its pages change |
| Source PNGs | Keep after packaging unless the user explicitly deletes them |
| Spread splitting | Deferred; one visible capture becomes one image |
| Automation | No automatic page turning, unattended capture, or capture-protection bypass |

Starting capture hides both the controller and bookshelf so they cannot cover or
activate over the target app. Clicking MangaCrisp in the Dock restores only the
controller; **Back to Bookshelf** explicitly restores the bookshelf. MangaCrisp
still owns the entry point, settings, and session history.

## User flow

1. Open Capture from the bookshelf camera action.
2. Choose a session name, output location, and shortcut.
3. Drag a fixed capture rectangle and confirm its physical pixel dimensions.
4. Resolve macOS Screen Recording permission if required.
5. Start the session and switch to the target application.
6. Press the shortcut once per page; turn pages manually.
7. Undo or retake pages when necessary.
8. Review thumbnails, duplicates, and failure warnings.
9. Export an atomic CBZ/ZIP and optionally add it to the bookshelf.

Defaults are `Option+C` for capture and `Option+Z` for undo. Legacy
`Command+Option+C/Z` and conflict-avoidance `Control+Return/Delete` remain
selectable. The session must not start if registration fails.

## Functional requirements

- Create a collision-free directory for each session.
- Reuse a fixed physical-pixel capture rectangle.
- Convert logical coordinates correctly on Retina and mixed-scale displays.
- Register a global shortcut without a generic keylogger permission.
- Save exactly one six-digit PNG for one accepted trigger.
- Persist each PNG immediately; completion only finalizes order, CBZ/ZIP, and optional bookshelf cover import.
- Use temporary files and atomic replacement; never silently overwrite pages.
- Support last-page undo and same-number retake.
- Support review ordering, deletion, rotation, and selected-page retake.
- Detect exact SHA-256 duplicates and preferably perceptual near-duplicates.
- Warn about black, transparent, and unreasonably small frames without bypassing
  the source application's behavior.
- Build and verify naturally ordered CBZ/ZIP output.
- Recover incomplete sessions after restart.
- Stop safely on permission loss, display removal, disk exhaustion, or capture
  failure.
- Hide the bookshelf and controller during capture without activating over the
  target application.
- Restore only the controller from the Dock and restore the bookshelf only on
  an explicit action.
- Read captured full-spread images in a viewer Single Page mode that centers
  one image at full reader width and advances one image per normal page turn.

## Non-goals

- Service-specific acquisition modes
- DRM, encryption, black-screen, or capture-protection bypass
- Process injection, memory extraction, internal-image extraction, or traffic
  interception
- Automatic page turns, continuous capture, or unattended full-book capture
- Watermark or rights-information removal
- Cloud sync, sharing, publishing, OCR, or PDF output
- JPEG/WebP/AVIF, automatic spread splitting, crop, or deskew

## Architecture

```text
src/mangacrisp_app/
  capture/
    models.py
    session.py
    coordinator.py
    validation.py
    package.py
    review_model.py
  capture_window.py
  region_selector.py
  platform/
    capture_base.py
    capture_macos.py
    capture_windows.py
```

The bookshelf only launches the controller. Capture must not couple the
bookshelf database, reader correction cache, Real-CUGAN, or PDF renderer to the
capture pipeline.

```python
class ScreenCaptureBackend(Protocol):
    def permission_state(self) -> PermissionState: ...
    def request_permission(self) -> PermissionState: ...
    def list_displays(self) -> list[CaptureDisplay]: ...
    def capture_region(self, region: PhysicalRect) -> CapturedFrame: ...
    def register_hotkeys(self, bindings: HotkeyBindings, callback: Callable) -> None: ...
    def unregister_hotkeys(self) -> None: ...
```

The state machine is:

```text
IDLE -> CONFIGURING -> PERMISSION_REQUIRED -> READY
READY -> CAPTURING -> SAVING -> READY
READY -> REVIEWING -> PACKAGING -> COMPLETE
CAPTURING/SAVING/PACKAGING -> ERROR -> READY or REVIEWING
```

Capture and save use one ordered worker queue. PNG compression, hashing, and
archive creation never run on the Qt UI thread. At most three unsaved frames
may be resident; further triggers are rejected visibly rather than dropped.

## Session data

```text
<chosen output>/
  <safe-name>-capture-<YYYYMMDD-HHMMSS>/
    pages/000001.png
    pages/000002.png
    .undo/
    manifest.json
    <safe-name>.cbz
```

Manifest schema version 1 stores creation time, capture mode, physical pixel
size, final page order, relative filenames, SHA-256, perceptual hash, warnings,
and output format. It must not store the target application name, window title,
user name, or absolute local paths. The CBZ contains only numbered images in
v1, not the private session manifest.

## macOS backend result

Before selecting a dependency, compare public-API prototypes for
ScreenCaptureKit and Qt fixed-region screen capture. Prefer ScreenCaptureKit,
but do not add it to the application until the prototype proves:

- correct Retina pixels and mixed-scale multi-display coordinates
- foreground and full-screen target operation
- explicit permission-denial detection
- distributable packaging with complete notices
- global shortcuts without generic keyboard-monitoring access
- ten sequential captures without gaps

The initial implementation uses Qt `QScreen.grabWindow` plus public macOS
framework APIs without adding a runtime dependency. On the M4 Pro development
Mac it reports and captures the full `3456x2234` display coordinate space in
color RGBA, and it detects Screen Recording permission. Global shortcuts use
Carbon `RegisterEventHotKey`, which does not require generic keyboard
monitoring or Accessibility permission. ScreenCaptureKit remains the fallback
if human testing finds failures with multiple displays, Spaces, or full-screen
targets.

## Quality targets

- Start capture within 100ms of an accepted shortcut where practical.
- Normally confirm a saved image within 300ms.
- Keep no more than three unsaved frames in memory.
- Create no missing or duplicate sequence numbers in a ten-page run.
- Preserve source PNGs if packaging fails.
- Send no image or session data over the network.
- Provide complete Japanese and English UI and button alternatives for every
  shortcut action.

## Test and delivery order

1. `core/capture-session`: TDD for models, numbering, atomic saves, recovery,
   validation, and CBZ generation.
2. `macos/capture-spike`: permission, pixel scaling, full screen, hotkeys, and
   packaging proof.
3. `macos/capture-backend`: implement the selected backend.
4. `core/capture-ui`: controller, region selector, and review UI.
5. Connect the bookshelf entry and optional bookshelf import.
6. Run distribution audit, automated tests, and the ten-page Mac human check.

The first human check passed on an Apple Silicon Mac with 86 sequential
captures, audible and visual feedback, immediate PNG persistence, one-time
archive completion, bookshelf import, and Single Page reading. Window capture,
spread splitting, JPEG output, and further automation remain deferred.
