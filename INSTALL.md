# Installing MangaCrisp

[English](INSTALL.md) | [日本語](INSTALL.ja.md)

## Requirements

- An Apple Silicon Mac (M1, M2, M3, M4, or A18 Pro MacBook Neo)
- macOS 13 or newer is recommended
- About 300 MB for the application and bundled AI engine
- Additional space for extracted reading copies

Intel Macs are not supported by the current standalone build.

The A18 Pro MacBook Neo is expected to be compatible because both MangaCrisp and its
bundled Real-CUGAN engine are native `arm64` executables and the engine uses
Metal. It has not yet been tested on physical MacBook Neo hardware. Its 8 GB of
unified memory and smaller GPU may reduce AI prefetch throughput compared with
M-series Pro Macs. See [Hardware compatibility](docs/hardware-compatibility.md).

## Download

1. Open [MangaCrisp Releases](https://github.com/jydie5/MangaCrisp/releases).
2. Expand the latest release's Assets section.
3. Download the file whose name contains `standalone.zip`.
4. Do not download GitHub's automatically generated `Source code` archives
   unless you intend to develop MangaCrisp.

The `.sha256` file is provided for integrity verification.

## Install and launch

1. Double-click the downloaded ZIP.
2. Drag `MangaCrisp.app` to the Applications folder.
3. In Applications, Control-click `MangaCrisp.app` and choose **Open**.
4. Choose **Open** again in the confirmation dialog.

Normal double-click launching should work afterward.

## Choose the interface language

MangaCrisp follows the first preferred language in macOS and includes English and
Japanese. Use the **Language** selector in the bookshelf header to override the
system choice, then restart MangaCrisp.

## If macOS blocks the app

The current beta does not have an Apple Developer ID signature or notarization.
Confirm that the app came from this GitHub repository, then:

1. Try opening `MangaCrisp.app` once and close the warning.
2. Open **System Settings**.
3. Open **Privacy & Security**.
4. Find the MangaCrisp message and choose **Open Anyway**.

There is no need to disable macOS security features. If the app still does not
launch, report the macOS version, Mac model, downloaded filename, and exact
warning text in [GitHub Issues](https://github.com/jydie5/MangaCrisp/issues).

## Add a book

Drag any supported item onto the bookshelf:

- ZIP / CBZ
- RAR / CBR
- 7z / CB7
- A folder containing images
- An individual image

After confirmation, MangaCrisp creates a managed reading copy in
`~/MangaCrisp Library` and adds its cover to the bookshelf. On the first launch
after upgrading, the previous default `~/RAIV Library` is renamed to this
location without copying its contents. User-selected custom locations remain
unchanged. The source file is not deleted.

The repository's [`demo`](demo) directory contains freely licensed ZIP files
that can be used for a first test.

## Allow Screen Recording for capture

Sequential Screen Capture is an optional macOS beta feature. Use it only for
screens you own or are authorized to save. It does not automate page turns,
bypass capture protection, or upload captured images.

The first capture needs macOS Screen Recording permission:

1. Open **Sequential Screen Capture** from the bookshelf.
2. Select a region and choose **Start Capture**.
3. When prompted, open **System Settings > Privacy & Security > Screen & System
   Audio Recording** (called **Screen Recording** on some macOS versions).
4. Enable MangaCrisp. If **Quit & Reopen** leaves the app open, quit MangaCrisp
   completely yourself and reopen the same installed `MangaCrisp.app`.
5. If macOS then asks whether MangaCrisp may access on-screen content, choose
   **Allow**. This second prompt does not normally require another restart.
6. Confirm that the Capture window says **Allowed (ready to capture)**.

macOS identifies the packaged app separately from a source build. Replacing or
rebuilding an ad-hoc signed development app can therefore require permission
again. Grant access to the copy in Applications and continue using that same
copy for the session.

### Capture and finish a book

1. Set a session name, output folder, display, and fixed capture region.
2. Start capture. MangaCrisp hides its bookshelf and controller without taking
   focus back from the source application.
3. Press `Option+C` once per image. Press `Option+Z` to undo the last image.
   Each successful capture is immediately saved as a numbered color PNG.
4. Click MangaCrisp in the Dock to restore the controller. The bookshelf stays
   hidden until you explicitly choose **Back to Bookshelf**.
5. Choose **Finish Capture**. MangaCrisp stops capture, waits for pending PNG
   saves, creates one CBZ/ZIP, and can add it to the bookshelf. Repeated clicks
   cannot package the same page set again.

The session folder keeps `pages/000001.png`, `000002.png`, and so on beside the
finished archive. When each PNG contains a complete two-page spread, open the
book and press `V` to use **Single Page (1 image)** layout.

The detailed acceptance procedure is in
[docs/testing/capture-human-check.md](docs/testing/capture-human-check.md).

## Compare AI enhancement

1. Open a book.
2. Press `P` to show Reading Settings.
3. Wait until the status indicates that the visible pages are enhanced.
4. Toggle **Show original**.

Enabled displays the source page; disabled displays the enhanced page. A
high-resolution page or a page still waiting for processing may look unchanged,
and the status panel explains why.

## Update

Download a newer standalone ZIP and replace the old `MangaCrisp.app`. The bookshelf
and reading positions are stored outside the app and are normally preserved.

## Report a problem

Open a [GitHub Issue](https://github.com/jydie5/MangaCrisp/issues) and include:

- Mac model
- macOS version
- MangaCrisp version
- Archive format
- Reproduction steps
- Exact error text

Do not upload copyrighted manga archives or page images.
