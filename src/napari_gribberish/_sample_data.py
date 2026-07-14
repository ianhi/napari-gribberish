"""Sample data provider for napari-gribberish.

Loads a small slice of NOAA HRRR (High-Resolution Rapid Refresh) surface data
directly from the public AWS Open Data bucket. This exercises gribberish's
remote-reading path: only the requested variables are fetched, using the
sidecar ``.idx`` index for efficient partial downloads.

See https://napari.org/stable/plugins/building_a_plugin/guides.html#sample-data
"""

from __future__ import annotations

# A stable, long-retained file in the public HRRR archive on AWS Open Data.
# https://registry.opendata.aws/noaa-hrrr-pds/
_HRRR_URL = (
    's3://noaa-hrrr-bdp-pds/hrrr.20240101/conus/hrrr.t00z.wrfsfcf00.grib2'
)
# Anonymous, region-pinned access for the public bucket.
_STORAGE_OPTIONS = {'region': 'us-east-1', 'skip_signature': True}
# 2 m temperature and 10 m wind gust: small, familiar surface fields.
_VARIABLES = ['tmp', 'gust']


def make_sample_data():
    """Return LayerData tuples for a HRRR surface temperature/gust sample.

    Requires network access to the public ``noaa-hrrr-bdp-pds`` S3 bucket.
    """
    import xarray as xr

    from ._reader import _dataset_to_layers

    ds = xr.open_dataset(
        _HRRR_URL,
        engine='gribberish',
        group='sfc/instant',
        use_index='auto',
        only_variables=_VARIABLES,
        storage_options=_STORAGE_OPTIONS,
    )
    return _dataset_to_layers(ds, source=_HRRR_URL)
