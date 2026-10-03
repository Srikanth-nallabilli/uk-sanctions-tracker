"""Read the UK Sanctions List CSV and turn it into one row per designation.

The FCDO publishes the list with one row per name record, so a single
designated person can appear on several rows (primary name, spelling
variations, aliases). Everything here works at the level of the Unique ID,
which is the identifier the FCDO asks firms to use since the OFSI
Consolidated List closed on 28 January 2026.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re

import pandas as pd

SOURCE_URL = "https://sanctionslist.fcdo.gov.uk/docs/UK-Sanctions-List.csv"

# Internal column name -> possible headings in the published file.
# Headings are compared after lowercasing and removing punctuation, so small
# changes in spacing or capitals on the FCDO side do not break the parser.
COLUMN_ALIASES = {
    "unique_id": ["unique id"],
    "ofsi_group_id": ["ofsi group id"],
    "un_ref": ["un reference number"],
    "last_updated": ["last updated"],
    "name1": ["name 1"],
    "name2": ["name 2"],
    "name3": ["name 3"],
    "name4": ["name 4"],
    "name5": ["name 5"],
    "name6": ["name 6"],
    "name_type": ["name type"],
    "regime": ["regime name", "regime"],
    "designation_type": ["individual entity ship", "individual entity or ship", "designation type"],
    "designation_source": ["designation source"],
    "sanctions_imposed": ["sanctions imposed"],
    "date_designated": ["date designated"],
    "dob": ["dob", "d o b", "date of birth"],
    "nationality": ["nationalityies", "nationality ies", "nationality"],
    "address_country": ["address country"],
    "position": ["position"],
    "imo_number": ["imo number"],
    "statement_of_reasons": ["uk statement of reasons"],
    "other_information": ["other information"],
    # Identifier fields. Only whether they are present is kept, never the numbers.
    "passport_number": ["passport number"],
    "national_id": ["national identifier number"],
    "town_of_birth": ["town of birth"],
    "country_of_birth": ["country of birth"],
    "gender": ["gender"],
    "business_reg": ["business registration number s", "business registration numbers",
                     "business registration number"],
    "type_of_entity": ["type of entity"],
    "parent_company": ["parent company"],
    # Ship fields
    "flag": ["current believed flag of ship", "current flag"],
    "previous_flags": ["previous flags"],
    "ship_type": ["type of ship"],
    "tonnage": ["tonnage of ship"],
    "length": ["length of ship"],
    "year_built": ["year built"],
    "owner_operator": ["current owneroperator s", "current owneroperators", "current owner operator s"],
    "previous_owner_operator": ["previous owneroperator s", "previous owneroperators",
                                "previous owner operator s"],
}

REQUIRED_FIELDS = {"unique_id", "name6"}

# Fields compared between two days to decide whether a listing was amended.
# Each one gets a plain English label for the dashboard.
TRACKED_FIELDS = {
    "primary_name": "Primary name",
    "other_names": "Aliases and name variations",
    "regime": "Regime",
    "designation_type": "Designation type",
    "sanctions_imposed": "Sanctions imposed",
    "date_designated": "Date designated",
    "dob": "Date of birth",
    "nationality": "Nationality",
    "address_country": "Address country",
    "position": "Position",
    "imo_number": "IMO number",
    "reasons_hash": "Statement of reasons",
    "other_info_hash": "Other information",
    "flag": "Flag of ship",
    "owner_operator": "Owner or operator of ship",
}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", str(text).lower()).strip()


def _clean(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace")


def read_raw(data: bytes) -> pd.DataFrame:
    """Parse the published CSV, skipping any title rows above the headings."""
    text = _decode(data)
    rows = list(csv.reader(io.StringIO(text)))
    header_idx = None
    for i, row in enumerate(rows[:25]):
        if any(_norm(cell) == "unique id" for cell in row):
            header_idx = i
            break
    if header_idx is None:
        raise ValueError("Could not find a 'Unique ID' column. The file format may have changed.")

    headers = rows[header_idx]
    lookup = {_norm(h): i for i, h in enumerate(headers)}
    mapping = {}
    for field, options in COLUMN_ALIASES.items():
        for option in options:
            if option in lookup:
                mapping[field] = lookup[option]
                break

    if "unique_id" not in mapping or "name6" not in mapping:
        raise ValueError("Required columns (Unique ID, Name 6) are missing from the file.")

    records = []
    for row in rows[header_idx + 1:]:
        if not row or not any(cell.strip() for cell in row):
            continue
        rec = {f: _clean(row[i]) if i < len(row) else "" for f, i in mapping.items()}
        if rec["unique_id"]:
            records.append(rec)

    raw = pd.DataFrame(records)
    for field in COLUMN_ALIASES:
        if field not in raw.columns:
            raw[field] = ""
    # Recorded so the daily job can log any heading it could not find.
    raw.attrs["missing_columns"] = sorted(set(COLUMN_ALIASES) - set(mapping))
    return raw


def _full_name(rec: pd.Series) -> str:
    parts = [rec[f"name{i}"] for i in range(1, 6)] + [rec["name6"]]
    return " ".join(p for p in parts if p)


def _join(values) -> str:
    items = sorted({v for v in values if v})
    return "; ".join(items)


def _hash(values) -> str:
    joined = "|".join(sorted({v for v in values if v}))
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:12] if joined else ""


def to_designations(raw: pd.DataFrame) -> pd.DataFrame:
    """Collapse name rows into one row per Unique ID."""
    raw = raw.copy()
    raw["full_name"] = raw.apply(_full_name, axis=1)
    is_primary = raw["name_type"].str.lower().eq("primary name")

    out = []
    for uid, grp in raw.groupby("unique_id", sort=True):
        # A few listings have only spelling variations or aliases and no row
        # marked "Primary Name". Fall back to the first name alphabetically so
        # the choice is the same every day and does not show as an amendment.
        primary = [n for n in grp.loc[is_primary.loc[grp.index], "full_name"] if n]
        candidates = primary or sorted(n for n in grp["full_name"] if n)
        primary_name = candidates[0] if candidates else ""
        other_names = _join(n for n in grp["full_name"] if n != primary_name)
        out.append({
            "unique_id": uid,
            "primary_name": primary_name,
            "other_names": other_names,
            "name_count": len({n for n in grp["full_name"] if n}),
            "regime": _join(grp["regime"]),
            "designation_type": _join(grp["designation_type"]),
            "designation_source": _join(grp["designation_source"]),
            "sanctions_imposed": _join(
                s.strip() for cell in grp["sanctions_imposed"] for s in re.split(r"[|;]", cell)
            ),
            "date_designated": _join(grp["date_designated"]),
            "last_updated": _join(grp["last_updated"]),
            "dob": _join(grp["dob"]),
            "nationality": _join(grp["nationality"]),
            "address_country": _join(grp["address_country"]),
            "position": _join(grp["position"]),
            "imo_number": _join(grp["imo_number"]),
            "ofsi_group_id": _join(grp["ofsi_group_id"]),
            "un_ref": _join(grp["un_ref"]),
            "reasons_hash": _hash(grp["statement_of_reasons"]),
            "other_info_hash": _hash(grp["other_information"]),
            # Identifier presence, used for the data quality view
            "has_passport": "Y" if grp["passport_number"].str.len().gt(0).any() else "",
            "has_national_id": "Y" if grp["national_id"].str.len().gt(0).any() else "",
            "has_business_reg": "Y" if grp["business_reg"].str.len().gt(0).any() else "",
            "town_of_birth": _join(grp["town_of_birth"]),
            "country_of_birth": _join(grp["country_of_birth"]),
            "gender": _join(grp["gender"]),
            "type_of_entity": _join(grp["type_of_entity"]),
            "parent_company": _join(grp["parent_company"]),
            # Ship details, used for the shadow fleet view
            "flag": _join(grp["flag"]),
            "previous_flags": _join(grp["previous_flags"]),
            "ship_type": _join(grp["ship_type"]),
            "tonnage": _join(grp["tonnage"]),
            "length": _join(grp["length"]),
            "year_built": _join(grp["year_built"]),
            "owner_operator": _join(grp["owner_operator"]),
            "previous_owner_operator": _join(grp["previous_owner_operator"]),
        })
    return pd.DataFrame(out)


def short_regime(name: str) -> str:
    """Turn a regulation title into a readable label for charts and tables.

    'The Russia (Sanctions) (EU Exit) Regulations 2019' becomes 'Russia'.
    Several regimes on one listing are separated by '; ' and each is shortened.
    """
    def one(title: str) -> str:
        s = re.sub(r"^The ", "", title.strip())
        s = s.replace("(International Sanctions)", "(International)")
        s = re.sub(r"\s*\((?:EU Exit|Sanctions|United Nations Sanctions)\)", "", s)
        s = re.sub(r"\s*(?:Sanctions )?Regulations \d{4}$", "", s)
        s = re.sub(r"^Isil\b", "ISIL", s)
        if s == "Counter-Terrorism":
            s = "Counter-Terrorism (Domestic)"
        return s.strip() or title

    return "; ".join(one(part) for part in str(name).split("; ") if part) if name else ""


CHANGE_COLUMNS = [
    "run_date", "change_type", "unique_id", "primary_name",
    "designation_type", "regime", "fields_changed", "detail",
]


def _short(value: str, limit: int = 120) -> str:
    return value if len(value) <= limit else value[: limit - 3] + "..."


def diff(previous: pd.DataFrame, current: pd.DataFrame, run_date: str) -> pd.DataFrame:
    """Compare two days of designations and return one row per change."""
    prev = previous.set_index("unique_id") if len(previous) else pd.DataFrame()
    curr = current.set_index("unique_id")
    prev_ids = set(prev.index) if len(prev) else set()
    curr_ids = set(curr.index)

    changes = []

    def base(uid, row, change_type):
        return {
            "run_date": run_date,
            "change_type": change_type,
            "unique_id": uid,
            "primary_name": row["primary_name"],
            "designation_type": row["designation_type"],
            "regime": row["regime"],
            "fields_changed": "",
            "detail": "",
        }

    for uid in sorted(curr_ids - prev_ids):
        row = base(uid, curr.loc[uid], "Added")
        row["detail"] = f"Sanctions imposed: {curr.loc[uid, 'sanctions_imposed'] or 'not stated'}"
        changes.append(row)

    for uid in sorted(prev_ids - curr_ids):
        changes.append(base(uid, prev.loc[uid], "Removed"))

    # Only compare fields both days have. When a new field is added to the
    # tracker, the first run after that must not flag every listing as amended.
    comparable = [f for f in TRACKED_FIELDS if f in prev.columns and f in curr.columns] if len(prev) else []
    for uid in sorted(prev_ids & curr_ids):
        old, new = prev.loc[uid], curr.loc[uid]
        changed = [f for f in comparable if str(old[f]) != str(new[f])]
        if not changed:
            continue
        row = base(uid, new, "Amended")
        row["fields_changed"] = "; ".join(TRACKED_FIELDS[f] for f in changed)
        notes = []
        for f in changed:
            if f.endswith("_hash"):
                notes.append(f"{TRACKED_FIELDS[f]} text changed")
            else:
                notes.append(f"{TRACKED_FIELDS[f]}: '{_short(str(old.get(f, '')))}' to '{_short(str(new.get(f, '')))}'")
        row["detail"] = " | ".join(notes)
        changes.append(row)

    return pd.DataFrame(changes, columns=CHANGE_COLUMNS)
