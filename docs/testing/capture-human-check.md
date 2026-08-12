# Sequential Capture Human Check

Target: MangaCrisp for macOS on Apple Silicon.

Use only images you own or are authorized to capture. The Pepper&Carrot archives under `demo/`
are provided under CC BY 4.0 and are suitable for this check.

## First-run permission

1. Open `MangaCrisp.app`, then choose **Screen Capture** on the bookshelf.
2. Select a region and choose **Start Capture**.
3. Open System Settings when macOS asks for Screen Recording access. If you dismiss the prompt,
   use **Open Screen Recording Settings** in the Capture window.
4. Enable MangaCrisp under Privacy & Security > Screen & System Audio Recording (or Screen
   Recording on earlier macOS releases).
5. Quit MangaCrisp completely and open it again.

The packaged app has its own macOS permission identity, so this is required once even when the
development build was already allowed. MangaCrisp does not upload captured images or metadata.

## Ten-page check

1. Add Pepper&Carrot v01 and v02 from `demo/`, then open v01. Together they contain ten pages.
2. Open Screen Capture and name the session `Capture Human Check`.
3. Select only the page area, leaving about 70px outside the region above or below for feedback.
4. Start capture. After the controller minimizes, return to the comic.
5. Press `Command+Option+C` once per page. After v01, use **Next Volume** to open v02 and continue
   until ten pages are saved. The transient message and Dock badge show the saved count.
6. Press `Command+Option+Z` once, then recapture that page and continue to ten.
7. Return to the controller and confirm thumbnails `000001` through `000010`.
8. Reorder two pages, deliberately capture one duplicate, confirm the warning, then delete it.
9. Select CBZ, keep **Add to Bookshelf when complete** enabled, and create the finished file.
10. Open the result from the bookshelf and verify color, orientation, and page order.
11. Open the destination and verify that both the CBZ and the original numbered PNG files remain.

The check passes when each shortcut press creates exactly one image, undo reuses its number, ten
rapid captures do not freeze or skip a number, feedback stays outside the selected region, and the
completed CBZ can be read from the bookshelf.
