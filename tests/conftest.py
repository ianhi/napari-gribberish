"""Shared test fixtures.

These build synthetic :class:`xarray.Dataset` objects that mimic what the
gribberish backend returns, so the plugin's logic can be tested without a
GRIB encoder or network access.
"""

import numpy as np
import pytest
import xarray as xr


@pytest.fixture
def grib_like_dataset():
    """A dataset resembling a decoded GRIB file with a regular lat/lon grid."""
    lat = np.linspace(50.0, 40.0, 5)  # descending, evenly spaced
    lon = np.linspace(-100.0, -90.0, 4)  # ascending, evenly spaced
    rng = np.random.default_rng(0)

    tmp = xr.DataArray(
        rng.random((5, 4)),
        dims=('latitude', 'longitude'),
        coords={'latitude': lat, 'longitude': lon},
        attrs={'unit': 'K', 'long_name': 'Temperature'},
    )
    gust = xr.DataArray(
        rng.random((5, 4)),
        dims=('latitude', 'longitude'),
        coords={'latitude': lat, 'longitude': lon},
        attrs={'units': 'm s-1', 'long_name': 'Wind gust'},
    )
    return xr.Dataset(
        {'tmp': tmp, 'gust': gust},
        coords={'valid_time': np.datetime64('2024-01-01T00:00:00')},
    )
