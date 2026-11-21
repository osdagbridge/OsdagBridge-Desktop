
import argparse
import csv
import json
import math
import sys

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from osdagbridge.core.bridge_types.plate_girder.bridge_geometry import (
    calculate_bridge_width,
    create_default_load_placement,
)


# =========================================================
# OPERATIONS
# =========================================================

def deck_load_geometry(**inputs):
    manager = create_default_load_placement(**inputs)
    return asdict(manager.deck_load())


def overlay_load_geometry(edge_clearance, **inputs):
    manager = create_default_load_placement(**inputs)
    return asdict(manager.overlay_load(edge_clearance))

def footpath_load_geometry(side, **inputs):
    manager = create_default_load_placement(**inputs)
    return asdict(manager.footpath_load(side))


def crash_barrier_load_geometry(side, **inputs):
    manager = create_default_load_placement(**inputs)
    return asdict(manager.crash_barrier_load(side))


def railing_load_geometry(side, **inputs):
    manager = create_default_load_placement(**inputs)
    return asdict(manager.railing_load(side))


def median_load_geometry(**inputs):
    manager = create_default_load_placement(**inputs)
    return asdict(manager.median_line_load())

OPERATIONS = {
    "calculate_bridge_width": calculate_bridge_width,
    "deck_load_geometry": deck_load_geometry,
    "overlay_load_geometry": overlay_load_geometry,
    "footpath_load_geometry": footpath_load_geometry,
    "crash_barrier_load_geometry": crash_barrier_load_geometry,
    "railing_load_geometry": railing_load_geometry,
    "median_load_geometry": median_load_geometry,
}

# =========================================================
# EXPECTED VALUE VALIDATION
# =========================================================

def valid_expected(value):
    """Check whether expected values contain finite numeric values."""

    if isinstance(value, bool):
        return False

    if isinstance(value, (int, float)):
        return math.isfinite(value)

    if isinstance(value, list):
        return all(valid_expected(item) for item in value)

    if isinstance(value, dict):
        return all(
            isinstance(key, str) and valid_expected(item)
            for key, item in value.items()
        )

    return False


# =========================================================
# VALUE COMPARISON
# =========================================================

def compare_values(expected, actual, tolerance):
    """Compare expected and actual values recursively."""

    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False

        if expected.keys() != actual.keys():
            return False

        return all(
            compare_values(expected[key], actual[key], tolerance)
            for key in expected
        )

    if isinstance(expected, list):
        if not isinstance(actual, list):
            return False

        if len(expected) != len(actual):
            return False

        return all(
            compare_values(e, a, tolerance)
            for e, a in zip(expected, actual)
        )

    if isinstance(expected, bool) or isinstance(actual, bool):
        return expected == actual

    if isinstance(expected, (int, float)):
        if not isinstance(actual, (int, float)):
            return False

        if not math.isfinite(actual):
            return False

        return math.isclose(
            expected,
            actual,
            rel_tol=tolerance,
            abs_tol=tolerance,
        )

    return expected == actual


# =========================================================
# SUITE VALIDATION
# =========================================================

def load_suite(file_path):
    """Load and validate a BridgeProof JSON test suite."""

    file_path = Path(file_path)

    with file_path.open("r", encoding="utf-8") as file:
        suite = json.load(file)

    validate_suite(suite)

    return suite

def validate_suite(suite):
    """Validate suite structure and test case configuration."""

    if not isinstance(suite, dict):
        raise ValueError("Suite must be a JSON object")

    required_fields = [
        "suite_id",
        "suite_name",
        "operation",
        "cases",
    ]

    for field in required_fields:
        if field not in suite:
            raise ValueError(f"Suite is missing field: {field}")

    if (
        not isinstance(suite["suite_id"], str)
        or not suite["suite_id"].strip()
    ):
        raise ValueError("suite_id must be a non-empty string")

    if (
        not isinstance(suite["suite_name"], str)
        or not suite["suite_name"].strip()
    ):
        raise ValueError("suite_name must be a non-empty string")

    operation = suite["operation"]

    if operation not in OPERATIONS:
        raise ValueError(f"Unsupported operation: {operation}")

    cases = suite["cases"]

    if not isinstance(cases, list) or not cases:
        raise ValueError("cases must be a non-empty list")

    seen_ids = set()

    for index, case in enumerate(cases):

        if not isinstance(case, dict):
            raise ValueError(f"Test case {index} must be an object")

        if "test_id" not in case:
            raise ValueError(
                f"Test case {index} is missing field: test_id"
            )

        test_id = case["test_id"]

        if not isinstance(test_id, str) or not test_id.strip():
            raise ValueError(
                f"Test case {index} has invalid test_id"
            )

        if test_id in seen_ids:
            raise ValueError(f"Duplicate test_id: {test_id}")

        seen_ids.add(test_id)

        if "inputs" not in case:
            raise ValueError(f"{test_id} is missing field: inputs")

        if not isinstance(case["inputs"], dict):
            raise ValueError(f"{test_id}: inputs must be an object")

        has_expected = "expected" in case
        has_expected_error = "expected_error" in case

        if not has_expected and not has_expected_error:
            raise ValueError(
                f"Test case {index} is missing field: expected"
            )

        if has_expected and has_expected_error:
            raise ValueError(
                f"{test_id}: provide only one of "
                "'expected' or 'expected_error'"
            )

        if has_expected:
            if not valid_expected(case["expected"]):
                raise ValueError(
                    f"{test_id}: expected must be a finite number"
                )

        if has_expected_error:
            expected_error = case["expected_error"]

            if (
                not isinstance(expected_error, str)
                or not expected_error.strip()
            ):
                raise ValueError(
                    f"{test_id}: expected_error must be a non-empty string"
                )

        tolerance = case.get("tolerance", 1e-6)

        if (
            isinstance(tolerance, bool)
            or not isinstance(tolerance, (int, float))
            or not math.isfinite(tolerance)
            or tolerance < 0
        ):
            raise ValueError(
                f"{test_id}: tolerance must be a non-negative finite number"
            )

    return True


# =========================================================
# INDIVIDUAL CASE EXECUTION
# =========================================================

def execute_case(case, operation):
    """Execute one test case and return its result."""

    test_id = case["test_id"]
    inputs = case["inputs"]
    tolerance = case.get("tolerance", 1e-6)

    has_expected_error = "expected_error" in case

    result = {
        "test_id": test_id,
        "status": None,
        "expected": case.get("expected"),
        "expected_error": case.get("expected_error"),
        "actual": None,
        "error": None,
    }

    try:
        actual = operation(**inputs)
        result["actual"] = actual

        if has_expected_error:
            result["status"] = "FAILED"
            result["error"] = (
                f"Expected {case['expected_error']}, "
                "but operation completed without an exception"
            )
            return result

        if compare_values(case["expected"], actual, tolerance):
            result["status"] = "PASSED"
        else:
            result["status"] = "FAILED"
            result["error"] = (
                "Expected and actual values do not match"
            )

    except Exception as error:

        actual_exception = type(error).__name__

        if has_expected_error:

            if actual_exception == case["expected_error"]:
                result["status"] = "PASSED"
                result["error"] = (
                    f"Expected exception raised: "
                    f"{actual_exception}: {error}"
                )
            else:
                result["status"] = "ERROR"
                result["error"] = (
                    f"Expected {case['expected_error']}, "
                    f"but received {actual_exception}: {error}"
                )

        else:
            result["status"] = "ERROR"
            result["error"] = (
                f"{actual_exception}: {error}"
            )

    return result


# =========================================================
# SUITE EXECUTION
# =========================================================

def run_suite(suite):
    """Validate and execute all cases in a test suite."""

    validate_suite(suite)

    operation = OPERATIONS[suite["operation"]]

    results = [
        execute_case(case, operation)
        for case in suite["cases"]
    ]

    summary = {
        "total": len(results),
        "passed": sum(
            result["status"] == "PASSED"
            for result in results
        ),
        "failed": sum(
            result["status"] == "FAILED"
            for result in results
        ),
        "errors": sum(
            result["status"] == "ERROR"
            for result in results
        ),
    }

    return {
        "suite_id": suite["suite_id"],
        "suite_name": suite["suite_name"],
        "operation": suite["operation"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "results": results,
    }


# =========================================================
# JSON REPORT EXPORT
# =========================================================

def export_json(report, output_path):
    """Export test evidence as a JSON report."""

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(
            report,
            file,
            indent=4,
            default=str,
        )

    return output_path


# =========================================================
# CSV REPORT EXPORT
# =========================================================

def export_csv(report, output_path):
    """Export individual test case evidence as CSV."""

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fields = [
        "test_id",
        "status",
        "expected",
        "expected_error",
        "actual",
        "error",
    ]

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fields,
        )

        writer.writeheader()

        for result in report["results"]:
            writer.writerow({
                "test_id": result["test_id"],
                "status": result["status"],
                "expected": json.dumps(result["expected"]),
                "expected_error": result["expected_error"],
                "actual": json.dumps(
                    result["actual"],
                    default=str,
                ),
                "error": result["error"],
            })

    return output_path


# =========================================================
# COMMAND LINE INTERFACE
# =========================================================

def main():

    parser = argparse.ArgumentParser(
        description="BridgeProof Reproducible Testing Framework"
    )

    parser.add_argument(
        "--cases",
        required=True,
        help="Path to the test suite JSON file",
    )

    parser.add_argument(
        "--output",
        default="reports/bridgeproof_report",
        help="Output report path without extension",
    )

    args = parser.parse_args()

    cases_path = Path(args.cases)
    output_path = Path(args.output)

    try:

        with cases_path.open("r", encoding="utf-8") as file:
            suite = json.load(file)

        report = run_suite(suite)

        json_path = output_path.with_suffix(".json")
        csv_path = output_path.with_suffix(".csv")

        export_json(report, json_path)
        export_csv(report, csv_path)

        summary = report["summary"]

        print("\n========== BRIDGEPROOF TEST REPORT ==========")
        print(f"Suite: {report['suite_name']}")
        print(f"Total: {summary['total']}")
        print(f"Passed: {summary['passed']}")
        print(f"Failed: {summary['failed']}")
        print(f"Errors: {summary['errors']}")

        for result in report["results"]:
            print(
                f"{result['test_id']} | "
                f"{result['status']} | "
                f"Expected: {result['expected']} | "
                f"Actual: {result['actual']}"
            )

        print(f"\nJSON report: {json_path}")
        print(f"CSV report: {csv_path}")

        if summary["failed"] or summary["errors"]:
            return 1

        return 0

    except Exception as error:
        print(
            f"BridgeProof execution failed: "
            f"{type(error).__name__}: {error}"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())

