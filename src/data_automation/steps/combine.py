"""Steps that combine datasets: ``concatenate`` (vertical) and ``join`` (by keys)."""

from __future__ import annotations

from typing import Literal

import pandas as pd
from pydantic import Field, model_validator

from ..dataset import Dataset
from ..registry import StepContext, StepFailure, StepParams, StepResult, StepType, register
from ..types import to_series
from ._common import require_columns, single_frame

# --------------------------------------------------------------------------- concatenate


class ConcatenateParams(StepParams):
    columns: Literal["same", "union"] = "same"
    add_source_column: str | None = Field(default=None, min_length=1)


def run_concatenate(params: ConcatenateParams, inputs: list[Dataset], ctx: StepContext) -> StepResult:
    parts = [(dataset, part) for dataset in inputs for part in dataset.parts]
    if not parts:
        raise StepFailure("nothing to concatenate: the input datasets have no parts")
    # Columns and types are taken file by file (never from the union of all files), so that
    # a column present in only some files is detected.
    order: list[str] = []
    types: dict[str, str] = {}
    first_seen: dict[str, str] = {}
    first_origin = parts[0][1].origin
    warnings: list[str] = []
    for position, (dataset, part) in enumerate(parts):
        for column in part.frame.columns:
            kind = dataset.types[column]
            if column in types:
                if types[column] != kind:
                    raise StepFailure(
                        f"column {column!r} is {types[column]} in {first_seen[column]} but {kind} in {part.origin}; "
                        "declare the same type for both"
                    )
                continue
            if position > 0 and params.columns == "same":
                raise StepFailure(
                    f"{part.origin} has column {column!r} that {first_origin} does not have "
                    "(use columns: union to combine different columns)"
                )
            types[column] = kind
            first_seen[column] = part.origin
            order.append(column)
    pieces = []
    for _dataset, part in parts:
        missing = [c for c in order if c not in part.frame.columns]
        if missing and params.columns == "same":
            raise StepFailure(
                f"{part.origin} lacks column(s) {', '.join(repr(c) for c in missing)} "
                "(use columns: union to fill them with missing values)"
            )
        if missing:
            warnings.append(f"{part.origin}: column(s) {', '.join(missing)} absent, filled with missing values")
        frame = part.frame.copy()
        for column in missing:
            frame[column] = to_series(types[column], [None] * len(frame), index=frame.index)
        frame = frame[order]
        if params.add_source_column:
            frame[params.add_source_column] = to_series("string", [part.origin] * len(frame), index=frame.index)
        pieces.append(frame)
    if params.add_source_column:
        if params.add_source_column in types:
            raise StepFailure(f"add_source_column {params.add_source_column!r} is already a column")
        types[params.add_source_column] = "string"
    result = pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame(columns=list(types))
    for column, kind in types.items():  # keep the storage of each logical type after concat
        result[column] = to_series(kind, result[column].tolist())
    rows_by_part = {part.origin: len(part.frame) for _d, part in parts}
    return StepResult(Dataset.from_frame(ctx.step_id, result, types), warnings, {"rows_by_part": rows_by_part})


register(
    StepType(
        "concatenate",
        "Stack the rows of one or more datasets (all files of a multi-file input) with an explicit column policy.",
        ConcatenateParams,
        run_concatenate,
        min_inputs=1,
        max_inputs=None,
    )
)

# --------------------------------------------------------------------------- join


class JoinParams(StepParams):
    relationship: Literal["one_to_one", "many_to_one", "one_to_many"]
    keys: list[str] | None = Field(default=None, min_length=1)
    left_keys: list[str] | None = Field(default=None, min_length=1)
    right_keys: list[str] | None = Field(default=None, min_length=1)
    how: Literal["inner", "left", "right", "outer"] = "inner"
    require_match: bool = False
    suffixes: tuple[str, str] = ("_left", "_right")

    @model_validator(mode="after")
    def _keys(self) -> JoinParams:
        if self.keys is None and (self.left_keys is None or self.right_keys is None):
            raise ValueError("give either 'keys' or both 'left_keys' and 'right_keys'")
        if self.keys is not None and (self.left_keys is not None or self.right_keys is not None):
            raise ValueError("'keys' cannot be combined with 'left_keys'/'right_keys'")
        if self.left_keys is not None and len(self.left_keys) != len(self.right_keys or []):
            raise ValueError("left_keys and right_keys must have the same length")
        if self.suffixes[0] == self.suffixes[1]:
            raise ValueError("the two suffixes must differ")
        return self


def _duplicated_keys(frame: pd.DataFrame, keys: list[str]) -> list[tuple]:
    duplicated = frame[frame.duplicated(keys, keep=False)][keys].drop_duplicates()
    return [tuple(row) for row in duplicated.itertuples(index=False, name=None)]


def run_join(params: JoinParams, inputs: list[Dataset], ctx: StepContext) -> StepResult:
    left_ds, right_ds = inputs
    left_keys = list(params.keys or params.left_keys or [])
    right_keys = list(params.keys or params.right_keys or [])
    require_columns(left_ds, left_keys, "join keys (left)")
    require_columns(right_ds, right_keys, "join keys (right)")
    for lk, rk in zip(left_keys, right_keys, strict=True):
        if left_ds.types[lk] != right_ds.types[rk]:
            raise StepFailure(f"key {lk!r} is {left_ds.types[lk]} on the left but {right_ds.types[rk]} on the right")
    left, right = single_frame(left_ds), single_frame(right_ds)

    # Rows with a missing key never match anything (pandas alone would match NA with NA).
    left_null = left[left_keys].isna().any(axis=1)
    right_null = right[right_keys].isna().any(axis=1)
    left_keyed, right_keyed = left[~left_null], right[~right_null]

    # The declared relationship is checked before joining, so rows can never multiply silently.
    unique_sides = {"one_to_one": ("left", "right"), "many_to_one": ("right",), "one_to_many": ("left",)}
    for side in unique_sides[params.relationship]:
        frame, keys = (left_keyed, left_keys) if side == "left" else (right_keyed, right_keys)
        duplicated = _duplicated_keys(frame, keys)
        if duplicated:
            raise StepFailure(
                f"relationship {params.relationship} violated: {len(duplicated)} key value(s) appear more than once "
                f"on the {side} side (e.g. {duplicated[:5]}); the join would multiply rows"
            )

    right_index = set(right_keyed[right_keys].itertuples(index=False, name=None))
    left_tuples = list(left_keyed[left_keys].itertuples(index=False, name=None))
    unmatched_left = sum(1 for key in left_tuples if key not in right_index) + int(left_null.sum())
    if params.require_match and unmatched_left:
        raise StepFailure(f"require_match: {unmatched_left} left row(s) have no matching row on the right")

    shared_keys = set(params.keys or [])
    overlap = (set(left.columns) & set(right.columns)) - shared_keys
    left_names = {c: c + params.suffixes[0] if c in overlap else c for c in left.columns}
    right_names = {c: c + params.suffixes[1] if c in overlap else c for c in right.columns}
    for name in set(left_names.values()) & {v for k, v in right_names.items() if k not in shared_keys}:
        raise StepFailure(f"column {name!r} would exist twice after the join; choose other suffixes")
    left_r = left.rename(columns=left_names)
    right_r = right.rename(columns=right_names)
    if params.keys:
        merged = pd.merge(left_r[~left_null], right_r[~right_null], how=params.how, on=left_keys, sort=False)
    else:
        merged = pd.merge(
            left_r[~left_null],
            right_r[~right_null],
            how=params.how,
            left_keys=[left_names[k] for k in left_keys],
            right_keys=[right_names[k] for k in right_keys],
            sort=False,
        )
    extra = []
    if params.how in ("left", "outer") and left_null.any():
        extra.append(left_r[left_null])
    if params.how in ("right", "outer") and right_null.any():
        extra.append(right_r[right_null])

    types = {left_names[c]: left_ds.types[c] for c in left.columns}
    types |= {right_names[c]: right_ds.types[c] for c in right.columns if c not in shared_keys}
    pieces = [merged, *extra]
    result = pd.concat([p.reindex(columns=list(types)) for p in pieces], ignore_index=True)
    for column, kind in types.items():
        result[column] = to_series(kind, result[column].tolist())
    warnings = []
    if overlap:
        warnings.append(
            f"columns present on both sides were renamed with suffixes {list(params.suffixes)}: {sorted(overlap)}"
        )
    if left_null.any() or right_null.any():
        warnings.append(
            f"rows with a missing key never match (left: {int(left_null.sum())}, right: {int(right_null.sum())})"
        )
    details = {
        "rows_left": len(left),
        "rows_right": len(right),
        "rows_out": len(result),
        "unmatched_left": unmatched_left,
    }
    return StepResult(Dataset.from_frame(ctx.step_id, result, types), warnings, details)


register(
    StepType(
        "join",
        "Match the rows of two datasets on key columns; the declared relationship is checked before joining.",
        JoinParams,
        run_join,
        min_inputs=2,
        max_inputs=2,
    )
)
