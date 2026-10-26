"""Read the UN Security Council Consolidated List and turn it into one row per designation.

The UN publishes an XML file with separate sections for individuals and
entities. Each listing already sits in one element, so there is no grouping
to do. The permanent reference number (for example QDi.001) is used as the
Unique ID because it is what the UK, EU and others cite when they carry a UN
listing into their own lists.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import pandas as pd

from tracker.common import _clean, _hash, _join, download, finish, uk_date

SOURCE_URL = "https://scsanctions.un.org/resources/xml/en/consolidated.xml"
SOURCE_PAGE = "https://main.un.org/securitycouncil/en/content/un-sc-consolidated-list"

# UN_LIST_TYPE -> the name of the sanctions committee regime.
REGIMES = {
    "Al-Qaida": "ISIL (Da'esh) and Al-Qaida",
    "Taliban": "Taliban (1988)",
    "DPRK": "North Korea (DPRK)",
    "DRC": "Democratic Republic of the Congo",
    "CAR": "Central African Republic",
    "GB": "Guinea-Bissau",
    "SouthSudan": "South Sudan",
    "Iran": "Iran (2231)",
}


def fetch() -> bytes:
    return download(SOURCE_URL)


def _texts(node, path: str) -> list[str]:
    return [_clean(e.text) for e in node.findall(path) if _clean(e.text)]


def _dob(node) -> list[str]:
    out = []
    for d in node.findall("INDIVIDUAL_DATE_OF_BIRTH"):
        if _clean(d.findtext("DATE")):
            out.append(uk_date(_clean(d.findtext("DATE"))) or _clean(d.findtext("DATE")))
        elif _clean(d.findtext("YEAR")):
            out.append(_clean(d.findtext("YEAR")))
        elif _clean(d.findtext("FROM_YEAR")):
            out.append(f"{_clean(d.findtext('FROM_YEAR'))} to {_clean(d.findtext('TO_YEAR'))}")
    return out


def _listing(node, kind: str) -> dict:
    prefix = "INDIVIDUAL" if kind == "Individual" else "ENTITY"
    primary = " ".join(_clean(node.findtext(t)) for t in
                       ("FIRST_NAME", "SECOND_NAME", "THIRD_NAME", "FOURTH_NAME") if _clean(node.findtext(t)))
    aliases = _texts(node, f"{prefix}_ALIAS/ALIAS_NAME") + _texts(node, "NAME_ORIGINAL_SCRIPT")
    others = [a for a in aliases if a != primary]
    comments = _clean(node.findtext("COMMENTS1"))
    documents = " ".join(_texts(node, "INDIVIDUAL_DOCUMENT/TYPE_OF_DOCUMENT")).lower()
    updated = sorted(_texts(node, "LAST_DAY_UPDATED/VALUE"))
    list_type = _clean(node.findtext("UN_LIST_TYPE"))
    ref = _clean(node.findtext("REFERENCE_NUMBER"))
    return {
        "unique_id": ref or _clean(node.findtext("DATAID")),
        "primary_name": primary,
        "other_names": _join(others),
        "name_count": len({primary, *others} - {""}),
        "regime": REGIMES.get(list_type, list_type),
        "designation_type": kind,
        "designation_source": "UN Security Council",
        "date_designated": uk_date(_clean(node.findtext("LISTED_ON"))),
        "last_updated": uk_date(updated[-1]) if updated else "",
        "dob": _join(_dob(node)),
        "nationality": _join(_texts(node, "NATIONALITY/VALUE")),
        "address_country": _join(_texts(node, f"{prefix}_ADDRESS/COUNTRY")),
        "position": _join(_texts(node, "DESIGNATION/VALUE")),
        "imo_number": _join(re.findall(r"IMO(?: number)?:? ?(\d{7})", comments)),
        "un_ref": ref,
        "other_info_hash": _hash([comments]),
        "has_passport": "Y" if "passport" in documents else "",
        "has_national_id": "Y" if re.search(r"national|identi", documents) else "",
        "town_of_birth": _join(_texts(node, "INDIVIDUAL_PLACE_OF_BIRTH/CITY")),
        "country_of_birth": _join(_texts(node, "INDIVIDUAL_PLACE_OF_BIRTH/COUNTRY")),
        "gender": _clean(node.findtext("GENDER")),
    }


def parse(data: bytes) -> pd.DataFrame:
    root = ET.fromstring(data)
    rows = [_listing(n, "Individual") for n in root.findall("INDIVIDUALS/INDIVIDUAL")]
    rows += [_listing(n, "Entity") for n in root.findall("ENTITIES/ENTITY")]
    if not rows:
        raise ValueError("No listings found in the UN file. The format may have changed.")
    return finish(rows)
