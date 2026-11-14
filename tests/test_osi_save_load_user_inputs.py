import yaml
from PySide6.QtWidgets import QApplication, QLineEdit, QComboBox

from osdagbridge_core.core.utils.common import (
    KEY_SPAN,
    KEY_CARRIAGEWAY_WIDTH,
    KEY_FOOTPATH,
    KEY_DESIGN_MODE,
    KEY_TS_NO_OF_GIRDERS,
    KEY_TS_GIRDER_SPACING,
    KEY_TS_DECK_OVERHANG,
    KEY_TS_DECK_THICKNESS,
    KEY_MP_GD_SELECT_GIRDER,
    KEY_MP_GIRDER_DEPTH,
    KEY_MP_GIRDER_TOP_FLANGE_WIDTH,
    KEY_MP_CB_SELECT_GIRDERS,
    KEY_MP_CB_NO_OF_CROSS_BRACINGS,
    KEY_MP_CB_SPACING,
    KEY_PL_SELF_WEIGHT_FACTOR,
    KEY_DO_GAMMA_C_BASIC,
)
from osdagbridge_core.core.bridge_types.plate_girder.defaults import (
    solve_extend_basic_input_dict,
)


def _get_app():
    return QApplication.instance() or QApplication(["-platform", "offscreen"])


def test_save_and_load_osi_user_inputs(tmp_path):
    _get_app()

    from osdagbridge_desktop.ui.template_page import CustomWindow
    from osdagbridge_desktop.ui.dialogs.additional_input.additional_inputs import AdditionalInputs

    # 1. Prepare user inputs with custom (non-default) values across all tabs
    user_inputs = {
        KEY_SPAN: 30.0,
        KEY_CARRIAGEWAY_WIDTH: 7.5,
        KEY_FOOTPATH: "None",
        KEY_DESIGN_MODE: "Custom",
        KEY_TS_NO_OF_GIRDERS: 6,
        KEY_TS_DECK_THICKNESS: 320.0,
        f"{KEY_MP_GIRDER_DEPTH}.G1.M1": 1900,
        f"{KEY_MP_GIRDER_TOP_FLANGE_WIDTH}.G1.M1": 550,
        KEY_MP_CB_NO_OF_CROSS_BRACINGS: 7,
        KEY_MP_CB_SPACING: 3.75,
        KEY_PL_SELF_WEIGHT_FACTOR: "1.15",
        KEY_DO_GAMMA_C_BASIC: "1.35",
    }

    # 2. Simulate saveOSI_inputs: solve_extend must not clobber user inputs
    solve_extend_basic_input_dict(user_inputs)

    assert user_inputs[KEY_TS_NO_OF_GIRDERS] == 6
    assert float(user_inputs[KEY_TS_DECK_THICKNESS]) == 320.0
    assert float(user_inputs[f"{KEY_MP_GIRDER_DEPTH}.G1.M1"]) == 1900
    assert float(user_inputs[f"{KEY_MP_GIRDER_TOP_FLANGE_WIDTH}.G1.M1"]) == 550
    assert user_inputs[KEY_MP_CB_NO_OF_CROSS_BRACINGS] == 7
    assert user_inputs[KEY_MP_CB_SPACING] == 3.75
    assert user_inputs[KEY_PL_SELF_WEIGHT_FACTOR] == "1.15"
    assert user_inputs[KEY_DO_GAMMA_C_BASIC] == "1.35"

    osi_path = tmp_path / "test_user_inputs.osi"
    with open(osi_path, "w") as f:
        yaml.dump(user_inputs, f)

    # 3. Simulate loadOSI_inputs into AdditionalInputs dialog
    with open(osi_path, "r") as f:
        loaded_data = yaml.safe_load(f)

    dlg = AdditionalInputs()
    dlg.set_input_dictionary(loaded_data)
    dlg.design_mode_trigger("Custom")

    # Verify dialog's working_input_dict and widgets have the loaded values
    assert dlg.working_input_dict[KEY_TS_NO_OF_GIRDERS] == 6
    assert float(dlg.working_input_dict[KEY_TS_DECK_THICKNESS]) == 320.0
    assert float(dlg.working_input_dict[f"{KEY_MP_GIRDER_DEPTH}.G1.M1"]) == 1900
    assert dlg.working_input_dict[KEY_MP_CB_NO_OF_CROSS_BRACINGS] == 7
    assert dlg.working_input_dict[KEY_DO_GAMMA_C_BASIC] == "1.35"

    # Verify visible widgets
    deck_thick_w = dlg.findChild(QLineEdit, KEY_TS_DECK_THICKNESS)
    assert deck_thick_w is not None
    assert float(deck_thick_w.text()) == 320.0

    girders_combo = dlg.findChild(QComboBox, KEY_MP_GD_SELECT_GIRDER)
    assert girders_combo is not None
    assert girders_combo.count() == 6

    cb_pairs_combo = dlg.findChild(QComboBox, KEY_MP_CB_SELECT_GIRDERS)
    assert cb_pairs_combo is not None
    assert cb_pairs_combo.count() == 5  # 5 pairs for 6 girders (G1 to G2 ... G5 to G6)
