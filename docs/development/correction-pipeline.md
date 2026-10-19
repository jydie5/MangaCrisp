# Reader correction and cache lifecycle

The correction pipeline is shared across macOS, Windows, and Linux. Keep its
cache and scheduling policies independent of Qt; the reader adapts them to UI
events and owns the worker generation.

| Module | Responsibility |
| --- | --- |
| `page_provider.py` | Materialize source pages lazily; provide stable PDF/ZIP page identities independent of temporary paths and LRU timestamps. |
| `correction_cache.py` | Map page identities and settings to output PNGs, load completed outputs, and apply disk capacity/age limits. |
| `correction_queue.py` | Synchronize pending jobs, visible-page priority, and one in-flight job between the UI and worker threads. |
| `engine_utils.py` | Run the engine, validate output dimensions and PNG contents, then atomically publish the result. |
| `display_cache.py` | Bound decoded display images while protecting both desired and fallback images of the current spread. |
| `viewer.py` | Select visible pages, react to navigation/settings, reject obsolete generations, and present ready spreads. |

## Job lifecycle

1. Navigation loads existing corrections and prioritizes missing visible pages.
   Resize debounce affects display quality, not correction scheduling.
2. The worker reserves one queued page. Navigation may update priority while
   that page finishes; it does not reset the in-flight reservation.
3. Engine output is written in a private temporary directory beside its final
   destination. Only a successful, verified PNG of the expected dimensions is
   atomically renamed to the final cache path. Failures preserve existing output.
4. The UI accepts a completion only if its generation and parameter key still
   match. Old-generation work may finish on disk but cannot replace the current
   display or current processed-page references.
5. A failed prefetch batch pauses retries while stationary. A page move or
   processing-settings change permits another attempt. Source-provider failures
   must also emit batch completion; error reporting must not materialize the
   failed source again.

## Cache invariants

- Image-folder keys retain the existing path/size/mtime identity. PDF keys use
  the source PDF fingerprint, render DPI, and page index. ZIP keys use the
  archive fingerprint and member identity, never the extraction directory.
- The engine's pro synchronization value and its cache-version suffix use the
  same constant. Older pro results are regenerated once after this change.
- Disk corrections survive distant navigation until age/capacity eviction.
  Each disk cache targets 2 GiB and 30 days. Protected active pages may exceed
  the size target temporarily. Final output paths and the entire staging
  directory of running jobs must survive cleanup, including empty directories.
- Disk-cache maintenance runs between completed pages as well as navigation.
  A new completion invalidates the previous maintenance signature.
- Display memory holds at most 18 decoded images under normal reader use.
  Current desired/fallback keys (at most four) are protected against late
  results from old pages. Navigation changes that protection, allowing old
  spreads to be evicted. Both corrected panes must be ready before switching.
- Cache access updates the disk LRU timestamp without repeatedly changing the
  display key. Deleted working-set references must be cleared before deciding
  whether a page needs correction.

## Verification

Run `uv run pytest -q` after changing the pipeline. The regression tests cover
late display completions, distant backtracking, active staging protection,
error recovery, resize-time navigation, provider reopening, and atomic engine
publication. Queue tests use controlled synchronization rather than timing
assumptions. The UI tests assert displayed pixels as well as cache bookkeeping.

For native validation, run a cold-cache correction while moving forward/back,
then repeat on a warm cache and confirm no engine calls occur. Build and smoke
test packaged applications on their target OS; source tests on macOS do not
replace Windows/Linux package validation.
