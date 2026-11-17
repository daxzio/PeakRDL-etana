from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from importlib.metadata import Distribution, EntryPoint

from importlib import metadata


def _get_entry_points(group_name: str) -> list[tuple["EntryPoint", "Distribution"]]:
    eps = []
    for ep in metadata.entry_points().select(group=group_name):  # type: ignore[attr-defined]
        eps.append((ep, ep.dist))
    return eps


def _get_name_from_dist(dist: "Distribution") -> str:
    return dist.name  # type: ignore


def get_entry_points(group_name: str) -> list[tuple["EntryPoint", "Distribution"]]:
    return _get_entry_points(group_name)


def get_name_from_dist(dist: "Distribution") -> str:
    return _get_name_from_dist(dist)
