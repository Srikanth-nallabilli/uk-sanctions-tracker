"""UK Sanctions List Change Tracker: Streamlit dashboard."""

import os
from datetime import timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from tracker.uksl import short_regime

DATA_DIR = Path(os.environ.get("TRACKER_DATA_DIR", Path(__file__).parent / "data"))
SOURCE_PAGE = "https://www.gov.uk/government/publications/the-uk-sanctions-list"
REPO = "https://github.com/Srikanth-nallabilli/uk-sanctions-tracker"

NAVY = "#1e3a8a"
CHANGE_COLOURS = {"Added": "#059669", "Removed": "#e11d48", "Amended": "#d97706"}
TYPE_COLOURS = {"Individual": "#1e3a8a", "Entity": "#0d9488", "Ship": "#d97706"}
SERIES = ["#1e3a8a", "#0d9488", "#d97706", "#e11d48", "#7c3aed", "#0284c7"]
OTHER = "#cbd5e1"

st.set_page_config(page_title="UK Sanctions List Tracker", page_icon="🛡️", layout="wide")

# ------------------------------------------------------------------ styling
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"], .stMarkdown, .stDataFrame, button, input { font-family: 'Inter', sans-serif; }
#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; height: 0; }
.block-container { padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1280px; }

.hero {
  background: radial-gradient(circle at 85% 20%, rgba(56,189,248,.25), transparent 40%),
              linear-gradient(135deg, #0b1f3a 0%, #1e3a8a 60%, #1d4ed8 100%);
  color: #fff; border-radius: 18px; padding: 30px 34px; margin-bottom: 18px;
  box-shadow: 0 10px 30px rgba(15,23,42,.18);
}
.hero h1 { color: #fff; font-size: 2.05rem; font-weight: 800; margin: 0 0 6px 0; letter-spacing: -.02em; }
.hero p { color: #cbd5e1; font-size: 1rem; margin: 0 0 16px 0; max-width: 760px; line-height: 1.5; }
.pill { display: inline-flex; align-items: center; gap: 7px; background: rgba(255,255,255,.12);
  border: 1px solid rgba(255,255,255,.18); color: #e2e8f0; padding: 5px 12px; border-radius: 999px;
  font-size: .82rem; margin: 0 8px 6px 0; text-decoration: none; }
.pill a { color: #e2e8f0; text-decoration: none; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: #34d399; box-shadow: 0 0 0 4px rgba(52,211,153,.25); }

.cards { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 14px; margin-bottom: 8px; }
@media (max-width: 900px) { .cards { grid-template-columns: repeat(2, minmax(0,1fr)); } }
.card { background: #fff; border-radius: 14px; padding: 18px 20px; border: 1px solid #e2e8f0;
  box-shadow: 0 1px 2px rgba(15,23,42,.04); position: relative; overflow: hidden; }
.card:before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4px; background: var(--accent); }
.card .label { color: #64748b; font-size: .78rem; font-weight: 600; text-transform: uppercase; letter-spacing: .06em; }
.card .value { color: #0f172a; font-size: 2rem; font-weight: 800; margin: 4px 0 2px; letter-spacing: -.02em; }
.card .sub { color: #64748b; font-size: .85rem; }
.chip { display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: .8rem; font-weight: 700; margin-right: 4px; }

.section-title { font-size: 1.05rem; font-weight: 700; color: #0f172a; margin: 6px 0 2px; }
.section-sub { color: #64748b; font-size: .88rem; margin-bottom: 6px; }
.empty { background: #fff; border: 1px dashed #cbd5e1; border-radius: 14px; padding: 26px; text-align: center; color: #475569; }
.empty h3 { margin: 0 0 6px; color: #0f172a; font-size: 1.1rem; }

.stTabs [data-baseweb="tab-list"] { gap: 6px; border-bottom: 1px solid #e2e8f0; }
.stTabs [data-baseweb="tab"] { font-weight: 600; padding: 10px 16px; border-radius: 10px 10px 0 0; }
.stTabs [aria-selected="true"] { background: #fff; color: #1e3a8a; }
[data-testid="stPlotlyChart"], [data-testid="stDataFrame"] { background: #fff; border-radius: 14px;
  border: 1px solid #e2e8f0; padding: 8px; }
.footer { color: #94a3b8; font-size: .8rem; text-align: center; margin-top: 28px; }
.footer a { color: #64748b; }
</style>
""",
    unsafe_allow_html=True,
)


def style_fig(fig, height=360, legend=True):
    fig.update_layout(
        template="plotly_white", height=height, margin=dict(l=10, r=10, t=10, b=10),
        font=dict(family="Inter, sans-serif", size=12, color="#334155"),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title_text="") if legend else None,
        showlegend=legend, hoverlabel=dict(font_family="Inter, sans-serif"),
    )
    fig.update_xaxes(showgrid=False, linecolor="#e2e8f0")
    fig.update_yaxes(gridcolor="#eef2f7", zeroline=False)
    return fig


def section(title, sub=""):
    st.markdown(f'<div class="section-title">{title}</div>'
                + (f'<div class="section-sub">{sub}</div>' if sub else ""), unsafe_allow_html=True)


# ------------------------------------------------------------------ data
@st.cache_data(ttl=3600)
def load():
    runs_path = DATA_DIR / "runs.csv"
    if not runs_path.exists():
        return None, None, None
    runs = pd.read_csv(runs_path).sort_values("run_date")
    changes_path = DATA_DIR / "changes.csv"
    changes = (pd.read_csv(changes_path, dtype=str, keep_default_na=False)
               if changes_path.exists() else pd.DataFrame())
    latest = pd.read_csv(DATA_DIR / "latest.csv.gz", dtype=str, keep_default_na=False)

    # Display helpers only; the stored data keeps the full official values.
    latest["regime_short"] = latest["regime"].map(short_regime)
    latest["main_regime"] = latest["regime_short"].str.split("; ").str[0]
    latest["designated"] = pd.to_datetime(
        latest["date_designated"].str.split("; ").str[0], format="%d/%m/%Y", errors="coerce")
    latest["updated"] = pd.to_datetime(
        latest["last_updated"].str.split("; ").str[-1], format="%d/%m/%Y", errors="coerce")
    if not changes.empty:
        changes["regime"] = changes["regime"].map(short_regime)
    return runs, changes, latest


runs, changes, latest = load()


def hero(last_checked="", since=""):
    pills = '<span class="pill"><span class="dot"></span>Live · checked every evening</span>'
    if last_checked:
        pills += f'<span class="pill">Last checked {last_checked}</span>'
    if since:
        pills += f'<span class="pill">Tracking since {since}</span>'
    pills += f'<span class="pill"><a href="{SOURCE_PAGE}" target="_blank">Source: FCDO, GOV.UK ↗</a></span>'
    pills += f'<span class="pill"><a href="{REPO}" target="_blank">View code ↗</a></span>'
    st.markdown(
        f"""<div class="hero"><h1>🛡️ UK Sanctions List Tracker</h1>
        <p>Every evening this tool downloads the official UK Sanctions List, compares it with the day before
        and records who was added, removed or amended. The list has been the single source for UK
        sanctions designations since the OFSI Consolidated List closed on 28 January 2026.</p>{pills}</div>""",
        unsafe_allow_html=True,
    )


def fmt_date(value):
    return pd.to_datetime(value).strftime("%-d %b %Y")


if runs is None:
    hero()
    st.markdown('<div class="empty"><h3>No data yet</h3>Run <code>python -m tracker.update</code> '
                'to save the first snapshot of the list.</div>', unsafe_allow_html=True)
    st.stop()

last = runs.iloc[-1]
hero(fmt_date(last["run_date"]), fmt_date(runs.iloc[0]["run_date"]))

# ------------------------------------------------------------------ headline cards
types = latest["designation_type"].value_counts()
this_year = pd.Timestamp(last["run_date"]).year
year_count = int((latest["designated"].dt.year == this_year).sum())
prev_year_count = int((latest["designated"].dt.year == this_year - 1).sum())
last_30 = int((latest["designated"] >= pd.Timestamp(last["run_date"]) - timedelta(days=30)).sum())
regime_count = latest["regime_short"].str.split("; ").explode().nunique()
baseline_only = len(runs) == 1


def chip(text, colour):
    return f'<span class="chip" style="background:{colour}1a;color:{colour}">{text}</span>'


daily_sub = ("First check saved. Comparisons start tonight."
             if baseline_only else f"Changes found on {fmt_date(last['run_date'])}")
st.markdown(
    f"""<div class="cards">
  <div class="card" style="--accent:{NAVY}"><div class="label">Designations</div>
    <div class="value">{len(latest):,}</div>
    <div class="sub">{types.get('Individual', 0):,} individuals · {types.get('Entity', 0):,} entities · {types.get('Ship', 0):,} ships</div></div>
  <div class="card" style="--accent:#0d9488"><div class="label">Designated in {this_year}</div>
    <div class="value">{year_count:,}</div>
    <div class="sub">{last_30} in the last 30 days · {prev_year_count:,} in {this_year - 1}</div></div>
  <div class="card" style="--accent:#7c3aed"><div class="label">Active regimes</div>
    <div class="value">{regime_count}</div>
    <div class="sub">Largest: {latest['main_regime'].value_counts().index[0]} ({latest['main_regime'].value_counts().iloc[0]:,})</div></div>
  <div class="card" style="--accent:#d97706"><div class="label">Latest daily check</div>
    <div class="value" style="font-size:1.5rem;padding:8px 0 6px">
      {chip(f"+{int(last['added'])} added", CHANGE_COLOURS['Added'])}
      {chip(f"−{int(last['removed'])} removed", CHANGE_COLOURS['Removed'])}
      {chip(f"~{int(last['amended'])} amended", CHANGE_COLOURS['Amended'])}</div>
    <div class="sub">{daily_sub}</div></div>
</div>""",
    unsafe_allow_html=True,
)

tab_overview, tab_recent, tab_daily, tab_search = st.tabs(
    ["📊 Overview", "🆕 Recent activity", "🔁 Daily changes", "🔎 Search the list"])

# ------------------------------------------------------------------ overview
with tab_overview:
    section("New designations per month",
            "When the people, entities and ships on today's list were first designated, by regime")
    recent = latest[latest["designated"] >= "2022-01-01"].copy()
    top_regimes = latest["main_regime"].value_counts().head(5).index.tolist()
    recent["Regime"] = recent["main_regime"].where(recent["main_regime"].isin(top_regimes), "Other")
    recent["Month"] = recent["designated"].dt.to_period("M").dt.to_timestamp()
    monthly = recent.groupby(["Month", "Regime"]).size().reset_index(name="Designations")
    colour_map = {r: SERIES[i] for i, r in enumerate(top_regimes)} | {"Other": OTHER}
    fig = px.bar(monthly, x="Month", y="Designations", color="Regime",
                 category_orders={"Regime": top_regimes + ["Other"]}, color_discrete_map=colour_map)
    fig.update_layout(bargap=0.15)
    st.plotly_chart(style_fig(fig, 380), width="stretch")

    left, right = st.columns([3, 2])
    with left:
        section("Designations by regime")
        by_regime = latest["main_regime"].value_counts().head(12).sort_values()
        fig = go.Figure(go.Bar(x=by_regime.values, y=by_regime.index, orientation="h",
                               marker_color=NAVY, text=by_regime.values, textposition="outside"))
        st.plotly_chart(style_fig(fig, 420, legend=False), width="stretch")
    with right:
        section("Who is on the list")
        fig = go.Figure(go.Pie(labels=types.index, values=types.values, hole=0.62, sort=False,
                               marker_colors=[TYPE_COLOURS.get(t, OTHER) for t in types.index],
                               textinfo="percent"))
        fig.add_annotation(text=f"<b>{len(latest):,}</b><br>total", showarrow=False, font_size=16)
        st.plotly_chart(style_fig(fig, 420), width="stretch")

    left, right = st.columns(2)
    with left:
        section("Most common nationalities", "Individuals where a nationality is given")
        nat = (latest.loc[latest["nationality"] != "", "nationality"].str.split("; ").explode()
               .value_counts().head(10).sort_values())
        fig = go.Figure(go.Bar(x=nat.values, y=nat.index, orientation="h", marker_color="#0d9488",
                               text=nat.values, textposition="outside"))
        st.plotly_chart(style_fig(fig, 380, legend=False), width="stretch")
    with right:
        section("Sanctions most often imposed")
        measures = (latest["sanctions_imposed"].str.split("; ").explode()
                    .str.replace(r"[:(].*$", "", regex=True).str.strip().str.capitalize())
        measures = measures[measures != ""].value_counts().head(8).sort_values()
        fig = go.Figure(go.Bar(x=measures.values, y=measures.index, orientation="h", marker_color="#7c3aed",
                               text=measures.values, textposition="outside"))
        st.plotly_chart(style_fig(fig, 380, legend=False), width="stretch")

# ------------------------------------------------------------------ recent activity
with tab_recent:
    window = st.radio("Period", [30, 90, 180], index=1, horizontal=True,
                      format_func=lambda d: f"Last {d} days")
    cutoff = pd.Timestamp(last["run_date"]) - timedelta(days=window)

    new = latest[latest["designated"] >= cutoff].sort_values("designated", ascending=False)
    amended = latest[(latest["updated"] >= cutoff) & (latest["updated"] > latest["designated"])]
    amended = amended.sort_values("updated", ascending=False)

    c1, c2 = st.columns(2)
    c1.metric("Newly designated", f"{len(new):,}")
    c2.metric("Listings amended by the FCDO", f"{len(amended):,}")
    st.caption("Based on the Date Designated and Last Updated fields published in the list itself.")

    section("Newly designated")
    st.dataframe(
        new[["designated", "primary_name", "designation_type", "main_regime", "sanctions_imposed"]].rename(columns={
            "designated": "Designated", "primary_name": "Name", "designation_type": "Type",
            "main_regime": "Regime", "sanctions_imposed": "Sanctions imposed"}),
        hide_index=True, width="stretch", height=380,
        column_config={"Designated": st.column_config.DateColumn(format="D MMM YYYY")},
    )
    section("Recently amended")
    st.dataframe(
        amended[["updated", "primary_name", "designation_type", "main_regime", "designated"]].rename(columns={
            "updated": "Last updated", "primary_name": "Name", "designation_type": "Type",
            "main_regime": "Regime", "designated": "First designated"}),
        hide_index=True, width="stretch", height=320,
        column_config={"Last updated": st.column_config.DateColumn(format="D MMM YYYY"),
                       "First designated": st.column_config.DateColumn(format="D MMM YYYY")},
    )

# ------------------------------------------------------------------ daily changes
with tab_daily:
    if changes.empty:
        st.markdown(
            f"""<div class="empty"><h3>⏳ Daily comparisons start tonight</h3>
            The first snapshot of {len(latest):,} designations was saved on {fmt_date(runs.iloc[0]['run_date'])}.
            Every evening from now on the tracker compares the new list with the day before, and each
            addition, removal and amendment will appear here with the fields that changed.</div>""",
            unsafe_allow_html=True,
        )
    else:
        history = runs[~runs["baseline"].astype(str).str.lower().eq("true")]
        if len(history):
            section("Changes per day")
            long = history.melt(id_vars="run_date", value_vars=["added", "removed", "amended"],
                                var_name="Change", value_name="Count")
            long["Change"] = long["Change"].str.title()
            fig = px.bar(long, x="run_date", y="Count", color="Change", color_discrete_map=CHANGE_COLOURS,
                         labels={"run_date": ""})
            st.plotly_chart(style_fig(fig, 300), width="stretch")

        dates = sorted(changes["run_date"].unique(), reverse=True)
        f1, f2 = st.columns([1, 2])
        chosen = f1.selectbox("Date", dates, format_func=fmt_date)
        kinds = f2.multiselect("Show", ["Added", "Removed", "Amended"], default=["Added", "Removed", "Amended"])
        day = changes[(changes["run_date"] == chosen) & changes["change_type"].isin(kinds)]
        section(f"{len(day)} changes on {fmt_date(chosen)}")
        st.dataframe(
            day[["change_type", "primary_name", "designation_type", "regime", "fields_changed", "detail", "unique_id"]]
            .rename(columns={"change_type": "Change", "primary_name": "Name", "designation_type": "Type",
                             "regime": "Regime", "fields_changed": "Fields changed", "detail": "Detail",
                             "unique_id": "Unique ID"}),
            hide_index=True, width="stretch",
        )
        st.download_button("⬇ Download the full change log (CSV)", changes.to_csv(index=False).encode("utf-8"),
                           file_name="uk_sanctions_changes.csv", mime="text/csv")

# ------------------------------------------------------------------ search
with tab_search:
    s1, s2, s3 = st.columns([2, 1, 1])
    query = s1.text_input("Name or alias", placeholder="Search e.g. Petrov, Bank, Shipping")
    regime_pick = s2.selectbox("Regime", ["All regimes"] + sorted(latest["main_regime"].unique()))
    type_pick = s3.selectbox("Type", ["All types"] + sorted(latest["designation_type"].unique()))

    hits = latest
    if query:
        q = query.strip().lower()
        hits = hits[hits["primary_name"].str.lower().str.contains(q, regex=False)
                    | hits["other_names"].str.lower().str.contains(q, regex=False)]
    if regime_pick != "All regimes":
        hits = hits[hits["main_regime"] == regime_pick]
    if type_pick != "All types":
        hits = hits[hits["designation_type"] == type_pick]

    section(f"{len(hits):,} designations")
    st.dataframe(
        hits.sort_values("designated", ascending=False)[
            ["primary_name", "other_names", "designation_type", "main_regime", "sanctions_imposed",
             "designated", "unique_id"]].rename(columns={
                "primary_name": "Name", "other_names": "Other names", "designation_type": "Type",
                "main_regime": "Regime", "sanctions_imposed": "Sanctions imposed",
                "designated": "Designated", "unique_id": "Unique ID"}),
        hide_index=True, width="stretch", height=460,
        column_config={"Designated": st.column_config.DateColumn(format="D MMM YYYY")},
    )
    if query and not changes.empty and len(hits):
        history = changes[changes["unique_id"].isin(hits["unique_id"])]
        if len(history):
            section("Change history for these designations")
            st.dataframe(history[["run_date", "change_type", "primary_name", "fields_changed", "detail"]],
                         hide_index=True, width="stretch")
    st.caption("A simple text search for exploring the list. It is not a screening tool and does not "
               "replace fuzzy matching against the official list.")

st.markdown(
    f"""<div class="footer">Contains public sector information licensed under the Open Government Licence v3.0 ·
    Built by Srikanth Nallabilli · <a href="{REPO}" target="_blank">GitHub</a></div>""",
    unsafe_allow_html=True,
)
