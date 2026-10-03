"""Build the Markdown text for the daily GitHub issue alert."""

from __future__ import annotations

import os

import pandas as pd

from tracker.uksl import short_regime

DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "https://uk-sanctions-tracker.streamlit.app")
MAX_ROWS = 40


def alert_title(summary: dict) -> str:
    changes = summary["changes_today"]
    counts = changes["change_type"].value_counts()
    parts = [f"{counts[k]} {k.lower()}" for k in ("Added", "Removed", "Amended") if counts.get(k)]
    return f"UK Sanctions List changes on {summary['run_date']}: " + ", ".join(parts)


def _table(rows: pd.DataFrame, columns: dict) -> str:
    header = "| " + " | ".join(columns.values()) + " |"
    rule = "|" + "---|" * len(columns)
    lines = [header, rule]
    for _, r in rows.head(MAX_ROWS).iterrows():
        cells = [str(r[c]).replace("|", "/").replace("\n", " ") or "-" for c in columns]
        lines.append("| " + " | ".join(cells) + " |")
    if len(rows) > MAX_ROWS:
        lines.append(f"\n_and {len(rows) - MAX_ROWS} more. See the dashboard for the full list._")
    return "\n".join(lines)


def build_alert(summary: dict) -> str:
    changes = summary["changes_today"].copy()
    changes["regime"] = changes["regime"].map(short_regime)
    out = [
        f"## {alert_title(summary)}",
        "",
        f"The list now has **{summary['total_designations']:,}** designations. "
        f"[Open the dashboard]({DASHBOARD_URL}) for details.",
    ]
    sections = [
        ("Added", "🟢 New designations",
         {"primary_name": "Name", "designation_type": "Type", "regime": "Regime", "unique_id": "Unique ID"}),
        ("Removed", "🔴 Removed from the list",
         {"primary_name": "Name", "designation_type": "Type", "regime": "Regime", "unique_id": "Unique ID"}),
        ("Amended", "🟠 Amended listings",
         {"primary_name": "Name", "regime": "Regime", "fields_changed": "What changed", "unique_id": "Unique ID"}),
    ]
    for kind, heading, cols in sections:
        rows = changes[changes["change_type"] == kind]
        if len(rows):
            out += ["", f"### {heading} ({len(rows)})", "", _table(rows, cols)]
    out += ["", "---", "_Posted automatically by the daily sanctions list check._"]
    return "\n".join(out)
