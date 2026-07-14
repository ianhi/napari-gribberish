"""Dock widget for browsing and loading GRIB variables into napari.

GRIB files frequently bundle dozens of variables (temperature, wind, wave
height, ...). The reader loads them all as separate layers (only the first
shown), which keeps drag-and-drop silent and scriptable. This widget is the
interactive alternative: pick a file, choose which variables to load, and how
to display them.

Display modes:

* **separate** - one layer per variable, only the first visible (toggle the
  rest). Best when variables have unrelated units/ranges.
* **blend** - all selected variables visible with additive blending. Useful
  for a few co-registered fields you want to overlay.
* **grid** - all selected variables visible in napari's grid view, side by
  side for comparison.

See https://napari.org/stable/plugins/building_a_plugin/guides.html#widgets
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from magicgui.types import FileDialogMode
from magicgui.widgets import (
    Container,
    FileEdit,
    Label,
    PushButton,
    RadioButtons,
    Select,
)

from ._reader import _dataset_to_layers, _open_grib

if TYPE_CHECKING:
    import napari
    import xarray as xr

DISPLAY_MODES = ('separate', 'blend', 'grid')


class GribVariableSelector(Container):
    """Pick a GRIB file, choose variables, and how to display them."""

    def __init__(self, viewer: napari.viewer.Viewer):
        super().__init__(labels=False)
        self._viewer = viewer
        self._dataset: xr.Dataset | None = None

        self._file_edit = FileEdit(
            label='GRIB file',
            mode=FileDialogMode.EXISTING_FILE,
            filter='GRIB files (*.grib *.grib2 *.grb *.grb2);;All files (*)',
        )
        self._status = Label(value='Select a GRIB file to list its variables.')
        self._var_select = Select(label='Variables', choices=())
        self._mode = RadioButtons(
            label='Display',
            choices=DISPLAY_MODES,
            orientation='horizontal',
        )
        self._mode.value = 'separate'
        self._load_button = PushButton(text='Add selected as layers')
        self._load_button.enabled = False

        self._file_edit.changed.connect(self._on_file_changed)
        self._load_button.clicked.connect(self._on_load_clicked)

        self.extend(
            [
                self._file_edit,
                self._status,
                self._var_select,
                self._mode,
                self._load_button,
            ]
        )

    def _on_file_changed(self) -> None:
        """Open the chosen file and populate the variable list."""
        path = str(self._file_edit.value or '')
        self._dataset = None
        self._var_select.choices = ()
        self._load_button.enabled = False

        if not path:
            self._status.value = 'Select a GRIB file to list its variables.'
            return

        try:
            self._dataset = _open_grib(path)
        except Exception as exc:  # noqa: BLE001 - surface any backend error
            self._status.value = f'Could not open file: {exc}'
            return

        variables = tuple(str(v) for v in self._dataset.data_vars)
        if not variables:
            self._status.value = 'No data variables found in this file.'
            return

        self._var_select.choices = variables
        self._var_select.value = variables
        self._load_button.enabled = True
        self._status.value = f'{len(variables)} variable(s) available.'

    def _on_load_clicked(self) -> None:
        """Add the selected variables to the viewer in the chosen mode."""
        if self._dataset is None:
            return

        selected = set(self._var_select.value)
        if not selected:
            self._status.value = 'Select at least one variable to load.'
            return

        # Preserve the dataset's variable order (Select returns an unordered
        # set) so the "first visible" layer is deterministic.
        ordered = [v for v in self._dataset.data_vars if v in selected]
        layers = _dataset_to_layers(
            self._dataset[ordered], source=str(self._file_edit.value)
        )

        mode = self._mode.value
        # Grid view is a viewer-level setting; only enable it for grid mode so
        # we don't leave a stale grid layout behind for the other modes.
        self._viewer.grid.enabled = mode == 'grid'

        for data, add_kwargs, _ in layers:
            # 'separate' keeps the reader default (only the first visible);
            # blend and grid reveal every selected variable.
            if mode != 'separate':
                add_kwargs['visible'] = True
            if mode == 'blend':
                add_kwargs['blending'] = 'additive'
            self._viewer.add_image(data, **add_kwargs)

        self._status.value = f'Added {len(layers)} layer(s) ({mode}).'
