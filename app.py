"""UK Sanctions List Change Tracker: Streamlit dashboard."""

import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from tracker.uksl import short_regime

DATA_DIR = Path(os.environ.get("TRACKER_DATA_DIR", Path(__file__).parent / "data"))
SOURCE_PAGE = "https://www.gov.uk/government/publications/the-uk-sanctions-list"
COLOURS = {"Added": "#2e7d32", "Removed": "#c62828", "Amended": "#ef8f00"}

st.set_page_config(page_title="UK Sanctions List Tracker", page_icon="🛡️", layout="wide")


@st.cache_data(ttl=3600)
def load():
    runs_path = DATA_DIR / "runs.csv"
    if not runs_path.exists():
        return None, None, None
    runs = pd.read_csv(runs_path).sort_values("run_date")
    changes_path = DATA_DIR / "changes.csv"
    changes = (
        pd.read_csv(changes_path, dtype=str, keep_default_na=False)
        if changes_path.exists() else pd.DataFrame()
    )
    latest = pd.read_csv(DATA_DIR / "latest.csv.gz", dtype=str, keep_default_na=False)
    # Shorten regulation titles for display only; stored data keeps the full title.
    latest["regime"] = latest["regime"].map(short_regime)
    if not changes.empty:
        changes["regime"] = changes["regime"].map(short_regime)
    return runs, changes, latest


runs, changes, latest = load()

st.title("UK Sanctions List Change Tracker")
st.caption(
    "Tracks daily changes to the UK Sanctions List published by the FCDO, the single source "
    f"for UK sanctions designations since 28 January 2026. [Source]({SOURCE_PAGE})"
)

if runs is None:
    st.info(
        "No data yet. Run `python -m tracker.update` to save the first snapshot. "
        "Changes appear from the second run onwards."
    )
    st.stop()

last = runs.iloc[-1]
tracking_since = runs.iloc[0]["run_date"]
recent_runs = runs[~runs["baseline"].astype(str).str.lower().eq("true")]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Designations on the list", f"{int(last['total_designations']):,}")
col2.metric("Added (last run)", int(last["added"]))
col3.metric("Removed (last run)", int(last["removed"]))
col4.metric("Amended (last run)", int(last["amended"]))
st.caption(f"Last checked {last['run_date']} · tracking since {tracking_since} · {len(runs)} daily runs")

tab_latest, tab_history, tab_regime, tab_search = st.tabs(
    ["Latest changes", "History", "By regime", "Search a name"]
)

# ---------------------------------------------------------------- Latest
with tab_latest:
    if changes.empty:
        st.write("No changes recorded yet. The first run only saves a baseline to compare against.")
    else:
        dates = sorted(changes["run_date"].unique(), reverse=True)
        chosen = st.selectbox("Change date", dates)
        day = changes[changes["run_date"] == chosen]
        kinds = st.multiselect("Show", ["Added", "Removed", "Amended"], default=["Added", "Removed", "Amended"])
        day = day[day["change_type"].isin(kinds)]
        st.write(f"**{len(day)} changes on {chosen}**")
        st.dataframe(
            day[["change_type", "primary_name", "designation_type", "regime", "unique_id", "fields_changed", "detail"]]
            .rename(columns={
                "change_type": "Change", "primary_name": "Name", "designation_type": "Type",
                "regime": "Regime", "unique_id": "Unique ID", "fields_changed": "Fields changed",
                "detail": "Detail",
            }),
            hide_index=True, width="stretch",
        )
        st.download_button(
            "Download full change log (CSV)", changes.to_csv(index=False).encode("utf-8"),
            file_name="uk_sanctions_changes.csv", mime="text/csv",
        )

# ---------------------------------------------------------------- History
with tab_history:
    if recent_runs.empty:
        st.write("History builds up after the second daily run.")
    else:
        long = recent_runs.melt(
            id_vars="run_date", value_vars=["added", "removed", "amended"],
            var_name="Change", value_name="Count",
        )
        long["Change"] = long["Change"].str.title()
        fig = px.bar(
            long, x="run_date", y="Count", color="Change", color_discrete_map=COLOURS,
            labels={"run_date": "Date"}, title="Changes per day",
        )
        fig.update_layout(legend_title_text="", bargap=0.3)
        st.plotly_chart(fig, width="stretch")

        size = px.line(
            runs, x="run_date", y="total_designations", markers=True,
            labels={"run_date": "Date", "total_designations": "Designations"},
            title="Size of the list over time",
        )
        st.plotly_chart(size, width="stretch")

# ---------------------------------------------------------------- Regime
with tab_regime:
    left, right = st.columns(2)
    with left:
        by_regime = latest["regime"].replace("", "Not stated").value_counts().reset_index()
        by_regime.columns = ["Regime", "Designations"]
        fig = px.bar(
            by_regime.head(15).sort_values("Designations"), x="Designations", y="Regime",
            orientation="h", title="Current designations by regime (top 15)",
        )
        st.plotly_chart(fig, width="stretch")
    with right:
        by_type = latest["designation_type"].replace("", "Not stated").value_counts().reset_index()
        by_type.columns = ["Type", "Designations"]
        fig = px.pie(by_type, names="Type", values="Designations", hole=0.5,
                     title="Individuals, entities and ships")
        st.plotly_chart(fig, width="stretch")

    if not changes.empty:
        regime_changes = changes.groupby(["regime", "change_type"]).size().reset_index(name="Count")
        fig = px.bar(
            regime_changes, x="Count", y="regime", color="change_type", orientation="h",
            color_discrete_map=COLOURS, labels={"regime": "Regime", "change_type": ""},
            title="Changes by regime since tracking began",
        )
        st.plotly_chart(fig, width="stretch")

# ---------------------------------------------------------------- Search
with tab_search:
    query = st.text_input("Search the current list by name or alias", placeholder="e.g. Petrov")
    if query:
        q = query.strip().lower()
        hits = latest[
            latest["primary_name"].str.lower().str.contains(q, regex=False)
            | latest["other_names"].str.lower().str.contains(q, regex=False)
        ]
        st.write(f"**{len(hits)} matching designations**")
        st.dataframe(
            hits[["primary_name", "other_names", "designation_type", "regime",
                  "sanctions_imposed", "date_designated", "unique_id"]]
            .rename(columns={
                "primary_name": "Name", "other_names": "Other names", "designation_type": "Type",
                "regime": "Regime", "sanctions_imposed": "Sanctions imposed",
                "date_designated": "Date designated", "unique_id": "Unique ID",
            }),
            hide_index=True, width="stretch",
        )
        if not changes.empty and len(hits):
            history = changes[changes["unique_id"].isin(hits["unique_id"])]
            if len(history):
                st.write("**Change history for these designations**")
                st.dataframe(
                    history[["run_date", "change_type", "primary_name", "fields_changed", "detail"]],
                    hide_index=True, width="stretch",
                )
        st.caption(
            "This is a simple text search for exploring the list. It is not a screening tool "
            "and does not replace fuzzy matching against the official list."
        )

st.divider()
st.caption(
    "Contains public sector information licensed under the Open Government Licence v3.0. "
    "Built by Srikanth Nallabilli."
)
