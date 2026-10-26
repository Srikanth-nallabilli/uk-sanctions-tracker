"""Small made-up extracts in the layouts of the OFAC, UN and EU files, used
only for testing. None of these names are real designations."""

import csv
import io

# ------------------------------------------------------------------ OFAC
# Headerless CSVs. '-0-' marks an empty field, and the real files end with a
# Ctrl-Z character on its own line.
OFAC_SDN = (
    '1001,"PETROV, Ivan","individual","RUSSIA-EO14024",-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,'
    '"DOB 01 Mar 1970; POB Moscow, Russia; nationality Russia; Gender Male; Passport 123 (Russia)."\r\n'
    '1002,"TESTOIL TRADING LLC",-0- ,"SDGT] [IRGC",-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,'
    '"Organization Type: Wholesale trade; Tax ID No. 555 (Iran)."\r\n'
    '1003,"SEA TEST",vessel,"IRAN",-0- ,"9V1234","Crude Oil Tanker",-0- ,"81000","Panama",'
    '"TESTOIL TRADING LLC","Vessel Registration Identification IMO 9123456; Former Vessel Flag Liberia;'
    ' Vessel Year of Build 2003."\r\n'
    "\x1a"
)
OFAC_ALT = '1001,1,"aka","PETROFF, Ivan",-0- \r\n1002,2,"fka","TEST OIL LLC",-0- \r\n'
OFAC_ADD = ('1001,1,-0- ,"Moscow","Russia",-0- \r\n1002,2,"1 Test St","Tehran","Iran",-0- \r\n'
            '1002,3,-0- ,"Dubai","United Arab Emirates",-0- \r\n')
OFAC_CONS = (
    '1002,"TESTOIL TRADING LLC",-0- ,"UKRAINE-EO13662",-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- \r\n'
    '2001,"NONSDN BANK",-0- ,"NS-MBS",-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- \r\n'
)


def ofac_files(sdn=OFAC_SDN, cons=OFAC_CONS) -> dict:
    return {"sdn.csv": sdn.encode("cp1252"), "alt.csv": OFAC_ALT.encode(), "add.csv": OFAC_ADD.encode(),
            "cons_prim.csv": cons.encode(), "cons_alt.csv": b"", "cons_add.csv": b""}


# ------------------------------------------------------------------ UN
def un_xml(extra_alias: str = "") -> bytes:
    alias = f"<INDIVIDUAL_ALIAS><QUALITY>Good</QUALITY><ALIAS_NAME>{extra_alias}</ALIAS_NAME></INDIVIDUAL_ALIAS>" \
        if extra_alias else ""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<CONSOLIDATED_LIST dateGenerated="2026-10-24T23:00:07Z">
  <INDIVIDUALS>
    <INDIVIDUAL>
      <DATAID>1</DATAID><FIRST_NAME>AHMAD</FIRST_NAME><SECOND_NAME>TESTER</SECOND_NAME>
      <UN_LIST_TYPE>Al-Qaida</UN_LIST_TYPE><REFERENCE_NUMBER>QDi.900</REFERENCE_NUMBER>
      <LISTED_ON>2011-05-04</LISTED_ON><GENDER>Male</GENDER><COMMENTS1>Test listing.</COMMENTS1>
      <DESIGNATION><VALUE>Financier</VALUE></DESIGNATION>
      <NATIONALITY><VALUE>Testland</VALUE></NATIONALITY>
      <LAST_DAY_UPDATED><VALUE>2015-01-02</VALUE><VALUE>2019-07-08</VALUE></LAST_DAY_UPDATED>
      <INDIVIDUAL_ALIAS><QUALITY>Good</QUALITY><ALIAS_NAME>Abu Test</ALIAS_NAME></INDIVIDUAL_ALIAS>
      {alias}
      <INDIVIDUAL_ADDRESS><COUNTRY>Testland</COUNTRY></INDIVIDUAL_ADDRESS>
      <INDIVIDUAL_DATE_OF_BIRTH><TYPE_OF_DATE>EXACT</TYPE_OF_DATE><DATE>1970-01-15</DATE></INDIVIDUAL_DATE_OF_BIRTH>
      <INDIVIDUAL_DATE_OF_BIRTH><TYPE_OF_DATE>APPROXIMATELY</TYPE_OF_DATE><YEAR>1971</YEAR></INDIVIDUAL_DATE_OF_BIRTH>
      <INDIVIDUAL_PLACE_OF_BIRTH><CITY>Testville</CITY><COUNTRY>Testland</COUNTRY></INDIVIDUAL_PLACE_OF_BIRTH>
      <INDIVIDUAL_DOCUMENT><TYPE_OF_DOCUMENT>Passport</TYPE_OF_DOCUMENT><NUMBER>X1</NUMBER></INDIVIDUAL_DOCUMENT>
    </INDIVIDUAL>
  </INDIVIDUALS>
  <ENTITIES>
    <ENTITY>
      <DATAID>2</DATAID><FIRST_NAME>TEST SHIPPING CO</FIRST_NAME>
      <UN_LIST_TYPE>DPRK</UN_LIST_TYPE><REFERENCE_NUMBER>KPe.900</REFERENCE_NUMBER>
      <LISTED_ON>2017-08-05</LISTED_ON><COMMENTS1>IMO: 5123456. Shipping company.</COMMENTS1>
      <ENTITY_ALIAS><QUALITY>a.k.a.</QUALITY><ALIAS_NAME>TSC</ALIAS_NAME></ENTITY_ALIAS>
      <ENTITY_ADDRESS><COUNTRY>Testland</COUNTRY></ENTITY_ADDRESS>
    </ENTITY>
  </ENTITIES>
</CONSOLIDATED_LIST>""".encode("utf-8")


# ------------------------------------------------------------------ EU
EU_HEADERS = [
    "fileGenerationDate", "Entity_LogicalId", "Entity_EU_ReferenceNumber", "Entity_UnitedNationId",
    "Entity_DesignationDate", "Entity_DesignationDetails", "Entity_Remark", "Entity_SubjectType",
    "Entity_SubjectType_ClassificationCode", "Entity_Regulation_PublicationDate", "Entity_Regulation_Programme",
    "NameAlias_WholeName", "NameAlias_NameLanguage", "NameAlias_Gender", "NameAlias_Function",
    "NameAlias_LogicalId", "NameAlias_Regulation_PublicationDate",
    "Address_City", "Address_CountryIso2Code", "Address_CountryDescription",
    "BirthDate_BirthDate", "BirthDate_Year", "BirthDate_City", "BirthDate_Place", "BirthDate_CountryIso2Code",
    "BirthDate_CountryDescription", "Identification_Number", "Identification_TypeCode",
    "Identification_CountryIso2Code", "Identification_CountryDescription",
    "Citizenship_CountryIso2Code",
]


def _eu_row(**values) -> dict:
    row = {h: "" for h in EU_HEADERS}
    row.update({"fileGenerationDate": "23/10/2026", **values})
    return row


def eu_rows() -> list[dict]:
    person = dict(Entity_LogicalId="5001", Entity_EU_ReferenceNumber="EU.1.1", Entity_DesignationDate="2022-02-28",
                  Entity_SubjectType="P", Entity_SubjectType_ClassificationCode="person",
                  Entity_Regulation_PublicationDate="2022-02-28", Entity_Regulation_Programme="UKR",
                  Entity_DesignationDetails="Reasons text")
    company = dict(Entity_LogicalId="5002", Entity_DesignationDate="2023-06-23", Entity_SubjectType="E",
                   Entity_SubjectType_ClassificationCode="enterprise", Entity_Regulation_Programme="IRN",
                   Entity_Regulation_PublicationDate="2023-06-23", Entity_UnitedNationId="KPe.900")
    return [
        # Cyrillic name has the lowest id, Latin transliterations follow.
        _eu_row(**person, NameAlias_WholeName="Иван ПЕТРОВ", NameAlias_LogicalId="10", NameAlias_Gender="M",
                Citizenship_CountryIso2Code="RU", BirthDate_BirthDate="1970-03-01",
                BirthDate_CountryIso2Code="RU", BirthDate_CountryDescription="RUSSIAN FEDERATION"),
        _eu_row(**person, NameAlias_WholeName="Ivan PETROV", NameAlias_LogicalId="11",
                NameAlias_Function="Deputy Minister", NameAlias_Regulation_PublicationDate="2024-05-17",
                Citizenship_CountryIso2Code="RU"),
        _eu_row(**person, NameAlias_WholeName="Ivan PETROFF", NameAlias_LogicalId="12",
                Identification_TypeCode="passport", Identification_Number="123"),
        _eu_row(**company, NameAlias_WholeName="Test Shipping Co", NameAlias_LogicalId="20",
                Address_CountryIso2Code="KP", Address_CountryDescription="KOREA, DEMOCRATIC PEOPLE'S REPUBLIC OF",
                Identification_TypeCode="imo", Identification_Number="5123456 (imo-IMO (vessel identification))"),
    ]


def eu_csv(rows=None) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=EU_HEADERS, delimiter=";")
    writer.writeheader()
    writer.writerows(rows if rows is not None else eu_rows())
    return ("﻿" + buf.getvalue()).encode("utf-8")
