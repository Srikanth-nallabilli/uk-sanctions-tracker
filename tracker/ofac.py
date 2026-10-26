"""Read the US Treasury (OFAC) lists and turn them into one row per designation.

OFAC publishes two lists in the same legacy CSV layout: the Specially
Designated Nationals (SDN) list and the Consolidated non-SDN lists (sectoral
sanctions, NS-MBS, CMIC and others). Each comes as three files with no
heading row: the main file, aliases and addresses, linked by the entity
number. Dates of birth, nationalities, IMO numbers and identity documents are
not separate columns but are written into a free-text Remarks field, so they
are pulled out with patterns here.

OFAC does not publish a designation date in these files, so the dashboard
relies on the tracker's own change log for when a listing first appeared.
"""

from __future__ import annotations

import csv
import io
import re
from collections import defaultdict

import pandas as pd

from tracker.common import _clean, _decode, _hash, _join, download, finish

BASE_URL = "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/"
SOURCE_PAGE = "https://ofac.treasury.gov/sanctions-list-service"

# File name -> which list it belongs to and what it holds.
FILES = {
    "sdn.csv": ("SDN", "main"),
    "alt.csv": ("SDN", "alt"),
    "add.csv": ("SDN", "add"),
    "cons_prim.csv": ("Non-SDN", "main"),
    "cons_alt.csv": ("Non-SDN", "alt"),
    "cons_add.csv": ("Non-SDN", "add"),
}

MAIN_COLUMNS = ["ent_num", "name", "type", "program", "title", "call_sign", "vess_type",
                "tonnage", "grt", "vess_flag", "vess_owner", "remarks"]
ALT_COLUMNS = ["ent_num", "alt_num", "alt_type", "alt_name", "alt_remarks"]
ADD_COLUMNS = ["ent_num", "add_num", "address", "city", "country", "add_remarks"]

TYPES = {"individual": "Individual", "vessel": "Ship", "aircraft": "Aircraft", "": "Entity"}


def fetch() -> dict[str, bytes]:
    return {name: download(BASE_URL + name.upper()) for name in FILES}


def _rows(data: bytes, columns: list[str]) -> list[dict]:
    """Parse one headerless OFAC CSV. '-0-' is OFAC's marker for an empty field."""
    out = []
    for row in csv.reader(io.StringIO(_decode(data))):
        if not row or not row[0].strip().isdigit():
            continue  # skips the end-of-file marker and any blank lines
        values = [_clean(v) for v in row] + [""] * len(columns)
        rec = {c: ("" if values[i] == "-0-" else values[i]) for i, c in enumerate(columns)}
        out.append(rec)
    return out


def _find(pattern: str, text: str) -> list[str]:
    return [_clean(m).rstrip(".") for m in re.findall(pattern, text)]


def programs(value: str) -> list[str]:
    """'[SDGT] [IRGC]' and 'SDGT] [IRGC' both become ['SDGT', 'IRGC']."""
    return [p.strip(" []") for p in re.split(r"\]\s*\[", value) if p.strip(" []")]


def parse(files: dict[str, bytes]) -> pd.DataFrame:
    main: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    aliases: dict[str, list[str]] = defaultdict(list)
    countries: dict[str, list[str]] = defaultdict(list)

    for name, (list_name, kind) in FILES.items():
        if name not in files:
            continue
        if kind == "main":
            for rec in _rows(files[name], MAIN_COLUMNS):
                main[rec["ent_num"]].append((list_name, rec))
        elif kind == "alt":
            for rec in _rows(files[name], ALT_COLUMNS):
                aliases[rec["ent_num"]].append(rec["alt_name"])
        else:
            for rec in _rows(files[name], ADD_COLUMNS):
                countries[rec["ent_num"]].append(rec["country"])

    if not main:
        raise ValueError("No OFAC records found. The file format may have changed.")

    out = []
    # A few entities sit on both the SDN and a non-SDN list under the same
    # entity number, so they are combined into one designation.
    for uid, entries in main.items():
        recs = [r for _, r in entries]
        first = recs[0]
        remarks = " ".join(r["remarks"] for r in recs)
        primary = first["name"]
        others = [a for a in aliases[uid] if a and a != primary]
        raw_type = first["type"].lower()
        out.append({
            "unique_id": uid,
            "primary_name": primary,
            "other_names": _join(others),
            "name_count": len({primary, *others}),
            "regime": _join(p for r in recs for p in programs(r["program"])),
            "designation_type": TYPES.get(raw_type, raw_type.title()),
            "designation_source": _join(list_name for list_name, _ in entries),
            "dob": _join(_find(r"DOB ([^;]+)", remarks)),
            "nationality": _join(_find(r"(?:nationality|citizen) ([^;]+)", remarks)),
            "address_country": _join(countries[uid]),
            "position": _join(r["title"] for r in recs),
            "imo_number": _join(_find(r"IMO (\d{7})", remarks)),
            "other_info_hash": _hash([remarks]),
            "has_passport": "Y" if "Passport" in remarks else "",
            "has_national_id": "Y" if re.search(r"National ID No|Cedula No|Identification Number", remarks) else "",
            "has_business_reg": "Y" if re.search(r"Registration (?:Number|ID)|Tax ID No", remarks) else "",
            "town_of_birth": _join(_find(r"POB ([^;]+)", remarks)),
            "gender": _join(_find(r"Gender (Male|Female)", remarks)),
            "type_of_entity": _join(_find(r"Organization Type: ([^;]+)", remarks)),
            "flag": _join(r["vess_flag"] for r in recs),
            "previous_flags": _join(_find(r"Former Vessel Flag ([^;]+)", remarks)),
            "ship_type": _join(r["vess_type"] for r in recs),
            "tonnage": _join(r["grt"] or r["tonnage"] for r in recs),
            "year_built": _join(_find(r"Vessel Year of Build (\d{4})", remarks)),
            "owner_operator": _join(r["vess_owner"] for r in recs),
        })
    return finish(out)


def read_folder(path) -> dict[str, bytes]:
    """Load the six OFAC files from a folder, for running the update by hand."""
    from pathlib import Path

    folder = Path(path)
    found = {f.name.lower(): f.read_bytes() for f in folder.iterdir() if f.name.lower() in FILES}
    if "sdn.csv" not in found:
        raise ValueError(f"{folder} does not contain sdn.csv")
    return found
