"""Horizontal model-to-observation matching for structured model grids."""

from __future__ import annotations

import importlib

import numpy as np
import xarray as xr
from pyproj import Geod
from scipy.spatial import cKDTree

_METHODS = {"bilinear", "nearest_s2d"}
_WGS84_GEOD = Geod(ellps="WGS84")


def horizontal_config(dataset: xr.Dataset, config: dict) -> dict:
    """Resolve the configured structured-grid matching method."""
    coordinates = config["coordinates"]
    resolved = dict(config.get("horizontal_grid", {}))
    resolved.setdefault("backend", "xesmf")
    resolved.setdefault("method", "bilinear")
    resolved.setdefault("longitude_variable", coordinates["lon"])
    resolved.setdefault("latitude_variable", coordinates["lat"])

    method = str(resolved["method"]).strip().lower()

    if method not in _METHODS:
        raise ValueError("horizontal_grid.method must be bilinear or nearest_s2d")

    resolved["method"] = method

    resolved["backend"] = (
        "scipy"
        if method == "nearest_s2d"
        else "xesmf"
    )

    if method == "nearest_s2d":
        if not resolved.get("valid_cells"):
            raise ValueError("nearest_s2d requires horizontal_grid.valid_cells")

        resolved["maximum_distance_km"] = float(resolved["maximum_distance_km"])

    native_lon = dataset[resolved["longitude_variable"]]
    native_lat = dataset[resolved["latitude_variable"]]
    # Retain only native dimensions and values. Extra model coordinates with
    # longitude-like names can otherwise make xESMF/CF discovery ambiguous.
    lon = xr.DataArray(native_lon.data, dims=native_lon.dims)
    lat = xr.DataArray(native_lat.data, dims=native_lat.dims)
    if lon.ndim == 1 and lat.ndim == 1:
        resolved.setdefault("x_dimension", lon.dims[0])
        resolved.setdefault("y_dimension", lat.dims[0])
        resolved.setdefault("topology", "rectilinear")
    elif lon.ndim == 2 and lat.ndim == 2 and lon.dims == lat.dims:
        resolved.setdefault("y_dimension", lon.dims[-2])
        resolved.setdefault("x_dimension", lon.dims[-1])
        resolved.setdefault("topology", "curvilinear")
    else:
        raise ValueError(
            "Longitude and latitude must be separate 1-D coordinates or "
            "matching 2-D curvilinear coordinates"
        )

    x_dim = resolved["x_dimension"]
    y_dim = resolved["y_dimension"]
    if x_dim not in dataset.dims or y_dim not in dataset.dims:
        raise ValueError(
            f"Horizontal dimensions {(y_dim, x_dim)} are not in the dataset"
        )
    if lon.ndim == 2 and set(lon.dims) != {y_dim, x_dim}:
        raise ValueError("2-D longitude/latitude do not use configured dimensions")
    return resolved


def horizontal_dimensions(dataset: xr.Dataset, config: dict) -> tuple[str, str]:
    resolved = horizontal_config(dataset, config)
    return resolved["y_dimension"], resolved["x_dimension"]


def _resolve_valid_cells(
    dataset: xr.Dataset,
    resolved: dict,
) -> xr.DataArray:
    """Return a Boolean valid-cell array on the horizontal grid."""
    specification = resolved["valid_cells"]

    variable_name = specification["variable"]
    variable = dataset[variable_name]
    condition = specification["condition"]

    if condition == "equals":
        valid = variable == specification["value"]

    elif condition == "greater_than":
        valid = variable > specification["value"]

    elif condition == "less_than":
        valid = variable < specification["value"]

    elif condition == "finite":
        valid = xr.apply_ufunc(
            np.isfinite,
            variable,
            dask="allowed",
        )

    else:
        raise ValueError(
            "valid_cells.condition must be equals, "
            "greater_than, less_than, or finite"
        )

    reduce_dimensions = specification.get("reduce_dimensions", [])

    if isinstance(reduce_dimensions, str):
        reduce_dimensions = [reduce_dimensions]

    missing_dimensions = [
        dimension
        for dimension in reduce_dimensions
        if dimension not in valid.dims
    ]

    if missing_dimensions:
        raise ValueError(
            "valid_cells.reduce_dimensions are not present "
            f"in {variable_name!r}: {missing_dimensions}"
        )

    if reduce_dimensions:
        reduction = specification.get("reduction", "any")

        if reduction == "any":
            valid = valid.any(dim=reduce_dimensions)

        elif reduction == "all":
            valid = valid.all(dim=reduce_dimensions)

        else:
            raise ValueError("valid_cells.reduction must be any or all")

    y_dim = resolved["y_dimension"]
    x_dim = resolved["x_dimension"]

    if set(valid.dims) != {y_dim, x_dim}:
        raise ValueError(
            f"Valid-cell variable {variable_name!r} must "
            f"resolve to dimensions {(y_dim, x_dim)}; "
            f"received {valid.dims}"
        )

    valid = valid.transpose(y_dim, x_dim)
    return xr.DataArray(valid.data, dims=valid.dims).astype(bool)


def _source_grid(
    dataset: xr.Dataset,
    config: dict,
) -> tuple[xr.Dataset, xr.DataArray, dict]:
    resolved = horizontal_config(dataset, config)
    y_dim = resolved["y_dimension"]
    x_dim = resolved["x_dimension"]
    native_lon = dataset[resolved["longitude_variable"]]
    native_lat = dataset[resolved["latitude_variable"]]
    lon = xr.DataArray(native_lon.data, dims=native_lon.dims)
    lat = xr.DataArray(native_lat.data, dims=native_lat.dims)

    if lon.ndim == 1:
        lon2d, lat2d = xr.broadcast(lon, lat)
        lon2d = lon2d.transpose(y_dim, x_dim)
        lat2d = lat2d.transpose(y_dim, x_dim)
        source = xr.Dataset({"lon": lon.rename("lon"), "lat": lat.rename("lat")})
    else:
        lon2d = lon.transpose(y_dim, x_dim)
        lat2d = lat.transpose(y_dim, x_dim)
        source = xr.Dataset(
            {
                "lon": lon2d.rename("lon"),
                "lat": lat2d.rename("lat"),
            }
        )

    valid = (
        xr.apply_ufunc(np.isfinite, lon2d, dask="allowed")
        & xr.apply_ufunc(np.isfinite, lat2d, dask="allowed")
        & (lat2d >= -90.0)
        & (lat2d <= 90.0)
    )
    for invalid in resolved.get("invalid_coordinate_values", []):
        valid = valid & (lon2d != float(invalid)) & (lat2d != float(invalid))

    if resolved.get("valid_cells"):
        cell_valid = _resolve_valid_cells(
            dataset,
            resolved,
        )
        valid = valid & cell_valid

    source["mask"] = valid.astype(np.int32)
    return source, valid, resolved


def horizontal_extent(
    dataset: xr.Dataset,
    config: dict,
) -> tuple[float, float, float, float]:
    """Return the valid source-grid bounding box used by legacy diagnostics."""
    source, valid, _ = _source_grid(dataset, config)
    lon = source["lon"]
    lat = source["lat"]
    if lon.ndim == 1:
        lon, lat = xr.broadcast(lon, lat)
        lon = lon.transpose(*valid.dims)
        lat = lat.transpose(*valid.dims)
    values = (
        float(lon.where(valid).min()),
        float(lon.where(valid).max()),
        float(lat.where(valid).min()),
        float(lat.where(valid).max()),
    )
    if not all(np.isfinite(values)):
        raise ValueError("Horizontal grid contains no valid wet coordinates")
    return values


def _source_coordinates_2d(
    source: xr.Dataset,
    valid: xr.DataArray,
) -> tuple[xr.DataArray, xr.DataArray]:
    """Return geographic longitude and latitude on matching 2-D dimensions."""
    lon = source["lon"]
    lat = source["lat"]

    if lon.ndim == 1:
        lon, lat = xr.broadcast(lon, lat)
        lon = lon.transpose(*valid.dims)
        lat = lat.transpose(*valid.dims)

    return lon, lat

def _unit_sphere(
    longitude: np.ndarray,
    latitude: np.ndarray,
) -> np.ndarray:
    """Convert geographic positions to Cartesian unit-sphere vectors."""
    lon_radians = np.deg2rad(longitude)
    lat_radians = np.deg2rad(latitude)
    cos_latitude = np.cos(lat_radians)

    return np.column_stack(
        (
            cos_latitude * np.cos(lon_radians),
            cos_latitude * np.sin(lon_radians),
            np.sin(lat_radians),
        )
    )


def nearest_s2d_lookup(
    grid_dataset: xr.Dataset,
    config: dict,
    target_lon: xr.DataArray,
    target_lat: xr.DataArray,
) -> xr.Dataset:
    """Find the nearest valid source cell for each observation point."""
    if target_lon.dims != target_lat.dims or target_lon.dims != ("points",):
        raise ValueError(
            "Target longitude and latitude must use dimension points"
        )
    source, valid, resolved = _source_grid(grid_dataset, config)

    lon2d, lat2d = _source_coordinates_2d(source, valid)
    lon_values = np.asarray(lon2d.values, dtype=float)
    lat_values = np.asarray(lat2d.values, dtype=float)
    valid_values = np.asarray(valid.values, dtype=bool)

    wet_y, wet_x = np.nonzero(valid_values)
    if wet_y.size == 0:
        raise ValueError("Horizontal grid contains no valid wet cells")

    wet_lon = lon_values[wet_y, wet_x]
    wet_lat = lat_values[wet_y, wet_x]

    tree = cKDTree(_unit_sphere(wet_lon, wet_lat))

    target_lon_values = np.asarray(target_lon.values, dtype=float)
    target_lat_values = np.asarray(target_lat.values, dtype=float)

    target_valid = (
        np.isfinite(target_lon_values)
        & np.isfinite(target_lat_values)
        & (target_lat_values >= -90.0)
        & (target_lat_values <= 90.0)
    )

    count = target_lon_values.size
    y_index = np.zeros(count, dtype=np.int64)
    x_index = np.zeros(count, dtype=np.int64)
    source_lon = np.full(count, np.nan, dtype=float)
    source_lat = np.full(count, np.nan, dtype=float)
    distance_km = np.full(count, np.nan, dtype=float)

    if target_valid.any():
        candidate_count = min(8, wet_y.size)

        _, wet_candidates = tree.query(
            _unit_sphere(
                target_lon_values[target_valid],
                target_lat_values[target_valid],
            ),
            k=candidate_count,
        )

        wet_candidates = np.asarray(
            wet_candidates,
            dtype=np.int64,
        ).reshape(
            (int(target_valid.sum()), candidate_count)
        )

        candidate_lon = wet_lon[wet_candidates]
        candidate_lat = wet_lat[wet_candidates]

        target_lon_candidates = np.broadcast_to(
            target_lon_values[target_valid, np.newaxis],
            candidate_lon.shape,
        )
        target_lat_candidates = np.broadcast_to(
            target_lat_values[target_valid, np.newaxis],
            candidate_lat.shape,
        )

        _, _, candidate_distance_m = _WGS84_GEOD.inv(
            target_lon_candidates,
            target_lat_candidates,
            candidate_lon,
            candidate_lat,
        )

        nearest_candidate = np.argmin(
            candidate_distance_m,
            axis=1,
        )
        rows = np.arange(wet_candidates.shape[0])
        wet_index = wet_candidates[rows, nearest_candidate]
        selected_y = wet_y[wet_index]
        selected_x = wet_x[wet_index]

        y_index[target_valid] = selected_y
        x_index[target_valid] = selected_x
        source_lon[target_valid] = wet_lon[wet_index]
        source_lat[target_valid] = wet_lat[wet_index]
        distance_km[target_valid] = (
            candidate_distance_m[rows, nearest_candidate]
            / 1000.0
        )

    within_distance = target_valid & (
        distance_km <= resolved["maximum_distance_km"]
    )

    return xr.Dataset(
        {
            "horizontal_y_index": ("points", y_index),
            "horizontal_x_index": ("points", x_index),
            "matched_model_longitude": ("points", source_lon),
            "matched_model_latitude": ("points", source_lat),
            "horizontal_distance_km": ("points", distance_km),
            "within_maximum_distance": (
                "points",
                within_distance,
            ),
        }
    )

def _select_nearest_s2d(
    data: xr.Dataset,
    grid_dataset: xr.Dataset,
    config: dict,
    target_lon: xr.DataArray,
    target_lat: xr.DataArray,
    lookup: xr.Dataset | None = None,
) -> xr.Dataset:
    """Select complete native-grid columns at the matched wet cells."""
    if lookup is None:
        lookup = nearest_s2d_lookup(
            grid_dataset,
            config,
            target_lon,
            target_lat,
        )

    resolved = horizontal_config(grid_dataset, config)
    y_dim = resolved["y_dimension"]
    x_dim = resolved["x_dimension"]

    y_index = lookup["horizontal_y_index"]
    x_index = lookup["horizontal_x_index"]
    accepted = lookup["within_maximum_distance"]

    mapped = data.isel(
        {
            y_dim: y_index,
            x_dim: x_index,
        }
    )

    point_variables = [
        name
        for name, array in mapped.data_vars.items()
        if "points" in array.dims
    ]
    for name in point_variables:
        mapped[name] = mapped[name].where(accepted)

    for name in (
        "matched_model_longitude",
        "matched_model_latitude",
        "horizontal_distance_km",
        "within_maximum_distance",
    ):
        mapped[name] = lookup[name]

    return mapped
def interpolate_horizontal(
    data: xr.Dataset,
    grid_dataset: xr.Dataset,
    config: dict,
    target_lon: xr.DataArray,
    target_lat: xr.DataArray,
    lookup: xr.Dataset | None = None,
) -> xr.Dataset:
    """Map native-grid variables directly to observation points."""
    if target_lon.dims != target_lat.dims or target_lon.dims != ("points",):
        raise ValueError("Target longitude and latitude must use dimension 'points'")

    resolved = horizontal_config(grid_dataset, config)

    if resolved["method"] == "nearest_s2d":
        return _select_nearest_s2d(
            data,
            grid_dataset,
            config,
            target_lon,
            target_lat,
            lookup,
        )

    xesmf = importlib.import_module("xesmf")

    source, valid, resolved = _source_grid(grid_dataset, config)
    target = xr.Dataset(
        {
            "lon": xr.DataArray(np.asarray(target_lon), dims="points"),
            "lat": xr.DataArray(np.asarray(target_lat), dims="points"),
        }
    )
    regridder = xesmf.Regridder(
        source,
        target,
        resolved["method"],
        locstream_out=True,
        unmapped_to_nan=True,
    )

    y_dim = resolved["y_dimension"]
    x_dim = resolved["x_dimension"]
    horizontal_dims = {y_dim, x_dim}
    valid_cells = resolved.get("valid_cells", {})
    static_mask_name = (
        valid_cells.get("variable")
        if valid_cells.get("condition") == "equals"
        else None
    )
    mapped_variables = {}

    for name, array in data.data_vars.items():
        present = horizontal_dims.intersection(array.dims)
        if present and present != horizontal_dims:
            raise ValueError(
                f"Variable {name!r} uses only part of horizontal grid "
                f"{(y_dim, x_dim)}"
            )
        if present:
            if name == static_mask_name and set(array.dims) == horizontal_dims:
                continue
            mapped_variables[name] = regridder(array, keep_attrs=True)
        else:
            mapped_variables[name] = array

    mapped = xr.Dataset(mapped_variables, attrs=data.attrs)
    if static_mask_name and static_mask_name in data:
        coverage = regridder(valid.astype(float))
        wet_value = valid_cells["value"]
        mapped[static_mask_name] = xr.where(
            xr.apply_ufunc(np.isfinite, coverage, dask="allowed"),
            wet_value,
            np.nan,
        )

    return mapped
