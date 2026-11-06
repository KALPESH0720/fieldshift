"""Season labels such as 'kharif-2027'. A year label groups kharif, rabi, summer in that order."""
from __future__ import annotations

SEASON_ORDER = {"kharif": 0, "rabi": 1, "summer": 2}


def parse_season(label: str) -> tuple[str, int]:
    name, year = label.rsplit("-", 1)
    return name, int(year)


def season_key(label: str) -> tuple[int, int]:
    name, year = parse_season(label)
    return (year, SEASON_ORDER.get(name, 9))


def next_seasons(start: str, n: int, cycle: tuple[str, ...]) -> list[str]:
    """`start` plus the following seasons, n labels in total."""
    name, year = parse_season(start)
    if name not in cycle:
        raise ValueError(f"season '{name}' is not in the configured cycle {list(cycle)}")
    out = [start]
    i = cycle.index(name)
    while len(out) < n:
        i += 1
        if i == len(cycle):
            i, year = 0, year + 1
        out.append(f"{cycle[i]}-{year}")
    return out
