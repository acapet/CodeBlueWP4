#!/usr/bin/env python3
"""Tier-1 vertical-coordinate handling for CodeBlue validation.

All model-native vertical coordinates are normalized in memory to metres below
the instantaneous water surface, positive downward.  This module never writes
model data.  Model-specific variable names and conventions remain in YAML.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import xarray as xr
import yaml
from xgcm import Grid


TIER1_METHODS = {
    "existing_z",
    "layer_thickness",
    "interface_variable",
    "depth_variable",
    "fixed_depth",
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
    else:
        required = [config.get("depth_variable", config.get("z_variable", "z"))]

    optional_keys = (
        "interface_variable",
        "thickness_variable",
        "bottom_depth_variable",
        "surface_variable",
        "bathymetry_variable",
        "sea_surface_elevation_variable",
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
    else:
        variable = config.get("depth_variable", config.get("z_variable", "z"))
        z_center, z_interface, bottom = _normalize_centers(
            profile_dataset, config, vertical_dim, variable
        )
        bottom = bottom.rename("model_bottom_depth")
        wet = xr.apply_ufunc(np.isfinite, z_center, dask="allowed").all(
            vertical_dim
        )

    increasing = (z_center.diff(vertical_dim) > 0.0).all(vertical_dim)
    nonnegative = (z_center >= 0.0).all(vertical_dim)
    bottom_valid = xr.apply_ufunc(np.isfinite, bottom, dask="allowed") & (
        bottom >= z_center.isel({vertical_dim: -1}, drop=True)
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
    wet_profile: xr.DataArray,
    vertical_dim: str,
    config: dict,
) -> tuple[xr.DataArray, xr.DataArray, xr.DataArray, xr.DataArray]:
    """Align and validate a tracer profile without transforming it."""
    if vertical_dim in z_center.coords and vertical_dim in tracer.coords:
        tracer = tracer.sel({vertical_dim: z_center[vertical_dim]})
    tracer = _mask_missing(tracer, config)
    tracer, z_center = xr.align(tracer, z_center, join="exact")

    finite_tracer = xr.apply_ufunc(np.isfinite, tracer, dask="allowed").all(
        vertical_dim
    )
    valid_profile = wet_profile & finite_tracer
    return tracer, z_center, finite_tracer, valid_profile


def observation_match_diagnostics(
    tracer: xr.DataArray,
    observation_depth: xr.DataArray,
    z_center: xr.DataArray,
    model_bottom_depth: xr.DataArray,
    wet_profile: xr.DataArray,
    vertical_dim: str,
    vertical_config: dict | None,
    transformed: xr.DataArray,
) -> xr.Dataset:
    """Return diagnostic masks explaining whether a collocation can succeed.

    These masks describe inputs to the existing transform; they do not fill or
    alter any model value. Horizontal bounding-box and time-range exclusions
    are assigned by the caller before profiles reach this function.
    """
    config = _config(vertical_config)
    _require_tier1(config)
    _, _, finite_tracer, _ = _prepare_tracer_profile(
        tracer, z_center, wet_profile, vertical_dim, config
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
    within_vertical_bounds = (
        finite_depth
        & valid_model_column
        & (observation_depth >= 0.0)
        & (observation_depth <= model_bottom_depth)
    )

    return xr.Dataset(
        {
            "valid_model_column": valid_model_column,
            "finite_tracer_profile": finite_tracer,
            "above_model_surface": above_surface,
            "below_model_bottom": below_bottom,
            "within_vertical_bounds": within_vertical_bounds,
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
    """Transform collocated profiles to one physical depth per observation."""
    config = _config(vertical_config)
    _require_tier1(config)
    if config["observation_reference"] not in _INSTANTANEOUS_SURFACE:
        raise NotImplementedError(
            "Tier 1 requires observation depths below the instantaneous surface"
        )
    if config["outside_column"] != "missing":
        raise NotImplementedError("Tier 1 supports outside_column: missing only")

    tracer, z_center, _, valid_profile = _prepare_tracer_profile(
        tracer, z_center, wet_profile, vertical_dim, config
    )
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


def _derived_variables(dataset: xr.Dataset, config: dict) -> xr.Dataset:
    """Evaluate trusted legacy YAML expressions for read-only check mode."""
    import re

    result = dataset
    for new_name, specification in config.get("derived_variables", {}).items():
        expression = specification["expression"]
        for name in list(result.data_vars) + list(result.coords):
            expression = re.sub(
                rf"\b{re.escape(name)}\b", f"result[{name!r}]", expression
            )
        result[new_name] = eval(expression, {"__builtins__": {}}, {"result": result})
    return result


def _sample_indexers(dataset: xr.Dataset, vertical_dim: str) -> dict[str, list[int]]:
    indexers = {}
    for dim, size in dataset.sizes.items():
        if dim == vertical_dim:
            continue
        values = sorted(set((0, size // 2, size - 1)))
        indexers[dim] = values
    return indexers


def check_configuration(config_path: Path, year: int) -> None:
    """Run a read-only sampled vertical configuration check."""
    with config_path.open() as stream:
        config = yaml.safe_load(stream)
    vertical = _config(config.get("vertical_coordinate"))
    method = _require_tier1(vertical)
    vertical_dim = config["coordinates"]["vertical"]
    model_path = Path(config["files"]["pattern"].format(year=year))
    if not model_path.is_file():
        raise FileNotFoundError(model_path)

    source = xr.open_dataset(model_path, chunks={})
    try:
        source = _derived_variables(source, config)
        model_variable_specs = {}
        for specification in config.get("variables", {}).values():
            name = specification.get("model_name")
            if name in source and name not in model_variable_specs:
                model_variable_specs[name] = specification
        model_variables = list(model_variable_specs)
        if not model_variables:
            raise KeyError("No configured validation tracer exists in the model file")
        required = vertical_input_names(vertical)
        missing = [name for name in required if name not in source]
        if missing:
            raise KeyError(f"Missing configured vertical inputs: {missing}")

        selected = source[list(dict.fromkeys(model_variables + required))]
        selected = selected.isel(_sample_indexers(selected, vertical_dim))
        selected = mask_vertical_inputs(selected, vertical)
        z_center, z_interface, bottom, wet = prepare_vertical_coordinates(
            selected, vertical, vertical_dim
        )

        tracer_profile_counts = {}
        masked_tracers = {}
        for name, specification in model_variable_specs.items():
            tracer_config = dict(vertical)
            tracer_config["missing_values"] = specification.get(
                "missing_values", vertical.get("missing_values", [])
            )
            masked, _, finite_profile, _ = _prepare_tracer_profile(
                selected[name], z_center, wet, vertical_dim, tracer_config
            )
            count = int((wet & finite_profile).sum().compute())
            tracer_profile_counts[name] = count
            masked_tracers[name] = masked

        tracer_name = max(tracer_profile_counts, key=tracer_profile_counts.get)
        if tracer_profile_counts[tracer_name] == 0:
            raise ValueError(
                "No sampled wet column has a complete configured tracer profile; "
                f"counts={tracer_profile_counts}"
            )
        selected_tracer = masked_tracers[tracer_name]

        # Match the production extractor contract: one vertical profile and
        # one target depth per ``points`` element.  Broadcast static geometry
        # across tracer dimensions before stacking so this also works when a
        # depth or bottom variable has no time dimension.
        tracer_for_transform, z_for_transform = xr.broadcast(
            selected_tracer, z_center
        )
        profile_template = tracer_for_transform.isel(
            {vertical_dim: 0}, drop=True
        )
        bottom_for_transform = bottom.broadcast_like(profile_template)
        wet_for_transform = wet.broadcast_like(profile_template)
        profile_dims = list(profile_template.dims)
        tracer_for_transform = tracer_for_transform.stack(points=profile_dims)
        z_for_transform = z_for_transform.stack(points=profile_dims)
        bottom_for_transform = bottom_for_transform.stack(points=profile_dims)
        wet_for_transform = wet_for_transform.stack(points=profile_dims)

        chunks = tracer_for_transform.chunksizes.get(vertical_dim, ())
        print(f"Configuration: {config_path}")
        print(f"Model file: {model_path}")
        print(f"Method: {method}")
        print(f"Tracer: {tracer_name}; dimensions={selected_tracer.dims}")
        print(f"Complete wet tracer profiles: {tracer_profile_counts}")
        print(f"Required vertical variables: {required}")
        print(
            "Native order: "
            f"{vertical.get('native_order', vertical.get('layer_order', 'surface_to_bottom'))}"
        )
        print(f"Normalized center range: {float(z_center.min().compute())} to {float(z_center.max().compute())} m")
        print(f"Bottom-depth range: {float(bottom.min().compute())} to {float(bottom.max().compute())} m")
        print(
            "Wet sampled profiles: "
            f"{int(wet_for_transform.sum().compute())} / {wet_for_transform.size}"
        )
        print(f"Vertical chunks before transform: {chunks or 'unchunked'}")
        if z_interface is not None:
            print(f"Interface dimensions: {z_interface.dims}")

        if method == "layer_thickness":
            thickness = selected[vertical["thickness_variable"]]
            print(f"Thickness range: {float(thickness.min().compute())} to {float(thickness.max().compute())} m")
            bathymetry_name = vertical.get("bathymetry_variable")
            elevation_name = vertical.get("sea_surface_elevation_variable")
            if bathymetry_name and elevation_name:
                expected = selected[bathymetry_name] + selected[elevation_name]
                residual = bottom - expected
                maximum = float(abs(residual).max(skipna=True).compute())
                tolerance = float(vertical.get("water_depth_tolerance_m", 0.05))
                print(f"max(abs(sum(h)-bathymetry-elevation)): {maximum} m")
                if maximum > tolerance:
                    print(f"WARNING: water-depth residual exceeds {tolerance} m")

        target = 0.5 * bottom_for_transform
        transformed = interpolate_to_observation_depths(
            tracer_for_transform,
            target,
            z_for_transform,
            bottom_for_transform,
            wet_for_transform,
            vertical_dim,
            vertical,
        )
        finite = int(
            xr.apply_ufunc(
                np.isfinite, transformed, dask="allowed"
            ).sum().compute()
        )
        print(f"XGCM sample transform finite results: {finite} / {transformed.size}")
        if finite == 0:
            raise ValueError(
                "The sampled configuration produced no finite XGCM transforms"
            )
        print("CHECK PASSED (read-only; no NetCDF or Parquet written)")
    finally:
        source.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("configuration", type=Path, help="model YAML file")
    parser.add_argument("year", type=int)
    parser.add_argument("--check", action="store_true", help="run read-only checks")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.check:
        raise SystemExit("vertical_handling.py is standalone only with --check")
    check_configuration(args.configuration, args.year)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
