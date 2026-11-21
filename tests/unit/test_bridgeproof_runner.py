import copy
import csv

import pytest

from bridgeproof.runner import (
    execute_case,
    export_csv,
    run_suite,
    validate_suite,
)


def make_suite():
    return {
        "suite_id": "BP-TEST-001",
        "suite_name": "Runner Verification",
        "module": "plate_girder.bridge_geometry",
        "operation": "calculate_bridge_width",
        "cases": [
            {
                "test_id": "BP-TEST-CASE-001",
                "description": "Valid bridge width",
                "inputs": {
                    "carriageway_width": 7.5,
                    "crash_barrier_width": 0.45,
                    "no_of_footpaths": 0,
                    "footpath_width": 1.5,
                    "railing_width": 0.3,
                    "median_width": 1.2,
                },
                "expected": 9.6,
                "tolerance": 0.000001,
            }
        ],
    }


def test_valid_suite_passes_validation():
    assert validate_suite(make_suite()) is True


def test_duplicate_test_ids_are_rejected():
    suite = make_suite()
    duplicate = copy.deepcopy(suite["cases"][0])
    suite["cases"].append(duplicate)

    with pytest.raises(ValueError, match="Duplicate test_id"):
        validate_suite(suite)


def test_missing_expected_value_is_rejected():
    suite = make_suite()
    del suite["cases"][0]["expected"]

    with pytest.raises(ValueError, match="missing field: expected"):
        validate_suite(suite)


def test_negative_tolerance_is_rejected():
    suite = make_suite()
    suite["cases"][0]["tolerance"] = -0.01

    with pytest.raises(ValueError, match="non-negative finite number"):
        validate_suite(suite)


def test_non_numeric_expected_value_is_rejected():
    suite = make_suite()
    suite["cases"][0]["expected"] = "nine point six"

    with pytest.raises(ValueError, match="expected must be a finite number"):
        validate_suite(suite)


def test_unsupported_operation_is_rejected():
    suite = make_suite()
    suite["operation"] = "unknown_operation"

    with pytest.raises(ValueError, match="Unsupported operation"):
        validate_suite(suite)


def test_execute_case_detects_incorrect_expected_value():
    case = make_suite()["cases"][0]
    case["expected"] = 10.0

    from osdagbridge.core.bridge_types.plate_girder.bridge_geometry import (
        calculate_bridge_width,
    )

    result = execute_case(case, calculate_bridge_width)

    assert result["status"] == "FAILED"
    assert result["expected"] == 10.0
    assert result["actual"] == pytest.approx(9.6)


def test_run_suite_generates_correct_summary():
    report = run_suite(make_suite())

    assert report["summary"]["total"] == 1
    assert report["summary"]["passed"] == 1
    assert report["summary"]["failed"] == 0
    assert report["summary"]["errors"] == 0

def test_export_csv_writes_case_evidence(tmp_path):
    report = run_suite(make_suite())
    output_file = tmp_path / "bridgeproof_evidence.csv"

    result = export_csv(report, output_file)

    assert result == output_file
    assert output_file.exists()

    with output_file.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert len(rows) == 1
    assert rows[0]["test_id"] == "BP-TEST-CASE-001"
    assert rows[0]["status"] == "PASSED"
    assert float(rows[0]["expected"]) == pytest.approx(9.6)
    assert float(rows[0]["actual"]) == pytest.approx(9.6)