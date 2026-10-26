"""Read the UK Sanctions List CSV and turn it into one row per designation.

The FCDO publishes the list with one row per name record, so a single
designated person can appear on several rows (primary name, spelling
variations, aliases). Everything here works at the level of the Unique ID,
which is the identifier the FCDO asks firms to use since the OFSI
Consolidated List closed on 28 January 2026.
"""

from __future__ import annotations

import csv
import io
import re

import pandas as pd

from tracker.common import (  # noqa: F401  (CHANGE_COLUMNS, TRACKED_FIELDS and diff are re-exported)
    CHANGE_COLUMNS, TRACKED_FIELDS, _clean, _decode, _hash, _join, diff, download,
)

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


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", str(text).lower()).strip()


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


def fetch() -> bytes:
    return download(SOURCE_URL)


def parse(data: bytes) -> pd.DataFrame:
    raw = read_raw(data)
    missing = raw.attrs.get("missing_columns", [])
    if missing:
        print("Note: these optional columns were not found in the file: " + ", ".join(missing))
    return to_designations(raw)
