"""napari reader for GRIB (GRIB1 / GRIB2) files, powered by ``gribberish``.

The reader opens a GRIB file with the ``gribberish`` xarray backend and turns
each data variable into a napari image layer. Non-spatial dimensions (time,
vertical level, ensemble member, ...) become slider axes in the viewer.

See https://napari.org/stable/plugins/building_a_plugin/guides.html#readers
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import xarray as xr

# Extensions commonly used for GRIB1/GRIB2 messages.
GRIB_SUFFIXES = ('.grib', '.grib2', '.grb', '.grb2')


def napari_get_reader(path):
    """Return a reader function if ``path`` looks like a GRIB file.

    This performs only cheap, path-based checks: napari calls ``get_reader``
    on every registered plugin, so it must be fast and must never raise.

    Parameters
    ----------
    path : str or list of str
        Path to a file, or list of paths.

    Returns
    -------
    function or None
        ``reader_function`` if the path has a GRIB extension, else ``None``.
    """
    # A stack of paths is handed to us as a list; we only read one GRIB file
    # per call, so inspect the first entry.
    single = path
    if isinstance(path, list):
        single = path[0] if path else None

    if not isinstance(single, str):
        return None

    if single.lower().endswith(GRIB_SUFFIXES):
        return reader_function

    return None


def reader_function(path):
    """Read GRIB file(s) and return a list of napari LayerData tuples.

    Each data variable in the file becomes one image layer.

    Parameters
    ----------
    path : str or list of str
        Path to a GRIB file, or a list of paths (each read independently).

    Returns
    -------
    list of tuple
        ``(data, add_kwargs, "image")`` tuples, one per data variable.
    """
    paths = [path] if isinstance(path, str) else path

    layers: list[tuple] = []
    for p in paths:
        ds = _open_grib(p)
        layers.extend(_dataset_to_layers(ds, source=p))
    return layers


def _open_grib(path: str) -> xr.Dataset:
    """Open a GRIB file as a single flat :class:`xarray.Dataset`.

    ``collapse_groups=True`` flattens gribberish's nested groups (e.g.
    ``sfc/instant``) into one dataset so every variable is directly available.
    """
    import xarray as xr

    return xr.open_dataset(path, engine='gribberish', collapse_groups=True)


def _dataset_to_layers(ds: xr.Dataset, source: str) -> list[tuple]:
    """Convert every data variable of ``ds`` into an image LayerData tuple."""
    base = os.path.basename(source)
    # Reference/valid time coords are shared by all variables in the dataset,
    # so materialise them once rather than per layer.
    time_meta = _reference_time_metadata(ds)
    layers: list[tuple] = []
    for name, da in ds.data_vars.items():
        # Skip anything without at least a 2D grid to display.
        if da.ndim < 2:
            continue

        # gribberish exposes the unit as ``unit`` (singular); fall back to the
        # CF-style ``units`` used by other backends. We keep it in metadata
        # rather than passing napari's ``units=`` kwarg: that kwarg describes
        # the *axis* units and is parsed by pint, which rejects GRIB-style
        # strings such as ``m2 s-2``.
        units = da.attrs.get('unit') or da.attrs.get('units')
        long_name = da.attrs.get('long_name') or da.attrs.get('standard_name')

        metadata = {'source': source, 'dims': list(da.dims)}
        metadata.update({str(k): v for k, v in da.attrs.items()})
        metadata.update(time_meta)
        if units:
            metadata['units'] = units
        if long_name:
            metadata['long_name'] = long_name

        # napari image layers are opaque and stack on top of each other, so a
        # file with many variables would show only the topmost one. Load them
        # all but reveal just the first; the user toggles the rest on demand.
        add_kwargs: dict = {
            'name': f'{name} ({base})' if long_name else str(name),
            'colormap': _default_colormap(str(name), units, long_name),
            'visible': not layers,
            'metadata': metadata,
        }

        scale, translate = _spatial_transform(da)
        if scale is not None:
            add_kwargs['scale'] = scale
            add_kwargs['translate'] = translate

        layers.append((np.asarray(da.values), add_kwargs, 'image'))

    return layers


def _default_colormap(name: str, units, long_name) -> str:
    """Pick a sensible colormap for a variable.

    Directional fields (wave/wind direction) are circular in [0, 360)°, where a
    sequential map wrongly shows 0° and 360° as opposite extremes. Give those a
    cyclic colormap; everything else gets the perceptually-uniform ``plasma``.

    ``twilight_shifted`` is cyclic with dark endpoints, so the 0-fill often used
    over land/missing areas stays dark rather than a jarring bright colour.
    """
    unit = (units or '').lower()
    text = f'{long_name or ""} {name}'.lower()
    is_degrees = unit.startswith('degree')
    # Rely on the CF long name containing the word "direction" (e.g.
    # "primarywavedirection") rather than a bare "dir" substring, which would
    # false-match names like "dirt" or "redirect".
    is_direction = 'direction' in text
    if is_degrees and is_direction:
        return 'twilight_shifted'  # cyclic
    return 'plasma'


def _reference_time_metadata(ds: xr.Dataset) -> dict:
    """Extract dataset-level time coordinates shared across all variables."""
    meta = {}
    for key in ('time', 'valid_time', 'reference_time', 'step'):
        if key in ds.coords:
            meta[key] = np.asarray(ds.coords[key].values).tolist()
    return meta


def _spatial_transform(da: xr.DataArray):
    """Derive ``(scale, translate)`` from evenly spaced 1D grid coordinates.

    Returns ``(None, None)`` when the last two dimensions are not backed by
    regular 1D coordinates, so napari falls back to pixel coordinates. Leading
    (non-spatial) axes always get unit scale/zero offset.
    """
    if da.ndim < 2:
        return None, None

    row_dim, col_dim = str(da.dims[-2]), str(da.dims[-1])
    row_step = _regular_step(da, row_dim)
    col_step = _regular_step(da, col_dim)
    if row_step is None or col_step is None:
        return None, None

    row_origin = float(np.asarray(da[row_dim].values)[0])
    col_origin = float(np.asarray(da[col_dim].values)[0])

    lead = da.ndim - 2
    scale = [1.0] * lead + [row_step, col_step]
    translate = [0.0] * lead + [row_origin, col_origin]
    return scale, translate


def _regular_step(da: xr.DataArray, dim: str) -> float | None:
    """Return the constant spacing of coordinate ``dim`` if it is regular."""
    if dim not in da.coords:
        return None

    values = np.asarray(da[dim].values)
    if values.ndim != 1 or values.size < 2:
        return None

    diffs = np.diff(values)
    if not np.allclose(diffs, diffs[0], rtol=1e-4, atol=0):
        return None
    return float(diffs[0])
