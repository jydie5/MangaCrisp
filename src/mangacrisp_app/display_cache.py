"""Display cache policy, independent of Qt and correction workers.

Only the UI thread owns this cache. Values are decoded display images, not
durable correction outputs; eviction must never remove the visible spread.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Hashable, Iterator, Mapping
from collections.abc import Set as AbstractSet
from pathlib import Path
from typing import Generic, TypeVar

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


class DisplayCache(Mapping[K, V], Generic[K, V]):
    def __init__(self, capacity: int = 18) -> None:
        self.capacity = capacity
        self._items: OrderedDict[K, V] = OrderedDict()

    def __getitem__(self, key: K) -> V:
        value = self._items[key]
        self._items.move_to_end(key)
        return value

    def __iter__(self) -> Iterator[K]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, key: object) -> bool:
        return key in self._items

    def clear(self) -> None:
        self._items.clear()

    def put(self, key: K, value: V, *, protected: AbstractSet[K]) -> None:
        self._items[key] = value
        self._items.move_to_end(key)
        while len(self._items) > max(0, self.capacity):
            oldest = next((item for item in self._items if item not in protected), None)
            if oldest is None:
                break
            del self._items[oldest]


def display_image_key(
    path: Path, width: int, height: int, high_quality: bool, normalize_color: bool
) -> tuple | None:
    if width <= 0 or height <= 0:
        return None
    try:
        stat = path.stat()
    except OSError:
        return None
    return (
        str(path),
        stat.st_size,
        stat.st_mtime_ns,
        width,
        height,
        int(high_quality),
        int(normalize_color),
    )


def display_keys_show_same_image(shown: tuple | None, desired: tuple | None) -> bool:
    """Keep a displayed image when only its LRU timestamp was refreshed."""
    if shown is None or desired is None:
        return False
    return (
        shown[0] == desired[0] and shown[3:5] == desired[3:5] and shown[6] == desired[6]
    )
