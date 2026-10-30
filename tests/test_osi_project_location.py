import os
import sys
from PySide6.QtWidgets import QApplication

from osdagbridge_core.utils.common import KEY_PROJECT_LOCATION
import osdagbridge_desktop.ui.dialogs.project_location as pl_mod
from osdagbridge_desktop.ui.dialogs.project_location import (
    ProjectLocationDialog, set_project_location_session,
)


def _get_app():
    return QApplication.instance() or QApplication(["-platform", "offscreen"])


def test_set_project_location_session_location_name():
    loc = {
        "method": "location_name",
        "data": {"state": "Maharashtra", "district": "Pune"},
        "weather_data": {
            "wind_speed": "39",
            "zone": "III",
            "z_value": "0.16",
            "max_temp": "42.0",
            "min_temp": "10.0",
        },
        "display_text": "Pune, Maharashtra",
        "show_display": True,
    }
    set_project_location_session(loc)
    assert pl_mod.LAST_LOCATION_METHOD == "location_name"
    assert pl_mod.LAST_LOCATION_DATA == {"state": "Maharashtra", "district": "Pune"}
    assert pl_mod.LAST_WEATHER_DATA["zone"] == "III"
    assert pl_mod.LAST_CUSTOM_DATA is None


def test_set_project_location_session_map():
    loc = {
        "method": "map",
        "data": {"latitude": "18.5204", "longitude": "73.8567", "station": "Pune", "state": "Maharashtra"},
        "weather_data": {
            "wind_speed": "39",
            "zone": "III",
            "z_value": "0.16",
            "max_temp": "42.0",
            "min_temp": "10.0",
        },
        "display_text": "Pune, Maharashtra",
        "show_display": True,
    }
    set_project_location_session(loc)
    assert pl_mod.LAST_LOCATION_METHOD == "map"
    assert pl_mod.LAST_LOCATION_DATA["latitude"] == "18.5204"
    assert pl_mod.LAST_LOCATION_DATA["station"] == "Pune"


def test_set_project_location_session_custom_data():
    loc = {
        "method": "custom_data",
        "data": {},
        "weather_data": {
            "wind_speed": "44",
            "zone": "IV",
            "z_value": "0.24",
            "max_temp": "45.0",
            "min_temp": "5.0",
        },
        "display_text": "Custom Data",
        "show_display": True,
    }
    set_project_location_session(loc)
    assert pl_mod.LAST_LOCATION_METHOD == "custom_data"
    assert pl_mod.LAST_LOCATION_DATA is None
    assert pl_mod.LAST_CUSTOM_DATA == {
        "wind_speed": "44",
        "zone": "IV",
        "max_temp": "45.0",
        "min_temp": "5.0",
    }


def test_set_project_location_session_none():
    set_project_location_session(None)
    assert pl_mod.LAST_LOCATION_METHOD is None
    assert pl_mod.LAST_LOCATION_DATA is None
    assert pl_mod.LAST_WEATHER_DATA is None
    assert pl_mod.LAST_CUSTOM_DATA is None


def test_input_dock_populate_project_location():
    app = _get_app()

    from osdagbridge_desktop.ui.docks.input_dock import InputDock
    from osdagbridge_core.bridge_types.plate_girder.defaults import BASIC_INPUT_DICT
    from osdagbridge_core.bridge_types.plate_girder.plategirderbridge import PlateGirderBridge

    class DummyParent:
        def __init__(self):
            self.input_dict = dict(BASIC_INPUT_DICT)
        def common_design_func(self, *args, **kwargs):
            pass

    parent = DummyParent()
    backend = PlateGirderBridge()
    dock = InputDock(backend, parent)

    info_lbl = dock._w(f"{KEY_PROJECT_LOCATION}_info_label")
    info_row = dock._w(f"{KEY_PROJECT_LOCATION}_info_row")
    assert info_lbl is not None
    assert info_row is not None
    assert info_row.isHidden()

    # Load OSI data with project location
    osi_data = dict(BASIC_INPUT_DICT)
    osi_data[KEY_PROJECT_LOCATION] = {
        "method": "location_name",
        "data": {"state": "Maharashtra", "district": "Pune"},
        "weather_data": {
            "wind_speed": "39",
            "zone": "III",
            "z_value": "0.16",
            "max_temp": "42.0",
            "min_temp": "10.0",
        },
        "display_text": "Pune, Maharashtra",
        "show_display": True,
    }

    dock.populate_from_dict(osi_data)

    assert not info_row.isHidden()
    assert info_lbl.text() == "Pune, Maharashtra"
    assert parent.input_dict[KEY_PROJECT_LOCATION]["method"] == "location_name"
    assert pl_mod.LAST_LOCATION_METHOD == "location_name"

    # Now load OSI data with None for project location
    empty_osi = dict(BASIC_INPUT_DICT)
    empty_osi[KEY_PROJECT_LOCATION] = None
    dock.populate_from_dict(empty_osi)

    assert info_row.isHidden()
    assert info_lbl.text() == "Location not selected"
    assert pl_mod.LAST_LOCATION_METHOD is None


def test_e2e_yaml_save_and_load_dialog_state(tmp_path):
    import yaml
    from osdagbridge_desktop.ui.docks.input_dock import InputDock
    from osdagbridge_core.bridge_types.plate_girder.defaults import BASIC_INPUT_DICT
    from osdagbridge_core.bridge_types.plate_girder.plategirderbridge import PlateGirderBridge
    from osdagbridge_core.utils.osi_validator import validate_osi_inputs

    app = _get_app()

    class DummyParent:
        def __init__(self):
            self.input_dict = dict(BASIC_INPUT_DICT)
        def common_design_func(self, *args, **kwargs):
            pass

    parent = DummyParent()
    backend = PlateGirderBridge()
    dock = InputDock(backend, parent)

    # 1. Simulate saving inputs with Project Location set
    saved_inputs = dict(BASIC_INPUT_DICT)
    saved_inputs[KEY_PROJECT_LOCATION] = {
        "method": "location_name",
        "data": {"state": "Maharashtra", "district": "Pune"},
        "weather_data": {
            "wind_speed": "39",
            "zone": "III",
            "z_value": "0.16",
            "max_temp": "42.0",
            "min_temp": "10.0",
        },
        "display_text": "Pune, Maharashtra",
        "show_display": True,
    }

    file_path = os.path.join(str(tmp_path), "test_inputs.osi")
    with open(file_path, "w") as f:
        yaml.dump(saved_inputs, f)

    # 2. Simulate loading the OSI file
    with open(file_path, "r") as f:
        loaded_data = yaml.safe_load(f)

    assert validate_osi_inputs(loaded_data).is_valid

    dock.populate_from_dict(loaded_data)

    info_lbl = dock._w(f"{KEY_PROJECT_LOCATION}_info_label")
    info_row = dock._w(f"{KEY_PROJECT_LOCATION}_info_row")
    assert not info_row.isHidden()
    assert info_lbl.text() == "Pune, Maharashtra"

    # 3. Simulate user opening the ProjectLocationDialog after loading
    dialog = ProjectLocationDialog()
    assert dialog.method_radio_location.isChecked()
    assert dialog.state_combo.currentText() == "Maharashtra"
    assert dialog.district_combo.currentText() == "Pune"
    assert dialog.location_city_label.text() == "City: Pune"
    assert dialog.location_state_label.text() == "State: Maharashtra"
    dialog.reject()


if __name__ == "__main__":
    import tempfile
    test_set_project_location_session_location_name()
    test_set_project_location_session_map()
    test_set_project_location_session_custom_data()
    test_set_project_location_session_none()
    test_input_dock_populate_project_location()
    with tempfile.TemporaryDirectory() as td:
        test_e2e_yaml_save_and_load_dialog_state(td)
    print("ALL TESTS PASSED SUCCESSFULLY!")

