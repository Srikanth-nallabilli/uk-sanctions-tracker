"""Daily job: download the UK Sanctions List, compare it with the last run,
and record what changed.

Usage:
    python -m tracker.update                  # download from GOV.UK
    python -m tracker.update --file list.csv  # use a file you already have
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import urllib.request
from pathlib import Path

import pandas as pd

from tracker.alert import build_alert
from tracker.uksl import CHANGE_COLUMNS, SOURCE_URL, diff, read_raw, to_designations

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def download(url: str = SOURCE_URL) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "uk-sanctions-tracker/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def run(data: bytes, run_date: str, data_dir: Path = DATA_DIR) -> dict:
    data_dir.mkdir(parents=True, exist_ok=True)
    latest_path = data_dir / "latest.csv.gz"
    changes_path = data_dir / "changes.csv"
    runs_path = data_dir / "runs.csv"

    raw = read_raw(data)
    missing = raw.attrs.get("missing_columns", [])
    if missing:
        print("Note: these optional columns were not found in the file: " + ", ".join(missing))
    current = to_designations(raw)
    if current.empty:
        raise ValueError("The downloaded list has no designations. Stopping so the history is not overwritten.")

    first_run = not latest_path.exists()
    if first_run:
        previous = current.iloc[0:0]
        changes = pd.DataFrame(columns=CHANGE_COLUMNS)
    else:
        previous = pd.read_csv(latest_path, dtype=str, keep_default_na=False)
        changes = diff(previous, current, run_date)

    # Safety check: a sudden loss of most of the list is far more likely to be
    # a bad download than a real mass de-listing.
    if not first_run and len(current) < 0.5 * len(previous):
        raise ValueError(
            f"List shrank from {len(previous)} to {len(current)} designations. "
            "Treating this as a bad download and leaving the history unchanged."
        )

    if len(changes):
        changes.to_csv(changes_path, mode="a", header=not changes_path.exists(), index=False)
    elif not changes_path.exists():
        changes.to_csv(changes_path, index=False)

    # Count every change logged for this date, so a second run on the same day
    # (for example a manual re-run) adds to the day's totals instead of replacing them.
    day_changes = pd.read_csv(changes_path, dtype=str, keep_default_na=False)
    day_changes = day_changes[day_changes["run_date"] == run_date]
    counts = day_changes["change_type"].value_counts()

    runs = pd.read_csv(runs_path) if runs_path.exists() else pd.DataFrame()
    same_day = runs[runs["run_date"] == run_date] if len(runs) else runs
    was_baseline = bool(len(same_day)) and str(same_day["baseline"].iloc[0]).lower() == "true"

    summary = {
        "run_date": run_date,
        "total_designations": len(current),
        "added": int(counts.get("Added", 0)),
        "removed": int(counts.get("Removed", 0)),
        "amended": int(counts.get("Amended", 0)),
        "baseline": first_run or was_baseline,
        "new_changes": len(changes),
    }

    if runs.empty:
        runs = pd.DataFrame(columns=[k for k in summary if k != "new_changes"])
    runs = runs[runs["run_date"] != run_date]
    record = {k: v for k, v in summary.items() if k != "new_changes"}
    runs = pd.concat([runs, pd.DataFrame([record])], ignore_index=True)
    runs.to_csv(runs_path, index=False)

    current.to_csv(latest_path, index=False, compression="gzip")
    summary["changes_today"] = changes
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", help="Path to a downloaded UK Sanctions List CSV")
    parser.add_argument("--date", default=dt.date.today().isoformat(), help="Run date, YYYY-MM-DD")
    parser.add_argument("--data-dir", default=str(DATA_DIR))
    parser.add_argument("--alert-file", help="Write a Markdown summary here when changes are found")
    args = parser.parse_args(argv)

    data = Path(args.file).read_bytes() if args.file else download()
    summary = run(data, args.date, Path(args.data_dir))

    if summary["baseline"]:
        print(f"{args.date}: baseline saved with {summary['total_designations']} designations.")
    else:
        print(
            f"{args.date}: {summary['total_designations']} designations | "
            f"{summary['added']} added, {summary['removed']} removed, {summary['amended']} amended."
        )

    if args.alert_file and summary["new_changes"]:
        Path(args.alert_file).write_text(build_alert(summary), encoding="utf-8")
        print(f"Alert written to {args.alert_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
