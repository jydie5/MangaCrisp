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
