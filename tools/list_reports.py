#!/usr/bin/env python3
"""
Quick helper to list available evaluation reports for re-evaluation.
"""

import json
from pathlib import Path
from datetime import datetime


def main():
    reports_dir = Path("outputs/reports")

    if not reports_dir.exists():
        print("❌ No reports directory found: outputs/reports/")
        return

    report_dirs = sorted(
        [d for d in reports_dir.glob("eval_*") if d.is_dir()],
        key=lambda x: x.name,
        reverse=True  # Most recent first
    )

    if not report_dirs:
        print("❌ No evaluation reports found in outputs/reports/")
        print("\nRun an evaluation first:")
        print("  python autoeval/scripts/evaluate.py --sample-size 10")
        return

    print(f"\n📊 Available Evaluation Reports ({len(report_dirs)} total)\n")
    print("=" * 80)

    for report_dir in report_dirs:
        report_id = report_dir.name
        summary_file = report_dir / "summary.json"
        report_file = report_dir / "report.json"

        # Extract timestamp from report_id
        try:
            # Format: eval_YYYYMMDD_HHMMSS
            date_str = report_id.replace("eval_", "")
            date_part = date_str[:8]  # YYYYMMDD
            time_part = date_str[9:]  # HHMMSS

            dt = datetime.strptime(f"{date_part}{time_part}", "%Y%m%d%H%M%S")
            timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            timestamp = "Unknown"

        print(f"\n🔹 {report_id}")
        print(f"   Date: {timestamp}")

        # Load summary if exists
        if summary_file.exists():
            try:
                with open(summary_file) as f:
                    summary = json.load(f)

                total = summary.get('total_evaluations', 0)
                acceptance = summary.get('acceptance_rate', 0) * 100
                avg_score = summary.get('average_scores', {}).get('overall', 0)

                print(f"   Q&A Pairs: {total}")
                print(f"   Acceptance Rate: {acceptance:.1f}%")
                print(f"   Avg Score: {avg_score:.2f}/5.0")
            except:
                print(f"   ⚠️  Could not load summary.json")

        # Check if report.json exists (needed for re-evaluation)
        if report_file.exists():
            try:
                with open(report_file) as f:
                    report = json.load(f)
                qa_count = len(report.get('evaluations', []))
                print(f"   ✅ Ready for re-evaluation ({qa_count} Q&A pairs)")
            except:
                print(f"   ⚠️  report.json exists but could not be loaded")
        else:
            print(f"   ❌ Missing report.json (cannot re-evaluate)")

    print("\n" + "=" * 80)
    print("\n💡 To re-evaluate using existing Q&A pairs:")
    print(f"   python autoeval/scripts/evaluate.py --load-qa-from {report_dirs[0].name}")
    print("\n📖 For more info, see: RE_EVALUATION_GUIDE.md\n")


if __name__ == "__main__":
    main()
