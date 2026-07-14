from napari_gribberish import _widget
from napari_gribberish._widget import GribVariableSelector


def test_variable_selector_populates_and_loads(
    make_napari_viewer, monkeypatch, grib_like_dataset
):
    monkeypatch.setattr(_widget, '_open_grib', lambda path: grib_like_dataset)
    viewer = make_napari_viewer()
    widget = GribVariableSelector(viewer)

    # Simulate the user choosing a file.
    widget._file_edit.value = 'sample.grib2'
    widget._on_file_changed()

    assert set(widget._var_select.choices) == {'tmp', 'gust'}
    assert widget._load_button.enabled

    # Load only one of the two variables.
    widget._var_select.value = ['tmp']
    widget._on_load_clicked()

    assert len(viewer.layers) == 1
    assert viewer.layers[0].name.startswith('tmp')


def test_blend_mode_makes_all_visible_and_additive(
    make_napari_viewer, monkeypatch, grib_like_dataset
):
    monkeypatch.setattr(_widget, '_open_grib', lambda path: grib_like_dataset)
    viewer = make_napari_viewer()
    widget = GribVariableSelector(viewer)
    widget._file_edit.value = 'sample.grib2'
    widget._on_file_changed()

    widget._mode.value = 'blend'
    widget._on_load_clicked()

    assert len(viewer.layers) == 2
    assert all(layer.visible for layer in viewer.layers)
    assert all(layer.blending == 'additive' for layer in viewer.layers)
    assert not viewer.grid.enabled


def test_grid_mode_enables_grid_view(
    make_napari_viewer, monkeypatch, grib_like_dataset
):
    monkeypatch.setattr(_widget, '_open_grib', lambda path: grib_like_dataset)
    viewer = make_napari_viewer()
    widget = GribVariableSelector(viewer)
    widget._file_edit.value = 'sample.grib2'
    widget._on_file_changed()

    widget._mode.value = 'grid'
    widget._on_load_clicked()

    assert viewer.grid.enabled
    assert all(layer.visible for layer in viewer.layers)


def test_variable_selector_handles_open_error(make_napari_viewer, monkeypatch):
    def boom(path):
        raise ValueError('bad file')

    monkeypatch.setattr(_widget, '_open_grib', boom)
    viewer = make_napari_viewer()
    widget = GribVariableSelector(viewer)

    widget._file_edit.value = 'broken.grib2'
    widget._on_file_changed()

    assert not widget._load_button.enabled
    assert 'Could not open file' in widget._status.value
    assert len(viewer.layers) == 0
