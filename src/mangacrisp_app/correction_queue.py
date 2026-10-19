"""Thread-safe work queue for reader image correction jobs.

The reader has a UI thread that refreshes the set of pages it wants corrected
while a worker thread consumes that set.  This module deliberately has no Qt
dependency so the two sides can share one small synchronization boundary.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from threading import Lock


def pick_next_correction_index(
    priority: Sequence[int],
    queued: Iterable[int],
    targets: set[int] | None = None,
) -> int | None:
    """Return the first queued index in priority order that is still wanted."""
    queued_set = set(queued)
    for index in priority:
        if index in queued_set and (targets is None or index in targets):
            return index
    return None


class CorrectionQueue:
    """Synchronize pending and in-flight correction outputs across threads.

    ``reset`` replaces the pending work set.  ``refresh`` updates priority and
    adds work without discarding jobs already pending or currently running.
    ``take`` reserves at most one job at a time; callers must invoke
    ``complete`` after the worker finishes it, including after a failed run.
    All snapshots are copies, so callers cannot mutate queue state without the
    mutex.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._pending: dict[int, Path] = {}
        self._priority: list[int] = []
        self._in_flight: tuple[int, Path] | None = None

    def reset(
        self,
        output_paths: Mapping[int, Path],
        priority: Sequence[int],
    ) -> None:
        """Replace all pending work and priority with a new correction batch."""
        with self._lock:
            self._pending = dict(output_paths)
            self._priority = list(priority)
            self._in_flight = None

    def refresh(
        self,
        additions: Mapping[int, Path],
        priority: Sequence[int],
    ) -> None:
        """Update priority and append jobs that are not already pending.

        An addition may have the same index as the in-flight job.  Keeping that
        duplicate until ``complete`` mirrors the reader's old queue behavior;
        completion removes both the reservation and any duplicate pending item.
        """
        with self._lock:
            self._priority = list(priority)
            for index, output_path in additions.items():
                self._pending.setdefault(index, output_path)

    def take(self, targets: set[int] | None = None) -> tuple[int, Path] | None:
        """Reserve and remove the next eligible pending correction.

        Only one job may be in flight.  If no pending item is eligible for the
        supplied target set, all pending work is discarded while an already
        running job remains reserved and visible through ``active_outputs``.
        """
        with self._lock:
            index = pick_next_correction_index(self._priority, self._pending, targets)
            if index is None:
                self._pending.clear()
                return None
            if self._in_flight is not None:
                return None
            output_path = self._pending.pop(index)
            self._in_flight = (index, output_path)
            return index, output_path

    def complete(self, index: int) -> None:
        """Release ``index`` and discard a duplicate requeued while it ran."""
        with self._lock:
            self._pending.pop(index, None)
            if self._in_flight is not None and self._in_flight[0] == index:
                self._in_flight = None

    def clear(self) -> None:
        """Discard pending and in-flight work and its priority order."""
        with self._lock:
            self._pending.clear()
            self._priority.clear()
            self._in_flight = None

    @property
    def in_flight(self) -> int | None:
        """Index reserved by ``take``, or ``None`` when no job is running."""
        with self._lock:
            return None if self._in_flight is None else self._in_flight[0]

    @property
    def pending(self) -> dict[int, Path]:
        """Copy of pending output paths keyed by page index."""
        with self._lock:
            return dict(self._pending)

    @property
    def priority(self) -> list[int]:
        """Copy of the current page priority order."""
        with self._lock:
            return list(self._priority)

    @property
    def active_outputs(self) -> set[Path]:
        """Output paths for the in-flight job and all pending jobs."""
        with self._lock:
            active = set(self._pending.values())
            if self._in_flight is not None:
                active.add(self._in_flight[1])
            return active


__all__ = ["CorrectionQueue", "pick_next_correction_index"]
