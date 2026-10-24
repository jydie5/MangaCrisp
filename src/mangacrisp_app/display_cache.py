"""Display cache policy, independent of Qt and correction workers.

Only the UI thread owns this cache. Values are decoded display images, not
durable correction outputs; eviction must never remove the visible spread.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Hashable, Iterator, Mapping
from collections.abc import Set as AbstractSet
from pathlib import Path
from typing import Generic, TypeVar

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


class DisplayCache(Mapping[K, V], Generic[K, V]):
    """Small LRU cache with optional item-count and byte-like budgets.

    ``weight`` is called for every value inserted or replaced and must return
    a positive ``int`` representing that value's budget usage.  The callback
    is a caller-supplied estimate; it is not required to be the object's
    serialized size.  A callback failure leaves the cache unchanged.

    Protected keys are never evicted by ``put``.  If every resident key is
    protected, a put may temporarily exceed either budget so the visible
    spread can remain available.
    """

    def __init__(
        self,
        capacity: int = 18,
        *,
        max_bytes: int | None = None,
        weight: Callable[[V], int] | None = None,
    ) -> None:
        self.capacity = capacity
        self.max_bytes = None if max_bytes is None else max(0, max_bytes)
        self._weight: Callable[[V], int] = weight or (lambda _value: 1)
        self._items: OrderedDict[K, V] = OrderedDict()
        self._weights: dict[K, int] = {}
        self._total_bytes = 0

    @property
    def total_bytes(self) -> int:
        """Current sum of the configured weights for resident values."""
        return self._total_bytes

    def _value_weight(self, value: V) -> int:
        weight = self._weight(value)
        if not isinstance(weight, int):
            raise TypeError("DisplayCache weight must return an int")
        if weight <= 0:
            raise ValueError("DisplayCache weight must return a positive int")
        return weight

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
        self._weights.clear()
        self._total_bytes = 0

    def put(self, key: K, value: V, *, protected: AbstractSet[K]) -> None:
        """Insert or replace ``key`` and evict the oldest unprotected items.

        The count and byte budgets are enforced together.  ``protected`` may
        contain visible desired and fallback keys; protected entries can make
        the cache exceed a budget when no eviction candidate remains.
        """
        value_weight = self._value_weight(value)
        previous_weight = self._weights.get(key, 0)
        self._items[key] = value
        self._weights[key] = value_weight
        self._items.move_to_end(key)
        self._total_bytes += value_weight - previous_weight
        while (
            len(self._items) > max(0, self.capacity)
            or self.max_bytes is not None and self._total_bytes > self.max_bytes
        ):
            oldest = next((item for item in self._items if item not in protected), None)
            if oldest is None:
                break
            del self._items[oldest]
            self._total_bytes -= self._weights.pop(oldest)


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
        and shown[7:] == desired[7:]
    )
