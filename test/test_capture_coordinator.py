from __future__ import annotations

from pathlib import Path
from threading import Event

import pytest
from PIL import Image

from mangacrisp_app.capture.coordinator import CaptureCoordinator, CaptureQueueFullError
from mangacrisp_app.capture.session import CaptureSession


def test_coordinator_preserves_submission_order(tmp_path: Path) -> None:
    session = CaptureSession.create(tmp_path, "Queue")
    coordinator = CaptureCoordinator(session)
    colors = [(240, 10, 10), (10, 240, 10), (10, 10, 240)]

    futures = [coordinator.submit(Image.new("RGB", (160, 240), color)) for color in colors]

    assert [future.result().position for future in futures] == [1, 2, 3]
    coordinator.close()


def test_coordinator_rejects_more_than_three_pending_images(tmp_path: Path, monkeypatch) -> None:
    session = CaptureSession.create(tmp_path, "Queue Limit")
    release = Event()
    original_capture = session.capture

    def delayed_capture(image, *, replace_position=None):
        release.wait(timeout=2)
        return original_capture(image, replace_position=replace_position)

    monkeypatch.setattr(session, "capture", delayed_capture)
    coordinator = CaptureCoordinator(session, max_pending=3)
    image = Image.new("RGB", (160, 240), "white")
    coordinator.submit(image)
    coordinator.submit(image)
    coordinator.submit(image)

    with pytest.raises(CaptureQueueFullError):
        coordinator.submit(image)

    release.set()
    coordinator.close()
