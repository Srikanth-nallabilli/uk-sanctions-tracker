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
def data_version():
    """Changes whenever the daily job commits new data, so the cache reloads straight away."""
    files = ["runs.csv", "changes.csv", "latest.csv.gz"]
    return tuple((f, (DATA_DIR / f).stat().st_mtime_ns, (DATA_DIR / f).stat().st_size)
                 for f in files if (DATA_DIR / f).exists())


@st.cache_data(ttl=3600, max_entries=2)
def load(version):
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


runs, changes, latest = load(data_version())


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

tab_overview, tab_recent, tab_daily, tab_fleet, tab_quality, tab_search = st.tabs(
    ["📊 Overview", "🆕 Recent activity", "🔁 Daily changes", "🚢 Shadow fleet", "✅ Data quality",
     "🔎 Search the list"])

HAS_EXTRA_FIELDS = "flag" in latest.columns
PENDING_NOTE = ('<div class="empty"><h3>Coming with the next daily check</h3>These details are saved from '
                'the next run of the daily check onwards.</div>')

# Moments that explain the big jumps in the monthly chart.
EVENTS = [  # (date, label, height on the chart so labels close together do not overlap)
    ("2022-02-24", "Russia invades Ukraine", 1.0),
    ("2025-09-29", "UN sanctions on Iran return", 0.88),
    ("2026-02-24", "297 Russia designations", 1.0),
]


def split_values(series):
    return series.str.split(r"\s*[;,]\s*").explode().str.strip().replace("", pd.NA).dropna()

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
    for day, label, height in EVENTS:
        fig.add_shape(type="line", x0=day, x1=day, y0=0, y1=height, yref="paper",
                      line=dict(color="#475569", width=1, dash="dot"))
        fig.add_annotation(x=day, y=height, yref="paper", text=label, showarrow=False,
                           xanchor="right" if day >= "2025-06-01" and height == 0.88 else "left",
                           yanchor="top", xshift=4, font=dict(size=11, color="#475569"),
                           bgcolor="rgba(255,255,255,.85)")
    st.plotly_chart(style_fig(fig, 380), width="stretch")

    section("Where designated people and companies are linked to",
            "Countries named as a nationality or address on each listing")
    countries = latest[["unique_id", "nationality", "address_country"]].copy()
    countries["country"] = (countries["nationality"] + "; " + countries["address_country"])
    country_counts = (countries.assign(country=countries["country"].str.split(r"\s*;\s*"))
                      .explode("country").query("country != ''")
                      .drop_duplicates(["unique_id", "country"])["country"].value_counts().reset_index())
    country_counts.columns = ["Country", "Designations"]
    fig = px.choropleth(country_counts, locations="Country", locationmode="country names",
                        color="Designations", color_continuous_scale=["#dbeafe", "#1e3a8a"],
                        hover_name="Country")
    fig.update_geos(showframe=False, showcoastlines=False, projection_type="natural earth",
                    bgcolor="rgba(0,0,0,0)", landcolor="#f1f5f9", showland=True)
    fig.update_layout(coloraxis_colorbar=dict(title="", thickness=12))
    st.plotly_chart(style_fig(fig, 420, legend=False), width="stretch")

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
            f"""<div class="empty"><h3>⏳ The tracker's own daily comparisons start tonight</h3>
            The first snapshot of {len(latest):,} designations was saved on {fmt_date(runs.iloc[0]['run_date'])}.
            From this evening, every addition, removal and amendment the tracker finds will appear here
            with the fields that changed.</div>""",
            unsafe_allow_html=True,
        )
        last_fcdo = latest["updated"].max()
        touched = latest[latest["updated"] == last_fcdo].sort_values("primary_name")
        st.write("")
        section(f"Meanwhile: the FCDO's most recent update, {fmt_date(last_fcdo)}",
                f"{len(touched)} listings carry this Last Updated date in the published list")
        touched = touched.assign(
            What=lambda d: d["designated"].eq(last_fcdo).map({True: "New designation", False: "Amended"}))
        st.dataframe(
            touched[["What", "primary_name", "designation_type", "main_regime", "designated"]].rename(columns={
                "primary_name": "Name", "designation_type": "Type", "main_regime": "Regime",
                "designated": "First designated"}),
            hide_index=True, width="stretch",
            column_config={"First designated": st.column_config.DateColumn(format="D MMM YYYY")},
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

# ------------------------------------------------------------------ shadow fleet
with tab_fleet:
    ships = latest[latest["designation_type"] == "Ship"].copy()
    st.markdown(
        f"""<div class="section-sub" style="font-size:.95rem">The UK has designated <b>{len(ships):,} ships</b>,
        most of them tankers moving Russian oil outside the price cap. Vessels in this "shadow fleet" often
        change flag and owner to stay hidden, so flags, ownership and age are the details that matter
        for trade finance and maritime screening.</div>""",
        unsafe_allow_html=True,
    )
    if not HAS_EXTRA_FIELDS or ships["flag"].eq("").all():
        st.markdown(PENDING_NOTE, unsafe_allow_html=True)
    else:
        ships["n_prev_flags"] = ships["previous_flags"].apply(
            lambda v: len([x for x in pd.Series([v]).str.split(r"\s*[;,]\s*").iloc[0] if x.strip()]) if v else 0)
        ships["built"] = pd.to_numeric(ships["year_built"].str.extract(r"(\d{4})")[0], errors="coerce")
        ships["age"] = pd.Timestamp(last["run_date"]).year - ships["built"]
        ships["gt"] = pd.to_numeric(ships["tonnage"].str.replace(",", "").str.extract(r"(\d+)")[0],
                                    errors="coerce")
        ships["ship_type_clean"] = ships["ship_type"].str.split(";").str[0].str.strip().str.capitalize()

        hopped = int((ships["n_prev_flags"] > 0).sum())
        median_age = ships["age"].median()
        over_15 = int((ships["age"] >= 15).sum())
        designated_2026 = int((ships["designated"].dt.year == this_year).sum())
        st.markdown(
            f"""<div class="cards">
  <div class="card" style="--accent:{NAVY}"><div class="label">Designated ships</div>
    <div class="value">{len(ships):,}</div><div class="sub">{designated_2026} added in {this_year}</div></div>
  <div class="card" style="--accent:#d97706"><div class="label">Changed flag before</div>
    <div class="value">{hopped / max(len(ships), 1):.0%}</div><div class="sub">{hopped:,} ships list at least one previous flag</div></div>
  <div class="card" style="--accent:#e11d48"><div class="label">Median age</div>
    <div class="value">{median_age:.0f} yrs</div><div class="sub">{over_15:,} ships are 15 years or older</div></div>
  <div class="card" style="--accent:#0d9488"><div class="label">Distinct current flags</div>
    <div class="value">{split_values(ships['flag']).nunique()}</div><div class="sub">across the designated fleet</div></div>
</div>""",
            unsafe_allow_html=True,
        )

        left, right = st.columns(2)
        with left:
            section("Current flag", "The country each ship is believed to be registered in today")
            flags = split_values(ships["flag"]).value_counts().head(12).sort_values()
            fig = go.Figure(go.Bar(x=flags.values, y=flags.index, orientation="h", marker_color=NAVY,
                                   text=flags.values, textposition="outside"))
            st.plotly_chart(style_fig(fig, 400, legend=False), width="stretch")
        with right:
            section("Flag hopping", "Number of previous flags listed for each ship")
            hops = ships["n_prev_flags"].clip(upper=5).value_counts().sort_index()
            labels = [f"{int(i)}{'+' if i == 5 else ''}" for i in hops.index]
            fig = go.Figure(go.Bar(x=labels, y=hops.values, marker_color="#d97706", text=hops.values,
                                   textposition="outside"))
            fig.update_xaxes(title="Previous flags")
            st.plotly_chart(style_fig(fig, 400, legend=False), width="stretch")

        left, right = st.columns(2)
        with left:
            section("Ship types")
            kinds = ships["ship_type_clean"].replace("", "Not stated").value_counts().head(8).sort_values()
            fig = go.Figure(go.Bar(x=kinds.values, y=kinds.index, orientation="h", marker_color="#0d9488",
                                   text=kinds.values, textposition="outside"))
            st.plotly_chart(style_fig(fig, 360, legend=False), width="stretch")
        with right:
            section("Age of the fleet", "Year each ship was built")
            fig = px.histogram(ships.dropna(subset=["built"]), x="built", nbins=30,
                               color_discrete_sequence=["#e11d48"])
            fig.update_xaxes(title="Year built")
            fig.update_yaxes(title="Ships")
            st.plotly_chart(style_fig(fig, 360, legend=False), width="stretch")

        section("Ships designated per month")
        per_month = (ships.dropna(subset=["designated"])
                     .assign(Month=lambda d: d["designated"].dt.to_period("M").dt.to_timestamp())
                     .groupby("Month").size().reset_index(name="Ships"))
        fig = px.bar(per_month[per_month["Month"] >= "2023-01-01"], x="Month", y="Ships",
                     color_discrete_sequence=[NAVY])
        st.plotly_chart(style_fig(fig, 300, legend=False), width="stretch")

        section("Fleet register", "Search by ship name, IMO number, flag or owner")
        fq = st.text_input("Filter ships", placeholder="e.g. Gabon, tanker, IMO 9", key="fleet_q")
        table = ships
        if fq:
            q = fq.lower()
            mask = pd.Series(False, index=ships.index)
            for col in ["primary_name", "imo_number", "flag", "previous_flags", "ship_type", "owner_operator"]:
                mask |= ships[col].str.lower().str.contains(q, regex=False)
            table = ships[mask]
        st.dataframe(
            table.sort_values("designated", ascending=False)[
                ["primary_name", "imo_number", "flag", "previous_flags", "ship_type_clean", "built", "gt",
                 "owner_operator", "designated"]].rename(columns={
                    "primary_name": "Ship", "imo_number": "IMO", "flag": "Current flag",
                    "previous_flags": "Previous flags", "ship_type_clean": "Type", "built": "Built",
                    "gt": "Gross tonnage", "owner_operator": "Owner or operator", "designated": "Designated"}),
            hide_index=True, width="stretch", height=420,
            column_config={"Designated": st.column_config.DateColumn(format="D MMM YYYY"),
                           "Built": st.column_config.NumberColumn(format="%d"),
                           "Gross tonnage": st.column_config.NumberColumn(format="%,d")},
        )

# ------------------------------------------------------------------ data quality
with tab_quality:
    st.markdown(
        """<div class="section-sub" style="font-size:.95rem">Screening systems match customers against
        names, then use other details to tell a real match from a namesake. When a listing has few
        identifiers, analysts get more false positives that are harder to clear. This view shows how
        complete the identifying details are across the list.</div>""",
        unsafe_allow_html=True,
    )
    if not HAS_EXTRA_FIELDS:
        st.markdown(PENDING_NOTE, unsafe_allow_html=True)
    else:
        has = lambda col: latest[col].ne("")  # noqa: E731
        people = latest["designation_type"] == "Individual"
        orgs = latest["designation_type"] == "Entity"
        vessels = latest["designation_type"] == "Ship"
        checks = {
            "Individual": {
                "Date of birth": has("dob"),
                "Nationality": has("nationality"),
                "Place of birth": has("town_of_birth") | has("country_of_birth"),
                "Passport or national ID": has("has_passport") | has("has_national_id"),
                "Position or role": has("position"),
            },
            "Entity": {
                "Address country": has("address_country"),
                "Business registration number": has("has_business_reg"),
                "Type of entity": has("type_of_entity"),
                "Parent company": has("parent_company"),
            },
            "Ship": {
                "IMO number": has("imo_number"),
                "Current flag": has("flag"),
                "Ship type": has("ship_type"),
                "Year built": has("year_built"),
            },
        }
        masks = {"Individual": people, "Entity": orgs, "Ship": vessels}

        # Strength for individuals: how many of the four core identifiers are present.
        core = ["Date of birth", "Nationality", "Place of birth", "Passport or national ID"]
        score = sum(checks["Individual"][c].astype(int) for c in core)
        latest["id_strength"] = pd.cut(score, bins=[-1, 1, 2, 4], labels=["Weak", "Moderate", "Strong"])
        indiv = latest[people]
        strong = (indiv["id_strength"] == "Strong").mean()
        weak = (indiv["id_strength"] == "Weak").mean()
        name_only = int(((score == 0) & people).sum())

        st.markdown(
            f"""<div class="cards">
  <div class="card" style="--accent:#059669"><div class="label">Strong identifiers</div>
    <div class="value">{strong:.0%}</div><div class="sub">individuals with 3 or 4 of DOB, nationality, place of birth, ID</div></div>
  <div class="card" style="--accent:#e11d48"><div class="label">Weak identifiers</div>
    <div class="value">{weak:.0%}</div><div class="sub">individuals with 1 or none of these</div></div>
  <div class="card" style="--accent:#d97706"><div class="label">Name only</div>
    <div class="value">{name_only:,}</div><div class="sub">individuals with none of the four</div></div>
  <div class="card" style="--accent:{NAVY}"><div class="label">Ships with IMO</div>
    <div class="value">{checks['Ship']['IMO number'][vessels].mean():.0%}</div><div class="sub">the one identifier that never changes</div></div>
</div>""",
            unsafe_allow_html=True,
        )

        cols = st.columns(3)
        for col, (kind, fields) in zip(cols, checks.items()):
            with col:
                plural = {"Individual": "Individuals", "Entity": "Entities", "Ship": "Ships"}[kind]
                section(plural, f"{int(masks[kind].sum()):,} listings")
                pct = pd.Series({f: m[masks[kind]].mean() * 100 for f, m in fields.items()}).sort_values()
                colours = ["#059669" if v >= 75 else "#d97706" if v >= 40 else "#e11d48" for v in pct.values]
                fig = go.Figure(go.Bar(x=pct.values, y=pct.index, orientation="h", marker_color=colours,
                                       text=[f"{v:.0f}%" for v in pct.values], textposition="inside",
                                       insidetextanchor="end", textfont=dict(color="white", size=12)))
                fig.update_xaxes(range=[0, 100], ticksuffix="%")
                st.plotly_chart(style_fig(fig, 300, legend=False), width="stretch")

        section("Identifier strength by regime", "Individuals only, regimes with at least 30 individuals")
        by_reg = (indiv.groupby("main_regime")["id_strength"].value_counts(normalize=True)
                  .unstack(fill_value=0).reindex(columns=["Strong", "Moderate", "Weak"], fill_value=0))
        by_reg = by_reg[indiv["main_regime"].value_counts().reindex(by_reg.index) >= 30].sort_values("Weak")
        fig = go.Figure()
        for level, colour in [("Strong", "#059669"), ("Moderate", "#d97706"), ("Weak", "#e11d48")]:
            fig.add_bar(y=by_reg.index, x=by_reg[level] * 100, name=level, orientation="h", marker_color=colour)
        fig.update_layout(barmode="stack")
        fig.update_xaxes(ticksuffix="%", range=[0, 100])
        st.plotly_chart(style_fig(fig, 420), width="stretch")

        section("Hardest listings to clear", "Individuals with no date of birth, nationality, place of birth or ID")
        st.dataframe(
            latest[people & (score == 0)][["primary_name", "other_names", "main_regime", "designated"]].rename(
                columns={"primary_name": "Name", "other_names": "Other names", "main_regime": "Regime",
                         "designated": "Designated"}),
            hide_index=True, width="stretch", height=300,
            column_config={"Designated": st.column_config.DateColumn(format="D MMM YYYY")},
        )

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
