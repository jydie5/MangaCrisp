from __future__ import annotations

import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor

from PIL import Image

from mangacrisp_app.capture.models import CapturePage
from mangacrisp_app.capture.session import CaptureSession


class CaptureQueueFullError(RuntimeError):
    pass


class CaptureCoordinator:
    def __init__(self, session: CaptureSession, *, max_pending: int = 3) -> None:
        self.session = session
        self.max_pending = max_pending
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="capture-save")
        self._lock = threading.Lock()
        self._pending = 0
        self._closed = False

    @property
    def pending(self) -> int:
        with self._lock:
            return self._pending

    def submit(
        self,
        image: Image.Image,
        *,
        replace_position: int | None = None,
        callback: Callable[[CapturePage | None, BaseException | None], None] | None = None,
    ) -> Future[CapturePage]:
        with self._lock:
            if self._closed:
                raise RuntimeError("capture coordinator is closed")
            if self._pending >= self.max_pending:
                raise CaptureQueueFullError("capture save queue is full")
            self._pending += 1
        future = self._executor.submit(
            self.session.capture,
            image.copy(),
            replace_position=replace_position,
        )

        def finish(completed: Future[CapturePage]) -> None:
            with self._lock:
                self._pending -= 1
            if callback is None:
                return
            try:
                page = completed.result()
            except Exception as exc:  # noqa: BLE001 - Worker boundary reports errors to the UI.
                callback(None, exc)
            else:
                callback(page, None)

        future.add_done_callback(finish)
        return future

    def wait(self) -> None:
        barrier = self._executor.submit(lambda: None)
        barrier.result()

    def close(self, *, wait: bool = True) -> None:
        with self._lock:
            self._closed = True
        self._executor.shutdown(wait=wait, cancel_futures=False)
