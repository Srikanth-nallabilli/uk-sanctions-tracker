"""Small made-up lists in the same layout as the published UK Sanctions List
CSV, used only for testing. None of these names are real designations."""

import csv
import io

HEADERS = [
    "Last Updated", "Unique ID", "OFSI Group ID", "UN Reference Number",
    "Name 6", "Name 1", "Name 2", "Name 3", "Name 4", "Name 5", "Name type",
    "Alias strength", "Title", "Name non-latin script", "Non-latin script type",
    "Non-latin script language", "Regime Name", "Individual, Entity, Ship",
    "Designation source", "Sanctions Imposed", "Other Information",
    "UK Statement of Reasons", "Address Line 1", "Address Line 2", "Address Line 3",
    "Address Line 4", "Address Line 5", "Address Line 6", "Address Postal Code",
    "Address Country", "Phone number", "Website", "Email address", "Date Designated",
    "D.O.B", "Nationality(/ies)", "National Identifier number",
    "National Identifier additional information", "Passport number",
    "Passport additional information", "Position", "Gender", "Town of birth",
    "Country of birth", "Type of entity", "Subsidiaries", "Parent Company",
    "Business registration number (s)", "IMO number", "Current owner/operator (s)",
    "Previous owner/operator (s)", "Current believed flag of ship", "Previous flags",
    "Type of ship", "Tonnage of ship", "Length of ship", "Year Built",
    "Hull identification number (HIN)",
]


def person(uid, surname, first, regime, sanctions="Asset freeze|Travel ban",
           aliases=(), designated="01/03/2022", nationality="Testland",
           reasons="Involved in activity covered by the regime."):
    rows = [{
        "Unique ID": uid, "Name 6": surname, "Name 1": first, "Name type": "Primary Name",
        "Regime Name": regime, "Individual, Entity, Ship": "Individual",
        "Designation source": "UK", "Sanctions Imposed": sanctions,
        "Date Designated": designated, "Nationality(/ies)": nationality,
        "UK Statement of Reasons": reasons, "Last Updated": designated,
    }]
    for alias in aliases:
        rows.append({**rows[0], "Name 6": alias, "Name 1": "", "Name type": "Alias"})
    return rows


def entity(uid, name, regime, kind="Entity", sanctions="Asset freeze", country="Testland", imo="",
           flag="", previous_flags="", ship_type="", year_built="", owner=""):
    return [{
        "Current believed flag of ship": flag, "Previous flags": previous_flags, "Type of ship": ship_type,
        "Year Built": year_built, "Current owner/operator (s)": owner,
        "Unique ID": uid, "Name 6": name, "Name type": "Primary Name",
        "Regime Name": regime, "Individual, Entity, Ship": kind,
        "Designation source": "UK", "Sanctions Imposed": sanctions,
        "Date Designated": "15/05/2023", "Address Country": country, "IMO number": imo,
        "UK Statement of Reasons": "Owned or controlled by a designated person.",
        "Last Updated": "15/05/2023",
    }]


def to_csv(records, report_date="01/10/2026") -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([f"Report Date: {report_date}"])
    writer.writerow(HEADERS)
    for rec in records:
        writer.writerow([rec.get(h, "") for h in HEADERS])
    return ("﻿" + buf.getvalue()).encode("utf-8")


def day_one():
    return (
        person("RUS0001", "PETROV", "Ivan", "Russia", aliases=["PETROFF"])
        + person("RUS0002", "SOKOLOVA", "Anna", "Russia")
        + entity("RUS0003", "NORTHWIND TRADING LLC", "Russia")
        + entity("RUS0004", "OCEAN STAR", "Russia", kind="Ship", sanctions="Shipping sanctions", imo="IMO1234567",
                 flag="Gabon", previous_flags="Panama; Liberia", ship_type="Crude oil tanker", year_built="2004",
                 owner="BLUE WAVE SHIPPING LTD")
        + person("IRN0001", "KARIMI", "Reza", "Iran", sanctions="Asset freeze")
        + person("GHR0001", "DOE", "Jon", "Global Human Rights")
    )


def day_two():
    records = []
    for rec in day_one():
        if rec["Unique ID"] == "GHR0001":           # de-listed
            continue
        if rec["Unique ID"] == "RUS0002":           # sanctions widened
            rec = {**rec, "Sanctions Imposed": "Asset freeze|Travel ban|Trust Services Sanctions"}
        records.append(rec)
    records +=[{**person("RUS0001", "PETROV", "Ivan", "Russia")[0], "Name 6": "PETROV IVANOVICH",
                 "Name 1": "", "Name type": "Primary Name Variation"}]  # new spelling variation
    records += person("CYB0001", "VOLKOV", "Dmitri", "Cyber")       # new
    records += entity("CYB0002", "GREYHAT SOLUTIONS", "Cyber")      # new
    return records
