"""Configuration and model-input loading for CodeBlue validation."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
import yaml


@dataclass(frozen=True)
class LoadedValidationConfig:
    values: dict
    path: Path


@dataclass
class OpenedModelInput:
    dataset: xr.Dataset
    mode: str
    periods: tuple[tuple[int, int], ...]
    paths: tuple[Path, ...]
    duplicate_times_removed: int


def _read_yaml(path: Path) -> dict:
    with path.open() as stream:
        values = yaml.safe_load(stream)
    if not isinstance(values, dict):
        raise ValueError(f"YAML document must be a mapping: {path}")
    return values


def load_validation_config(path: Path) -> LoadedValidationConfig:
    """Load one self-contained model and run configuration."""
    config_path = path.resolve()
    values = _read_yaml(config_path)

    input_values = dict(values.get("input", {}))
    pattern = input_values.get("pattern")
    if pattern and not Path(pattern).is_absolute():
        input_values["pattern"] = str((config_path.parent / pattern).resolve())
    if input_values:
        values["input"] = input_values

    files = dict(values.get("files", {}))
    legacy_pattern = files.get("pattern")
    if legacy_pattern and not Path(legacy_pattern).is_absolute():
        files["pattern"] = str((config_path.parent / legacy_pattern).resolve())
    for key in ("insitudatadir", "outdir"):
        configured = files.get(key)
        if configured and not Path(configured).is_absolute():
            files[key] = str((config_path.parent / configured).resolve())
    if files:
        values["files"] = files

    return LoadedValidationConfig(values=values, path=config_path)


def resolve_periods(
    year: int,
    months: list[int] | tuple[int, ...] | None = None,
) -> tuple[tuple[int, int], ...]:
    """Resolve ordered months, using ``year`` as the ending year after a wrap."""
    selected = list(range(1, 13)) if months is None else list(months)
    if not selected:
        raise ValueError("input.months must contain at least one month")
    if any(isinstance(month, bool) or not isinstance(month, int) for month in selected):
        raise ValueError("input.months must contain integers")
    if any(month < 1 or month > 12 for month in selected):
        raise ValueError("input.months values must be between 1 and 12")
    if len(set(selected)) != len(selected):
        raise ValueError("input.months must not contain duplicates")

    wrap_indices = [
        index
        for index in range(1, len(selected))
        if selected[index] < selected[index - 1]
    ]
    if len(wrap_indices) > 1:
        raise ValueError("input.months may wrap across a year only once")

    wrap_index = wrap_indices[0] if wrap_indices else 0
    return tuple(
        (
            year - 1 if wrap_indices and index < wrap_index else year,
            month,
        )
        for index, month in enumerate(selected)
    )


def input_plan(config: dict, year: int) -> tuple[str, tuple[tuple[int, int], ...], tuple[Path, ...]]:
    """Return storage mode, selected periods, and ordered model paths."""
    input_config = config.get("input", {})
    mode = input_config.get("mode", "yearly")
    if mode not in {"yearly", "monthly"}:
        raise ValueError("input.mode must be 'yearly' or 'monthly'")

    pattern = input_config.get("pattern", config.get("files", {}).get("pattern"))
    if not pattern:
        raise KeyError("A model file pattern is required")
    periods = resolve_periods(year, input_config.get("months"))

    if mode == "yearly":
        years = tuple(dict.fromkeys(period_year for period_year, _ in periods))
        paths = tuple(Path(pattern.format(year=period_year)) for period_year in years)
    else:
        paths = tuple(
            Path(pattern.format(year=period_year, month=month))
            for period_year, month in periods
        )

    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
    return mode, periods, paths


def period_mask(values, periods: tuple[tuple[int, int], ...]) -> np.ndarray:
    """Select timestamps belonging to the configured year/month pairs."""
    times = pd.to_datetime(values, errors="coerce", utc=True)
    if isinstance(times, pd.Series):
        years = times.dt.year.to_numpy()
        months = times.dt.month.to_numpy()
    else:
        index = pd.DatetimeIndex(times)
        years = index.year
        months = index.month

    selected = np.zeros(len(times), dtype=bool)
    for period_year, month in periods:
        selected |= (years == period_year) & (months == month)
    return selected


def open_model_input(config: dict, year: int) -> OpenedModelInput:
    """Open selected model files lazily as one time-ordered dataset."""
    mode, periods, paths = input_plan(config, year)
    time_dim = config["coordinates"]["time"]

    if len(paths) == 1:
        dataset = xr.open_dataset(paths[0], chunks={})
    else:
        dataset = xr.open_mfdataset(
            paths,
            combine="nested",
            concat_dim=time_dim,
            data_vars="minimal",
            coords="minimal",
            compat="override",
            combine_attrs="override",
            chunks={},
        )

    times = pd.DatetimeIndex(
        pd.to_datetime(
            np.asarray(dataset[time_dim].values).reshape(-1),
            errors="raise",
            utc=True,
        )
    ).tz_localize(None)
    keep = ~times.duplicated(keep="last")
    duplicate_times_removed = int((~keep).sum())
    if duplicate_times_removed:
        dataset = dataset.isel({time_dim: np.flatnonzero(keep)})

    dataset = dataset.sortby(time_dim)
    sorted_times = pd.DatetimeIndex(
        pd.to_datetime(
            np.asarray(dataset[time_dim].values).reshape(-1),
            errors="raise",
            utc=True,
        )
    ).tz_localize(None)
    if not sorted_times.is_unique:
        raise ValueError(f"Model time coordinate {time_dim!r} is not unique")
    if not sorted_times.is_monotonic_increasing:
        raise ValueError(f"Model time coordinate {time_dim!r} is not increasing")

    selected = period_mask(sorted_times, periods)
    dataset = dataset.isel({time_dim: np.flatnonzero(selected)})
    if dataset.sizes[time_dim] == 0:
        raise ValueError("Configured period contains no model timestamps")

    return OpenedModelInput(
        dataset=dataset,
        mode=mode,
        periods=periods,
        paths=paths,
        duplicate_times_removed=duplicate_times_removed,
    )


def observation_paths(
    config: dict,
    variable: str,
    periods: tuple[tuple[int, int], ...],
) -> tuple[Path, ...]:
    """Return the annual observation files needed by the selected period."""
    years = tuple(dict.fromkeys(period_year for period_year, _ in periods))
    directory = Path(config["files"]["insitudatadir"])
    paths = tuple(directory / f"{variable}_{year}.parquet" for year in years)
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
    return paths


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
