from __future__ import annotations

import pytest

from mangacrisp_app.display_cache import DisplayCache, display_keys_show_same_image


def test_default_cache_remains_count_limited_and_tracks_unit_weights() -> None:
    cache: DisplayCache[str, str] = DisplayCache(capacity=2)

    cache.put("a", "A", protected=set())
    cache.put("b", "B", protected=set())
    cache.put("c", "C", protected=set())

    assert list(cache) == ["b", "c"]
    assert cache.total_bytes == 2


def test_byte_budget_evicts_oldest_unprotected_items() -> None:
    cache: DisplayCache[str, str] = DisplayCache(
        capacity=10,
        max_bytes=5,
        weight=len,
    )

    cache.put("a", "aa", protected=set())
    cache.put("b", "bbb", protected=set())
    cache.put("c", "c", protected=set())

    assert list(cache) == ["b", "c"]
    assert cache.total_bytes == 4


def test_protected_visible_keys_can_temporarily_exceed_byte_budget() -> None:
    cache: DisplayCache[str, str] = DisplayCache(
        capacity=1,
        max_bytes=3,
        weight=len,
    )

    cache.put("desired", "1234", protected={"desired"})
    cache.put("fallback", "12", protected={"desired", "fallback"})

    assert set(cache) == {"desired", "fallback"}
    assert cache.total_bytes == 6

    cache.put("next", "x", protected=set())
    assert set(cache) == {"next"}
    assert cache.total_bytes == 1


def test_replacement_updates_weight_without_duplicate_count() -> None:
    cache: DisplayCache[str, str] = DisplayCache(max_bytes=10, weight=len)

    cache.put("page", "1234", protected=set())
    cache.put("page", "12", protected=set())
    assert len(cache) == 1
    assert cache["page"] == "12"
    assert cache.total_bytes == 2

    cache.put("other", "56789", protected=set())
    assert set(cache) == {"page", "other"}
    assert cache.total_bytes == 7


def test_clear_resets_byte_accounting() -> None:
    cache: DisplayCache[str, str] = DisplayCache(weight=len)
    cache.put("page", "123", protected=set())
    cache.clear()

    assert len(cache) == 0
    assert cache.total_bytes == 0


@pytest.mark.parametrize(
    ("weight", "error"),
    [(lambda _value: 0, ValueError), (lambda _value: -1, ValueError), (lambda _value: "1", TypeError)],
)
def test_weight_callback_requires_positive_int(weight, error) -> None:
    cache: DisplayCache[str, str] = DisplayCache(weight=weight)

    with pytest.raises(error):
        cache.put("page", "value", protected=set())
    assert len(cache) == 0
    assert cache.total_bytes == 0


def test_failed_replacement_leaves_existing_value_and_accounting_unchanged() -> None:
    def weight(value: str) -> int:
        if value == "bad":
            raise RuntimeError("cannot measure")
        return len(value)

    cache: DisplayCache[str, str] = DisplayCache(weight=weight)
    cache.put("page", "good", protected=set())

    with pytest.raises(RuntimeError):
        cache.put("page", "bad", protected=set())

    assert cache["page"] == "good"
    assert cache.total_bytes == 4


def test_display_key_tail_metadata_must_match() -> None:
    shown = ("page.png", 10, 100, 640, 480, 1, 1, 2.0, 1024, 768)

    assert display_keys_show_same_image(
        shown,
        ("page.png", 11, 200, 640, 480, 0, 1, 2.0, 1024, 768),
    )
    assert not display_keys_show_same_image(
        shown,
        ("page.png", 11, 200, 640, 480, 0, 1, 1.0, 1024, 768),
    )
    assert display_keys_show_same_image(
        ("page.png", 10, 100, 640, 480, 1, 1),
        ("page.png", 11, 200, 640, 480, 0, 1),
    )
