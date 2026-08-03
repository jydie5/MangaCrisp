# PDF, Comic EPUB, and OPDS product design

Status: design baseline for implementation planning
Implementation order: PDF, Comic EPUB, OPDS 1.2
Scope: shared macOS and Windows behavior

## Product goal

MangaCrisp should read more legally obtained, DRM-free comics without becoming
a general-purpose document browser or ebook store. New sources must preserve
the product's existing strengths:

- the first readable page appears quickly;
- right-to-left and left-to-right spreads remain correct;
- reading remains available when AI enhancement is unavailable;
- enhancement is prepared around the current position, not for the whole book;
- imported books work offline and remain under the user's control;
- macOS and Windows expose the same reading behavior.

The three phases are intentionally ordered:

1. PDF adds the most common scanned-document container.
2. Comic EPUB adds publisher-neutral fixed-layout comics.
3. OPDS connects the same local reader to existing personal libraries.

## Non-goals

The first implementation does not include:

- DRM removal or support for Kindle, Kobo, Apple Books, or Adobe-protected
  publications;
- reflowable text EPUB, font controls, annotations, text-to-speech, or
  dictionary features;
- JavaScript execution or unrestricted remote content inside Comic EPUB;
- an OPDS server hosted by MangaCrisp;
- server-side AI processing;
- OPDS reading-progress synchronization;
- reading a remote publication while it is still streaming.

Unsupported files must produce a specific explanation. They must never be
silently imported with missing pages, overlays, text, or reading order.

## Shared publication contract

The current viewer consumes a `Sequence[Path]`. Preserve that interface during
the first implementation by introducing a lazy publication adapter:

```text
PublicationProbe
  inspect(source) -> PublicationMetadata

PublicationPageSource (Sequence[Path])
  page_count
  page(index) -> materialized local image Path
  page_info(index) -> PageInfo
  close()
```

`PublicationPageSource` materializes only the requested page. The returned path
is then used by the existing display decode, Real-CUGAN correction, comparison,
prefetch, and revolving-cache logic. This keeps format parsing out of
`viewer.py`.

Required implementations:

- `FolderPageSource`
- `ArchivePageSource`
- `PdfPageSource`
- `FixedLayoutEpubPageSource`

The factory that opens a book selects the implementation by inspected content,
not only by the filename extension. Existing archive behavior must continue to
pass through the same contract.

```mermaid
flowchart LR
    A["File, folder, or OPDS download"] --> B["Probe and validate"]
    B --> C["Managed original and metadata"]
    C --> D["Page-source factory"]
    D --> E["Lazy rendered-page cache"]
    E --> F["Existing viewer and prefetch"]
    F --> G["Existing AI enhancement cache"]
```

### Publication metadata

The common probe returns:

```text
title
authors
series
volume
format
page_count
cover_page_index
reading_direction: rtl | ltr | unknown
layout: paginated | fixed | reflowable
content_fingerprint
capabilities
warnings
```

Filename-derived metadata remains a fallback. Embedded metadata takes
precedence only when it is present and valid.

### Page information

Each page may report:

```text
intrinsic_width
intrinsic_height
spread_position: left | right | center | unspecified
source_kind: raster | vector | mixed
enhancement_recommendation: automatic | original_preferred
```

The existing cover-single rule applies when the source does not provide a
spread position. Explicit EPUB spread metadata takes precedence.

## Storage and cache contract

Persistent library storage and disposable cache storage have different roles.

```text
MangaCrisp Library/
  <managed-book>/
    original/
      <original PDF, EPUB, or archive>
    pages/
      <existing fully extracted archive pages only>
    cover.*

MangaCrisp cache/
  rendered/
    <content-fingerprint>/<renderer-version>/<render-profile>/<page>.png
  upscale/
    <existing correction-key>/<page>.png
```

Requirements:

- importing PDF or EPUB copies the original publication into managed library
  storage and creates the cover, but does not render every page;
- the source file selected by the user is never deleted;
- page rendering is atomic: write to a temporary file, validate it, then rename;
- cache keys include the source fingerprint, renderer version, color mode,
  target dimensions, and page index;
- replacing or modifying a source produces a new fingerprint and cannot reuse
  stale rendered or enhanced pages;
- deleting a book deletes its managed copy and eligible caches, but never the
  user's original source;
- rendered pages use a global LRU disk budget, initially 2 GiB and configurable
  later;
- the existing revolving AI cache remains centered on the reading position.

## Local import and bookshelf experience

- PDF and EPUB appear in the existing multi-file picker and drag-and-drop
  targets;
- the confirmation dialog describes the actual action per format:
  archives are extracted, while PDF/EPUB are copied and indexed;
- mixed batches summarize each action and continue processing other valid books
  when one item fails;
- import remains sequential in the first implementation to avoid saturating
  disk, CPU, and thumbnail rendering;
- a newly registered PDF/EPUB card appears after metadata and cover processing,
  without waiting for page rendering or AI enhancement;
- cards may show a small PDF, EPUB, or network-source label, but format must not
  replace the title or volume text;
- double-click, `Read`, next-volume navigation, deletion, bookmarks, and reading
  progress behave the same as archive books;
- opening a book whose managed original is missing reports the missing path and
  offers removal from the bookshelf; it does not recreate content from a
  remote URL without confirmation.

## Phase 1: PDF

### Supported input

- local `.pdf` files;
- unencrypted PDFs;
- raster, vector, and mixed pages;
- standard page sizes and pages with different sizes in the same file;
- embedded title, author, page labels, and outline when available.

Password-protected PDF is detected and reported separately. A later increment
may accept a session-only password; passwords must not be stored in SQLite or
plain-text settings.

### Rendering design

Use `pypdfium2` as the primary implementation candidate because it supports
headless, cross-platform, on-demand rendering with a permissive PDFium license.
Before adopting it, complete a dependency spike that verifies:

- arm64 macOS and x64 Windows packaging;
- RGB and grayscale color preservation;
- rendering from worker threads;
- corrupt and password-protected document errors;
- bundled binary size and third-party notices;
- deterministic output dimensions.

`PySide6.QtPdf.QPdfDocument` is the fallback candidate because PySide6 already
ships the Qt PDF API. It must not be mixed into worker threads without a proven
Qt object-thread ownership design.

Render only the current spread first, then feed future requests through the
existing prefetch scheduler. Render dimensions are derived from the display
target and enhancement scale; do not rasterize every PDF at a fixed high DPI.

### Enhancement behavior

- a rendered PDF page enters the same color-preserving enhancement pipeline as
  archive images;
- sufficiently large pages follow the existing skip-height behavior;
- vector or mixed pages default to `original_preferred` in automatic mode to
  avoid degrading clean text and vector lines;
- users may explicitly select an enhancement preset for scanned PDFs;
- original/comparison switching must change both pages of a spread together.

### PDF acceptance criteria

- a 300-page PDF is registered without rendering 300 pages;
- the cover is visible after import;
- opening at page 1 and reopening at a saved page both show a readable original
  before background enhancement;
- mixed portrait and landscape pages preserve aspect ratio;
- color pages remain color;
- a corrupt, encrypted, or zero-page PDF shows an actionable message;
- repeated navigation reuses rendered and enhanced caches;
- deleting the book leaves the user's source PDF untouched.

## Phase 2: Comic EPUB

### Supported profile

The first release supports DRM-free EPUB 2/3 publications that can be mapped
losslessly to a fixed sequence of visual pages:

- package metadata declares fixed/pre-paginated layout; or
- every spine item is a direct image, SVG page, or XHTML page containing one
  full-page local image with no required script or remote resource;
- spine order defines page order;
- `page-progression-direction` defines RTL or LTR when present;
- `page-spread-left`, `page-spread-right`, and equivalent rendition properties
  define spread placement;
- embedded cover metadata supplies the bookshelf cover.

The parser reads `META-INF/container.xml`, the OPF manifest, metadata, and spine
using namespace-aware XML parsing. It must not infer order by sorting ZIP member
names.

### Explicitly unsupported in the first release

- reflowable text EPUB;
- DRM-encrypted EPUB;
- scripted or interactive content;
- pages that require remote fonts, styles, images, audio, or video;
- complex XHTML/CSS composition that cannot be represented without loss;
- media overlays and read-aloud behavior.

When an EPUB is valid but outside this profile, the message should say
`This EPUB uses a text or interactive layout that MangaCrisp does not support
yet`, not `file is broken`.

### Security requirements

Treat every EPUB as an untrusted ZIP:

- reject absolute paths, parent traversal, drive prefixes, NULs, and unsafe
  normalized paths;
- disable XML external entities and network resolution;
- enforce limits for member count, individual uncompressed size, total
  uncompressed size, and compression ratio;
- never execute JavaScript;
- never fetch remote resources while rendering;
- validate declared media types against file signatures where practical.

### Comic EPUB acceptance criteria

- RTL and LTR samples open with the correct page order;
- cover-single and explicit spread positions produce the intended spreads;
- image-only XHTML, direct image spine items, and supported SVG pages render;
- color and transparency are preserved;
- an EPUB with shuffled ZIP member names still follows OPF spine order;
- reflowable, scripted, remote-resource, DRM, malformed, and zip-bomb fixtures
  are rejected with distinct errors;
- only current and prefetched pages are materialized.

## Phase 3: OPDS 1.2

### User experience

Add `Network libraries` to the bookshelf:

1. The user adds a catalog name and OPDS URL.
2. MangaCrisp validates the connection and authentication.
3. The user browses navigation feeds, paginated acquisition feeds, and search
   when advertised.
4. A publication card shows cover, title, author, format, and download state.
5. Selecting `Download and add to bookshelf` downloads to a temporary file,
   verifies it, and imports it through the same local pipeline.
6. Downloaded books are fully readable offline.

The first release is download-first. It does not stream pages directly into the
viewer. This avoids network stalls in the reading loop and keeps enhancement,
deletion, and cache behavior identical to local books.

### Interoperability target

Target OPDS 1.2 first and test against current releases of:

- Komga;
- Kavita;
- Calibre Content Server.

Required protocol behavior:

- Atom navigation and acquisition feeds;
- relative URL resolution;
- `next`, `previous`, `start`, `search`, `self`, and acquisition relations;
- CBZ, CBR, PDF, and EPUB acquisition media types;
- cover and thumbnail relations;
- HTTP Basic and Digest authentication;
- redirects, timeouts, cancellation, and resumable retry from the UI;
- Unicode titles, authors, and URLs.

OPDS 2.0 and proprietary Komga/Kavita APIs are later extensions. Progress sync
is not part of OPDS 1.2 and must not be implied by the first implementation.

### Credential and network security

- save non-secret catalog settings in SQLite;
- save secrets through macOS Keychain and Windows Credential Manager via a
  reviewed credential-store adapter;
- never include credentials in URLs, logs, database rows, or error reports;
- require valid HTTPS certificates by default;
- allow plain HTTP only after an explicit per-server warning, primarily for
  local networks;
- do not forward authorization headers to a different origin after redirect;
- apply connection, response, and total-download timeouts;
- limit feed size, XML depth, download size, and redirect count;
- disable XML external entities;
- download to cache, validate content type and signature, then atomically move
  into managed storage;
- cancellation removes incomplete temporary files.

### OPDS data model

Add a schema migration rather than overloading `books.source_uri`:

```text
catalogs
  id
  name
  base_url
  auth_kind
  credential_key
  allow_insecure_http
  created_at
  updated_at

remote_publications
  catalog_id
  remote_id
  title
  authors_json
  cover_url
  acquisition_url
  media_type
  remote_updated_at
  local_book_id
  PRIMARY KEY (catalog_id, remote_id)
```

`credential_key` is an opaque keychain lookup identifier, never the secret.
After download, the regular `books` row remains the source of reading state and
bookmarks. Removing a catalog does not delete already downloaded books.

### OPDS acceptance criteria

- Komga, Kavita, and Calibre catalogs can be added and browsed;
- Basic/Digest authentication works without exposing credentials;
- pagination and search do not freeze the bookshelf;
- downloads show queued, downloading, validating, imported, failed, and
  cancelled states;
- duplicate acquisition resolves to the existing local book;
- network loss never prevents opening an already downloaded book;
- an invalid certificate, insecure redirect, oversized feed, malformed XML,
  unsupported media type, and interrupted download have distinct messages;
- deleting a catalog and deleting a downloaded book remain separate actions.

## Performance budgets

These are acceptance targets, not renderer implementation details:

| Operation | Target |
|---|---:|
| Probe local PDF/EPUB metadata | under 1 second for a typical book |
| Show imported cover | under 2 seconds after metadata probe |
| Open cached current spread | under 100 ms |
| Show uncached PDF/EPUB original spread | under 500 ms on the reference M4 Pro |
| React to page input | under 50 ms, with original fallback |
| OPDS feed UI response | never block the UI thread |
| Cancel network download | visible response under 250 ms |

Large-file tests must cover at least 300 pages, 2 GiB source size where fixtures
permit sparse/generated data, rapid forward/backward navigation, and 10 minutes
of reading without unbounded memory or disk growth.

## Implementation sequence

### Foundation

1. Add the publication metadata and lazy page-source contracts.
2. Adapt folders and existing archives without changing visible behavior.
3. Add format-independent tests for lazy materialization, lifecycle, cache
   identity, and spread metadata.

### PDF

1. Complete the renderer/license/packaging spike.
2. Add PDF probe, managed import, cover generation, and lazy rendering.
3. Integrate enhancement recommendation and cache invalidation.
4. Validate both release packages and physical macOS/Windows devices.

### Comic EPUB

1. Add safe EPUB container and OPF parser.
2. Implement the supported fixed-layout profile and capability diagnostics.
3. Add malicious and unsupported fixtures.
4. Validate RTL/LTR spread behavior and color enhancement.

### OPDS

1. Add catalog storage and credential adapter.
2. Add protocol client and parser tests using a local deterministic server.
3. Build asynchronous browse/search/download UI.
4. Import downloads through the existing publication pipeline.
5. Run compatibility tests against Komga, Kavita, and Calibre.

Each phase is a separate `core/` pull request series. Platform packaging changes
follow only after the shared implementation is merged.

### Proposed issue breakdown

1. Define publication metadata, capability errors, and lazy page-source API.
2. Move folder/archive opening behind the common page-source factory.
3. Spike and select the cross-platform PDF renderer.
4. Add PDF probe, managed import, cover, and lazy rendering.
5. Integrate PDF rendering with display and enhancement cache policy.
6. Add safe EPUB container/OPF parsing and fixed-layout capability detection.
7. Add Comic EPUB lazy page materialization and spread metadata.
8. Add catalog/remote-publication migrations and credential storage adapters.
9. Add the OPDS 1.2 client with deterministic mock-server tests.
10. Add network-library browse, search, download, and cancellation UI.
11. Validate Komga, Kavita, and Calibre interoperability.
12. Audit and package new runtime dependencies on macOS and Windows.

## Test fixture policy

- commit only generated, public-domain, or explicitly redistributable fixtures;
- keep small PDF and EPUB fixtures deterministic and document their creation;
- generate malformed, encrypted, oversized-header, and traversal fixtures in
  tests where possible;
- use a local mock OPDS server in CI;
- keep private library URLs, credentials, and copyrighted books out of the
  repository and test logs.

## Decision record

- PDF is rendered lazily, not converted in full during import.
- Comic EPUB means a losslessly supported fixed-layout subset, not all EPUB.
- OPDS is a catalog/download source; MangaCrisp remains a local-first reader.
- Downloaded OPDS books use the same library, page, enhancement, and reading
  state path as local books.
- Existing viewer behavior is protected through a lazy `Sequence[Path]`
  adapter before any larger viewer API refactor.

## References

- Qt PDF for Python: https://doc.qt.io/qtforpython-6/PySide6/QtPdf/
- pypdfium2: https://pypdfium2.readthedocs.io/
- EPUB 3.3: https://www.w3.org/TR/epub-33/
- OPDS 1.2: https://specs.opds.io/opds-1.2.html
