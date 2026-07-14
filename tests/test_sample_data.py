import xarray as xr

from napari_gribberish import _sample_data
from napari_gribberish._sample_data import make_sample_data


def test_make_sample_data_returns_layers(monkeypatch, grib_like_dataset):
    """make_sample_data should read via the backend and return layer tuples.

    We stub out ``xarray.open_dataset`` so the test needs no network access,
    and assert the expected engine/options are passed through.
    """
    captured = {}

    def fake_open_dataset(url, **kwargs):
        captured['url'] = url
        captured['kwargs'] = kwargs
        return grib_like_dataset

    monkeypatch.setattr(xr, 'open_dataset', fake_open_dataset)

    layers = make_sample_data()

    assert captured['url'] == _sample_data._HRRR_URL
    assert captured['kwargs']['engine'] == 'gribberish'
    assert captured['kwargs']['only_variables'] == _sample_data._VARIABLES
    assert len(layers) == 2
    assert all(layer[2] == 'image' for layer in layers)
