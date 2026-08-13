# Sequential Capture Human Check

Target: MangaCrisp for macOS on Apple Silicon.

Result: passed on 2026-08-13. The release candidate completed an 86-image
session and the checks below, including one-time completion and Single Page reading.

Use only images you own or are authorized to capture. The Pepper&Carrot archives under `demo/`
are provided under CC BY 4.0 and are suitable for this check.

## First-run permission

1. Open `MangaCrisp.app`, then choose **Screen Capture** on the bookshelf.
2. Select a region and choose **Start Capture**.
3. Open System Settings when macOS asks for Screen Recording access. If you dismiss the prompt,
   use **Open Screen Recording Settings** in the Capture window.
4. Enable MangaCrisp under Privacy & Security > Screen & System Audio Recording (or Screen
   Recording on earlier macOS releases).
5. If macOS offers **Quit & Reopen**, use it. If the app remains open, quit MangaCrisp normally
   and launch the same `MangaCrisp.app` again.
6. After relaunch, macOS may show a second prompt asking whether MangaCrisp may access private
   windows or on-screen content. Choose **Allow**. No further relaunch is needed for this prompt.
7. Confirm that the Capture window reports **Allowed (ready to capture)**.

The packaged app has its own macOS permission identity, so this is required once even when the
development build was already allowed. Rebuilding an ad-hoc signed development app also changes
its macOS identity, so do not rebuild between granting access and running this check. MangaCrisp
does not upload captured images or metadata.

## Ten-page check

1. Add Pepper&Carrot v01 and v02 from `demo/`, then open v01. Together they contain ten pages.
2. Open Screen Capture and name the session `Capture Human Check`.
3. Select only the page area, leaving about 70px outside the region above or below for feedback.
4. Start capture. Confirm that both MangaCrisp windows hide and the target comic stays in front.
5. Press `Option+C` once per page and continue until ten pages are saved. The MangaCrisp Dock icon
   briefly animates and its badge count increases after a successful save. The sound is supplemental.
   MangaCrisp must not come forward.
6. Press `Option+Z` once, then recapture that page and continue to ten.
7. Click MangaCrisp in the Dock. Confirm that only Capture returns, then check that the
   thumbnails run from `000001` through `000010`.
8. While capture is active, click Finish Capture. Confirm pending PNG saves complete and exactly one CBZ/ZIP is created.
9. Confirm the button changes to Completed and repeated clicks cannot create or import another archive.
10. Reorder two pages, deliberately capture one duplicate, confirm the warning, then delete it.
11. Open the result from the bookshelf and select **Single Page (1 image)** under Page Layout.
    Confirm that one captured full-spread image is centered at full width and normal arrows,
    Space, and side clicks advance exactly one image.
12. Press `V` to return to Spread and press `V` again to return to Single Page. Confirm Original /
    Enhanced comparison and AI enhancement apply to the complete current image.
13. Open the destination and verify that both the CBZ and the original numbered PNG files remain.

The check passes when each shortcut press creates exactly one image, undo reuses its number, ten
rapid captures do not freeze or skip a number, feedback stays outside the selected region, and the
completed CBZ can be read from the bookshelf. MangaCrisp must not steal focus while capturing;
**Back to Bookshelf** must restore the bookshelf explicitly. Single Page must display and advance
one captured image at a time without pairing it with another captured spread.
