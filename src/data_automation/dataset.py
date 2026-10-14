"""Named datasets exchanged between steps (ADR-0004).

A :class:`Dataset` has a name, ordered columns with a logical type each, and one or
more *parts*. An input that matches several files produces one part per file, so that
the files can be checked and combined explicitly by a ``concatenate`` step; every other
step works on single-part datasets.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .types import to_series


class DatasetError(ValueError):
    """A dataset cannot be used the way a step requires."""


@dataclass
class Part:
    """One block of rows and where it came from (a file path or a dataset name)."""

    frame: pd.DataFrame
    origin: str


@dataclass
class Dataset:
    name: str
    columns: list[str]
    types: dict[str, str]
    parts: list[Part] = field(default_factory=list)

    @property
    def rows(self) -> int:
        return sum(len(part.frame) for part in self.parts)

    def frame(self) -> pd.DataFrame:
        """The rows as one frame; a dataset with several parts must be concatenated first."""
        if len(self.parts) != 1:
            raise DatasetError(
                f"dataset {self.name!r} has {len(self.parts)} parts (one per file); "
                "combine them with a 'concatenate' step first"
            )
        return self.parts[0].frame

    @classmethod
    def from_frame(cls, name: str, frame: pd.DataFrame, types: dict[str, str]) -> Dataset:
        frame = frame.reset_index(drop=True)
        return cls(name, list(frame.columns), {c: types[c] for c in frame.columns}, [Part(frame, name)])

    @classmethod
    def from_columns(
        cls, name: str, columns: dict[str, list], types: dict[str, str], origin: str | None = None
    ) -> Dataset:
        frame = pd.DataFrame({c: to_series(types[c], values) for c, values in columns.items()})
        return cls(name, list(columns), dict(types), [Part(frame, origin or name)])
