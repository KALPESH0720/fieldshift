from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Cell:
    ix: int
    iy: int
    size_deg: float

    @property
    def cell_id(self) -> str:
        return f"g{self.size_deg:g}_{self.iy}_{self.ix}"

    @property
    def center_lat(self) -> float:
        return round((self.iy + 0.5) * self.size_deg, 6)

    @property
    def center_lon(self) -> float:
        return round((self.ix + 0.5) * self.size_deg, 6)


def parse_cell_id(cell_id: str) -> Cell:
    size, iy, ix = cell_id.split("_")
    return Cell(ix=int(ix), iy=int(iy), size_deg=float(size[1:]))
