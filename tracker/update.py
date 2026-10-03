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

    current = to_designations(read_raw(data))
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

    counts = changes["change_type"].value_counts() if len(changes) else {}
    summary = {
        "run_date": run_date,
        "total_designations": len(current),
        "added": int(counts.get("Added", 0)),
        "removed": int(counts.get("Removed", 0)),
        "amended": int(counts.get("Amended", 0)),
        "baseline": first_run,
    }

    runs = pd.read_csv(runs_path) if runs_path.exists() else pd.DataFrame(columns=summary.keys())
    runs = runs[runs["run_date"] != run_date]
    runs = pd.concat([runs, pd.DataFrame([summary])], ignore_index=True)
    runs.to_csv(runs_path, index=False)

    current.to_csv(latest_path, index=False, compression="gzip")
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", help="Path to a downloaded UK Sanctions List CSV")
    parser.add_argument("--date", default=dt.date.today().isoformat(), help="Run date, YYYY-MM-DD")
    parser.add_argument("--data-dir", default=str(DATA_DIR))
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
