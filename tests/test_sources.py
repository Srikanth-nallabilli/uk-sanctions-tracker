import dataclasses

import pandas as pd

from tests.sample_lists import day_one, to_csv
from tests.sample_other_lists import OFAC_SDN, eu_csv, ofac_files, un_xml
from tracker import eu, ofac, un
from tracker.common import DESIGNATION_COLUMNS, name_key
from tracker.update import run


def test_ofac_parser_reads_remarks_and_merges_lists():
    d = ofac.parse(ofac_files()).set_index("unique_id")
    assert list(d.columns) == DESIGNATION_COLUMNS[1:]
    assert len(d) == 4

    petrov = d.loc["1001"]
    assert petrov["designation_type"] == "Individual"
    assert petrov["other_names"] == "PETROFF, Ivan"
    assert petrov["dob"] == "01 Mar 1970"
    assert petrov["nationality"] == "Russia"
    assert petrov["town_of_birth"] == "Moscow, Russia"
    assert petrov["has_passport"] == "Y" and petrov["gender"] == "Male"

    # On the SDN list and a non-SDN list under the same entity number.
    oil = d.loc["1002"]
    assert oil["designation_source"] == "Non-SDN; SDN"
    assert oil["regime"] == "IRGC; SDGT; UKRAINE-EO13662"
    assert oil["designation_type"] == "Entity"
    assert oil["address_country"] == "Iran; United Arab Emirates"
    assert oil["has_business_reg"] == "Y"

    ship = d.loc["1003"]
    assert ship["designation_type"] == "Ship"
    assert (ship["imo_number"], ship["flag"], ship["previous_flags"]) == ("9123456", "Panama", "Liberia")
    assert (ship["year_built"], ship["tonnage"], ship["ship_type"]) == ("2003", "81000", "Crude Oil Tanker")

    assert d.loc["2001", "designation_source"] == "Non-SDN"


def test_un_parser():
    d = un.parse(un_xml()).set_index("unique_id")
    person = d.loc["QDi.900"]
    assert person["primary_name"] == "AHMAD TESTER"
    assert person["regime"] == "ISIL (Da'esh) and Al-Qaida"
    assert person["date_designated"] == "04/05/2011"
    assert person["last_updated"] == "08/07/2019"
    assert person["dob"] == "15/01/1970; 1971"
    assert person["un_ref"] == "QDi.900"
    assert (person["town_of_birth"], person["has_passport"], person["position"]) == ("Testville", "Y", "Financier")

    company = d.loc["KPe.900"]
    assert company["designation_type"] == "Entity"
    assert company["regime"] == "North Korea (DPRK)"
    assert company["imo_number"] == "5123456"


def test_eu_parser_groups_rows_and_prefers_latin_names():
    d = eu.parse(eu_csv()).set_index("unique_id")
    assert len(d) == 2

    person = d.loc["5001"]
    assert person["primary_name"] == "Ivan PETROV"
    assert person["other_names"] == "Ivan PETROFF; Иван ПЕТРОВ"
    assert person["regime"] == "Ukraine territorial integrity"
    assert person["date_designated"] == "28/02/2022"
    assert person["last_updated"] == "17/05/2024"
    # Citizenship only has a code; the name is learned from another column.
    assert person["nationality"] == "Russian Federation"
    assert (person["gender"], person["position"], person["has_passport"]) == ("Male", "Deputy Minister", "Y")

    company = d.loc["5002"]
    assert company["designation_type"] == "Entity"
    assert company["imo_number"] == "5123456"
    assert company["address_country"] == "Korea, Democratic People's Republic of"
    assert company["designation_source"] == "UN"


def test_un_history_records_amendment(tmp_path):
    run(un_xml(), "2026-10-01", tmp_path, "un")
    summary = run(un_xml(extra_alias="Abu Example"), "2026-10-02", tmp_path, "un")
    assert (summary["added"], summary["removed"], summary["amended"]) == (0, 0, 1)
    changes = pd.read_csv(tmp_path / "changes.csv")
    assert changes.loc[0, "unique_id"] == "QDi.900"
    assert "Aliases" in changes.loc[0, "fields_changed"]


def test_ofac_removal_is_recorded(tmp_path):
    run(ofac_files(), "2026-10-01", tmp_path, "ofac")
    smaller = "\r\n".join(line for line in OFAC_SDN.split("\r\n") if not line.startswith("1003"))
    summary = run(ofac_files(sdn=smaller), "2026-10-02", tmp_path, "ofac")
    assert (summary["added"], summary["removed"]) == (0, 1)


def test_one_failing_source_does_not_stop_the_others(tmp_path, monkeypatch):
    from tracker import update
    from tracker.sources import SOURCES

    def broken():
        raise OSError("site down")

    fake = {
        "uk": dataclasses.replace(SOURCES["uk"], fetch=lambda: to_csv(day_one())),
        "un": dataclasses.replace(SOURCES["un"], fetch=broken),
        "eu": dataclasses.replace(SOURCES["eu"], fetch=eu_csv),
    }
    monkeypatch.setattr(update, "SOURCES", fake)
    monkeypatch.setattr("tracker.sources.SOURCES", fake)
    code = update.main(["--data-dir", str(tmp_path), "--date", "2026-10-01"])
    assert code == 1
    assert (tmp_path / "uk" / "runs.csv").exists()
    assert (tmp_path / "eu" / "runs.csv").exists()
    assert not (tmp_path / "un").exists()


def test_alert_covers_several_lists(tmp_path):
    from tracker.alert import alert_title, build_alert

    run(un_xml(), "2026-10-01", tmp_path / "un", "un")
    un_summary = run(un_xml(extra_alias="Abu Example"), "2026-10-02", tmp_path / "un", "un")
    run(ofac_files(), "2026-10-01", tmp_path / "ofac", "ofac")
    smaller = "\r\n".join(line for line in OFAC_SDN.split("\r\n") if not line.startswith("1003"))
    ofac_summary = run(ofac_files(sdn=smaller), "2026-10-02", tmp_path / "ofac", "ofac")

    assert alert_title(un_summary) == "UN Security Council Consolidated List changes on 2026-10-02: 1 amended"
    both = [ofac_summary, un_summary]
    assert alert_title(both) == "Sanctions list changes on 2026-10-02: US (OFAC) 1, UN 1"
    text = build_alert(both)
    assert "SEA TEST" in text and "AHMAD TESTER" in text


def test_name_key_ignores_order_case_and_accents():
    assert name_key("PETROV, Ivan") == name_key("Ivan Petrov") == "ivan petrov"
    assert name_key("José ORNELLAS") == "jose ornellas"


def test_compare_finds_listing_on_other_lists():
    from tracker.compare import found_on, keys_for

    ofac_d = ofac.parse(ofac_files())
    eu_d = eu.parse(eu_csv())
    un_d = un.parse(un_xml())

    on_ofac = found_on(keys_for(eu_d), keys_for(ofac_d))
    on_un = found_on(keys_for(eu_d), keys_for(un_d))
    eu_ids = eu_d["unique_id"].tolist()
    # Ivan PETROV matches 'PETROV, Ivan' on OFAC by name.
    assert on_ofac[eu_ids.index("5001")]
    # The shipping company matches the UN listing by UN reference and IMO number.
    assert on_un[eu_ids.index("5002")]
    assert not on_un[eu_ids.index("5001")]


def test_compare_ignores_bracketed_acronyms():
    from tracker.common import finish
    from tracker.compare import found_on, keys_for

    a = finish([{"unique_id": "A1", "primary_name": "HAQQANI NETWORK (HQN)", "designation_type": "Entity"}])
    b = finish([{"unique_id": "B1", "primary_name": "Haqqani Network", "designation_type": "Entity"}])
    c = finish([{"unique_id": "C1", "primary_name": "Haqqani Network", "designation_type": "Individual"}])
    assert found_on(keys_for(a), keys_for(b)).all()
    # A person and an organisation with the same name are not the same listing.
    assert not found_on(keys_for(a), keys_for(c)).any()
