"""The sanctions lists the tracker follows.

Each list keeps its own history in data/<key>/, so a problem with one
publisher's file never touches the others.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd

from tracker import eu, ofac, uksl, un


@dataclass(frozen=True)
class Source:
    key: str
    name: str          # used in headings and alerts, e.g. "UK Sanctions List"
    short: str         # used on buttons and chart labels, e.g. "UK"
    publisher: str
    page: str          # the publisher's page for the list
    fetch: Callable[[], Any]
    parse: Callable[[Any], pd.DataFrame]
    licence: str


SOURCES = {
    "uk": Source("uk", "UK Sanctions List", "UK", "FCDO", "https://www.gov.uk/government/publications/the-uk-sanctions-list",
                 uksl.fetch, uksl.parse, "Open Government Licence v3.0"),
    "ofac": Source("ofac", "OFAC SDN and Consolidated Lists", "US (OFAC)", "US Treasury, OFAC", ofac.SOURCE_PAGE,
                   ofac.fetch, ofac.parse, "US government work, public domain"),
    "un": Source("un", "UN Security Council Consolidated List", "UN", "UN Security Council", un.SOURCE_PAGE,
                 un.fetch, un.parse, "United Nations"),
    "eu": Source("eu", "EU Consolidated Financial Sanctions List", "EU", "European Commission", eu.SOURCE_PAGE,
                 eu.fetch, eu.parse, "European Commission, reuse under Decision 2011/833/EU"),
}
