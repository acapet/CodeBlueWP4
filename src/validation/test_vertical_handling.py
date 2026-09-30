from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr
import yaml

from vertical_handling import (
    check_configuration,
    interpolate_to_observation_depths,
    mask_vertical_inputs,
    prepare_vertical_coordinates,
)


def _layer_profiles(
    thickness,
    tracer=None,
    points=1,
    chunks=None,
):
    thickness = np.asarray(thickness, dtype=float)
    if thickness.ndim == 1:
        thickness = np.tile(thickness, (points, 1))
    if tracer is None:
        tracer = np.tile(
            np.arange(1, thickness.shape[1] + 1, dtype=float),
            (thickness.shape[0], 1),
        )
    dataset = xr.Dataset(
        {
            "h": (("points", "level"), thickness),
            "tracer": (("points", "level"), np.asarray(tracer, dtype=float)),
        },
        coords={
            "points": np.arange(thickness.shape[0]),
            "level": np.arange(thickness.shape[1]),
        },
    )
    return dataset.chunk(chunks) if chunks else dataset


def test_equal_layers_and_physical_outer_half_layers():
    dataset = _layer_profiles(
        [2.0, 2.0, 2.0],
        tracer=np.tile([10.0, 20.0, 30.0], (7, 1)),
        points=7,
    )
    config = {
        "method": "layer_thickness",
        "thickness_variable": "h",
        "native_order": "surface_to_bottom",
    }
    z_center, z_interface, bottom, wet = prepare_vertical_coordinates(
        dataset, config, "level"
    )
    np.testing.assert_allclose(z_center.isel(points=0), [1.0, 3.0, 5.0])
    np.testing.assert_allclose(
        z_interface.isel(points=0), [0.0, 2.0, 4.0, 6.0]
    )
    np.testing.assert_allclose(bottom, 6.0)
    assert wet.all()

    observations = xr.DataArray(
        [0.0, 1.0, 2.0, 5.0, 6.0, -0.1, 6.1],
        dims="points",
        coords={"points": dataset.points},
    )
    result = interpolate_to_observation_depths(
        dataset.tracer,
        observations,
        z_center,
        bottom,
        wet,
        "level",
        config,
    ).compute()
    np.testing.assert_allclose(
        result.values[:5], [10.0, 10.0, 15.0, 30.0, 30.0]
    )
    assert np.isnan(result.values[5:]).all()


def test_unequal_bottom_to_surface_layers_and_inactive_padding():
    dataset = xr.Dataset(
        {
            "h": (("points", "level"), [[-9999.0, 3.0, 2.0, 1.0]]),
            "tracer": (
                ("points", "level"),
                [[-9999.0, 30.0, 20.0, 10.0]],
            ),
        },
        coords={"points": [0], "level": [0, 1, 2, 3]},
    )
    config = {
        "method": "layer_thickness",
        "thickness_variable": "h",
        "native_order": "bottom_to_surface",
        "inactive_level_indices": [0],
        "missing_values": [-9999.0],
    }
    dataset = mask_vertical_inputs(dataset, config)
    z_center, z_interface, bottom, wet = prepare_vertical_coordinates(
        dataset, config, "level"
    )
    assert list(z_center.level.values) == [3, 2, 1]
    np.testing.assert_allclose(z_center.values, [[0.5, 2.0, 4.5]])
    np.testing.assert_allclose(z_interface.values, [[0.0, 1.0, 3.0, 6.0]])
    assert bottom.item() == pytest.approx(6.0)
    assert wet.item()

    observation = xr.DataArray([2.0], dims="points", coords={"points": [0]})
    result = interpolate_to_observation_depths(
        dataset.tracer,
        observation,
        z_center,
        bottom,
        wet,
        "level",
        config,
    )
    assert result.compute().item() == pytest.approx(20.0)


def test_check_configuration_excludes_inactive_tracer_padding(tmp_path, capsys):
    model_path = tmp_path / "native_2014.nc"
    shape = (1, 4, 3, 3)
    thickness = np.empty(shape, dtype=float)
    thickness[:, 0, :, :] = -9999.0
    thickness[:, 1, :, :] = 3.0
    thickness[:, 2, :, :] = 2.0
    thickness[:, 3, :, :] = 1.0
    tracer = np.empty(shape, dtype=float)
    tracer[:, 0, :, :] = -9999.0
    tracer[:, 1, :, :] = 30.0
    tracer[:, 2, :, :] = 20.0
    tracer[:, 3, :, :] = 10.0

    xr.Dataset(
        {
            "h": (("time", "level", "lat", "lon"), thickness),
            "tracer": (("time", "level", "lat", "lon"), tracer),
        },
        coords={
            "time": pd.to_datetime(["2014-01-01"]),
            "level": [0, 1, 2, 3],
            "lat": [50.0, 51.0, 52.0],
            "lon": [2.0, 3.0, 4.0],
        },
    ).to_netcdf(model_path)

    configuration = {
        "files": {"pattern": str(model_path).replace("2014", "{year}")},
        "coordinates": {
            "time": "time",
            "lon": "lon",
            "lat": "lat",
            "vertical": "level",
        },
        "vertical_coordinate": {
            "method": "layer_thickness",
            "thickness_variable": "h",
            "native_order": "bottom_to_surface",
            "inactive_level_indices": [0],
            "missing_values": [-9999.0],
        },
        "variables": {
            "temp": {"model_name": "tracer", "conversion": 1.0}
        },
    }
    config_path = tmp_path / "native.yml"
    config_path.write_text(yaml.safe_dump(configuration, sort_keys=False))

    check_configuration(config_path, 2014)
    output = capsys.readouterr().out
    assert "Complete wet tracer profiles: {'tracer': 9}" in output
    assert "CHECK PASSED (read-only; no NetCDF or Parquet written)" in output


def test_time_varying_thickness_preserves_instantaneous_bottom():
    dataset = xr.Dataset(
        {
            "h": (("time", "level"), [[1.0, 2.0], [2.0, 3.0]]),
            "tracer": (("time", "level"), [[10.0, 20.0], [30.0, 40.0]]),
        },
        coords={"time": [0, 1], "level": [0, 1]},
    )
    config = {
        "method": "layer_thickness",
        "thickness_variable": "h",
        "native_order": "surface_to_bottom",
    }
    center, _, bottom, wet = prepare_vertical_coordinates(dataset, config, "level")
    np.testing.assert_allclose(center, [[0.5, 2.0], [1.0, 3.5]])
    np.testing.assert_allclose(bottom, [3.0, 5.0])
    target = xr.DataArray([3.0, 5.0], dims="time", coords={"time": [0, 1]})
    result = interpolate_to_observation_depths(
        dataset.tracer, target, center, bottom, wet, "level", config
    )
    np.testing.assert_allclose(result.compute(), [20.0, 40.0])


def test_dry_zero_negative_missing_and_fill_profiles_are_rejected():
    dataset = _layer_profiles(
        [
            [1.0, 2.0],
            [0.0, 0.0],
            [1.0, -1.0],
            [1.0, np.nan],
            [1.0, -9999.0],
        ]
    )
    config = {
        "method": "layer_thickness",
        "thickness_variable": "h",
        "missing_values": [-9999.0],
    }
    dataset = mask_vertical_inputs(dataset, config)
    _, _, _, wet = prepare_vertical_coordinates(dataset, config, "level")
    np.testing.assert_array_equal(wet.values, [True, False, False, False, False])


@pytest.mark.parametrize(
    ("positive", "centers", "bottom_value", "bottom_positive"),
    [
        ("down", [1.0, 3.0, 5.0], 6.0, "down"),
        ("up", [-1.0, -3.0, -5.0], -6.0, "up"),
    ],
)
def test_existing_and_depth_variable_signs(
    positive, centers, bottom_value, bottom_positive
):
    dataset = xr.Dataset(
        {
            "z_native": ("level", centers),
            "bottom": xr.DataArray(bottom_value),
        },
        coords={"level": [0, 1, 2]},
    )
    config = {
        "method": "depth_variable",
        "depth_variable": "z_native",
        "bottom_depth_variable": "bottom",
        "positive": positive,
        "bottom_depth_positive": bottom_positive,
        "reference": "instantaneous_surface",
    }
    center, interface, bottom, wet = prepare_vertical_coordinates(
        dataset, config, "level"
    )
    np.testing.assert_allclose(center, [1.0, 3.0, 5.0])
    np.testing.assert_allclose(interface, [0.0, 2.0, 4.0, 6.0])
    assert bottom.item() == pytest.approx(6.0)
    assert wet.item()


def test_interface_variable_derives_centers_and_bounds():
    dataset = xr.Dataset(
        {
            "interfaces": ("level_interface", [0.0, 2.0, 5.0, 9.0]),
        },
        coords={"level": [10, 20, 30], "level_interface": [0, 1, 2, 3]},
    )
    config = {
        "method": "interface_variable",
        "interface_variable": "interfaces",
        "interface_dimension": "level_interface",
        "positive": "down",
    }
    center, interface, bottom, wet = prepare_vertical_coordinates(
        dataset, config, "level"
    )
    np.testing.assert_allclose(center, [1.0, 3.5, 7.0])
    np.testing.assert_allclose(interface, [0.0, 2.0, 5.0, 9.0])
    assert bottom.item() == pytest.approx(9.0)
    assert wet.item()


def test_fixed_depth_uses_local_bottom_and_rejects_below_bottom():
    dataset = xr.Dataset(
        {
            "depth": ("level", [1.0, 3.0, 5.0]),
            "bottom": ("points", [4.0, 6.0]),
            "tracer": (
                ("points", "level"),
                [[10.0, 20.0, 30.0], [10.0, 20.0, 30.0]],
            ),
        },
        coords={"points": [0, 1], "level": [0, 1, 2]},
    )
    config = {
        "method": "fixed_depth",
        "depth_variable": "depth",
        "bottom_depth_variable": "bottom",
        "positive": "down",
    }
    center, _, bottom, wet = prepare_vertical_coordinates(dataset, config, "level")
    np.testing.assert_array_equal(wet, [False, True])
    target = xr.DataArray([4.5, 4.5], dims="points", coords={"points": [0, 1]})
    result = interpolate_to_observation_depths(
        dataset.tracer, target, center, bottom, wet, "level", config
    ).compute()
    assert np.isnan(result[0])
    assert result[1] == pytest.approx(27.5)


def test_dask_vertical_rechunk_and_transform():
    dataset = _layer_profiles(
        [1.0, 1.0, 1.0, 1.0],
        tracer=[[1.0, 2.0, 3.0, 4.0]],
        chunks={"points": 1, "level": 1},
    )
    config = {"method": "layer_thickness", "thickness_variable": "h"}
    center, _, bottom, wet = prepare_vertical_coordinates(dataset, config, "level")
    target = xr.DataArray([2.0], dims="points", coords={"points": [0]})
    result = interpolate_to_observation_depths(
        dataset.tracer, target, center, bottom, wet, "level", config
    )
    assert hasattr(result.data, "chunks")
    assert result.compute().item() == pytest.approx(2.5)


def test_original_command_and_parquet_contract(tmp_path):
    validation_dir = Path(__file__).resolve().parent
    script = validation_dir / "Extract_validation_tables.py"
    model_path = tmp_path / "toy_2014.nc"
    observation_dir = tmp_path / "observations"
    output_dir = tmp_path / "outputs"
    observation_dir.mkdir()
    output_dir.mkdir()

    times = pd.to_datetime(["2014-01-01", "2014-01-02"])
    levels = np.array([0.25, 0.75])
    tracer = np.empty((2, 2, 3, 3), dtype=np.float64)
    tracer[:, 0, :, :] = 1.0
    tracer[:, 1, :, :] = 3.0
    tracer[:, :, 0, 2] = np.nan
    bathymetry = np.full((3, 3), 10.0)
    bathymetry[2, 2] = np.nan
    model = xr.Dataset(
        {
            "tracer": (("time", "lev", "lat", "lon"), tracer),
            "missing_tracer": (
                ("time", "lev", "lat", "lon"),
                np.full_like(tracer, -9998.0),
            ),
            "depth": (("lat", "lon"), bathymetry),
        },
        coords={
            "time": times,
            "lev": levels,
            "lat": [50.0, 51.0, 52.0],
            "lon": [2.0, 3.0, 4.0],
        },
    )
    model.to_netcdf(model_path)

    variables = [
        "oxy", "nox", "nh4", "po4", "sio", "chl", "temp", "sal", "talk"
    ]
    for variable in variables:
        frame = pd.DataFrame(
            {
                "datetime": pd.to_datetime([
                    "2014-01-01", "2014-01-01", "2014-01-01",
                    "2014-01-01", "2014-01-03", "2014-01-01",
                    "2014-01-01",
                ], utc=True),
                "lon": [2.0, 2.0, 2.0, 5.0, 2.0, 4.0, 4.0],
                "lat": [50.0, 50.0, 50.0, 50.0, 50.0, 52.0, 50.0],
                "depth": [5.0, 11.0, -1.0, 5.0, 5.0, 5.0, 5.0],
                variable: [8.0] * 7,
                f"{variable}_qv": [0] * 7,
            }
        )
        frame.to_parquet(observation_dir / f"{variable}_2014.parquet", index=False)

    configuration = {
        "model": {"name": "TOY"},
        "files": {
            "pattern": str(model_path).replace("2014", "{year}"),
            "insitudatadir": f"{observation_dir}/",
            "outdir": f"{output_dir}/",
        },
        "coordinates": {
            "time": "time",
            "lon": "lon",
            "lat": "lat",
            "vertical": "lev",
        },
        "derived_variables": {"z": {"expression": "lev * depth"}},
        "vertical_coordinate": {
            "method": "existing_z",
            "z_variable": "z",
            "bottom_depth_variable": "depth",
            "positive": "down",
            "reference": "instantaneous_surface",
            "observation_reference": "instantaneous_surface",
            "outside_column": "missing",
        },
        "variables": {
            variable: {
                "model_name": "tracer",
                "conversion": 2.0 if variable == "oxy" else 1.0,
            }
            for variable in variables
        },
    }
    config_path = tmp_path / "toy.yml"
    config_path.write_text(yaml.safe_dump(configuration, sort_keys=False))

    completed = subprocess.run(
        [
            sys.executable, str(script), "-v", "--match-diagnostics",
            "toy", "2014",
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

    for variable in variables:
        path = output_dir / f"VALID_{variable}_2014_toy.parquet"
        assert path.is_file()
        result = pd.read_parquet(path)
        assert list(result.columns) == [
            "datetime",
            "lon",
            "lat",
            "depth",
            variable,
            f"{variable}_qv",
            "mod",
        ]
        assert len(result) == 6
        assert str(result["datetime"].dt.tz) == "UTC"

        diagnostic_path = output_dir / f"MATCH_STATUS_{variable}_2014_toy.parquet"
        assert diagnostic_path.is_file()
        diagnostic = pd.read_parquet(diagnostic_path)
        assert len(diagnostic) == 7
        assert diagnostic["match_status"].tolist() == [
            "matched",
            "below_model_bottom",
            "above_model_surface",
            "outside_horizontal_bounds",
            "outside_model_time_range",
            "no_valid_model_column",
            "missing_model_tracer_profile",
        ]
        below = diagnostic.loc[
            diagnostic["match_status"] == "below_model_bottom"
        ].iloc[0]
        assert below["model_bottom_depth"] == pytest.approx(10.0)
        assert below["depth_minus_model_bottom"] == pytest.approx(1.0)

    oxygen = pd.read_parquet(output_dir / "VALID_oxy_2014_toy.parquet")
    assert oxygen["mod"].iloc[0] == pytest.approx(4.0)

    summary_path = output_dir / "MATCH_STATUS_SUMMARY_2014_toy.csv"
    assert summary_path.is_file()
    summary = pd.read_csv(summary_path)
    assert set(summary["variable"]) == set(variables)
    assert summary.groupby("variable")["N"].sum().eq(7).all()

    check_configuration = dict(configuration)
    check_configuration["variables"] = {
        "missing_first": {
            "model_name": "missing_tracer",
            "conversion": 1.0,
        },
        "valid_second": {
            "model_name": "tracer",
            "conversion": 1.0,
        },
    }
    check_config_path = tmp_path / "toy_check.yml"
    check_config_path.write_text(
        yaml.safe_dump(check_configuration, sort_keys=False)
    )

    checked = subprocess.run(
        [
            sys.executable,
            str(validation_dir / "vertical_handling.py"),
            str(check_config_path),
            "2014",
            "--check",
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "Tracer: tracer" in checked.stdout
    assert "'missing_tracer': 0" in checked.stdout
    assert "CHECK PASSED (read-only; no NetCDF or Parquet written)" in checked.stdout
