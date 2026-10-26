"""Find the same designation on different lists.

There is no shared identifier across the UK, US, UN and EU lists, so a
listing counts as found on another list when any of these line up:

- the UN reference number (for listings that come from the UN),
- the IMO number (ships and shipping companies),
- a name or alias, compared word for word after ignoring case, accents,
  punctuation and word order, and only between people and people or
  organisations and organisations.

This is deliberately strict. It misses transliteration differences such as
PETROV and PETROFF unless one list carries the other spelling as an alias,
and it is a way to explore the lists, not a screening tool.
"""

from __future__ import annotations

import re

import pandas as pd

from tracker.common import name_key


def _keys(row) -> set[str]:
    keys = set()
    for ref in str(row["un_ref"]).split("; "):
        if ref:
            keys.add("un:" + ref.strip().upper())
    for imo in str(row["imo_number"]).split("; "):
        if imo:
            keys.add("imo:" + imo.strip())
    group = "person" if row["designation_type"] == "Individual" else "other"
    names = [row["primary_name"]] + str(row["other_names"]).split("; ")
    # Lists differ in whether an acronym is added in brackets:
    # 'HAQQANI NETWORK (HQN)' on one list is 'Haqqani Network' on another.
    names += [re.sub(r"\([^)]*\)", " ", n) for n in names if "(" in n]
    for name in names:
        key = name_key(name)
        # One-word names and very short names ('ALI', 'TSC') match far too
        # many unrelated listings to be useful.
        if len(key.split()) >= 2 and len(key) >= 6:
            keys.add(f"name:{group}:{key}")
    return keys


def keys_for(designations: pd.DataFrame) -> pd.Series:
    """The matching keys for every listing, indexed like the input."""
    return designations.apply(_keys, axis=1)


def found_on(keys: pd.Series, other_keys: pd.Series) -> pd.Series:
    """True for each listing in `keys` that shares a key with any listing in `other_keys`."""
    pool = set().union(*other_keys) if len(other_keys) else set()
    return keys.map(lambda k: bool(k & pool))
