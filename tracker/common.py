"""Pieces shared by every list the tracker follows.

Each source module (UK, OFAC, UN, EU) turns its own published file into the
same table: one row per designation with the columns in DESIGNATION_COLUMNS.
Everything after that point, from the daily comparison to the dashboard,
works the same way whichever list the rows came from.
"""

from __future__ import annotations

import hashlib
import re
import urllib.request

import pandas as pd

USER_AGENT = "uk-sanctions-tracker/1.0"

# The columns every source produces. A source that does not publish a field
# leaves it blank, so the dashboard can tell "not published" from "missing".
DESIGNATION_COLUMNS = [
    "unique_id", "primary_name", "other_names", "name_count", "regime", "designation_type",
    "designation_source", "sanctions_imposed", "date_designated", "last_updated", "dob",
    "nationality", "address_country", "position", "imo_number", "ofsi_group_id", "un_ref",
    "reasons_hash", "other_info_hash", "has_passport", "has_national_id", "has_business_reg",
    "town_of_birth", "country_of_birth", "gender", "type_of_entity", "parent_company",
    "flag", "previous_flags", "ship_type", "tonnage", "length", "year_built",
    "owner_operator", "previous_owner_operator",
]

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

CHANGE_COLUMNS = [
    "run_date", "change_type", "unique_id", "primary_name",
    "designation_type", "regime", "fields_changed", "detail",
]


def download(url: str, timeout: int = 120) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


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


def _join(values) -> str:
    items = sorted({v for v in values if v})
    return "; ".join(items)


def _hash(values) -> str:
    joined = "|".join(sorted({v for v in values if v}))
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:12] if joined else ""


def uk_date(value: str) -> str:
    """Turn 2024-03-01 into 01/03/2024, the format the UK list and the dashboard use."""
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", value or "")
    return f"{match[3]}/{match[2]}/{match[1]}" if match else ""


def finish(rows: list[dict]) -> pd.DataFrame:
    """Put a source's designations into the shared column order, blanks for anything not published."""
    out = pd.DataFrame(rows)
    for col in DESIGNATION_COLUMNS:
        if col not in out.columns:
            out[col] = ""
    out = out[DESIGNATION_COLUMNS]
    out["name_count"] = out["name_count"].replace("", 0)
    return out.sort_values("unique_id", kind="stable").reset_index(drop=True)


def name_key(name: str) -> str:
    """A spelling-insensitive key for matching the same name across lists.

    'PETROV, Ivan' and 'Ivan Petrov' both become 'ivan petrov'. Word order,
    case, accents dropped to ASCII and punctuation are ignored.
    """
    import unicodedata

    text = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    words = re.sub(r"[^a-z0-9 ]", " ", text.lower()).split()
    return " ".join(sorted(words))


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
        # Only the UK list publishes the measures imposed on each listing.
        imposed = curr.loc[uid, "sanctions_imposed"]
        row["detail"] = f"Sanctions imposed: {imposed}" if imposed else ""
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
