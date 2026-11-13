#!/usr/bin/env python3
"""Tier-1 vertical-coordinate handling for CodeBlue validation.

All model-native vertical coordinates are normalized in memory to metres below
the instantaneous water surface, positive downward.  This module never writes
model data.  Model-specific variable names and conventions remain in YAML.
"""

from __future__ import annotations

import numpy as np
import xarray as xr
from xgcm import Grid


TIER1_METHODS = {
    "existing_z",
    "layer_thickness",
    "interface_variable",
    "depth_variable",
    "fixed_depth",
    "sigma_fraction",
    "roms_s_coordinate",
}


_SURFACE_TO_BOTTOM = {"surface_to_bottom", "top_to_bottom"}
_BOTTOM_TO_SURFACE = {"bottom_to_surface", "bottom_to_top"}
_INSTANTANEOUS_SURFACE = {"instantaneous_surface", "surface"}


def _config(config: dict | None) -> dict:
    result = dict(config or {})
    result.setdefault("method", "existing_z")
    result.setdefault("z_variable", "z")
    result.setdefault("positive", "down")
    result.setdefault("reference", "instantaneous_surface")
    result.setdefault("observation_reference", "instantaneous_surface")
    result.setdefault("outside_column", "missing")
    result.setdefault("missing_values", [-9998.0, -9999.0])
    return result


def _require_tier1(config: dict) -> str:
    method = str(config["method"]).strip().lower().replace("-", "_")
    if method not in TIER1_METHODS:
        raise NotImplementedError(
            f"Vertical method {method!r} is not available in Tier 1; "
            f"supported methods are {sorted(TIER1_METHODS)}"
        )
    return method


def vertical_input_names(vertical_config: dict | None) -> list[str]:
    """Return model variables required by one Tier-1 vertical configuration."""
    config = _config(vertical_config)
    method = _require_tier1(config)

    if method == "layer_thickness":
        required = [config["thickness_variable"]]
    elif method == "interface_variable":
        required = [config["interface_variable"]]
    elif method == "sigma_fraction":
        required = [config["center_variable"], config["interface_variable"]]
    elif method == "roms_s_coordinate":
        required = [
            config["center_variable"],
            config["center_stretching_variable"],
            config["interface_variable"],
            config["interface_stretching_variable"],
            config["bathymetry_variable"],
        ]
    else:
        required = [config.get("depth_variable", config.get("z_variable", "z"))]

    optional_keys = (
        "interface_variable",
        "thickness_variable",
        "bottom_depth_variable",
        "surface_variable",
        "bathymetry_variable",
        "sea_surface_elevation_variable",
        "scale_variable",
        "wet_mask_variable",
        "hc_variable",
        "vtransform_variable",
    )
    required.extend(config[key] for key in optional_keys if config.get(key))
    return list(dict.fromkeys(required))


def _mask_missing(data: xr.DataArray, config: dict) -> xr.DataArray:
    valid = xr.apply_ufunc(np.isfinite, data, dask="allowed")
    for value in config.get("missing_values", []):
        valid = valid & (data != float(value))
    return data.where(valid)


def mask_vertical_inputs(
    dataset: xr.Dataset, vertical_config: dict | None
) -> xr.Dataset:
    """Mask fill values before horizontal/time interpolation.

    Invalid thickness is masked here so a negative or zero dry-cell sentinel
    cannot contaminate interpolation into an otherwise wet profile.
    """
    config = _config(vertical_config)
    method = _require_tier1(config)
    result = dataset.copy()

    for name in vertical_input_names(config):
        if name in result:
            result[name] = _mask_missing(result[name], config)

    if method == "layer_thickness":
        name = config["thickness_variable"]
        result[name] = result[name].where(result[name] > 0.0)
    return result


def _inactive_indices(config: dict, size: int) -> list[int]:
    indices = []
    for raw in config.get("inactive_level_indices", []):
        index = int(raw)
        if index < 0:
            index += size
        if index < 0 or index >= size:
            raise IndexError(
                f"Inactive vertical index {raw} is outside a dimension of size {size}"
            )
        indices.append(index)
    return sorted(set(indices))


def _select_active(
    data: xr.DataArray, vertical_dim: str, config: dict
) -> xr.DataArray:
    if vertical_dim not in data.dims:
        return data
    inactive = _inactive_indices(config, data.sizes[vertical_dim])
    if not inactive:
        return data
    active = [
        index
        for index in range(data.sizes[vertical_dim])
        if index not in inactive
    ]
    if not active:
        raise ValueError("All vertical levels were configured as inactive")
    return data.isel({vertical_dim: active})


def _surface_to_bottom(
    data: xr.DataArray, vertical_dim: str, config: dict
) -> xr.DataArray:
    order = str(
        config.get("native_order", config.get("layer_order", "surface_to_bottom"))
    ).lower()
    if order in _SURFACE_TO_BOTTOM:
        return data
    if order in _BOTTOM_TO_SURFACE:
        return data.isel({vertical_dim: slice(None, None, -1)})
    raise ValueError(
        "vertical_coordinate.native_order must be surface_to_bottom or "
        "bottom_to_surface"
    )


def _normalize_depth_sign(data: xr.DataArray, positive: str) -> xr.DataArray:
    positive = str(positive).strip().lower()
    if positive == "down":
        return data
    if positive == "up":
        return -data
    raise ValueError("Depth sign must be 'down' or 'up'")


def _normalized_depth(
    data: xr.DataArray, dataset: xr.Dataset, config: dict
) -> xr.DataArray:
    depth = _normalize_depth_sign(_mask_missing(data, config), config["positive"])
    reference = str(config.get("reference", "instantaneous_surface")).lower()
    if reference in _INSTANTANEOUS_SURFACE:
        return depth

    surface_name = config.get("surface_variable")
    if not surface_name:
        raise ValueError(
            f"reference={reference!r} requires vertical_coordinate.surface_variable"
        )
    if surface_name not in dataset:
        raise KeyError(f"Surface variable {surface_name!r} was not found")
    surface = _normalize_depth_sign(
        _mask_missing(dataset[surface_name], config),
        config.get("surface_positive", config["positive"]),
    )
    return depth - surface


def _configured_bottom(
    dataset: xr.Dataset, config: dict, vertical_dim: str
) -> xr.DataArray | None:
    name = config.get("bottom_depth_variable")
    if not name:
        return None
    if name not in dataset:
        raise KeyError(f"Bottom-depth variable {name!r} was not found")
    bottom = _mask_missing(dataset[name], config)
    if vertical_dim in bottom.dims:
        raise ValueError(f"Bottom-depth variable {name!r} must not use {vertical_dim!r}")
    return _normalize_depth_sign(
        bottom, config.get("bottom_depth_positive", "down")
    )


def _configured_wet_levels(
    dataset: xr.Dataset, config: dict, vertical_dim: str
) -> xr.DataArray | None:
    """Return an optional native wet mask in surface-to-bottom order."""
    name = config.get("wet_mask_variable")
    if not name:
        return None
    if name not in dataset:
        raise KeyError(f"Wet-mask variable {name!r} was not found")

    source = _mask_missing(dataset[name], config)
    if "wet_mask_value" in config:
        wet = source == config["wet_mask_value"]
    else:
        wet = xr.apply_ufunc(np.isfinite, source, dask="allowed")
    if vertical_dim in wet.dims:
        wet = _select_active(wet, vertical_dim, config)
        wet = _surface_to_bottom(wet, vertical_dim, config)
    return wet


def _column_bottom_from_wet_levels(
    z_interface: xr.DataArray,
    wet_levels: xr.DataArray,
    vertical_dim: str,
) -> tuple[xr.DataArray, xr.DataArray]:
    """Derive local bottom from one contiguous wet prefix per column."""
    interface_dims = [
        dim
        for dim in z_interface.dims
        if z_interface.sizes[dim] == wet_levels.sizes[vertical_dim] + 1
    ]
    if len(interface_dims) != 1:
        raise ValueError("Could not identify the fixed-depth interface dimension")
    interface_dim = interface_dims[0]

    wet_count = wet_levels.sum(vertical_dim).astype(np.int64)
    position = xr.DataArray(
        np.arange(wet_levels.sizes[vertical_dim]),
        dims=(vertical_dim,),
        coords={vertical_dim: wet_levels[vertical_dim]},
    )
    expected = position < wet_count
    contiguous = (wet_levels == expected).all(vertical_dim) & (wet_count > 0)
    bottom = z_interface.isel({interface_dim: wet_count}).where(contiguous)
    return bottom.rename("model_bottom_depth"), contiguous


def _sigma_fraction_coordinates(
    dataset: xr.Dataset, config: dict, vertical_dim: str
) -> tuple[xr.DataArray, xr.DataArray, xr.DataArray, xr.DataArray]:
    """Convert dimensionless surface-to-bottom fractions to metre depths."""
    center_name = config["center_variable"]
    interface_name = config["interface_variable"]
    scale_name = config.get("scale_variable", config.get("bottom_depth_variable"))
    if not scale_name:
        raise KeyError(
            "sigma_fraction requires scale_variable or bottom_depth_variable"
        )
    for name in (center_name, interface_name, scale_name):
        if name not in dataset:
            raise KeyError(f"Sigma-coordinate input {name!r} was not found")

    center_fraction = _select_active(dataset[center_name], vertical_dim, config)
    center_fraction = _surface_to_bottom(center_fraction, vertical_dim, config)
    center_fraction = _mask_missing(center_fraction, config)

    interface_fraction = _mask_missing(dataset[interface_name], config)
    interface_dim = _interface_dimension(
        interface_fraction, dataset, config, vertical_dim
    )
    interface_fraction = _surface_to_bottom(
        interface_fraction, interface_dim, config
    )

    scale = _mask_missing(dataset[scale_name], config)
    if vertical_dim in scale.dims or interface_dim in scale.dims:
        raise ValueError("Sigma depth scale must not use a vertical dimension")
    scale = _normalize_depth_sign(
        scale, config.get("scale_positive", config.get("bottom_depth_positive", "down"))
    )

    z_center = (center_fraction * scale).rename("z_center")
    z_interface = (interface_fraction * scale).rename("z_interface")
    bottom = z_interface.isel({interface_dim: -1}, drop=True).rename(
        "model_bottom_depth"
    )
    wet = (
        xr.apply_ufunc(np.isfinite, z_center, dask="allowed").all(vertical_dim)
        & xr.apply_ufunc(np.isfinite, z_interface, dask="allowed").all(interface_dim)
        & (z_interface.diff(interface_dim) > 0.0).all(interface_dim)
    )
    return z_center, z_interface, bottom, wet


def _scalar_from_config_or_dataset(
    dataset: xr.Dataset,
    config: dict,
    value_key: str,
    variable_key: str,
) -> xr.DataArray | float:
    if value_key in config:
        return float(config[value_key])
    name = config.get(variable_key)
    if not name or name not in dataset:
        raise KeyError(f"Configure {value_key} or an existing {variable_key}")
    value = dataset[name]
    if value.size != 1:
        raise ValueError(f"{name!r} must contain one scalar value")
    return value.squeeze()


def _roms_depth(
    s: xr.DataArray,
    stretching: xr.DataArray,
    bathymetry: xr.DataArray,
    elevation: xr.DataArray,
    hc: xr.DataArray | float,
    vtransform: int,
) -> xr.DataArray:
    if vtransform == 1:
        z0 = hc * s + (bathymetry - hc) * stretching
        z = z0 + elevation * (1.0 + z0 / bathymetry)
    elif vtransform == 2:
        z0 = (hc * s + bathymetry * stretching) / (hc + bathymetry)
        z = elevation + (elevation + bathymetry) * z0
    else:
        raise ValueError("ROMS Vtransform must be 1 or 2")
    return elevation - z


def _roms_s_coordinates(
    dataset: xr.Dataset, config: dict, vertical_dim: str
) -> tuple[xr.DataArray, xr.DataArray, xr.DataArray, xr.DataArray]:
    """Decode standard ROMS/CROCO s-coordinates to positive-down metres."""
    h = _mask_missing(dataset[config["bathymetry_variable"]], config)
    h = _normalize_depth_sign(h, config.get("bathymetry_positive", "down"))
    elevation_name = config.get("sea_surface_elevation_variable")
    elevation = (
        _mask_missing(dataset[elevation_name], config)
        if elevation_name
        else xr.zeros_like(h)
    )
    hc = _scalar_from_config_or_dataset(
        dataset, config, "hc_value", "hc_variable"
    )
    vtransform = int(
        _scalar_from_config_or_dataset(
            dataset, config, "vtransform_value", "vtransform_variable"
        )
    )

    s_center = _select_active(dataset[config["center_variable"]], vertical_dim, config)
    c_center = _select_active(
        dataset[config["center_stretching_variable"]], vertical_dim, config
    )
    s_center = _surface_to_bottom(s_center, vertical_dim, config)
    c_center = _surface_to_bottom(c_center, vertical_dim, config)

    s_interface = dataset[config["interface_variable"]]
    c_interface = dataset[config["interface_stretching_variable"]]
    interface_dim = _interface_dimension(s_interface, dataset, config, vertical_dim)
    s_interface = _surface_to_bottom(s_interface, interface_dim, config)
    c_interface = _surface_to_bottom(c_interface, interface_dim, config)

    z_center = _roms_depth(
        s_center, c_center, h, elevation, hc, vtransform
    ).rename("z_center")
    z_interface = _roms_depth(
        s_interface, c_interface, h, elevation, hc, vtransform
    ).rename("z_interface")
    bottom = z_interface.isel({interface_dim: -1}, drop=True).rename(
        "model_bottom_depth"
    )
    wet = (
        xr.apply_ufunc(np.isfinite, z_center, dask="allowed").all(vertical_dim)
        & xr.apply_ufunc(np.isfinite, z_interface, dask="allowed").all(interface_dim)
        & (z_interface.diff(interface_dim) > 0.0).all(interface_dim)
    )
    return z_center, z_interface, bottom, wet


def _interfaces_from_centers(
    z_center: xr.DataArray,
    bottom: xr.DataArray,
    vertical_dim: str,
) -> xr.DataArray:
    interface_dim = f"{vertical_dim}_interface"
    count = z_center.sizes[vertical_dim]
    surface = xr.zeros_like(z_center.isel({vertical_dim: 0}, drop=True)).expand_dims(
        {interface_dim: [0]}
    )
    pieces = [surface]

    if count > 1:
        left = z_center.isel({vertical_dim: slice(0, -1)}).rename(
            {vertical_dim: interface_dim}
        )
        right = z_center.isel({vertical_dim: slice(1, None)}).rename(
            {vertical_dim: interface_dim}
        )
        positional = np.arange(1, count)
        left = left.assign_coords({interface_dim: positional})
        right = right.assign_coords({interface_dim: positional})
        pieces.append(0.5 * (left + right))

    pieces.append(bottom.expand_dims({interface_dim: [count]}))
    combined = xr.concat(pieces, dim=interface_dim)
    return combined.transpose(
        *[dim for dim in combined.dims if dim != interface_dim], interface_dim
    )


def _bottom_from_centers(
    z_center: xr.DataArray, vertical_dim: str
) -> xr.DataArray:
    count = z_center.sizes[vertical_dim]
    last = z_center.isel({vertical_dim: -1}, drop=True)
    if count == 1:
        return 2.0 * last
    previous = z_center.isel({vertical_dim: -2}, drop=True)
    return last + 0.5 * (last - previous)


def _normalize_centers(
    dataset: xr.Dataset, config: dict, vertical_dim: str, variable: str
) -> tuple[xr.DataArray, xr.DataArray | None, xr.DataArray]:
    if variable not in dataset:
        raise KeyError(f"Depth variable {variable!r} was not found")
    center = _select_active(dataset[variable], vertical_dim, config)
    center = _surface_to_bottom(center, vertical_dim, config)
    center = _normalized_depth(center, dataset, config).rename("z_center")

    interface = None
    if config.get("interface_variable"):
        interface, _, interface_dim = _normalize_interfaces(
            dataset, config, vertical_dim
        )
        bottom = interface.isel({interface_dim: -1}, drop=True)
    else:
        bottom = _configured_bottom(dataset, config, vertical_dim)
        if bottom is None:
            bottom = _bottom_from_centers(center, vertical_dim)
        interface = _interfaces_from_centers(center, bottom, vertical_dim)
    return center, interface, bottom


def _interface_dimension(
    interface: xr.DataArray,
    dataset: xr.Dataset,
    config: dict,
    vertical_dim: str,
) -> str:
    configured = config.get("interface_dimension")
    if configured:
        if configured not in interface.dims:
            raise ValueError(
                f"Configured interface dimension {configured!r} is not in "
                f"{interface.dims}"
            )
        return configured

    center_size = dataset.sizes.get(vertical_dim)
    candidates = [
        dim
        for dim in interface.dims
        if dim != vertical_dim
        and center_size is not None
        and interface.sizes[dim] == center_size + 1
    ]
    if len(candidates) == 1:
        return candidates[0]
    if vertical_dim in interface.dims and center_size is not None:
        if interface.sizes[vertical_dim] == center_size + 1:
            return vertical_dim
    raise ValueError(
        "Could not infer the interface dimension; configure "
        "vertical_coordinate.interface_dimension"
    )


def _normalize_interfaces(
    dataset: xr.Dataset, config: dict, vertical_dim: str
) -> tuple[xr.DataArray, xr.DataArray, str]:
    name = config["interface_variable"]
    if name not in dataset:
        raise KeyError(f"Interface variable {name!r} was not found")
    interface = _mask_missing(dataset[name], config)
    interface_dim = _interface_dimension(interface, dataset, config, vertical_dim)
    interface_config = dict(config)
    interface_config["positive"] = config.get(
        "interface_positive", config.get("positive", "down")
    )
    interface = _normalized_depth(interface, dataset, interface_config)
    interface = _surface_to_bottom(interface, interface_dim, config)
    interface = interface.rename("z_interface")

    left = interface.isel({interface_dim: slice(0, -1)}).rename(
        {interface_dim: vertical_dim}
    )
    right = interface.isel({interface_dim: slice(1, None)}).rename(
        {interface_dim: vertical_dim}
    )
    count = left.sizes[vertical_dim]
    center_coordinate = dataset.coords.get(vertical_dim)
    if center_coordinate is not None and center_coordinate.size == count:
        values = center_coordinate.values
        order = str(
            config.get("native_order", config.get("layer_order", "surface_to_bottom"))
        ).lower()
        if order in _BOTTOM_TO_SURFACE:
            values = values[::-1]
    else:
        values = np.arange(count)
    left = left.assign_coords({vertical_dim: values})
    right = right.assign_coords({vertical_dim: values})
    center = (0.5 * (left + right)).rename("z_center")
    bottom = interface.isel({interface_dim: -1}, drop=True)
    return interface, center, interface_dim


def prepare_vertical_coordinates(
    profile_dataset: xr.Dataset,
    vertical_config: dict | None,
    vertical_dim: str,
) -> tuple[xr.DataArray, xr.DataArray | None, xr.DataArray, xr.DataArray]:
    """Normalize Tier-1 vertical inputs to physical positive-down depths.

    Returns ``z_center``, ``z_interface``, ``model_bottom_depth`` and a
    geometry-only ``wet_profile`` mask.  Arrays remain lazy when inputs are
    Dask-backed.
    """
    config = _config(vertical_config)
    method = _require_tier1(config)
    if vertical_dim not in profile_dataset.dims:
        raise ValueError(f"Vertical dimension {vertical_dim!r} was not found")

    if method == "layer_thickness":
        name = config["thickness_variable"]
        if name not in profile_dataset:
            raise KeyError(f"Thickness variable {name!r} was not found")
        thickness = _select_active(profile_dataset[name], vertical_dim, config)
        thickness = _surface_to_bottom(thickness, vertical_dim, config)
        thickness = _mask_missing(thickness, config)
        valid_thickness = xr.apply_ufunc(
            np.isfinite, thickness, dask="allowed"
        ) & (thickness > 0.0)
        wet = valid_thickness.all(vertical_dim)
        safe_thickness = thickness.where(valid_thickness)
        cumulative = safe_thickness.cumsum(vertical_dim, skipna=False)
        z_center = (cumulative - 0.5 * safe_thickness).rename("z_center")
        bottom = safe_thickness.sum(vertical_dim, skipna=False).rename(
            "model_bottom_depth"
        )
        interface_dim = f"{vertical_dim}_interface"
        surface = xr.zeros_like(bottom).expand_dims({interface_dim: [0]})
        remainder = cumulative.rename({vertical_dim: interface_dim}).assign_coords(
            {interface_dim: np.arange(1, cumulative.sizes[vertical_dim] + 1)}
        )
        z_interface = xr.concat([surface, remainder], dim=interface_dim).rename(
            "z_interface"
        )
        z_interface = z_interface.transpose(
            *[dim for dim in z_interface.dims if dim != interface_dim],
            interface_dim,
        )
    elif method == "interface_variable":
        z_interface, z_center, interface_dim = _normalize_interfaces(
            profile_dataset, config, vertical_dim
        )
        bottom = z_interface.isel({interface_dim: -1}, drop=True).rename(
            "model_bottom_depth"
        )
        interface_valid = xr.apply_ufunc(
            np.isfinite, z_interface, dask="allowed"
        ).all(interface_dim)
        increasing_interfaces = (z_interface.diff(interface_dim) > 0.0).all(
            interface_dim
        )
        wet = interface_valid & increasing_interfaces
    elif method == "sigma_fraction":
        z_center, z_interface, bottom, wet = _sigma_fraction_coordinates(
            profile_dataset, config, vertical_dim
        )
    elif method == "roms_s_coordinate":
        z_center, z_interface, bottom, wet = _roms_s_coordinates(
            profile_dataset, config, vertical_dim
        )
    else:
        variable = config.get("depth_variable", config.get("z_variable", "z"))
        z_center, z_interface, bottom = _normalize_centers(
            profile_dataset, config, vertical_dim, variable
        )
        bottom = bottom.rename("model_bottom_depth")
        wet = xr.apply_ufunc(np.isfinite, z_center, dask="allowed").all(
            vertical_dim
        )

    configured_wet = _configured_wet_levels(
        profile_dataset, config, vertical_dim
    )
    if configured_wet is not None:
        if vertical_dim in configured_wet.dims:
            if config.get("allow_trailing_missing_levels", False):
                bottom, contiguous = _column_bottom_from_wet_levels(
                    z_interface, configured_wet, vertical_dim
                )
                wet = wet & contiguous
            else:
                wet = wet & configured_wet.all(vertical_dim)
        else:
            wet = wet & configured_wet

    increasing = (z_center.diff(vertical_dim) > 0.0).all(vertical_dim)
    nonnegative = (z_center >= 0.0).all(vertical_dim)
    if config.get("allow_trailing_missing_levels", False):
        deepest_center = z_center.where(z_center <= bottom).max(
            vertical_dim, skipna=True
        )
    else:
        deepest_center = z_center.isel({vertical_dim: -1}, drop=True)
    bottom_valid = xr.apply_ufunc(np.isfinite, bottom, dask="allowed") & (
        bottom >= deepest_center
    )
    wet = (wet & increasing & nonnegative & bottom_valid).rename("wet_profile")

    z_center = z_center.where(wet)
    if z_interface is not None:
        z_interface = z_interface.where(wet)
    bottom = bottom.where(wet)
    return z_center, z_interface, bottom, wet


def _prepare_tracer_profile(
    tracer: xr.DataArray,
    z_center: xr.DataArray,
    model_bottom_depth: xr.DataArray | None,
    wet_profile: xr.DataArray,
    vertical_dim: str,
    config: dict,
) -> tuple[xr.DataArray, xr.DataArray, xr.DataArray, xr.DataArray]:
    """Align and validate a tracer profile without transforming it."""
    if vertical_dim in z_center.coords and vertical_dim in tracer.coords:
        tracer = tracer.sel({vertical_dim: z_center[vertical_dim]})
    tracer = _mask_missing(tracer, config)
    tracer, z_center = xr.align(tracer, z_center, join="exact")

    finite_levels = xr.apply_ufunc(np.isfinite, tracer, dask="allowed")
    if config.get("allow_trailing_missing_levels", False):
        if model_bottom_depth is None:
            raise ValueError(
                "allow_trailing_missing_levels requires model bottom depth"
            )
        required_levels = z_center <= model_bottom_depth
        finite_tracer = (finite_levels | ~required_levels).all(vertical_dim)

        def fill_trailing(values):
            result = np.array(values, copy=True)
            valid = np.isfinite(result)
            if valid.any():
                result[np.flatnonzero(valid)[-1] + 1 :] = result[valid][-1]
            return result

        tracer = xr.apply_ufunc(
            fill_trailing,
            tracer,
            input_core_dims=[[vertical_dim]],
            output_core_dims=[[vertical_dim]],
            vectorize=True,
            dask="parallelized",
            output_dtypes=[tracer.dtype],
            dask_gufunc_kwargs={"allow_rechunk": True},
        )
    else:
        finite_tracer = finite_levels.all(vertical_dim)
    valid_profile = wet_profile & finite_tracer
    return tracer, z_center, finite_tracer, valid_profile


def _interpolate_prepared_profile(
    tracer: xr.DataArray,
    observation_depth: xr.DataArray,
    z_center: xr.DataArray,
    model_bottom_depth: xr.DataArray,
    valid_profile: xr.DataArray,
    vertical_dim: str,
) -> xr.DataArray:
    tracer = tracer.where(valid_profile).chunk({vertical_dim: -1})
    z_center = z_center.where(valid_profile).chunk({vertical_dim: -1})

    grid_dataset = xr.Dataset(
        {"tracer": tracer.rename("tracer"), "z_center": z_center.rename("z_center")}
    )
    grid = Grid(
        grid_dataset,
        coords={"Z": {"center": vertical_dim}},
        padding="fill",
        autoparse_metadata=False,
    )

    target_dim = "observation_depth_target"
    target = observation_depth.astype(float).expand_dims({target_dim: [0]}, axis=-1)
    transformed = grid.transform(
        grid_dataset["tracer"],
        "Z",
        target,
        target_data=grid_dataset["z_center"],
        target_dim=target_dim,
        method="linear",
        mask_edges=False,
        bypass_checks=True,
    ).squeeze(target_dim, drop=True)

    physical_bounds = (
        xr.apply_ufunc(np.isfinite, observation_depth, dask="allowed")
        & (observation_depth >= 0.0)
        & (observation_depth <= model_bottom_depth)
    )
    return transformed.where(valid_profile & physical_bounds).rename(tracer.name)


def interpolate_with_diagnostics(
    tracer: xr.DataArray,
    observation_depth: xr.DataArray,
    z_center: xr.DataArray,
    model_bottom_depth: xr.DataArray,
    wet_profile: xr.DataArray,
    vertical_dim: str,
    vertical_config: dict | None,
) -> xr.Dataset:
    """Interpolate once and return the value with its diagnostic masks."""
    config = _config(vertical_config)
    _require_tier1(config)
    if config["observation_reference"] not in _INSTANTANEOUS_SURFACE:
        raise NotImplementedError(
            "Tier 1 requires observation depths below the instantaneous surface"
        )
    if config["outside_column"] != "missing":
        raise NotImplementedError("Tier 1 supports outside_column: missing only")

    tracer, z_center, finite_tracer, valid_profile = _prepare_tracer_profile(
        tracer,
        z_center,
        model_bottom_depth,
        wet_profile,
        vertical_dim,
        config,
    )
    transformed = _interpolate_prepared_profile(
        tracer,
        observation_depth,
        z_center,
        model_bottom_depth,
        valid_profile,
        vertical_dim,
    )

    finite_depth = xr.apply_ufunc(
        np.isfinite, observation_depth, dask="allowed"
    )
    finite_bottom = xr.apply_ufunc(
        np.isfinite, model_bottom_depth, dask="allowed"
    )
    valid_model_column = wet_profile & finite_bottom
    above_surface = finite_depth & (observation_depth < 0.0)
    below_bottom = (
        finite_depth
        & valid_model_column
        & (observation_depth > model_bottom_depth)
    )

    return xr.Dataset(
        {
            "mod": transformed,
            "valid_model_column": valid_model_column,
            "finite_tracer_profile": finite_tracer,
            "above_model_surface": above_surface,
            "below_model_bottom": below_bottom,
            "within_vertical_bounds": (
                finite_depth
                & valid_model_column
                & (observation_depth >= 0.0)
                & (observation_depth <= model_bottom_depth)
            ),
            "transformed_finite": xr.apply_ufunc(
                np.isfinite, transformed, dask="allowed"
            ),
            "model_bottom_depth": model_bottom_depth,
        }
    )


def interpolate_to_observation_depths(
    tracer: xr.DataArray,
    observation_depth: xr.DataArray,
    z_center: xr.DataArray,
    model_bottom_depth: xr.DataArray,
    wet_profile: xr.DataArray,
    vertical_dim: str,
    vertical_config: dict | None,
) -> xr.DataArray:
    """Return only the interpolated value for callers that do not need diagnostics."""
    return interpolate_with_diagnostics(
        tracer,
        observation_depth,
        z_center,
        model_bottom_depth,
        wet_profile,
        vertical_dim,
        vertical_config,
    )["mod"].rename(tracer.name)
