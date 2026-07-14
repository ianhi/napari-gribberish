import numpy as np
import pytest

from napari_gribberish import _reader
from napari_gribberish._reader import (
    _dataset_to_layers,
    _spatial_transform,
    napari_get_reader,
)


@pytest.mark.parametrize(
    'name',
    ['a.grib', 'a.grib2', 'a.grb', 'a.grb2', 'PATH.GRIB2', 'x.y.grib'],
)
def test_get_reader_accepts_grib(name):
    assert callable(napari_get_reader(name))


@pytest.mark.parametrize(
    'name', ['a.npy', 'a.nc', 'a.txt', 'grib', 'a.grib.bak']
)
def test_get_reader_rejects_non_grib(name):
    assert napari_get_reader(name) is None


def test_get_reader_handles_list():
    assert callable(napari_get_reader(['a.grib2', 'b.grib2']))


def test_get_reader_handles_non_string():
    assert napari_get_reader(42) is None
    assert napari_get_reader([]) is None


def test_dataset_to_layers(grib_like_dataset):
    layers = _dataset_to_layers(grib_like_dataset, source='/tmp/file.grib2')

    assert len(layers) == 2
    for data, kwargs, layer_type in layers:
        assert layer_type == 'image'
        assert data.shape == (5, 4)
        assert kwargs['colormap'] == 'plasma'
        assert kwargs['metadata']['source'] == '/tmp/file.grib2'
        # valid_time is promoted from the dataset coords into metadata
        assert 'valid_time' in kwargs['metadata']

    names = [kwargs['name'] for _, kwargs, _ in layers]
    assert any('tmp' in n for n in names)

    # only the first variable is revealed; the rest are toggled on demand
    visibility = [kwargs['visible'] for _, kwargs, _ in layers]
    assert visibility == [True, False]


def test_dataset_to_layers_units_and_long_name(grib_like_dataset):
    layers = _dataset_to_layers(grib_like_dataset, source='file.grib2')
    tmp_layer = next(k for _, k, _ in layers if k['name'].startswith('tmp'))
    assert tmp_layer['metadata']['units'] == 'K'
    assert tmp_layer['metadata']['long_name'] == 'Temperature'


def test_dataset_to_layers_keeps_units_out_of_kwargs():
    """GRIB-style units (e.g. ``m2 s-2``) must not reach napari's pint-parsed
    ``units=`` kwarg; they belong in metadata only."""
    import xarray as xr

    da = xr.DataArray(
        np.zeros((3, 3)),
        dims=('latitude', 'longitude'),
        attrs={'unit': 'm2 s-2', 'long_name': 'Geopotential'},
    )
    ds = xr.Dataset({'z': da})
    (_, kwargs, _) = _dataset_to_layers(ds, source='z.grib2')[0]
    assert 'units' not in kwargs
    assert kwargs['metadata']['units'] == 'm2 s-2'


def test_directional_variable_gets_cyclic_colormap():
    import xarray as xr

    grid = np.zeros((3, 3))
    ds = xr.Dataset(
        {
            'dirpw': xr.DataArray(
                grid,
                dims=('latitude', 'longitude'),
                attrs={'unit': 'degree', 'long_name': 'primarywavedirection'},
            ),
            'htsgw': xr.DataArray(
                grid,
                dims=('latitude', 'longitude'),
                attrs={'unit': 'm', 'long_name': 'significantwaveheight'},
            ),
        }
    )
    layers = {
        k['name'].split()[0]: k for _, k, _ in _dataset_to_layers(ds, 'w')
    }
    assert layers['dirpw']['colormap'] == 'twilight_shifted'
    assert layers['htsgw']['colormap'] == 'plasma'


def test_dataset_to_layers_skips_scalars():
    import xarray as xr

    ds = xr.Dataset({'scalar': xr.DataArray(1.0)})
    assert _dataset_to_layers(ds, source='x.grib2') == []


def test_spatial_transform_regular(grib_like_dataset):
    scale, translate = _spatial_transform(grib_like_dataset['tmp'])
    # lat descending by 2.5, lon ascending by 10/3
    np.testing.assert_allclose(scale, [-2.5, 10.0 / 3.0])
    np.testing.assert_allclose(translate, [50.0, -100.0])


def test_spatial_transform_irregular():
    import xarray as xr

    lat = np.array([0.0, 1.0, 3.0])  # not evenly spaced
    da = xr.DataArray(
        np.zeros((3, 2)),
        dims=('latitude', 'longitude'),
        coords={'latitude': lat, 'longitude': [0.0, 1.0]},
    )
    scale, translate = _spatial_transform(da)
    assert scale is None and translate is None


def test_reader_function_end_to_end(monkeypatch, grib_like_dataset):
    """reader_function should open via the backend and emit layer tuples."""
    monkeypatch.setattr(_reader, '_open_grib', lambda path: grib_like_dataset)
    reader = napari_get_reader('sample.grib2')
    layers = reader('sample.grib2')
    assert len(layers) == 2
    assert all(t[2] == 'image' for t in layers)
