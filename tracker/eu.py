"""Read the EU Consolidated Financial Sanctions List and turn it into one row per designation.

The European Commission publishes a semicolon separated CSV with one row for
every combination of a listing's names, addresses, dates of birth, identity
documents and citizenships, so a single person can fill dozens of rows.
Everything is grouped back together on the Entity LogicalId, the Commission's
stable identifier for a listing.
"""

from __future__ import annotations

import csv
import io
import re

import pandas as pd

from tracker.common import _clean, _decode, _hash, _join, download, finish, uk_date

SOURCE_URL = ("https://webgate.ec.europa.eu/fsd/fsf/public/files/csvFullSanctionsList_1_1/content"
              "?token=dG9rZW4tMjAxNw")
SOURCE_PAGE = ("https://data.europa.eu/data/datasets/consolidated-list-of-persons-groups-and-entities-"
               "subject-to-eu-financial-sanctions")

# Programme codes used in the file -> readable regime names.
REGIMES = {
    "UKR": "Ukraine territorial integrity", "RUS": "Russia", "RUSDA": "Russia destabilising activities",
    "BLR": "Belarus", "IRN": "Iran", "IRQ": "Iraq", "SYR": "Syria", "PRK": "North Korea (DPRK)",
    "AFG": "Afghanistan (Taliban)", "TAQA": "ISIL (Da'esh) and Al-Qaida", "EUAQ": "ISIL and Al-Qaida (EU)",
    "TERR": "Terrorism", "HAM": "Hamas and Palestinian Islamic Jihad", "HR": "Global human rights",
    "CYB": "Cyber-attacks", "CHEM": "Chemical weapons", "MMR": "Myanmar (Burma)",
    "COD": "Democratic Republic of the Congo", "CAF": "Central African Republic", "VEN": "Venezuela",
    "LBY": "Libya", "MDA": "Moldova", "TUN": "Tunisia", "SDNZ": "Sudan", "SDN": "Sudan", "SSD": "South Sudan",
    "SOM": "Somalia", "NIC": "Nicaragua", "HTI": "Haiti", "YEM": "Yemen", "GTM": "Guatemala",
    "GIN": "Guinea", "MLI": "Mali", "LBN": "Lebanon", "ZWE": "Zimbabwe", "BDI": "Burundi", "NER": "Niger",
    "TUR": "Turkey drilling activities", "UNLI": "UN listed (other)", "SRB": "Serbia",
}

TYPES = {"person": "Individual", "enterprise": "Entity"}


def fetch() -> bytes:
    return download(SOURCE_URL, timeout=180)


SMALL_WORDS = {"of", "the", "and", "da", "de", "du"}


def _country(name: str) -> str:
    """'DEMOCRATIC REPUBLIC OF THE CONGO' -> 'Democratic Republic of the Congo'."""
    if not name or name.upper() in {"UNKNOWN", "00"}:
        return ""
    out = []
    for i, word in enumerate(name.lower().split()):
        keep_lower = i and word.strip("(),") in SMALL_WORDS
        out.append(word if keep_lower else re.sub(r"[a-z]", lambda m: m[0].upper(), word, count=1))
    return " ".join(out)


def _latin(name: str) -> bool:
    return all(ord(c) < 0x250 for c in name if c.isalpha())


def _country_names(rows: list[dict]) -> dict[str, str]:
    """Citizenship only gives a two-letter code, so learn code -> name from the address
    and birth columns of the same file, which carry both."""
    names = {}
    for r in rows:
        for prefix in ("Address", "BirthDate", "Identification"):
            code, desc = r.get(f"{prefix}_CountryIso2Code", ""), r.get(f"{prefix}_CountryDescription", "")
            if code and desc and code not in names:
                names[code] = _country(desc)
    return names


def parse(data: bytes) -> pd.DataFrame:
    reader = csv.DictReader(io.StringIO(_decode(data)), delimiter=";")
    rows = [{k: _clean(v) for k, v in r.items() if k} for r in reader]
    if not rows or "Entity_LogicalId" not in rows[0]:
        raise ValueError("Could not find the Entity_LogicalId column. The EU file format may have changed.")
    pub_cols = [c for c in rows[0] if c.endswith("_Regulation_PublicationDate")]
    countries = _country_names(rows)
    gender = {"M": "Male", "F": "Female"}

    groups: dict[str, list[dict]] = {}
    for r in rows:
        if r.get("Entity_LogicalId"):
            groups.setdefault(r["Entity_LogicalId"], []).append(r)

    out = []
    for uid, grp in groups.items():
        def values(col):
            return [r[col] for r in grp if r.get(col)]

        # The Commission numbers names in the order they were added, so the
        # lowest name id is the original listing name.
        named = sorted((int(r["NameAlias_LogicalId"] or 0), r["NameAlias_WholeName"])
                       for r in grp if r.get("NameAlias_WholeName"))
        names = list(dict.fromkeys(n for _, n in named))
        # Names are also given in other scripts (Cyrillic, Arabic...). Use the
        # first one in Latin script as the primary name where there is one.
        primary = next((n for n in names if _latin(n)), names[0] if names else "")
        id_types = {v.lower() for v in values("Identification_TypeCode")}
        imo = [re.search(r"\d{7}", r["Identification_Number"])[0] for r in grp
               if r.get("Identification_TypeCode", "").lower() == "imo"
               and re.search(r"\d{7}", r.get("Identification_Number", ""))]
        # IMO numbers here are company numbers for shipping firms: the EU
        # financial sanctions file does not list vessels themselves.
        subject = grp[0]["Entity_SubjectType_ClassificationCode"]
        kind = TYPES.get(subject, subject.title())
        published = sorted(v for c in pub_cols for v in values(c))
        out.append({
            "unique_id": uid,
            "primary_name": primary,
            "other_names": _join(n for n in names if n != primary),
            "name_count": len(names),
            "regime": _join(REGIMES.get(p, p) for p in values("Entity_Regulation_Programme")),
            "designation_type": kind,
            "designation_source": "UN" if values("Entity_UnitedNationId") else "EU",
            "date_designated": _join(uk_date(v) for v in values("Entity_DesignationDate")),
            "last_updated": uk_date(published[-1]) if published else "",
            "dob": _join(uk_date(r["BirthDate_BirthDate"]) or r["BirthDate_BirthDate"] or r["BirthDate_Year"]
                         for r in grp),
            "nationality": _join(countries.get(c, c) for c in values("Citizenship_CountryIso2Code")),
            "address_country": _join(_country(v) for v in values("Address_CountryDescription")),
            "position": _join(values("NameAlias_Function")),
            "imo_number": _join(imo),
            "un_ref": _join(values("Entity_UnitedNationId")),
            "reasons_hash": _hash(values("Entity_DesignationDetails")),
            "other_info_hash": _hash(values("Entity_Remark")),
            "has_passport": "Y" if "passport" in id_types else "",
            "has_national_id": "Y" if id_types & {"id", "nationalid", "fiscalcode", "ssn"} else "",
            "has_business_reg": "Y" if id_types & {"regnumber", "taxid", "fiscalcode", "swiftbic"} else "",
            "town_of_birth": _join(values("BirthDate_City") + values("BirthDate_Place")),
            "country_of_birth": _join(_country(v) for v in values("BirthDate_CountryDescription")),
            "gender": _join(gender.get(g, g) for g in values("NameAlias_Gender")),
        })
    return finish(out)
