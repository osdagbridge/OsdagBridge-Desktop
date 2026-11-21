
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

from bridgeproof.runner import load_suite, run_suite, export_csv


BASE_DIR = Path(__file__).resolve().parent
CASES_DIR = BASE_DIR / "cases"
REPORTS_DIR = BASE_DIR.parent / "reports"


def main():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Deliberate failure datasets are excluded from normal regression runs.
    case_files = sorted(
        path for path in CASES_DIR.glob("*.json")
        if not path.stem.endswith("_failure")
    )

    if not case_files:
        print("No BridgeProof test datasets found.")
        raise SystemExit(1)

    combined = {
        "framework": "BridgeProof",
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
        },
        "summary": {
            "suites": 0,
            "total": 0,
            "passed": 0,
            "failed": 0,
            "errors": 0,
        },
        "suite_reports": [],
    }

    for case_file in case_files:
        print(f"\nRunning suite: {case_file.name}")

        suite = load_suite(case_file)
        report = run_suite(suite)

        output_path = REPORTS_DIR / f"{case_file.stem}_report.json"

        with open(output_path, "w", encoding="utf-8") as file:
            json.dump(report, file, indent=4)

        csv_path = export_csv(
            report,
            output_path.with_suffix(".csv"),
        )

        summary = report["summary"]

        combined["summary"]["suites"] += 1

        for key in ("total", "passed", "failed", "errors"):
            combined["summary"][key] += summary[key]

        combined["suite_reports"].append({
            "suite_id": report["suite_id"],
            "suite_name": report["suite_name"],
            "json_report": str(output_path),
            "csv_report": str(csv_path),
            "summary": summary,
        })

        print(
            f"Total: {summary['total']} | "
            f"Passed: {summary['passed']} | "
            f"Failed: {summary['failed']} | "
            f"Errors: {summary['errors']}"
        )

    summary_path = REPORTS_DIR / "bridgeproof_summary.json"

    with open(summary_path, "w", encoding="utf-8") as file:
        json.dump(combined, file, indent=4)

    print("\n========== BRIDGEPROOF MASTER REPORT ==========")
    print(f"Suites: {combined['summary']['suites']}")
    print(f"Total: {combined['summary']['total']}")
    print(f"Passed: {combined['summary']['passed']}")
    print(f"Failed: {combined['summary']['failed']}")
    print(f"Errors: {combined['summary']['errors']}")
    print(f"\nMaster evidence saved to: {summary_path}")

    if combined["summary"]["failed"] or combined["summary"]["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
