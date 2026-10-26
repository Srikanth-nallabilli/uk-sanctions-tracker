"""Build the Markdown text for the daily GitHub issue alert."""

from __future__ import annotations

import os

import pandas as pd

from tracker.sources import SOURCES
from tracker.uksl import short_regime

DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "https://uk-sanctions-tracker.streamlit.app")
MAX_ROWS = 40


def _counts(summary: dict) -> str:
    counts = summary["changes_today"]["change_type"].value_counts()
    return ", ".join(f"{counts[k]} {k.lower()}" for k in ("Added", "Removed", "Amended") if counts.get(k))


def alert_title(summary: dict | list[dict]) -> str:
    summaries = [summary] if isinstance(summary, dict) else summary
    run_date = summaries[0]["run_date"]
    if len(summaries) == 1:
        name = SOURCES[summaries[0].get("source", "uk")].name
        return f"{name} changes on {run_date}: {_counts(summaries[0])}"
    parts = [f"{SOURCES[s['source']].short} {len(s['changes_today'])}" for s in summaries]
    return f"Sanctions list changes on {run_date}: " + ", ".join(parts)


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


def _section(summary: dict, level: str) -> list[str]:
    changes = summary["changes_today"].copy()
    changes["regime"] = changes["regime"].map(short_regime)
    out = []
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
            out += ["", f"{level} {heading} ({len(rows)})", "", _table(rows, cols)]
    return out


def build_alert(summary: dict | list[dict]) -> str:
    summaries = [summary] if isinstance(summary, dict) else summary
    out = [f"## {alert_title(summaries)}", ""]
    if len(summaries) == 1:
        s = summaries[0]
        out.append(f"The list now has **{s['total_designations']:,}** designations. "
                   f"[Open the dashboard]({DASHBOARD_URL}) for details.")
        out += _section(s, "###")
    else:
        out.append(f"[Open the dashboard]({DASHBOARD_URL}) for details.")
        for s in summaries:
            src = SOURCES[s["source"]]
            out += ["", f"### {src.name}: {_counts(s)}", "",
                    f"The list now has **{s['total_designations']:,}** designations."]
            out += _section(s, "####")
    out += ["", "---", "_Posted automatically by the daily sanctions list check._"]
    return "\n".join(out)
